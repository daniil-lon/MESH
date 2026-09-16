import os

os.environ.setdefault("PYTHONUNBUFFERED", "1")

from backend.main import app

application = app