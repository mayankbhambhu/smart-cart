from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import MANAGERS, ensure_store_access, require_roles
from app.models import User
from app.services.analytics import resolve_range, staff_hours, store_report

router = APIRouter(prefix="/ops/stores/{store_id}/analytics", tags=["business analytics"])


@router.get("")
def analytics(store_id: int, period: str = "today", start: date | None = None, end: date | None = None,
              user: User = Depends(require_roles(*MANAGERS)), db: Session = Depends(get_db)):
    """period = today | week | month | year | custom (with start & end)."""
    ensure_store_access(user, store_id)
    s, e = resolve_range(period, start, end)
    report = store_report(db, store_id, s, e)
    hours = staff_hours(db, store_id, s, e)
    report["labour"] = {"hours": round(sum(h["hours"] for h in hours), 1),
                        "cost": round(sum(h["earned"] for h in hours), 2)}
    report["kpis"]["profit_after_labour"] = round(report["kpis"]["gross_profit"] - report["labour"]["cost"], 2)
    return report
