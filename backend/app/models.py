from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    estimated_total_minutes: Mapped[int] = mapped_column(Integer)
    remaining_minutes: Mapped[int] = mapped_column(Integer)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(80), default="General", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    recurrence_rule: Mapped[str] = mapped_column(String(20), default="none", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sessions: Mapped[list["WorkSession"]] = relationship(back_populates="task", cascade="all, delete-orphan")

class WorkSession(Base):
    __tablename__ = "work_sessions"
    __table_args__ = (UniqueConstraint("submission_key", name="uq_session_submission_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    available_minutes: Mapped[int] = mapped_column(Integer)
    estimated_total_minutes_at_start: Mapped[int] = mapped_column(Integer)
    remaining_minutes_at_start: Mapped[int] = mapped_column(Integer)
    priority_at_start: Mapped[int] = mapped_column(Integer)
    deadline_urgency_at_start: Mapped[float] = mapped_column(Float)
    category_at_start: Mapped[str] = mapped_column(String(80))
    actual_minutes: Mapped[int] = mapped_column(Integer)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_fraction: Mapped[float] = mapped_column(Float)
    remaining_minutes_after: Mapped[int] = mapped_column(Integer)
    followed_recommendation: Mapped[bool] = mapped_column(Boolean, default=False)
    submission_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    task: Mapped[Task] = relationship(back_populates="sessions")
