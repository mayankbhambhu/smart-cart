"""FreshFlow API — FastAPI application entry point.

Run:  uvicorn app.main:app --reload   (from the backend/ folder)
Docs: http://localhost:8000/docs
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (admin, analytics, auth, cart, gate, lists, orders, people, store_ops, stores,
                            support, ws)
from app.core.config import settings
from app.core.database import init_db
from app.core.realtime import hub

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    hub.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title=f"{settings.APP_NAME} API", version="1.0.0", lifespan=lifespan,
              description="Quick-commerce + scan-and-go in-store shopping platform.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, auth.me_router, stores.router, lists.router, cart.router, orders.router, gate.router,
          store_ops.router, people.router, people.me_router, analytics.router, support.router, admin.router,
          ws.router):
    app.include_router(r)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.APP_NAME, "payments_mode": settings.PAYMENTS_MODE}
