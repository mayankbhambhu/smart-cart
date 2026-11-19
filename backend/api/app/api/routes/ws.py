"""WebSocket endpoint. Connect with:  ws://host/ws?token=<JWT>&channels=list:3,user:7
Each requested channel is authorised against the user's access rights."""
import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import SessionLocal
from app.core.realtime import hub
from app.core.security import decode_access_token
from app.models import ListMember, ShoppingList, User

router = APIRouter()


def _allowed(db, user: User, channel: str) -> bool:
    kind, _, ident = channel.partition(":")
    if kind == "user":
        return ident == str(user.id)
    if kind == "admin":
        return user.role == "admin"
    if kind == "store":
        return user.role == "admin" or (user.is_staff and str(user.store_id) == ident)
    if kind == "list" and ident.isdigit():
        sl = db.get(ShoppingList, int(ident))
        return bool(sl) and (sl.owner_id == user.id or
                             db.query(ListMember).filter_by(list_id=sl.id, user_id=user.id).first() is not None)
    return False


@router.websocket("/ws")
async def websocket(ws: WebSocket, token: str, channels: str = ""):
    try:
        uid = int(decode_access_token(token)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        await ws.close(code=4401)
        return
    with SessionLocal() as db:
        user = db.get(User, uid)
        if not user or not user.is_active:
            await ws.close(code=4401)
            return
        wanted = [c.strip() for c in channels.split(",") if c.strip()] + [f"user:{uid}"]
        granted = sorted({c for c in wanted if _allowed(db, user, c)})
    await hub.connect(ws, granted)
    await ws.send_json({"event": "subscribed", "channels": granted})
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        hub.disconnect(ws)
