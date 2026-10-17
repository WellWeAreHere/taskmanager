from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..models import Task, WorkSession

NUMERIC_FEATURES = ["available_minutes", "estimated_total_minutes", "remaining_minutes", "priority", "deadline_urgency", "time_to_remaining_ratio", "category_history_outcome"]
CATEGORICAL_FEATURES = ["category"]

def deadline_urgency(deadline: datetime | None, now: datetime | None = None) -> float:
    if not deadline: return 0.0
    now = now or datetime.utcnow()
    hours = (deadline.replace(tzinfo=None) - now.replace(tzinfo=None)).total_seconds() / 3600
    if hours <= 0: return 1.0
    return round(min(1.0, 72 / (hours + 72)), 4)

def outcome_score(session: WorkSession) -> float:
    """Outcome score: weighted completion, progress, time fit, estimate realism (0..1)."""
    completion = 1.0 if session.completed else 0.0
    time_fit = 1.0 if session.actual_minutes <= session.available_minutes else max(0.0, session.available_minutes / session.actual_minutes)
    expected_progress = min(1.0, session.actual_minutes / max(1, session.remaining_minutes_at_start))
    realism = max(0.0, 1 - abs(session.progress_fraction - expected_progress))
    return round(min(1.0, 0.40 * completion + 0.35 * session.progress_fraction + 0.15 * time_fit + 0.10 * realism), 4)

def category_history_outcome(db: Session, category: str) -> float:
    sessions = db.query(WorkSession).filter(WorkSession.category_at_start == category).all()
    return sum(outcome_score(s) for s in sessions) / len(sessions) if sessions else 0.5

def task_feature_row(db: Session, task: Task, available_minutes: int) -> dict:
    return {"available_minutes": available_minutes, "estimated_total_minutes": task.estimated_total_minutes, "remaining_minutes": task.remaining_minutes,
            "priority": task.priority, "deadline_urgency": deadline_urgency(task.deadline),
            "time_to_remaining_ratio": min(5.0, available_minutes / max(1, task.remaining_minutes)),
            "category_history_outcome": category_history_outcome(db, task.category), "category": task.category}

def session_feature_row(db: Session, session: WorkSession) -> dict:
    return {"available_minutes": session.available_minutes, "estimated_total_minutes": session.estimated_total_minutes_at_start, "remaining_minutes": session.remaining_minutes_at_start,
            "priority": session.priority_at_start, "deadline_urgency": session.deadline_urgency_at_start,
            "time_to_remaining_ratio": min(5.0, session.available_minutes / max(1, session.remaining_minutes_at_start)),
            "category_history_outcome": category_history_outcome(db, session.category_at_start), "category": session.category_at_start}

def chronological_session_rows(sessions: list[WorkSession]) -> list[dict]:
    """Build history features without using the current or any future outcome."""
    category_scores: dict[str, list[float]] = {}
    rows = []
    for session in sessions:
        prior = category_scores.get(session.category_at_start, [])
        history = sum(prior) / len(prior) if prior else 0.5
        rows.append({"available_minutes": session.available_minutes, "estimated_total_minutes": session.estimated_total_minutes_at_start, "remaining_minutes": session.remaining_minutes_at_start,
            "priority": session.priority_at_start, "deadline_urgency": session.deadline_urgency_at_start,
            "time_to_remaining_ratio": min(5.0, session.available_minutes / max(1, session.remaining_minutes_at_start)),
            "category_history_outcome": history, "category": session.category_at_start})
        category_scores.setdefault(session.category_at_start, []).append(outcome_score(session))
    return rows
