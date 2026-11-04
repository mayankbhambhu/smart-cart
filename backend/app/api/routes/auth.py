"""Authentication & customer profile: email, phone OTP, Google, Apple."""
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_otp, hash_password, verify_password
from app.models import Notification, OTPCode, PaymentMethod, User
from app.models._mixins import utcnow
from app.schemas import (ChangePasswordIn, LoginIn, OTPRequestIn, OTPVerifyIn, PaymentMethodIn,
                         PaymentMethodOut, ProfileUpdateIn, RegisterIn, SocialLoginIn, TokenOut, UserOut)
from app.services.auth_providers import send_sms, verify_apple_identity_token, verify_google_id_token

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["profile"])


def _token(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(409, "An account with this email already exists")
    if data.phone and db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(409, "An account with this phone already exists")
    user = User(full_name=data.full_name, email=data.email.lower(), phone=data.phone,
                password_hash=hash_password(data.password), auth_provider="email")
    db.add(user)
    db.commit()
    return _token(user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    ident = data.identifier.strip().lower()
    user = db.query(User).filter(or_(User.email == ident, User.phone == data.identifier.strip())).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect email/phone or password")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated")
    return _token(user)


@router.post("/otp/request")
def request_otp(data: OTPRequestIn, db: Session = Depends(get_db)):
    recent = db.query(OTPCode).filter(OTPCode.phone == data.phone,
                                      OTPCode.expires_at > utcnow() + timedelta(minutes=4)).count()
    if recent >= 3:
        raise HTTPException(429, "Too many codes requested. Try again in a minute.")
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(OTPCode(phone=data.phone, code_hash=hash_otp(data.phone, code),
                   expires_at=utcnow() + timedelta(minutes=5)))
    db.commit()
    delivered = send_sms(data.phone, f"Your {settings.APP_NAME} code is {code}. It expires in 5 minutes.")
    resp = {"sent": True}
    if settings.DEBUG and not delivered:
        resp["dev_code"] = code  # only in development without an SMS provider
    return resp


@router.post("/otp/verify", response_model=TokenOut)
def verify_otp(data: OTPVerifyIn, db: Session = Depends(get_db)):
    otp = (db.query(OTPCode).filter(OTPCode.phone == data.phone, OTPCode.used.is_(False),
                                    OTPCode.expires_at > utcnow()).order_by(OTPCode.id.desc()).first())
    if not otp or otp.attempts >= 5:
        raise HTTPException(401, "Code expired. Request a new one.")
    if otp.code_hash != hash_otp(data.phone, data.code):
        otp.attempts += 1
        db.commit()
        raise HTTPException(401, "Incorrect code")
    otp.used = True
    user = db.query(User).filter(User.phone == data.phone).first()
    if not user:
        user = User(phone=data.phone, full_name=data.full_name or "", auth_provider="phone")
        db.add(user)
    db.commit()
    return _token(user)


def _social(db: Session, provider: str, info: dict, full_name: str | None) -> TokenOut:
    user = db.query(User).filter(User.auth_provider == provider, User.provider_subject == info["sub"]).first()
    if not user and info.get("email"):
        user = db.query(User).filter(User.email == info["email"].lower()).first()  # link existing account
    if not user:
        user = User(email=(info.get("email") or "").lower() or None, full_name=full_name or info.get("name", ""),
                    auth_provider=provider)
        db.add(user)
    user.provider_subject = info["sub"]
    db.commit()
    return _token(user)


@router.post("/google", response_model=TokenOut)
def google_login(data: SocialLoginIn, db: Session = Depends(get_db)):
    return _social(db, "google", verify_google_id_token(data.id_token), data.full_name)


@router.post("/apple", response_model=TokenOut)
def apple_login(data: SocialLoginIn, db: Session = Depends(get_db)):
    return _social(db, "apple", verify_apple_identity_token(data.id_token), data.full_name)


# ---- Profile -----------------------------------------------------------------------
@me_router.get("", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@me_router.patch("", response_model=UserOut)
def update_me(data: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    return user


@me_router.post("/password")
def change_password(data: ChangePasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    db.add(user)
    db.commit()
    return {"ok": True}


@me_router.get("/payment-methods", response_model=list[PaymentMethodOut])
def list_methods(user: User = Depends(get_current_user)):
    return user.payment_methods


@me_router.post("/payment-methods", response_model=PaymentMethodOut, status_code=201)
def add_method(data: PaymentMethodIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.is_default or not user.payment_methods:
        for m in user.payment_methods:
            m.is_default = False
    pm = PaymentMethod(user_id=user.id, **data.model_dump())
    pm.is_default = data.is_default or not user.payment_methods
    db.add(pm)
    db.commit()
    return pm


@me_router.delete("/payment-methods/{pm_id}", status_code=204)
def delete_method(pm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pm = db.get(PaymentMethod, pm_id)
    if not pm or pm.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(pm)
    db.commit()


@me_router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter_by(user_id=user.id).order_by(Notification.id.desc()).limit(50).all()
    return [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": n.read,
             "created_at": n.created_at} for n in rows]


@me_router.post("/notifications/read")
def mark_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter_by(user_id=user.id, read=False).update({"read": True})
    db.commit()
    return {"ok": True}
