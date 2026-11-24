"""The website's one login page, like the phone app's: email + password, phone OTP, sign up, Google
button, Firebase email magic link and single sign-on. Every method ends in finish_login(), so the role on
the account decides which section opens: the shop, Store Operations (/store) or Admin (/admin)."""
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.shared import (PUBLIC_API_URL, ROLE_NAMES, SECTION_NAMES, SHOW_DEMO_ACCOUNTS, SITE_URL, Api, ApiError,
                        app_for_role, finish_login, flash, home_for, render)

APP_LINK_SCHEMES = ("exp://", "freshflow://")  # the phone app (Expo Go in development, the built app later)


def _json_login(request: Request, api_path: str, body: dict) -> JSONResponse:
    try:
        payload = Api().post(api_path, body)
    except ApiError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"redirect": finish_login(request, payload)})


DEMO_ACCOUNTS = [  # (email, role shown on the login page)
    ("asha@example.com", "Shopper"), ("rohan@example.com", "Shopper · same family list"),
    ("worker1.blr01@freshflow.app", "Floor Assistant"), ("floor1.blr01@freshflow.app", "Floor Manager"),
    ("manager.blr01@freshflow.app", "Store Manager"), ("owner.blr01@freshflow.app", "Store Owner"),
    ("admin@freshflow.app", "Platform Admin"),
]


def add_signin_routes(app: FastAPI, templates: Jinja2Templates) -> None:
    def to_login(mode: str = "email", **extra) -> RedirectResponse:
        return RedirectResponse("/login?" + urlencode({"mode": mode, **extra}), status_code=303)

    # ---- one login page for every role -------------------------------------------------
    @app.get("/login")
    async def login_page(request: Request, next: str = "/", mode: str = "email", step: str = ""):
        if request.session.get("user"):  # already signed in: straight to your section
            return RedirectResponse(home_for(request.session["user"]["role"]), status_code=303)
        if mode not in ("email", "phone", "register"):
            mode = "email"
        return render(templates, request, "_login.html", next=next, mode=mode,
                      otp_step=step == "verify" and bool(request.session.get("otp_phone")),
                      otp_phone=request.session.get("otp_phone"), demo_accounts=DEMO_ACCOUNTS if SHOW_DEMO_ACCOUNTS else [])

    @app.post("/login")
    async def login(request: Request, identifier: str = Form(...), password: str = Form(...), next: str = Form("/")):
        try:
            r = Api().post("/auth/login", {"identifier": identifier, "password": password})
        except ApiError as e:
            flash(request, str(e), "error")
            return to_login("email", identifier=identifier)
        return RedirectResponse(finish_login(request, r, next or "/"), status_code=303)

    @app.post("/register")
    async def register(request: Request, full_name: str = Form(...), email: str = Form(...), password: str = Form(...)):
        try:
            r = Api().post("/auth/register", {"full_name": full_name, "email": email, "password": password})
        except ApiError as e:
            flash(request, str(e), "error")
            return to_login("register")
        flash(request, "Welcome to FreshFlow! Use WELCOME50 on your first order.")
        return RedirectResponse(finish_login(request, r), status_code=303)  # new accounts are shoppers

    @app.post("/otp/request")
    async def otp_request(request: Request, phone: str = Form(...)):
        try:
            r = Api().post("/auth/otp/request", {"phone": phone})
        except ApiError as e:
            flash(request, str(e), "error")
            return to_login("phone")
        request.session["otp_phone"] = phone
        msg = "We sent a 6-digit code to your phone."
        if r.get("dev_code"):
            msg += f" (Development mode code: {r['dev_code']})"
        flash(request, msg)
        return to_login("phone", step="verify")

    @app.post("/otp/verify")
    async def otp_verify(request: Request, code: str = Form(...), full_name: str = Form("")):
        try:
            r = Api().post("/auth/otp/verify", {"phone": request.session.get("otp_phone"), "code": code, "full_name": full_name})
        except ApiError as e:
            flash(request, str(e), "error")
            return to_login("phone", step="verify")
        request.session.pop("otp_phone", None)
        return RedirectResponse(finish_login(request, r), status_code=303)

    @app.get("/privacy")
    async def privacy(request: Request):
        """Public privacy policy (Google Play asks for its address and shows it on the store page)."""
        return render(templates, request, "_privacy.html")

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @app.post("/auth/google")
    async def google_signin(request: Request):
        """The Google button posts the ID token ("credential") it received from Google."""
        body = await request.json()
        return _json_login(request, "/auth/google", {"id_token": str(body.get("credential", ""))})

    @app.post("/auth/firebase")
    async def firebase_signin(request: Request):
        """The email-link page posts the Firebase ID token after Firebase confirms the link."""
        body = await request.json()
        return _json_login(request, "/auth/firebase", {"id_token": str(body.get("id_token", "")),
                                                       "full_name": body.get("full_name") or None})

    @app.get("/auth/email-link")
    async def email_link(request: Request, app_url: str = Query("", alias="app")):
        """Where the magic link lands. On a phone it forwards the link into the app; otherwise it
        finishes the sign-in here."""
        target = app_url if app_url.startswith(APP_LINK_SCHEMES) else None
        return render(templates, request, "_email_link.html", app_url=target)

    @app.get("/auth/sso")
    async def sso_start(request: Request):
        query = urlencode({"redirect": f"{SITE_URL}/auth/continue"})
        return RedirectResponse(f"{PUBLIC_API_URL}/auth/sso/start?{query}", status_code=303)

    @app.get("/auth/continue")
    async def continue_signin(request: Request, code: str = "", error: str = ""):
        """Return point for SSO: swap the one-time code for a session."""
        if error or not code:
            flash(request, error or "Sign-in was cancelled.", "error")
            return RedirectResponse("/login", status_code=303)
        try:
            payload = Api().post("/auth/exchange", {"code": code})
        except ApiError as e:
            flash(request, str(e), "error")
            return RedirectResponse("/login", status_code=303)
        role = payload["user"]["role"]
        if role != "customer":
            flash(request, f"Signed in as {ROLE_NAMES.get(role, role)} · opening {SECTION_NAMES[app_for_role(role)]}")
        return RedirectResponse(finish_login(request, payload), status_code=303)
