import os

# Eventlet monkey-patching MUST happen before any other imports.
# gunicorn's eventlet worker does this too, but doing it here ensures
# it's early enough for all stdlib modules (threading, socket, etc.).
if os.environ.get("RENDER"):
    import eventlet
    eventlet.monkey_patch()

from dotenv import load_dotenv
load_dotenv()

from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=True, port=8000, allow_unsafe_werkzeug=True)
