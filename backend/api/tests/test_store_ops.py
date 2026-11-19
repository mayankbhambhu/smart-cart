"""Store operations + admin: onboarding workflow, tasks, shifts, attendance, analytics, tickets."""


def test_credential_workflow_manager_owner_admin(client, login):
    mgr, owner, admin = (login("manager.blr01@freshflow.app"), login("owner.blr01@freshflow.app"),
                         login("admin@freshflow.app"))
    body = {"full_name": "New Hire", "email": "new.hire@example.com", "phone": "+919855555555", "role": "worker",
            "hourly_wage": 165, "joining_date": "2026-12-01"}
    req = client.post("/ops/stores/1/credential-requests", json=body, headers=mgr).json()
    assert req["status"] == "pending_owner"
    # owner cannot be skipped
    assert client.post(f"/admin/credential-requests/{req['id']}/review", json={"decision": "approve"},
                       headers=admin).status_code == 409
    r = client.post(f"/ops/stores/1/credential-requests/{req['id']}/owner-review",
                    json={"decision": "send_back", "note": "Wage too high"}, headers=owner).json()
    assert r["status"] == "changes_requested"
    r = client.put(f"/ops/stores/1/credential-requests/{req['id']}", json={**body, "hourly_wage": 155}, headers=mgr).json()
    assert r["status"] == "pending_owner"
    r = client.post(f"/ops/stores/1/credential-requests/{req['id']}/owner-review",
                    json={"decision": "approve"}, headers=owner).json()
    assert r["status"] == "pending_admin"
    r = client.post(f"/admin/credential-requests/{req['id']}/review", json={"decision": "approve"}, headers=admin).json()
    creds = r["credentials"]
    login_r = client.post("/auth/login", json={"identifier": creds["login"], "password": creds["temporary_password"]})
    assert login_r.status_code == 200 and login_r.json()["user"]["must_change_password"]
    # admin offboards -> login revoked
    uid = login_r.json()["user"]["id"]
    assert client.delete(f"/admin/employees/{uid}", params={"reason": "fired"}, headers=admin).json()["ok"]
    assert client.post("/auth/login", json={"identifier": creds["login"],
                                            "password": creds["temporary_password"]}).status_code == 401


def test_store_staff_cannot_cross_stores(client, login):
    mgr = login("manager.blr01@freshflow.app")
    assert client.get("/ops/stores/2/inventory", headers=mgr).status_code == 403
    assert client.get("/admin/stores", headers=mgr).status_code == 403
    cust = login("asha@example.com")
    assert client.get("/ops/stores/1/inventory", headers=cust).status_code == 403


def test_task_assign_complete_review(client, login):
    mgr, worker = login("manager.blr01@freshflow.app"), login("worker1.blr01@freshflow.app")
    wid = client.get("/me", headers=worker).json()["id"]
    t = client.post("/ops/stores/1/tasks", json={"title": "Restock chips", "assigned_to_id": wid, "priority": "high"},
                    headers=mgr).json()
    notes = client.get("/me/notifications", headers=worker).json()
    assert any("Restock chips" in n["title"] for n in notes)
    assert client.post(f"/ops/me/tasks/{t['id']}", json={"status": "done"}, headers=worker).status_code == 400
    done = client.post(f"/ops/me/tasks/{t['id']}", json={"status": "done", "completion_note": "Aisle 4 full"},
                       headers=worker).json()
    assert done["status"] == "done"
    rev = client.post(f"/ops/stores/1/tasks/{t['id']}/review", json={"rating": 4, "feedback": "Good"}, headers=mgr).json()
    assert rev["status"] == "reviewed" and rev["manager_rating"] == 4
    # a worker cannot assign tasks
    assert client.post("/ops/stores/1/tasks", json={"title": "x", "assigned_to_id": wid}, headers=worker).status_code == 403


def test_shifts_and_attendance(client, login):
    mgr, worker = login("manager.blr01@freshflow.app"), login("worker2.blr01@freshflow.app")
    wid = client.get("/me", headers=worker).json()["id"]
    r = client.post("/ops/stores/1/shifts", json={"user_id": wid, "starts_at": "2099-01-01T07:00:00",
                                                  "ends_at": "2099-01-01T15:00:00", "label": "Morning"}, headers=mgr)
    assert r.status_code == 201
    clash = client.post("/ops/stores/1/shifts", json={"user_id": wid, "starts_at": "2099-01-01T10:00:00",
                                                      "ends_at": "2099-01-01T18:00:00"}, headers=mgr)
    assert clash.status_code == 409
    assert client.post("/ops/me/clock", headers=worker).json()["action"] == "clocked_in"
    assert client.post("/ops/me/clock", headers=worker).json()["action"] == "clocked_out"
    att = client.get("/ops/stores/1/attendance", params={"period": "month"}, headers=mgr).json()
    row = next(s for s in att["summary"] if s["user_id"] == wid)
    assert row["days_present"] >= 1 and row["hours"] > 0


def test_inventory_threshold_alert_creates_task(client, login):
    mgr = login("manager.blr01@freshflow.app")
    inv = next(i for i in client.get("/ops/stores/1/inventory", params={"q": "Cola"}, headers=mgr).json()
               if i["name"] == "Cola")
    client.patch(f"/ops/stores/1/inventory/{inv['id']}", json={"quantity": 4}, headers=mgr)
    alerts = client.get("/ops/stores/1/alerts", headers=mgr).json()
    a = next(a for a in alerts if a["product"] == "Cola")
    assert a["status"] == "assigned" and a["task_id"]
    client.patch(f"/ops/stores/1/inventory/{inv['id']}", json={"quantity_delta": 60}, headers=mgr)
    assert not any(a["product"] == "Cola" for a in client.get("/ops/stores/1/alerts", headers=mgr).json())


def test_analytics(client, login):
    owner = login("owner.blr01@freshflow.app")
    for period in ("today", "month", "year"):
        r = client.get("/ops/stores/1/analytics", params={"period": period}, headers=owner)
        assert r.status_code == 200
    rep = client.get("/ops/stores/1/analytics", params={"period": "custom", "start": "2020-01-01",
                                                         "end": "2099-01-01"}, headers=owner).json()
    k = rep["kpis"]
    assert k["orders"] > 500 and k["net_sales"] > k["gross_profit"] > 0
    assert rep["top_products"] and rep["offers"] and len(rep["rush_hours"]) == 3
    assert rep["rush_hours"][0]["hour"] in (18, 19, 20)  # seeded evening peak
    worker = login("worker1.blr01@freshflow.app")
    assert client.get("/ops/stores/1/analytics", headers=worker).status_code == 403


def test_support_ticket_roundtrip(client, login):
    mgr, admin = login("manager.blr01@freshflow.app"), login("admin@freshflow.app")
    t = client.post("/ops/stores/1/tickets", json={"category": "payments", "subject": "UPI failures",
                                                   "description": "Several UPI payments timing out"}, headers=mgr).json()
    r = client.post(f"/admin/tickets/{t['id']}", json={"status": "resolved", "admin_response": "Gateway fixed"},
                    headers=admin).json()
    assert r["status"] == "resolved"
    assert any(x["id"] == t["id"] and x["admin_response"] for x in client.get("/ops/stores/1/tickets", headers=mgr).json())


def test_admin_create_store_and_overview(client, login):
    admin = login("admin@freshflow.app")
    r = client.post("/admin/stores", json={"code": "DEL01", "name": "FreshFlow Saket", "address": "Saket",
                                           "city": "Delhi", "latitude": 28.52, "longitude": 77.21,
                                           "owner_name": "Dev Owner", "owner_email": "dev.owner@example.com",
                                           "owner_phone": "+919866666666"}, headers=admin)
    assert r.status_code == 201 and r.json()["owner_credentials"]["temporary_password"]
    ov = client.get("/admin/overview", headers=admin).json()
    assert ov["counts"]["stores"] == 4 and ov["kpis"]["orders"] > 0
    detail = client.get("/admin/stores/1", headers=admin).json()
    assert detail["employees"] and "hourly_wage" in detail["employees"][0]
