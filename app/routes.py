"""
REST API routes for the Cloud To-Do application.

Endpoints
---------
GET    /api/health          – liveness / readiness probe
GET    /api/tasks           – list all tasks (newest first)
POST   /api/tasks           – create a task
PATCH  /api/tasks/<id>      – update title, description, or completed flag
DELETE /api/tasks/<id>      – delete a task
"""

import sqlite3
from flask import Blueprint, jsonify, request, current_app

from .database import get_db, utcnow

api_bp = Blueprint("api", __name__)

# ── Limits ─────────────────────────────────────────────────────────────────
MAX_TITLE_LEN = 200
MAX_DESC_LEN = 1000
ALLOWED_UPDATE_FIELDS = {"title", "description", "completed"}


# ── Helpers ─────────────────────────────────────────────────────────────────

def task_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"] or "",
        "completed": bool(row["completed"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _json_body() -> tuple[dict | None, str | None]:
    """Parse JSON body; return (data, error_message)."""
    if not request.is_json:
        return None, "Request Content-Type must be application/json"
    try:
        data = request.get_json(force=False, silent=False)
    except Exception:
        return None, "Invalid JSON in request body"
    if data is None:
        return None, "Empty or malformed JSON body"
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object"
    return data, None


# ── Health ───────────────────────────────────────────────────────────────────

@api_bp.route("/health", methods=["GET"])
def health():
    """Liveness and readiness probe."""
    db_ok = False
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
            db_ok = True
    except Exception as exc:
        current_app.logger.error("Health-check DB error: %s", exc)

    status = "healthy" if db_ok else "degraded"
    http_code = 200 if db_ok else 503
    return jsonify({"status": status, "database": db_ok}), http_code


# ── Tasks ────────────────────────────────────────────────────────────────────

@api_bp.route("/tasks", methods=["GET"])
def list_tasks():
    """Return all tasks ordered by creation date (newest first)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([task_to_dict(r) for r in rows]), 200


@api_bp.route("/tasks", methods=["POST"])
def create_task():
    """Create a new task."""
    data, err = _json_body()
    if err:
        return jsonify({"error": err}), 400

    title = data.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "Task title is required and cannot be blank"}), 400
    title = title.strip()
    if len(title) > MAX_TITLE_LEN:
        return jsonify({"error": f"Title must be {MAX_TITLE_LEN} characters or fewer"}), 400

    description = data.get("description", "") or ""
    if not isinstance(description, str):
        return jsonify({"error": "Description must be a string"}), 400
    description = description.strip()
    if len(description) > MAX_DESC_LEN:
        return jsonify({"error": f"Description must be {MAX_DESC_LEN} characters or fewer"}), 400

    now = utcnow()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, description, completed, created_at, updated_at) "
            "VALUES (?, ?, 0, ?, ?)",
            (title, description, now, now),
        )
        task_id = cur.lastrowid
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    return jsonify(task_to_dict(row)), 201


@api_bp.route("/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id: int):
    """Update title, description, and/or completed status of a task."""
    data, err = _json_body()
    if err:
        return jsonify({"error": err}), 400

    # Reject unknown fields
    unknown = set(data.keys()) - ALLOWED_UPDATE_FIELDS
    if unknown:
        return jsonify({"error": f"Unknown field(s): {', '.join(sorted(unknown))}"}), 400

    if not data:
        return jsonify({"error": "Request body must contain at least one field to update"}), 400

    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if existing is None:
            return jsonify({"error": f"Task {task_id} not found"}), 404

        # Validate and collect updates
        updates: dict = {}

        if "title" in data:
            title = data["title"]
            if not isinstance(title, str) or not title.strip():
                return jsonify({"error": "Title cannot be blank"}), 400
            title = title.strip()
            if len(title) > MAX_TITLE_LEN:
                return jsonify({"error": f"Title must be {MAX_TITLE_LEN} characters or fewer"}), 400
            updates["title"] = title

        if "description" in data:
            desc = data["description"] or ""
            if not isinstance(desc, str):
                return jsonify({"error": "Description must be a string"}), 400
            desc = desc.strip()
            if len(desc) > MAX_DESC_LEN:
                return jsonify({"error": f"Description must be {MAX_DESC_LEN} characters or fewer"}), 400
            updates["description"] = desc

        if "completed" in data:
            completed = data["completed"]
            if not isinstance(completed, bool):
                return jsonify({"error": "'completed' must be a boolean"}), 400
            updates["completed"] = int(completed)

        updates["updated_at"] = utcnow()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)  # noqa: S608
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    return jsonify(task_to_dict(row)), 200


@api_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id: int):
    """Delete a task."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if existing is None:
            return jsonify({"error": f"Task {task_id} not found"}), 404
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    return jsonify({"message": f"Task {task_id} deleted successfully"}), 200


# ── Error handlers ────────────────────────────────────────────────────────────

@api_bp.app_errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Endpoint not found"}), 404
    # Let the frontend catch-all handle non-API 404s
    return e


@api_bp.app_errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


@api_bp.app_errorhandler(413)
def request_too_large(e):
    return jsonify({"error": "Request body too large (max 1 MB)"}), 413


@api_bp.app_errorhandler(500)
def internal_error(e):
    current_app.logger.exception("Unhandled exception")
    return jsonify({"error": "An internal server error occurred"}), 500
