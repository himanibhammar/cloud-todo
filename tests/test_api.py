"""
Comprehensive test suite for the Cloud To-Do REST API.

Covers:
  - Health endpoint
  - Task list (empty and populated)
  - Creating tasks (valid, blank title, malformed JSON)
  - Updating tasks (toggle completion, update title/description)
  - Deleting tasks
  - 404 handling for missing task IDs
  - Confirmed deletion (task no longer returned)
  - Input length limits
"""

import json
import pytest


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def post_task(client, title="Test Task", description=""):
    return client.post(
        "/api/tasks",
        data=json.dumps({"title": title, "description": description}),
        content_type="application/json",
    )


def get_tasks(client):
    return client.get("/api/tasks")


# ═════════════════════════════════════════════════════════════════════════════
# 1. Health endpoint
# ═════════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health_returns_200(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200

    def test_health_json_shape(self, client):
        res = client.get("/api/health")
        data = res.get_json()
        assert "status" in data
        assert "database" in data

    def test_health_status_is_healthy(self, client):
        res = client.get("/api/health")
        data = res.get_json()
        assert data["status"] == "healthy"
        assert data["database"] is True


# ═════════════════════════════════════════════════════════════════════════════
# 2. List tasks
# ═════════════════════════════════════════════════════════════════════════════

class TestListTasks:
    def test_empty_task_list_returns_200(self, client):
        res = get_tasks(client)
        assert res.status_code == 200

    def test_empty_task_list_is_array(self, client):
        res = get_tasks(client)
        assert isinstance(res.get_json(), list)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Create tasks
# ═════════════════════════════════════════════════════════════════════════════

class TestCreateTask:
    def test_create_valid_task_returns_201(self, client):
        res = post_task(client, title="Buy groceries", description="Milk and eggs")
        assert res.status_code == 201

    def test_created_task_has_required_fields(self, client):
        res = post_task(client, title="Walk the dog")
        data = res.get_json()
        for field in ("id", "title", "description", "completed", "created_at", "updated_at"):
            assert field in data, f"Missing field: {field}"

    def test_created_task_title_matches(self, client):
        title = "Read a book"
        res = post_task(client, title=title)
        assert res.get_json()["title"] == title

    def test_created_task_is_not_completed(self, client):
        res = post_task(client, title="New task")
        assert res.get_json()["completed"] is False

    def test_create_task_without_description(self, client):
        res = client.post(
            "/api/tasks",
            data=json.dumps({"title": "No description"}),
            content_type="application/json",
        )
        assert res.status_code == 201
        assert res.get_json()["description"] == ""

    def test_create_task_with_description(self, client):
        res = post_task(client, title="With desc", description="Some detail")
        assert res.get_json()["description"] == "Some detail"

    def test_reject_empty_title(self, client):
        res = post_task(client, title="")
        assert res.status_code == 400

    def test_reject_whitespace_title(self, client):
        res = post_task(client, title="   ")
        assert res.status_code == 400

    def test_reject_missing_title_field(self, client):
        res = client.post(
            "/api/tasks",
            data=json.dumps({"description": "no title here"}),
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_reject_malformed_json(self, client):
        res = client.post(
            "/api/tasks",
            data="{bad json!!}",
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_reject_non_json_content_type(self, client):
        res = client.post(
            "/api/tasks",
            data="title=Hello",
            content_type="application/x-www-form-urlencoded",
        )
        assert res.status_code == 400

    def test_reject_title_too_long(self, client):
        res = post_task(client, title="A" * 201)
        assert res.status_code == 400

    def test_reject_description_too_long(self, client):
        res = post_task(client, title="Title", description="D" * 1001)
        assert res.status_code == 400

    def test_title_is_stripped(self, client):
        res = post_task(client, title="  Trimmed  ")
        assert res.get_json()["title"] == "Trimmed"


# ═════════════════════════════════════════════════════════════════════════════
# 4. Retrieve created tasks
# ═════════════════════════════════════════════════════════════════════════════

class TestRetrieveTasks:
    def test_created_task_appears_in_list(self, client):
        unique_title = "Unique task for retrieval test"
        post_task(client, title=unique_title)
        tasks = get_tasks(client).get_json()
        titles = [t["title"] for t in tasks]
        assert unique_title in titles

    def test_tasks_list_contains_all_required_fields(self, client):
        post_task(client, title="Field check task")
        tasks = get_tasks(client).get_json()
        assert len(tasks) > 0
        for field in ("id", "title", "description", "completed", "created_at", "updated_at"):
            assert field in tasks[0]

    def test_newest_task_is_first(self, client):
        post_task(client, title="Older task")
        post_task(client, title="Newer task")
        tasks = get_tasks(client).get_json()
        # The first element should have a >= created_at than the second
        assert tasks[0]["created_at"] >= tasks[1]["created_at"]


# ═════════════════════════════════════════════════════════════════════════════
# 5. Update tasks
# ═════════════════════════════════════════════════════════════════════════════

class TestUpdateTask:
    def _create(self, client, title="Update me"):
        return post_task(client, title=title).get_json()["id"]

    def test_mark_completed(self, client):
        tid = self._create(client)
        res = client.patch(
            f"/api/tasks/{tid}",
            data=json.dumps({"completed": True}),
            content_type="application/json",
        )
        assert res.status_code == 200
        assert res.get_json()["completed"] is True

    def test_mark_pending(self, client):
        tid = self._create(client, title="Complete then reopen")
        client.patch(f"/api/tasks/{tid}", data=json.dumps({"completed": True}), content_type="application/json")
        res = client.patch(f"/api/tasks/{tid}", data=json.dumps({"completed": False}), content_type="application/json")
        assert res.status_code == 200
        assert res.get_json()["completed"] is False

    def test_update_title(self, client):
        tid = self._create(client, title="Old title")
        res = client.patch(
            f"/api/tasks/{tid}",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
        )
        assert res.status_code == 200
        assert res.get_json()["title"] == "New title"

    def test_update_description(self, client):
        tid = self._create(client)
        res = client.patch(
            f"/api/tasks/{tid}",
            data=json.dumps({"description": "Updated desc"}),
            content_type="application/json",
        )
        assert res.status_code == 200
        assert res.get_json()["description"] == "Updated desc"

    def test_reject_unknown_fields(self, client):
        tid = self._create(client)
        res = client.patch(
            f"/api/tasks/{tid}",
            data=json.dumps({"priority": "high"}),
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_reject_non_boolean_completed(self, client):
        tid = self._create(client)
        res = client.patch(
            f"/api/tasks/{tid}",
            data=json.dumps({"completed": "yes"}),
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_reject_blank_title_update(self, client):
        tid = self._create(client)
        res = client.patch(
            f"/api/tasks/{tid}",
            data=json.dumps({"title": ""}),
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_update_nonexistent_task_returns_404(self, client):
        res = client.patch(
            "/api/tasks/999999",
            data=json.dumps({"completed": True}),
            content_type="application/json",
        )
        assert res.status_code == 404

    def test_updated_at_changes_after_update(self, client):
        tid = self._create(client, title="Timestamp test")
        original = client.get(f"/api/tasks").get_json()
        orig_updated = next((t["updated_at"] for t in original if t["id"] == tid), None)

        import time; time.sleep(1)  # ensure at least 1 second passes
        client.patch(f"/api/tasks/{tid}", data=json.dumps({"completed": True}), content_type="application/json")

        tasks = client.get("/api/tasks").get_json()
        new_updated = next((t["updated_at"] for t in tasks if t["id"] == tid), None)
        assert new_updated >= orig_updated


# ═════════════════════════════════════════════════════════════════════════════
# 6. Delete tasks
# ═════════════════════════════════════════════════════════════════════════════

class TestDeleteTask:
    def _create(self, client, title="Delete me"):
        return post_task(client, title=title).get_json()["id"]

    def test_delete_returns_200(self, client):
        tid = self._create(client)
        res = client.delete(f"/api/tasks/{tid}")
        assert res.status_code == 200

    def test_deleted_task_not_in_list(self, client):
        tid = self._create(client, title="Gone task")
        client.delete(f"/api/tasks/{tid}")
        tasks = get_tasks(client).get_json()
        assert not any(t["id"] == tid for t in tasks)

    def test_delete_nonexistent_task_returns_404(self, client):
        res = client.delete("/api/tasks/888888")
        assert res.status_code == 404

    def test_delete_response_has_message(self, client):
        tid = self._create(client)
        res = client.delete(f"/api/tasks/{tid}")
        data = res.get_json()
        assert "message" in data


# ═════════════════════════════════════════════════════════════════════════════
# 7. Edge cases and error handling
# ═════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_unknown_api_endpoint_returns_404(self, client):
        res = client.get("/api/nonexistent")
        assert res.status_code == 404

    def test_wrong_method_returns_405(self, client):
        res = client.put("/api/tasks")
        assert res.status_code == 405

    def test_patch_with_empty_body_returns_400(self, client):
        # Create a task first
        tid = post_task(client, title="Empty patch test").get_json()["id"]
        res = client.patch(
            f"/api/tasks/{tid}",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert res.status_code == 400
