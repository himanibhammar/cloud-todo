"""
Cloud To-Do Flask application factory.
"""

import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from .database import init_db
from .routes import api_bp


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder="static", static_url_path="")

    # ── Default configuration ──────────────────────────────────────────────
    app.config.from_mapping(
        DATABASE_PATH=os.environ.get(
            "DATABASE_PATH", os.path.join(os.getcwd(), "data", "tasks.db")
        ),
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,  # 1 MB request-size limit
    )

    if test_config is not None:
        app.config.update(test_config)

    # Enable CORS only when explicitly requested (for local dev without the
    # Flask static-file server).
    if os.environ.get("ENABLE_CORS", "false").lower() == "true":
        CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ── Database ───────────────────────────────────────────────────────────
    with app.app_context():
        init_db(app.config["DATABASE_PATH"])

    # ── Blueprints ─────────────────────────────────────────────────────────
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── Frontend – serve index.html for all non-API routes ─────────────────
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str):
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        if path and os.path.exists(os.path.join(static_dir, path)):
            return send_from_directory(static_dir, path)
        return send_from_directory(static_dir, "index.html")

    return app
