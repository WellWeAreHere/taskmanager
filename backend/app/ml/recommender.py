import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy.orm import Session
from ..models import Task, WorkSession
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, outcome_score, chronological_session_rows, task_feature_row, deadline_urgency

MIN_TRAINING_EXAMPLES = 10

def build_pipeline(n_neighbors: int) -> Pipeline:
    preprocessing = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC_FEATURES),
        ("category", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    return Pipeline([("features", preprocessing), ("model", KNeighborsRegressor(n_neighbors=n_neighbors, weights="distance"))])

def trained_model(db: Session):
    sessions = db.query(WorkSession).order_by(WorkSession.created_at).all()
    if len(sessions) < MIN_TRAINING_EXAMPLES: return None, sessions
    rows = chronological_session_rows(sessions)
    model = build_pipeline(min(7, len(rows)))
    model.fit(pd.DataFrame(rows), [outcome_score(s) for s in sessions])
    return model, sessions

def baseline_score(task: Task, minutes: int) -> tuple[float, str]:
    fits = task.remaining_minutes <= minutes
    fit_score = 1.0 if fits else max(0.25, minutes / max(1, task.remaining_minutes))
    priority = task.priority / 5
    urgency = deadline_urgency(task.deadline)
    score = min(1.0, 0.40 * fit_score + 0.30 * priority + 0.20 * urgency + 0.10 * (1 if task.remaining_minutes <= minutes * 2 else 0.4))
    detail = "fits your available time" if fits else "is suitable for a focused partial-work block"
    return round(score, 3), f"{detail}; priority {task.priority}/5" + (" and an urgent deadline" if urgency >= .5 else "")

def recommendations(db: Session, minutes: int):
    tasks = db.query(Task).filter(Task.status != "completed", Task.remaining_minutes > 0).all()
    model, sessions = trained_model(db)
    method = "knn" if model else "baseline"
    results = []
    for task in tasks:
        baseline, explanation = baseline_score(task, minutes)
        if model:
            predicted = float(model.predict(pd.DataFrame([task_feature_row(db, task, minutes)]))[0])
            score = round(min(1.0, max(0.0, .80 * predicted + .20 * baseline)), 3)
            explanation = f"KNN estimated a useful outcome from {len(sessions)} similar work sessions; {explanation}."
        else: score = baseline
        results.append({"task": task, "suitability_score": score, "recommendation_method": method,
                        "explanation": explanation, "estimated_remaining_minutes": task.remaining_minutes,
                        "expected_to_fit": task.remaining_minutes <= minutes})
    return method, sorted(results, key=lambda r: r["suitability_score"], reverse=True)[:3]
