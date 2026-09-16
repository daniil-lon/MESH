import os
import sys
import threading
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

import backend.main as main
from a2wsgi import ASGIMiddleware


def _run_background():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.create_task(main._startup_tasks())
        loop.run_forever()
    except Exception:
        pass


threading.Thread(target=_run_background, daemon=True).start()

application = ASGIMiddleware(main.app)