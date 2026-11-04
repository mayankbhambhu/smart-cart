"""Admin Operations dashboard — the FreshFlow platform team.

Run: uvicorn web.admin.app:app --port 8003   (from the repo root)
"""
from pathlib import Path

from fastapi import Form, Request
from fastapi.responses import RedirectResponse

from web.shared import Api, ApiError, api_for, back, flash, login_required, make_app, render, store_session

app, templates = make_app("FreshFlow Admin", Path(__file__).parent / "templates", "admin")
ADMIN = {"admin"}
guard = login_required(ADMIN)
NAV = [("/", "Overview", "📊"), ("/requests", "Credential requests", "🔐"), ("/stores", "Stores & owners", "🏬"),
       ("/employees", "Employees", "👥"), ("/tickets", "Store issues", "🛟")]


def page(request, name, **ctx):
    ctx.setdefault("live_channels", ["admin", f"user:{request.session['user']['id']}"])
    ctx["nav"] = NAV
    return render(templates, request, name, **ctx)


@app.get("/login")
async def login_page(request: Request, next: str = "/"):
    return render(templates, request, "_login.html", next=next, subtitle="Admin Operations",
                  demo_accounts=["admin@freshflow.app"])


@app.post("/login")
async def login(request: Request, identifier: str = Form(...), password: str = Form(...), next: str = Form("/")):
    try:
        r = Api().post("/auth/login", {"identifier": identifier, "password": password})
    except ApiError as e:
        flash(request, str(e), "error")
        return RedirectResponse("/login", status_code=303)
    if r["user"]["role"] != "admin":
        flash(request, "Admin accounts only.", "error")
        return RedirectResponse("/login", status_code=303)
    store_session(request, r)
    return RedirectResponse(next or "/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
@guard
async def overview(request: Request, period: str = "month"):
    api = api_for(request)
    return page(request, "overview.html", ov=api.get("/admin/overview", period=period), period=period,
                pending=api.get("/admin/credential-requests", status="pending_admin")[:5],
                tickets=[t for t in api.get("/admin/tickets") if t["status"] != "resolved"][:5])


@app.get("/requests")
@guard
async def requests_page(request: Request, status: str = "pending_admin"):
    return page(request, "requests.html", rows=api_for(request).get("/admin/credential-requests", status=status),
                status=status, issued=request.session.pop("issued", None))


@app.post("/requests/{req_id}")
@guard
async def review(request: Request, req_id: int, decision: str = Form(...), note: str = Form("")):
    if decision == "send_back" and not note.strip():
        flash(request, "Add a note telling the store what to change.", "error")
        return back(request)
    r = api_for(request).post(f"/admin/credential-requests/{req_id}/review", {"decision": decision, "note": note})
    if r.get("credentials"):
        request.session["issued"] = {"name": r["full_name"], **r["credentials"]}
    flash(request, {"approve": "Credentials issued", "send_back": "Sent back to the store",
                    "reject": "Request rejected"}[decision])
    return back(request)


@app.get("/stores")
@guard
async def stores(request: Request):
    return page(request, "stores.html", stores=api_for(request).get("/admin/stores"),
                issued=request.session.pop("issued", None))


@app.post("/stores")
@guard
async def create_store(request: Request):
    f = await request.form()
    body = {k: f.get(k) for k in ("code", "name", "address", "city", "pincode", "phone", "owner_name", "owner_email",
                                  "owner_phone")}
    body |= {"latitude": float(f["latitude"]), "longitude": float(f["longitude"]),
             "aisle_count": int(f.get("aisle_count") or 8), "rows_per_aisle": int(f.get("rows_per_aisle") or 6)}
    r = api_for(request).post("/admin/stores", body)
    request.session["issued"] = {"name": f"Owner of {body['name']}", **r["owner_credentials"]}
    flash(request, "Store created with owner account and an exit gate")
    return back(request)


@app.get("/stores/{store_id}")
@guard
async def store_detail(request: Request, store_id: int):
    return page(request, "store_detail.html", d=api_for(request).get(f"/admin/stores/{store_id}"))


@app.post("/stores/{store_id}/toggle")
@guard
async def toggle_store(request: Request, store_id: int):
    api_for(request).post(f"/admin/stores/{store_id}/toggle")
    return back(request)


@app.get("/employees")
@guard
async def employees(request: Request, store_id: str = "", role: str = "", active: str = "true", q: str = ""):
    api = api_for(request)
    return page(request, "employees.html", rows=api.get("/admin/employees", store_id=store_id, role=role,
                                                         active=active, q=q),
                stores=api.get("/admin/stores"), f={"store_id": store_id, "role": role, "active": active, "q": q},
                issued=request.session.pop("issued", None))


@app.post("/employees/{user_id}/remove")
@guard
async def remove_employee(request: Request, user_id: int, reason: str = Form("left")):
    api_for(request).delete(f"/admin/employees/{user_id}", reason=reason)
    flash(request, f"Employee removed ({reason}). Login revoked; attendance history kept for payroll.")
    return back(request)


@app.post("/employees/{user_id}/reset")
@guard
async def reset_password(request: Request, user_id: int):
    r = api_for(request).post(f"/admin/employees/{user_id}/reset-password")
    request.session["issued"] = {"name": "Password reset", "login": r["login"], "temporary_password": r["temporary_password"]}
    return back(request)


@app.get("/tickets")
@guard
async def tickets(request: Request, status: str = ""):
    return page(request, "tickets.html", rows=api_for(request).get("/admin/tickets", status=status), status=status)


@app.post("/tickets/{ticket_id}")
@guard
async def respond(request: Request, ticket_id: int, status: str = Form(...), admin_response: str = Form("")):
    api_for(request).post(f"/admin/tickets/{ticket_id}", {"status": status, "admin_response": admin_response})
    flash(request, "Store notified")
    return back(request)
