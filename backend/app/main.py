from datetime import datetime, date
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from .database import Base, engine, get_db
from .models import Task, WorkSession
from .schemas import *
from .ml.features import deadline_urgency
from .ml.recommender import MIN_TRAINING_EXAMPLES, recommendations
from .ml.evaluation import evaluate

Base.metadata.create_all(bind=engine)
if "recurrence_rule" not in {column["name"] for column in inspect(engine).get_columns("tasks")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE tasks ADD COLUMN recurrence_rule VARCHAR(20) NOT NULL DEFAULT 'none'"))
app = FastAPI(title="TaskManager API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def task_or_404(db: Session, task_id: int):
    task = db.get(Task, task_id)
    if not task: raise HTTPException(404, "Task not found")
    return task

def materialize_daily_tasks(db: Session):
    """Create today's instance after a daily task has been completed on an earlier day."""
    today = date.today()
    recurring = db.query(Task).filter(Task.recurrence_rule == "daily", Task.status == "completed").all()
    changed = False
    for task in recurring:
        if task.created_at.date() < today:
            already_today = db.query(Task).filter(Task.recurrence_rule == "daily", Task.title == task.title, Task.created_at >= datetime.combine(today, datetime.min.time())).first()
            if not already_today:
                db.add(Task(title=task.title, description=task.description, priority=task.priority, estimated_total_minutes=task.estimated_total_minutes, remaining_minutes=task.estimated_total_minutes, deadline=task.deadline, category=task.category, status="pending", recurrence_rule="daily"))
                changed = True
    if changed: db.commit()

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(); data["remaining_minutes"] = data["remaining_minutes"] if data["remaining_minutes"] is not None else data["estimated_total_minutes"]
    if data["status"] == "completed": data["remaining_minutes"] = 0
    task = Task(**data); db.add(task); db.commit(); db.refresh(task); return task

@app.get("/tasks", response_model=list[TaskRead])
def list_tasks(status: str | None = None, category: str | None = None, priority: int | None = Query(None, ge=1, le=5), deadline_before: datetime | None = None, db: Session = Depends(get_db)):
    materialize_daily_tasks(db)
    q = db.query(Task)
    if status: q = q.filter(Task.status == status)
    if category: q = q.filter(Task.category == category)
    if priority: q = q.filter(Task.priority == priority)
    if deadline_before: q = q.filter(Task.deadline <= deadline_before)
    return q.order_by(Task.created_at.desc()).all()

@app.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: int, db: Session = Depends(get_db)): return task_or_404(db, task_id)

@app.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = task_or_404(db, task_id)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(task, key, value)
    if task.remaining_minutes > task.estimated_total_minutes: raise HTTPException(422, "remaining_minutes cannot exceed estimated_total_minutes")
    if task.status == "completed": task.remaining_minutes = 0
    elif task.remaining_minutes == 0: task.status = "completed"
    db.commit(); db.refresh(task); return task

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db.delete(task_or_404(db, task_id)); db.commit()

@app.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    task = task_or_404(db, payload.task_id)
    if task.status == "completed": raise HTTPException(409, "Cannot record work for a completed task")
    if payload.completed and payload.remaining_minutes_after != 0: raise HTTPException(422, "Completed sessions must have zero remaining minutes")
    if payload.remaining_minutes_after > task.remaining_minutes: raise HTTPException(422, "remaining_minutes_after cannot exceed current remaining work")
    session = WorkSession(**payload.model_dump(), estimated_total_minutes_at_start=task.estimated_total_minutes, remaining_minutes_at_start=task.remaining_minutes, priority_at_start=task.priority, deadline_urgency_at_start=deadline_urgency(task.deadline), category_at_start=task.category)
    db.add(session); task.remaining_minutes = payload.remaining_minutes_after
    task.status = "completed" if payload.completed or payload.remaining_minutes_after == 0 else "in_progress"
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Duplicate session submission")
    db.refresh(session); return session

@app.get("/sessions", response_model=list[SessionRead])
def list_sessions(task_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(WorkSession)
    if task_id: q = q.filter(WorkSession.task_id == task_id)
    return q.order_by(WorkSession.created_at.desc()).all()

@app.get("/sessions/{session_id}", response_model=SessionRead)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(WorkSession, session_id)
    if not session: raise HTTPException(404, "Work session not found")
    return session

@app.post("/recommendations", response_model=RecommendationResponse)
def get_recommendations(payload: RecommendationRequest, db: Session = Depends(get_db)):
    mode, items = recommendations(db, payload.available_minutes)
    return {"available_minutes": payload.available_minutes, "mode": mode, "recommendations": items}

@app.get("/ml/status")
def ml_status(db: Session = Depends(get_db)):
    count = db.query(WorkSession).count()
    return {"mode": "knn" if count >= MIN_TRAINING_EXAMPLES else "baseline", "valid_training_examples": count, "minimum_training_examples": MIN_TRAINING_EXAMPLES, "note": "KNN uses historical outcomes; this threshold is not a reliability guarantee."}

@app.get("/ml/metrics")
def ml_metrics(db: Session = Depends(get_db)): return evaluate(db)
