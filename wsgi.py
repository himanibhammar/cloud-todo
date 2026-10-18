"""
WSGI entry-point for Gunicorn.

Usage (development):
    flask --app wsgi:app run --port 5000

Usage (production via Gunicorn):
    gunicorn --bind 0.0.0.0:5000 wsgi:app
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
