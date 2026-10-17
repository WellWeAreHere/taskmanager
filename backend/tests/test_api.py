from datetime import datetime, timedelta

def make_task(client, **overrides):
    payload = {"title": "Write model report", "priority": 4, "estimated_total_minutes": 90, "remaining_minutes": 90, "category": "Work"}
    payload.update(overrides)
    response = client.post("/tasks", json=payload); assert response.status_code == 201
    return response.json()

def test_task_crud_and_validation(client):
    task = make_task(client)
    assert client.get(f"/tasks/{task['id']}").json()["title"] == "Write model report"
    updated = client.patch(f"/tasks/{task['id']}", json={"remaining_minutes": 40}).json()
    assert updated["remaining_minutes"] == 40
    assert client.post("/tasks", json={"title":"Bad", "priority":9, "estimated_total_minutes":20}).status_code == 422
    assert client.delete(f"/tasks/{task['id']}").status_code == 204
    assert client.get(f"/tasks/{task['id']}").status_code == 404

def test_session_snapshots_progress_and_duplicate(client):
    task = make_task(client, deadline=(datetime.now() + timedelta(days=1)).isoformat())
    body = {"task_id": task["id"], "available_minutes": 30, "actual_minutes": 28, "progress_fraction": .4, "remaining_minutes_after": 54, "submission_key": "entry-1"}
    response = client.post("/sessions", json=body); assert response.status_code == 201
    session = response.json(); assert session["remaining_minutes_at_start"] == 90 and session["category_at_start"] == "Work"
    assert client.get(f"/tasks/{task['id']}").json()["remaining_minutes"] == 54
    assert client.post("/sessions", json=body).status_code == 409
    body["submission_key"] = "entry-2"; body["completed"] = True; body["remaining_minutes_after"] = 3
    assert client.post("/sessions", json=body).status_code == 422

def test_baseline_then_knn_and_unseen_category(client):
    task = make_task(client, category="Unseen category")
    recs = client.post("/recommendations", json={"available_minutes": 30}).json()
    assert recs["mode"] == "baseline" and recs["recommendations"][0]["task"]["id"] == task["id"]
    for index in range(10):
        created = make_task(client, title=f"task {index}", category="Study", estimated_total_minutes=60, remaining_minutes=60)
        response = client.post("/sessions", json={"task_id": created["id"], "available_minutes":30, "actual_minutes":25, "progress_fraction": .5, "remaining_minutes_after":30, "completed":False, "submission_key":f"k-{index}"})
        assert response.status_code == 201
    assert client.post("/recommendations", json={"available_minutes":30}).json()["mode"] == "knn"

def test_metrics_small_history_is_honest(client):
    assert client.get("/ml/metrics").json()["available"] is False

def test_chronological_evaluation_after_enough_history(client):
    for index in range(13):
        task = make_task(client, title=f"evaluation {index}", estimated_total_minutes=40, remaining_minutes=40)
        result = client.post("/sessions", json={"task_id": task["id"], "available_minutes": 30, "actual_minutes": 20, "progress_fraction": .5, "remaining_minutes_after": 10, "completed": False, "submission_key": f"eval-{index}"})
        assert result.status_code == 201
    metrics = client.get("/ml/metrics").json()
    assert metrics["available"] is True
    assert metrics["training_examples"] >= 10 and "knn_mae" in metrics
