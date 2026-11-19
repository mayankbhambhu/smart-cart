import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import Timestamped


class CredentialStatus(str, enum.Enum):
    PENDING_OWNER = "pending_owner"  # raised by store manager, waiting for owner
    PENDING_ADMIN = "pending_admin"  # owner approved, waiting for platform admin
    CHANGES_REQUESTED = "changes_requested"  # sent back to the manager
    APPROVED = "approved"  # admin issued credentials
    REJECTED = "rejected"


class CredentialRequest(Timestamped, Base):
    """New-employee onboarding: Store Manager -> Owner -> Admin -> account issued."""

    __tablename__ = "credential_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(20))  # worker|floor_manager|store_manager
    hourly_wage: Mapped[float] = mapped_column(Float)
    joining_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[str] = mapped_column(String(20), default=CredentialStatus.PENDING_OWNER, index=True)
    sent_back_by: Mapped[str | None] = mapped_column(String(10))  # owner|admin
    owner_note: Mapped[str | None] = mapped_column(Text)
    admin_note: Mapped[str | None] = mapped_column(Text)
    owner_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    admin_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class TaskStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    DONE = "done"  # worker finished and left a completion note
    REVIEWED = "reviewed"  # manager reviewed/rated the work


class Task(Timestamped, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10), default="normal")  # low|normal|high|urgent
    assigned_to_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(15), default=TaskStatus.ASSIGNED, index=True)
    completion_note: Mapped[str | None] = mapped_column(Text)  # the worker's report when done
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    manager_rating: Mapped[int | None] = mapped_column(Integer)  # 1-5
    manager_feedback: Mapped[str | None] = mapped_column(Text)


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    label: Mapped[str] = mapped_column(String(40), default="")  # Morning / Evening / Night
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    clock_in: Mapped[datetime] = mapped_column(DateTime, index=True)
    clock_out: Mapped[datetime | None] = mapped_column(DateTime)

    @property
    def hours(self) -> float:
        if not self.clock_out:
            return 0.0
        return round((self.clock_out - self.clock_in).total_seconds() / 3600, 2)
