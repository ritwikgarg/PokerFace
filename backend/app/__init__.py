from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

import logging
import os
import sys

# Configure logging early so all modules pick it up.
# force=True ensures it overrides any prior config (e.g. gunicorn/eventlet).
# Stream to stdout so Render captures logs.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
# Also ensure the root logger flushes immediately
for handler in logging.root.handlers:
    if hasattr(handler, 'stream'):
        handler.stream = sys.stdout

socketio = SocketIO()


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.config.from_object("app.config.Config")

    async_mode = "eventlet" if os.environ.get("RENDER") else "threading"
    socketio.init_app(app, cors_allowed_origins="*", async_mode=async_mode)

    from app.routes.agents import agents_bp
    from app.routes.models import models_bp
    from app.routes.matches import matches_bp
    from app.routes.leaderboard import leaderboard_bp
    from app.routes.game import game_bp
    from app.routes.tables import tables_bp
    from app.routes.rooms import rooms_bp

    app.register_blueprint(agents_bp, url_prefix="/api")
    app.register_blueprint(models_bp, url_prefix="/api")
    app.register_blueprint(matches_bp, url_prefix="/api")
    app.register_blueprint(leaderboard_bp, url_prefix="/api")
    app.register_blueprint(game_bp, url_prefix="/api")
    app.register_blueprint(tables_bp, url_prefix="/api")
    app.register_blueprint(rooms_bp, url_prefix="/api")

    from app.sockets.table_namespace import register_socket_events
    from app.routes.tables import get_table_store

    class TableManager:
        def get(self, table_id):
            return get_table_store().get(table_id)

    register_socket_events(socketio, TableManager())

    @app.route("/api/health")
    def health():
        from app.services.modal_workers import health_check
        from app.services.supermemory import status as supermemory_status
        return {
            "status": "ok",
            "workers": health_check(),
            "supermemory": supermemory_status(),
        }

    @app.route("/api/modal-test")
    def modal_test():
        """Smoke test: verify Modal auth + connectivity by calling Mistral 7B."""
        import time as _time
        try:
            import modal
        except ImportError:
            return {"ok": False, "error": "modal package not installed"}, 500
        try:
            t0 = _time.perf_counter()
            cls = modal.Cls.from_name("agent-poker-inference", "InferL4")
            result = cls().infer.remote(
                hf_repo_id="mistralai/Mistral-7B-Instruct-v0.3",
                messages=[
                    {"role": "system", "content": "Reply with exactly: PONG"},
                    {"role": "user", "content": "PING"},
                ],
                temperature=0.01,
                max_tokens=16,
            )
            latency = round((_time.perf_counter() - t0) * 1000)
            return {
                "ok": True,
                "latency_ms": latency,
                "raw_response": result.get("raw_response", ""),
                "tokens_used": result.get("tokens_used", 0),
            }
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {str(e)}"}, 500

    return app
