import os
import sys

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _parent)
sys.path.insert(0, os.path.join(_parent, "backend"))

os.environ.setdefault("MESH_DATA_DIR", "/tmp/mesh/data")
os.environ.setdefault("MESH_UPLOADS_DIR", "/tmp/mesh/uploads")
os.environ.setdefault("MESH_KEYS_DIR", "/tmp/mesh")

for _d in ("/tmp/mesh/data", "/tmp/mesh/uploads", "/tmp/mesh"):
    os.makedirs(_d, exist_ok=True)

from a2wsgi import ASGIMiddleware
from backend.main import app

application = ASGIMiddleware(app)