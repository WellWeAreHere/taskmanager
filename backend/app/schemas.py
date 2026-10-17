from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["pending", "in_progress", "completed"]

class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: int = Field(default=3, ge=1, le=5)
    estimated_total_minutes: int = Field(gt=0, le=100000)
    remaining_minutes: int | None = Field(default=None, ge=0, le=100000)
    deadline: datetime | None = None
    category: str = Field(default="General", min_length=1, max_length=80)
    status: Status = "pending"
    parent_task_id: int | None = None
    recurrence_rule: Literal["none", "daily"] = "none"

    @model_validator(mode="after")
    def remaining_is_valid(self):
        if self.remaining_minutes is not None and self.remaining_minutes > self.estimated_total_minutes:
            raise ValueError("remaining_minutes cannot exceed estimated_total_minutes")
        return self

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: int | None = Field(default=None, ge=1, le=5)
    estimated_total_minutes: int | None = Field(default=None, gt=0, le=100000)
    remaining_minutes: int | None = Field(default=None, ge=0, le=100000)
    deadline: datetime | None = None
    category: str | None = Field(default=None, min_length=1, max_length=80)
    status: Status | None = None
    recurrence_rule: Literal["none", "daily"] | None = None

class TaskRead(TaskBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SessionCreate(BaseModel):
    task_id: int
    available_minutes: int = Field(gt=0, le=1440)
    actual_minutes: int = Field(gt=0, le=1440)
    completed: bool = False
    progress_fraction: float = Field(ge=0, le=1)
    remaining_minutes_after: int = Field(ge=0, le=100000)
    followed_recommendation: bool = False
    submission_key: str | None = Field(default=None, min_length=1, max_length=100)

class SessionRead(BaseModel):
    id: int; task_id: int; available_minutes: int; estimated_total_minutes_at_start: int
    remaining_minutes_at_start: int; priority_at_start: int; deadline_urgency_at_start: float
    category_at_start: str; actual_minutes: int; completed: bool; progress_fraction: float
    remaining_minutes_after: int; followed_recommendation: bool; created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class RecommendationRequest(BaseModel):
    available_minutes: int = Field(gt=0, le=1440)

class Recommendation(BaseModel):
    task: TaskRead
    suitability_score: float = Field(ge=0, le=1)
    recommendation_method: Literal["baseline", "knn"]
    explanation: str
    estimated_remaining_minutes: int
    expected_to_fit: bool

class RecommendationResponse(BaseModel):
    available_minutes: int
    mode: Literal["baseline", "knn"]
    recommendations: list[Recommendation]
