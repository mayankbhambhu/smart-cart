"""Store people management: onboarding requests, tasks, shifts, attendance."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ALL_STAFF, MANAGERS, SUPERVISORS, ensure_store_access, get_current_user, require_roles
from app.core.realtime import hub
from app.models import Attendance, CredentialRequest, CredentialStatus, Role, Shift, Task, TaskStatus, User
from app.models._mixins import utcnow
from app.schemas import CredentialRequestIn, ReviewIn, ShiftIn, TaskIn, TaskProgressIn, TaskReviewIn
from app.services.analytics import resolve_range, staff_hours
from app.services.notify import notify, notify_roles

router = APIRouter(prefix="/ops/stores/{store_id}", tags=["people & work"])
me_router = APIRouter(prefix="/ops/me", tags=["people & work"])
staff = require_roles(*ALL_STAFF)

# who may assign tasks to whom
CAN_ASSIGN = {
    Role.OWNER.value: {Role.STORE_MANAGER.value, Role.FLOOR_MANAGER.value, Role.WORKER.value},
    Role.STORE_MANAGER.value: {Role.FLOOR_MANAGER.value, Role.WORKER.value},
    Role.FLOOR_MANAGER.value: {Role.WORKER.value},
}


def user_brief(u: User) -> dict:
    return {"id": u.id, "name": u.full_name, "role": u.role, "email": u.email, "phone": u.phone,
            "employee_code": u.employee_code, "joined_on": u.joined_on, "hourly_wage": u.hourly_wage,
            "is_active": u.is_active}


def cred_dict(r: CredentialRequest, db: Session) -> dict:
    by = db.get(User, r.requested_by_id)
    return {"id": r.id, "store_id": r.store_id, "full_name": r.full_name, "email": r.email, "phone": r.phone,
            "role": r.role, "hourly_wage": r.hourly_wage, "joining_date": r.joining_date, "notes": r.notes,
            "status": r.status, "sent_back_by": r.sent_back_by, "owner_note": r.owner_note,
            "admin_note": r.admin_note, "requested_by": by.full_name if by else "", "created_at": r.created_at,
            "updated_at": r.updated_at, "created_user_id": r.created_user_id}


# ---- Employees ---------------------------------------------------------------------
@router.get("/employees")
def employees(store_id: int, user: User = Depends(require_roles(*SUPERVISORS)), db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    rows = db.query(User).filter(User.store_id == store_id).order_by(User.role, User.full_name).all()
    today = utcnow().date()
    on_clock = {a.user_id for a in db.query(Attendance).filter(Attendance.store_id == store_id,
                                                                Attendance.clock_out.is_(None))}
    out = []
    for u in rows:
        open_tasks = db.query(Task).filter(Task.assigned_to_id == u.id,
                                           Task.status.in_(["assigned", "in_progress"])).count()
        out.append({**user_brief(u), "on_clock": u.id in on_clock, "open_tasks": open_tasks})
    _ = today
    return out


# ---- Credential requests (Store Manager -> Owner -> Admin) ---------------------------
@router.get("/credential-requests")
def list_requests(store_id: int, user: User = Depends(require_roles(*MANAGERS)), db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    rows = db.query(CredentialRequest).filter_by(store_id=store_id).order_by(CredentialRequest.id.desc())
    return [cred_dict(r, db) for r in rows]


@router.post("/credential-requests", status_code=201)
def raise_request(store_id: int, data: CredentialRequestIn, user: User = Depends(require_roles(Role.STORE_MANAGER)),
                  db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(409, "A user with this email already exists")
    r = CredentialRequest(store_id=store_id, requested_by_id=user.id, **data.model_dump())
    r.email = r.email.lower()
    db.add(r)
    db.flush()
    notify_roles(db, store_id, [Role.OWNER], "credential", "New employee credential request",
                 f"{data.full_name} ({data.role.replace('_', ' ')}) needs your review", link="/team/requests")
    db.commit()
    return cred_dict(r, db)


@router.put("/credential-requests/{req_id}")
def resubmit_request(store_id: int, req_id: int, data: CredentialRequestIn,
                     user: User = Depends(require_roles(Role.STORE_MANAGER)), db: Session = Depends(get_db)):
    """Manager edits a request that was sent back and resubmits it to the owner."""
    ensure_store_access(user, store_id)
    r = db.get(CredentialRequest, req_id)
    if not r or r.store_id != store_id:
        raise HTTPException(404, "Request not found")
    if r.status not in (CredentialStatus.CHANGES_REQUESTED.value, CredentialStatus.PENDING_OWNER.value):
        raise HTTPException(409, "Only pending or sent-back requests can be edited")
    for k, v in data.model_dump().items():
        setattr(r, k, v)
    r.status = CredentialStatus.PENDING_OWNER.value
    notify_roles(db, store_id, [Role.OWNER], "credential", "Credential request resubmitted", r.full_name,
                 link="/team/requests")
    db.commit()
    return cred_dict(r, db)


@router.post("/credential-requests/{req_id}/owner-review")
def owner_review(store_id: int, req_id: int, data: ReviewIn, user: User = Depends(require_roles(Role.OWNER)),
                 db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    r = db.get(CredentialRequest, req_id)
    if not r or r.store_id != store_id:
        raise HTTPException(404, "Request not found")
    if r.status != CredentialStatus.PENDING_OWNER.value:
        raise HTTPException(409, f"Request is {r.status}, not waiting for the owner")
    r.owner_note, r.owner_reviewed_at = data.note, utcnow()
    if data.decision == "approve":
        r.status = CredentialStatus.PENDING_ADMIN.value
        for admin in db.query(User).filter_by(role=Role.ADMIN.value, is_active=True):
            notify(db, admin.id, "credential", "Credential request awaiting admin review",
                   f"{r.full_name} — store #{store_id}", link="/requests")
        hub.publish("admin", "credential_request", {"id": r.id, "store_id": store_id, "name": r.full_name})
    elif data.decision == "send_back":
        r.status, r.sent_back_by = CredentialStatus.CHANGES_REQUESTED.value, "owner"
        notify(db, r.requested_by_id, "credential", f"Owner requested changes: {r.full_name}", data.note,
               link="/team/requests")
    else:
        r.status = CredentialStatus.REJECTED.value
        notify(db, r.requested_by_id, "credential", f"Owner rejected request: {r.full_name}", data.note)
    db.commit()
    return cred_dict(r, db)


# ---- Tasks -------------------------------------------------------------------------
def task_dict(t: Task, db: Session) -> dict:
    to, by = db.get(User, t.assigned_to_id), db.get(User, t.assigned_by_id)
    return {"id": t.id, "title": t.title, "description": t.description, "priority": t.priority,
            "status": t.status, "due_at": t.due_at, "created_at": t.created_at,
            "assigned_to": {"id": to.id, "name": to.full_name, "role": to.role} if to else None,
            "assigned_by": {"id": by.id, "name": by.full_name} if by else None,
            "completion_note": t.completion_note, "completed_at": t.completed_at,
            "manager_rating": t.manager_rating, "manager_feedback": t.manager_feedback}


@router.get("/tasks")
def store_tasks(store_id: int, status: str | None = None, assignee_id: int | None = None,
                user: User = Depends(require_roles(*SUPERVISORS)), db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    q = db.query(Task).filter_by(store_id=store_id)
    if status:
        q = q.filter(Task.status == status)
    if assignee_id:
        q = q.filter(Task.assigned_to_id == assignee_id)
    return [task_dict(t, db) for t in q.order_by(Task.id.desc()).limit(300)]


@router.post("/tasks", status_code=201)
def assign_task(store_id: int, data: TaskIn, user: User = Depends(require_roles(*SUPERVISORS)),
                db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    assignee = db.get(User, data.assigned_to_id)
    if not assignee or assignee.store_id != store_id or not assignee.is_active:
        raise HTTPException(404, "Employee not found in this store")
    if assignee.role not in CAN_ASSIGN.get(user.role, set()):
        raise HTTPException(403, f"A {user.role.replace('_', ' ')} cannot assign work to a {assignee.role}")
    t = Task(store_id=store_id, assigned_by_id=user.id, **data.model_dump())
    db.add(t)
    db.flush()
    notify(db, assignee.id, "task", f"New task: {t.title}", f"Priority {t.priority}. From {user.full_name}",
           link=f"/tasks/{t.id}")
    db.commit()
    hub.publish(f"store:{store_id}", "task", {"task_id": t.id, "status": t.status})
    return task_dict(t, db)


@router.post("/tasks/{task_id}/review")
def review_task(store_id: int, task_id: int, data: TaskReviewIn, user: User = Depends(require_roles(*SUPERVISORS)),
                db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    t = db.get(Task, task_id)
    if not t or t.store_id != store_id:
        raise HTTPException(404, "Task not found")
    if t.status != TaskStatus.DONE.value:
        raise HTTPException(409, "Only completed tasks can be reviewed")
    t.status, t.manager_rating, t.manager_feedback = TaskStatus.REVIEWED.value, data.rating, data.feedback
    notify(db, t.assigned_to_id, "task", f"Your work was reviewed: {t.title}", f"{'★' * data.rating} {data.feedback}")
    db.commit()
    return task_dict(t, db)


@me_router.get("/tasks")
def my_tasks(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.query(Task).filter_by(assigned_to_id=user.id).order_by(Task.status, Task.id.desc()).limit(200)
    return [task_dict(t, db) for t in rows]


@me_router.post("/tasks/{task_id}")
def progress_task(task_id: int, data: TaskProgressIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t or t.assigned_to_id != user.id:
        raise HTTPException(404, "Task not found")
    if t.status == TaskStatus.REVIEWED.value:
        raise HTTPException(409, "Task already reviewed")
    if data.status == "done":
        if not (data.completion_note or "").strip():
            raise HTTPException(400, "Please leave a short note describing the work done")
        t.completion_note, t.completed_at = data.completion_note, utcnow()
        notify(db, t.assigned_by_id, "task", f"Task completed: {t.title}",
               f"{user.full_name}: {data.completion_note}", link="/tasks")
    t.status = data.status
    db.commit()
    hub.publish(f"store:{t.store_id}", "task", {"task_id": t.id, "status": t.status})
    return task_dict(t, db)


# ---- Shifts ------------------------------------------------------------------------
def shift_dict(s: Shift, names: dict[int, str]) -> dict:
    return {"id": s.id, "user_id": s.user_id, "name": names.get(s.user_id, ""), "starts_at": s.starts_at,
            "ends_at": s.ends_at, "label": s.label,
            "hours": round((s.ends_at - s.starts_at).total_seconds() / 3600, 2)}


@router.get("/shifts")
def shifts(store_id: int, start: date | None = None, days: int = 7, user: User = Depends(staff),
           db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    start = start or utcnow().date()
    s_dt = datetime.combine(start, datetime.min.time())
    q = db.query(Shift).filter(Shift.store_id == store_id, Shift.starts_at >= s_dt,
                               Shift.starts_at < s_dt + timedelta(days=days))
    if user.role == Role.WORKER.value:
        q = q.filter(Shift.user_id == user.id)
    names = {u.id: u.full_name for u in db.query(User).filter_by(store_id=store_id)}
    return [shift_dict(s, names) for s in q.order_by(Shift.starts_at)]


@router.post("/shifts", status_code=201)
def create_shift(store_id: int, data: ShiftIn, user: User = Depends(require_roles(*MANAGERS)),
                 db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    emp = db.get(User, data.user_id)
    if not emp or emp.store_id != store_id:
        raise HTTPException(404, "Employee not found in this store")
    if data.ends_at <= data.starts_at:
        raise HTTPException(400, "Shift must end after it starts")
    clash = db.query(Shift).filter(Shift.user_id == emp.id, Shift.starts_at < data.ends_at,
                                   Shift.ends_at > data.starts_at).first()
    if clash:
        raise HTTPException(409, "This employee already has an overlapping shift")
    s = Shift(store_id=store_id, created_by_id=user.id, **data.model_dump())
    db.add(s)
    notify(db, emp.id, "shift", "New shift assigned",
           f"{data.label or 'Shift'}: {data.starts_at:%a %d %b, %I:%M %p} – {data.ends_at:%I:%M %p}")
    db.commit()
    return shift_dict(s, {emp.id: emp.full_name})


@router.delete("/shifts/{shift_id}", status_code=204)
def delete_shift(store_id: int, shift_id: int, user: User = Depends(require_roles(*MANAGERS)),
                 db: Session = Depends(get_db)):
    ensure_store_access(user, store_id)
    s = db.get(Shift, shift_id)
    if not s or s.store_id != store_id:
        raise HTTPException(404, "Shift not found")
    db.delete(s)
    db.commit()


# ---- Attendance --------------------------------------------------------------------
@router.get("/attendance")
def attendance(store_id: int, period: str = "week", start: date | None = None, end: date | None = None,
               user: User = Depends(require_roles(*SUPERVISORS)), db: Session = Depends(get_db)):
    """Who came to work, when they clocked in/out, hours and days present."""
    ensure_store_access(user, store_id)
    s, e = resolve_range(period, start, end)
    names = {u.id: u.full_name for u in db.query(User).filter_by(store_id=store_id)}
    log = (db.query(Attendance).filter(Attendance.store_id == store_id, Attendance.clock_in >= s,
                                       Attendance.clock_in <= e).order_by(Attendance.clock_in.desc()).all())
    return {"summary": staff_hours(db, store_id, s, e),
            "log": [{"id": a.id, "user_id": a.user_id, "name": names.get(a.user_id, ""), "clock_in": a.clock_in,
                     "clock_out": a.clock_out, "hours": a.hours} for a in log]}


@me_router.get("/attendance")
def my_attendance(user: User = Depends(staff), db: Session = Depends(get_db)):
    open_rec = db.query(Attendance).filter_by(user_id=user.id, clock_out=None).first()
    recent = db.query(Attendance).filter_by(user_id=user.id).order_by(Attendance.id.desc()).limit(14).all()
    return {"on_clock": bool(open_rec), "since": open_rec.clock_in if open_rec else None,
            "recent": [{"clock_in": a.clock_in, "clock_out": a.clock_out, "hours": a.hours} for a in recent]}


@me_router.post("/clock")
def clock(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Toggle clock-in / clock-out."""
    open_rec = db.query(Attendance).filter_by(user_id=user.id, clock_out=None).first()
    if open_rec:
        open_rec.clock_out = utcnow()
        action = "clocked_out"
    else:
        db.add(Attendance(user_id=user.id, store_id=user.store_id, clock_in=utcnow()))
        action = "clocked_in"
    db.commit()
    hub.publish(f"store:{user.store_id}", "attendance", {"user_id": user.id, "name": user.full_name, "action": action})
    return {"action": action}


@me_router.get("/shifts")
def my_shifts(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.query(Shift).filter(Shift.user_id == user.id, Shift.ends_at >= utcnow()).order_by(Shift.starts_at).limit(20)
    return [shift_dict(s, {user.id: user.full_name}) for s in rows]


_ = get_current_user
