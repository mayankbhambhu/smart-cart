"""Shared plumbing for the three web dashboards (customer, store operations, admin).

Each dashboard is a separate FastAPI app (its own port / domain / live link). They render
server-side with Jinja2 and talk to the API over HTTP with the logged-in user's JWT, which is
kept in a signed session cookie. Live updates come from the API's WebSocket.
"""
import os
from datetime import datetime
from urllib.parse import urlencode
from functools import wraps
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

API_URL = os.getenv("API_URL", "http://localhost:8000")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", API_URL)  # what the browser uses (WebSocket)
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret-change-me")
# The dashboards' HTML templates, CSS and JS live in the top-level web/ folder (the frontend);
# this package is only the Python server side. WEB_UI_DIR overrides it (used by the Docker image).
WEB_UI_DIR = Path(os.getenv("WEB_UI_DIR") or Path(__file__).resolve().parents[3] / "web")
SHARED_DIR = WEB_UI_DIR / "shared"

# Where each dashboard lives. The role stored on the account decides which one a person uses.
APP_URLS = {
    "customer": os.getenv("CUSTOMER_APP_URL", "http://localhost:8001").rstrip("/"),
    "store": os.getenv("STORE_APP_URL", "http://localhost:8002").rstrip("/"),
    "admin": os.getenv("ADMIN_APP_URL", "http://localhost:8003").rstrip("/"),
}
STAFF_ROLES = {"worker", "floor_manager", "store_manager", "owner"}
ROLE_NAMES = {"customer": "Shopper", "worker": "Floor Assistant", "floor_manager": "Floor Manager",
              "store_manager": "Store Manager", "owner": "Store Owner", "admin": "Platform Admin"}
APP_NAMES = {"customer": "Shopping", "store": "Store Operations", "admin": "Admin"}


def app_for_role(role: str) -> str:
    if role == "admin":
        return "admin"
    return "store" if role in STAFF_ROLES else "customer"


def finish_login(request: Request, payload: dict, app_key: str, next_url: str = "/") -> str:
    """After any sign-in (password, OTP, Google, email link, SSO), decide where to go. If the account
    belongs on this dashboard, start the session here; otherwise hand the user, already signed in, to the
    dashboard for their role with a one-minute single-use code. Targets come only from APP_URLS."""
    user = payload["user"]
    target = app_for_role(user["role"])
    if target == app_key:
        store_session(request, payload)
        return next_url if next_url.startswith("/") and not next_url.startswith("//") else "/"
    try:
        code = Api(payload["access_token"]).post("/auth/handoff")["code"]
        return f"{APP_URLS[target]}/auth/continue?" + urlencode({"code": code})
    except ApiError:  # fall back to that dashboard's login page with the email filled in
        return f"{APP_URLS[target]}/login?" + urlencode({"identifier": user.get("email") or "", "switched": target})


_providers_cache: dict = {"at": 0.0, "value": None}


def signin_providers() -> dict:
    """Which sign-in buttons to show (asked from the API, cached for a minute)."""
    import time

    if _providers_cache["value"] is None or time.time() - _providers_cache["at"] > 60:
        try:
            _providers_cache["value"] = Api().get("/auth/providers")
        except (ApiError, httpx.HTTPError):
            return {"google": {"enabled": False}, "firebase_email_link": {"enabled": False}, "sso": {"enabled": False}}
        _providers_cache["at"] = time.time()
    return _providers_cache["value"]


class ApiError(Exception):
    def __init__(self, status: int, detail: Any):
        self.status, self.detail = status, detail
        if isinstance(detail, list):  # pydantic validation errors
            detail = "; ".join(f"{'.'.join(map(str, e.get('loc', [])[1:]))}: {e.get('msg')}" for e in detail)
        super().__init__(str(detail))


class Api:
    """Thin HTTP client around the FreshFlow API."""

    def __init__(self, token: str | None = None):
        self.token = token

    def _req(self, method: str, path: str, **kw) -> Any:
        headers = kw.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        params = kw.get("params")
        if params:
            kw["params"] = {k: v for k, v in params.items() if v not in (None, "")}
        r = httpx.request(method, API_URL + path, headers=headers, timeout=20, **kw)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise ApiError(r.status_code, detail)
        if r.status_code == 204 or not r.content:
            return None
        return r.json() if "json" in r.headers.get("content-type", "") else r.content

    def get(self, path, **params):
        return self._req("GET", path, params=params)

    def post(self, path, json=None, **params):
        return self._req("POST", path, json=json, params=params)

    def put(self, path, json=None):
        return self._req("PUT", path, json=json)

    def patch(self, path, json=None):
        return self._req("PATCH", path, json=json)

    def delete(self, path, **params):
        return self._req("DELETE", path, params=params)

    def raw(self, path) -> bytes:
        return self._req("GET", path)


# ---- formatting helpers -------------------------------------------------------------
def inr(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    s = f"{abs(v):,.2f}"
    whole, dec = s.split(".")
    digits = whole.replace(",", "")
    if len(digits) > 3:  # Indian grouping 12,34,567
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{'-' if v < 0 else ''}₹{whole}.{dec}" if dec != "00" else f"{'-' if v < 0 else ''}₹{whole}"


def dt(v, fmt="%d %b %Y, %I:%M %p") -> str:
    if not v:
        return "—"
    if isinstance(v, str):
        v = datetime.fromisoformat(v.replace("Z", ""))
    return v.strftime(fmt)


def nice(v) -> str:
    return str(v or "").replace("_", " ").title()


def make_app(name: str, template_dir: Path, accent: str) -> tuple[FastAPI, Jinja2Templates]:
    app = FastAPI(title=name, docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, session_cookie=f"ff_{accent}",
                       max_age=60 * 60 * 24 * 7, same_site="lax")
    app.mount("/static", StaticFiles(directory=SHARED_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=[template_dir, SHARED_DIR / "templates"])
    templates.env.filters.update(inr=inr, dt=dt, nice=nice)
    templates.env.globals.update(PUBLIC_API_URL=PUBLIC_API_URL, APP_ACCENT=accent, APP_NAME=name,
                                 signin_providers=signin_providers)
    return app, templates


# ---- session helpers ----------------------------------------------------------------
def api_for(request: Request) -> Api:
    return Api(request.session.get("token"))


def flash(request: Request, message: str, kind: str = "ok") -> None:
    request.session.setdefault("flash", []).append({"kind": kind, "message": message})


def pop_flash(request: Request) -> list[dict]:
    return request.session.pop("flash", [])


def back(request: Request, fallback: str = "/") -> RedirectResponse:
    ref = request.headers.get("referer") or fallback
    return RedirectResponse(ref, status_code=303)


def login_required(roles: set[str] | None = None, login_url: str = "/login"):
    """Decorator for page handlers. Redirects to login, checks role, and turns API errors into
    flash messages so forms never crash the page."""

    def deco(fn):
        @wraps(fn)
        async def wrapper(request: Request, *a, **kw):
            user = request.session.get("user")
            if not user:
                return RedirectResponse(f"{login_url}?next={request.url.path}", status_code=303)
            if roles and user["role"] not in roles:
                # Logged in, but this page is above their role: keep the session, go home.
                flash(request, "You don't have access to that page.", "error")
                return RedirectResponse("/" if request.url.path != "/" else login_url, status_code=303)
            try:
                return await fn(request, *a, **kw)
            except ApiError as e:
                if e.status == 401:
                    request.session.clear()
                    return RedirectResponse(login_url, status_code=303)
                flash(request, str(e), "error")
                if request.method == "GET":
                    return RedirectResponse("/", status_code=303) if request.url.path != "/" else \
                        RedirectResponse(login_url, status_code=303)
                return back(request)

        return wrapper

    return deco


def store_session(request: Request, token_payload: dict) -> None:
    request.session["token"] = token_payload["access_token"]
    request.session["user"] = token_payload["user"]


def render(templates: Jinja2Templates, request: Request, name: str, **ctx):
    ctx.setdefault("user", request.session.get("user"))
    ctx.setdefault("token", request.session.get("token"))
    ctx["flashes"] = pop_flash(request)
    ctx["path"] = request.url.path
    return templates.TemplateResponse(request, name, ctx)
