import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, precision_score, recall_score
from sqlalchemy.orm import Session
from ..models import WorkSession
from .features import outcome_score, chronological_session_rows
from .recommender import MIN_TRAINING_EXAMPLES, build_pipeline

def evaluate(db: Session) -> dict:
    sessions = db.query(WorkSession).order_by(WorkSession.created_at).all()
    n = len(sessions)
    if n < MIN_TRAINING_EXAMPLES + 3:
        return {"available": False, "reason": f"Need at least {MIN_TRAINING_EXAMPLES + 3} sessions for chronological evaluation", "training_examples": n}
    split = max(MIN_TRAINING_EXAMPLES, int(n * .75))
    train, test = sessions[:split], sessions[split:]
    all_rows = chronological_session_rows(sessions)
    model = build_pipeline(min(7, len(train)))
    model.fit(pd.DataFrame(all_rows[:split]), [outcome_score(x) for x in train])
    predicted = model.predict(pd.DataFrame(all_rows[split:]))
    targets = [outcome_score(x) for x in test]
    actual_complete = [x.completed and x.actual_minutes <= x.available_minutes for x in test]
    pred_complete = [p >= .65 for p in predicted]
    return {"available": True, "training_examples": len(train), "test_examples": len(test),
            "knn_mae": round(float(mean_absolute_error(targets, predicted)), 4),
            "completion_accuracy": round(float(accuracy_score(actual_complete, pred_complete)), 4),
            "completion_precision": round(float(precision_score(actual_complete, pred_complete, zero_division=0)), 4),
            "completion_recall": round(float(recall_score(actual_complete, pred_complete, zero_division=0)), 4),
            "completion_f1": round(float(f1_score(actual_complete, pred_complete, zero_division=0)), 4),
            "note": "Chronological holdout only; observational sessions do not establish causation."}
