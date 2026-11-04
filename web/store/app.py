"""Store Operations dashboard — owner, store manager, floor manager, worker.

Run: uvicorn web.store.app:app --port 8002   (from the repo root)
"""
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Form, Request
from fastapi.responses import RedirectResponse

from web.shared import Api, ApiError, api_for, back, flash, login_required, make_app, render, store_session

app, templates = make_app("FreshFlow Store Ops", Path(__file__).parent / "templates", "store")
STAFF = {"owner", "store_manager", "floor_manager", "worker"}
MANAGERS = {"owner", "store_manager"}
SUPERVISORS = MANAGERS | {"floor_manager"}

# (path, label, icon, roles allowed)
NAV = [
    ("/", "Overview", "🏠", STAFF),
    ("/tasks", "Work & tasks", "✅", STAFF),
    ("/inventory", "Live inventory", "📦", STAFF),
    ("/orders", "Orders", "🧾", STAFF),
    ("/gate", "Exit gates", "🚪", STAFF),
    ("/shifts", "Shifts", "🗓️", STAFF),
    ("/attendance", "Attendance", "⏱️", SUPERVISORS),
    ("/team", "Team & onboarding", "👥", SUPERVISORS),
    ("/analytics", "Business analysis", "📈", MANAGERS),
    ("/offers", "Offers", "🏷️", MANAGERS),
    ("/support", "Support tickets", "🛟", MANAGERS),
]


def page(request: Request, name: str, **ctx):
    user = request.session["user"]
    if user.get("must_change_password") and name != "account.html":
        flash(request, "Please set a new password before continuing.", "error")
        return RedirectResponse("/account", status_code=303)
    ctx.setdefault("live_channels", [f"store:{user['store_id']}", f"user:{user['id']}"])
    ctx["nav"] = [n for n in NAV if user["role"] in n[3]]
    ctx["sid"] = user["store_id"]
    return render(templates, request, name, **ctx)


def guard(roles=STAFF):
    return login_required(roles)


def sid(request: Request) -> int:
    return request.session["user"]["store_id"]


# ---- auth ------------------------------------------------------------------------------
@app.get("/login")
async def login_page(request: Request, next: str = "/"):
    return render(templates, request, "_login.html", next=next, subtitle="Store Operations",
                  demo_accounts=["owner.blr01@freshflow.app", "manager.blr01@freshflow.app",
                                 "floor1.blr01@freshflow.app", "worker1.blr01@freshflow.app"])


@app.post("/login")
async def login(request: Request, identifier: str = Form(...), password: str = Form(...), next: str = Form("/")):
    try:
        r = Api().post("/auth/login", {"identifier": identifier, "password": password})
    except ApiError as e:
        flash(request, str(e), "error")
        return RedirectResponse("/login", status_code=303)
    if r["user"]["role"] not in STAFF:
        flash(request, "This dashboard is for store staff only.", "error")
        return RedirectResponse("/login", status_code=303)
    store_session(request, r)
    return RedirectResponse(next or "/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/account")
@guard()
async def account(request: Request):
    return page(request, "account.html")


@app.post("/account")
@guard()
async def change_password(request: Request, current_password: str = Form(...), new_password: str = Form(...)):
    api_for(request).post("/me/password", {"current_password": current_password, "new_password": new_password})
    request.session["user"] = {**request.session["user"], "must_change_password": False}
    flash(request, "Password updated")
    return RedirectResponse("/", status_code=303)


# ---- overview ---------------------------------------------------------------------------
@app.get("/")
@guard()
async def home(request: Request):
    api, role = api_for(request), request.session["user"]["role"]
    ctx = {"store": api.get(f"/stores/{sid(request)}"), "clock": api.get("/ops/me/attendance"),
           "my_tasks": [t for t in api.get("/ops/me/tasks") if t["status"] in ("assigned", "in_progress")],
           "my_shifts": api.get("/ops/me/shifts")[:3], "alerts": api.get(f"/ops/stores/{sid(request)}/alerts")}
    if role in MANAGERS:
        ctx["report"] = api.get(f"/ops/stores/{sid(request)}/analytics", period="today")
    if role in SUPERVISORS:
        ctx["employees"] = api.get(f"/ops/stores/{sid(request)}/employees")
        ctx["to_review"] = api.get(f"/ops/stores/{sid(request)}/tasks", status="done")
    ctx["notifications"] = api.get("/me/notifications")[:8]
    return page(request, "home.html", **ctx)


@app.post("/clock")
@guard()
async def clock(request: Request):
    r = api_for(request).post("/ops/me/clock")
    flash(request, "Clocked in — have a great shift!" if r["action"] == "clocked_in" else "Clocked out. See you next time!")
    return back(request)


# ---- inventory --------------------------------------------------------------------------
@app.get("/inventory")
@guard()
async def inventory(request: Request, q: str = "", low: int = 0):
    api = api_for(request)
    return page(request, "inventory.html", rows=api.get(f"/ops/stores/{sid(request)}/inventory", q=q, low_only=bool(low)),
                alerts=api.get(f"/ops/stores/{sid(request)}/alerts"), q=q, low=low)


@app.post("/inventory/{inv_id}")
@guard()
async def update_inventory(request: Request, inv_id: int):
    form = await request.form()
    body = {k: int(v) for k, v in form.items() if v not in ("", None) and k in
            ("quantity_delta", "quantity", "aisle", "row", "low_stock_threshold")}
    r = api_for(request).patch(f"/ops/stores/{sid(request)}/inventory/{inv_id}", body)
    flash(request, f"Updated · now {r['quantity']} at Aisle {r['aisle']}, Row {r['row']}")
    return back(request)


# ---- orders -----------------------------------------------------------------------------
@app.get("/orders")
@guard()
async def orders(request: Request, status: str = "", fulfilment: str = ""):
    rows = api_for(request).get(f"/ops/stores/{sid(request)}/orders", status=status, fulfilment=fulfilment)
    return page(request, "orders.html", rows=rows, status=status, fulfilment=fulfilment)


@app.post("/orders/{order_id}/status")
@guard()
async def order_status(request: Request, order_id: int, status: str = Form(...)):
    api_for(request).post(f"/ops/stores/{sid(request)}/orders/{order_id}/status", {"status": status})
    return back(request)


# ---- tasks ------------------------------------------------------------------------------
@app.get("/tasks")
@guard()
async def tasks(request: Request, status: str = ""):
    api, role = api_for(request), request.session["user"]["role"]
    ctx = {"mine": api.get("/ops/me/tasks"), "status": status}
    if role in SUPERVISORS:
        ctx["all"] = api.get(f"/ops/stores/{sid(request)}/tasks", status=status)
        assignable = {"owner": {"store_manager", "floor_manager", "worker"},
                      "store_manager": {"floor_manager", "worker"}, "floor_manager": {"worker"}}[role]
        ctx["assignees"] = [e for e in api.get(f"/ops/stores/{sid(request)}/employees")
                            if e["role"] in assignable and e["is_active"]]
    return page(request, "tasks.html", **ctx)


@app.post("/tasks")
@guard(SUPERVISORS)
async def assign_task(request: Request, title: str = Form(...), description: str = Form(""),
                      priority: str = Form("normal"), assigned_to_id: int = Form(...), due_at: str = Form("")):
    api_for(request).post(f"/ops/stores/{sid(request)}/tasks", {
        "title": title, "description": description, "priority": priority, "assigned_to_id": assigned_to_id,
        "due_at": due_at or None})
    flash(request, "Task assigned — the employee has been alerted")
    return back(request)


@app.post("/tasks/{task_id}/progress")
@guard()
async def task_progress(request: Request, task_id: int, status: str = Form(...), completion_note: str = Form("")):
    api_for(request).post(f"/ops/me/tasks/{task_id}", {"status": status, "completion_note": completion_note or None})
    flash(request, "Marked as done — your manager has been notified" if status == "done" else "Task started")
    return back(request)


@app.post("/tasks/{task_id}/review")
@guard(SUPERVISORS)
async def task_review(request: Request, task_id: int, rating: int = Form(...), feedback: str = Form("")):
    api_for(request).post(f"/ops/stores/{sid(request)}/tasks/{task_id}/review", {"rating": rating, "feedback": feedback})
    flash(request, "Review saved")
    return back(request)


# ---- shifts & attendance ------------------------------------------------------------------
@app.get("/shifts")
@guard()
async def shifts(request: Request, start: str | None = None):
    api = api_for(request)
    start_d = date.fromisoformat(start) if start else date.today()
    rows = api.get(f"/ops/stores/{sid(request)}/shifts", start=start_d.isoformat(), days=7)
    days = [start_d + timedelta(days=i) for i in range(7)]
    people: dict[int, dict] = {}
    for s in rows:
        p = people.setdefault(s["user_id"], {"name": s["name"], "days": {d.isoformat(): [] for d in days}, "hours": 0})
        p["days"][s["starts_at"][:10]].append(s)
        p["hours"] += s["hours"]
    employees = api.get(f"/ops/stores/{sid(request)}/employees") if request.session["user"]["role"] in SUPERVISORS else []
    return page(request, "shifts.html", days=days, people=people, employees=employees, start=start_d,
                prev=(start_d - timedelta(days=7)).isoformat(), next=(start_d + timedelta(days=7)).isoformat())


@app.post("/shifts")
@guard(MANAGERS)
async def create_shift(request: Request, user_id: int = Form(...), day: str = Form(...), start_time: str = Form(...),
                       end_time: str = Form(...), label: str = Form(""), repeat_days: int = Form(1)):
    api = api_for(request)
    made = 0
    for i in range(max(1, min(repeat_days, 14))):
        d = date.fromisoformat(day) + timedelta(days=i)
        s = datetime.fromisoformat(f"{d}T{start_time}")
        e = datetime.fromisoformat(f"{d}T{end_time}")
        if e <= s:
            e += timedelta(days=1)  # overnight shift
        try:
            api.post(f"/ops/stores/{sid(request)}/shifts", {"user_id": user_id, "starts_at": s.isoformat(),
                                                            "ends_at": e.isoformat(), "label": label})
            made += 1
        except ApiError as err:
            flash(request, f"{d}: {err}", "error")
    if made:
        flash(request, f"{made} shift(s) assigned")
    return back(request)


@app.post("/shifts/{shift_id}/delete")
@guard(MANAGERS)
async def delete_shift(request: Request, shift_id: int):
    api_for(request).delete(f"/ops/stores/{sid(request)}/shifts/{shift_id}")
    return back(request)


@app.get("/attendance")
@guard(SUPERVISORS)
async def attendance(request: Request, period: str = "week", start: str = "", end: str = "", user_id: int | None = None):
    data = api_for(request).get(f"/ops/stores/{sid(request)}/attendance", period=period, start=start, end=end)
    if user_id:
        data["log"] = [r for r in data["log"] if r["user_id"] == user_id]
    return page(request, "attendance.html", data=data, period=period, start=start, end=end, user_id=user_id)


# ---- analytics ------------------------------------------------------------------------------
@app.get("/analytics")
@guard(MANAGERS)
async def analytics(request: Request, period: str = "month", start: str = "", end: str = ""):
    r = api_for(request).get(f"/ops/stores/{sid(request)}/analytics", period=period, start=start, end=end)
    return page(request, "analytics.html", r=r, period=period, start=start, end=end)


# ---- team & onboarding -------------------------------------------------------------------
@app.get("/team")
@guard(SUPERVISORS)
async def team(request: Request):
    api, role = api_for(request), request.session["user"]["role"]
    reqs = api.get(f"/ops/stores/{sid(request)}/credential-requests") if role in MANAGERS else []
    return page(request, "team.html", employees=api.get(f"/ops/stores/{sid(request)}/employees"), requests=reqs)


@app.get("/team/requests")
@guard(SUPERVISORS)
async def team_requests(request: Request):
    return RedirectResponse("/team#requests", status_code=303)


def _cred_body(form) -> dict:
    return {k: form.get(k) for k in ("full_name", "email", "phone", "role", "joining_date", "notes")} | \
        {"hourly_wage": float(form.get("hourly_wage") or 0)}


@app.post("/team/requests")
@guard({"store_manager"})
async def raise_request(request: Request):
    api_for(request).post(f"/ops/stores/{sid(request)}/credential-requests", _cred_body(await request.form()))
    flash(request, "Request sent to the store owner for review")
    return back(request)


@app.post("/team/requests/{req_id}")
@guard({"store_manager"})
async def resubmit_request(request: Request, req_id: int):
    api_for(request).put(f"/ops/stores/{sid(request)}/credential-requests/{req_id}", _cred_body(await request.form()))
    flash(request, "Request updated and resubmitted to the owner")
    return back(request)


@app.post("/team/requests/{req_id}/review")
@guard({"owner"})
async def owner_review(request: Request, req_id: int, decision: str = Form(...), note: str = Form("")):
    api_for(request).post(f"/ops/stores/{sid(request)}/credential-requests/{req_id}/owner-review",
                          {"decision": decision, "note": note})
    flash(request, {"approve": "Approved — forwarded to the FreshFlow admin team",
                    "send_back": "Sent back to the store manager", "reject": "Request rejected"}[decision])
    return back(request)


# ---- offers / gates / support ----------------------------------------------------------------
@app.get("/offers")
@guard(MANAGERS)
async def offers(request: Request):
    api = api_for(request)
    return page(request, "offers.html", offers=api.get(f"/ops/stores/{sid(request)}/offers"),
                categories=api.get("/categories"),
                stats={o["code"]: o for o in api.get(f"/ops/stores/{sid(request)}/analytics", period="month")["offers"]})


@app.post("/offers")
@guard(MANAGERS)
async def create_offer(request: Request):
    f = await request.form()
    api_for(request).post(f"/ops/stores/{sid(request)}/offers", {
        "code": f["code"], "title": f["title"], "discount_percent": float(f["discount_percent"]),
        "max_discount": float(f.get("max_discount") or 100), "min_order": float(f.get("min_order") or 0),
        "category_id": int(f["category_id"]) if f.get("category_id") else None, "ends_at": f.get("ends_at") or None})
    flash(request, "Offer is live")
    return back(request)


@app.post("/offers/{offer_id}/toggle")
@guard(MANAGERS)
async def toggle_offer(request: Request, offer_id: int):
    api_for(request).post(f"/ops/stores/{sid(request)}/offers/{offer_id}/toggle")
    return back(request)


@app.get("/gate")
@guard()
async def gate(request: Request):
    return page(request, "gate.html", data=api_for(request).get(f"/ops/stores/{sid(request)}/gates"),
                result=request.session.pop("gate_result", None))


@app.post("/gate/{gate_id}/scan")
@guard()
async def gate_scan(request: Request, gate_id: int, code: str = Form(...)):
    request.session["gate_result"] = api_for(request).post(f"/gate/{gate_id}/simulate", {"code": code})
    return RedirectResponse("/gate", status_code=303)


@app.get("/support")
@guard(MANAGERS)
async def support(request: Request):
    return page(request, "support.html", tickets=api_for(request).get(f"/ops/stores/{sid(request)}/tickets"))


@app.post("/support")
@guard(MANAGERS)
async def raise_ticket(request: Request, category: str = Form(...), priority: str = Form(...),
                       subject: str = Form(...), description: str = Form(...)):
    api_for(request).post(f"/ops/stores/{sid(request)}/tickets", {"category": category, "priority": priority,
                                                                  "subject": subject, "description": description})
    flash(request, "Ticket sent to the FreshFlow admin team")
    return back(request)
