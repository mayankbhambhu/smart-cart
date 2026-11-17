"""Sign-in routes shared by all three dashboards: Google button, Firebase email magic link and
single sign-on. Each ends in finish_login(), so the account's role still decides which dashboard opens."""
from urllib.parse import urlencode

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.shared import APP_URLS, PUBLIC_API_URL, Api, ApiError, finish_login, flash, render

APP_LINK_SCHEMES = ("exp://", "freshflow://")  # the phone app (Expo Go in development, the built app later)


def _json_login(request: Request, api_path: str, body: dict, app_key: str) -> JSONResponse:
    try:
        payload = Api().post(api_path, body)
    except ApiError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"redirect": finish_login(request, payload, app_key)})


def add_signin_routes(app: FastAPI, templates: Jinja2Templates, app_key: str) -> None:
    @app.post("/auth/google")
    async def google_signin(request: Request):
        """The Google button posts the ID token ("credential") it received from Google."""
        body = await request.json()
        return _json_login(request, "/auth/google", {"id_token": str(body.get("credential", ""))}, app_key)

    @app.post("/auth/firebase")
    async def firebase_signin(request: Request):
        """The email-link page posts the Firebase ID token after Firebase confirms the link."""
        body = await request.json()
        return _json_login(request, "/auth/firebase", {"id_token": str(body.get("id_token", "")),
                                                       "full_name": body.get("full_name") or None}, app_key)

    @app.get("/auth/email-link")
    async def email_link(request: Request, app_url: str = Query("", alias="app")):
        """Where the magic link lands. On a phone it forwards the link into the app; otherwise it
        finishes the sign-in here."""
        target = app_url if app_url.startswith(APP_LINK_SCHEMES) else None
        return render(templates, request, "_email_link.html", app_url=target)

    @app.get("/auth/sso")
    async def sso_start(request: Request):
        query = urlencode({"redirect": f"{APP_URLS[app_key]}/auth/continue"})
        return RedirectResponse(f"{PUBLIC_API_URL}/auth/sso/start?{query}", status_code=303)

    @app.get("/auth/continue")
    async def continue_signin(request: Request, code: str = "", error: str = ""):
        """Return point for SSO and for hand-offs from another dashboard: swap the one-time code."""
        if error or not code:
            flash(request, error or "Sign-in was cancelled.", "error")
            return RedirectResponse("/login", status_code=303)
        try:
            payload = Api().post("/auth/exchange", {"code": code})
        except ApiError as e:
            flash(request, str(e), "error")
            return RedirectResponse("/login", status_code=303)
        return RedirectResponse(finish_login(request, payload, app_key), status_code=303)
