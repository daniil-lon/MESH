import os
import shutil
import socket
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

import webview

REMOTE_URL = os.getenv("MESH_REMOTE_URL", "https://kipitch.pythonanywhere.com")
SERVER_PORT = int(os.getenv("MESH_LOCAL_PORT", "8765"))
LOCAL_URL = "http://127.0.0.1:%d" % SERVER_PORT
APP_DIR = "MeshCollege"
_HOME = None


def _app_home():
    global _HOME
    if _HOME is None:
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_DIR
        base.mkdir(parents=True, exist_ok=True)
        _HOME = base
    return _HOME


def _bundle_root():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return Path(__file__).resolve().parent


def _log(msg):
    try:
        with open(_app_home() / "mesh_desktop.log", "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass


def _copy_tree(src, dst, ignore=None):
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True,
                        ignore=ignore or shutil.ignore_patterns("__pycache__", "*.pyc"))
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def ensure_files():
    home = _app_home()
    root = _bundle_root()
    for name in ("index.html", "admin.html", "manifest.json", "sw.js", "css", "js", "icons", "uploads"):
        s = root / name
        if s.exists():
            _copy_tree(s, home / name)
    bsrc, bdst = root / "backend", home / "backend"
    if (bsrc / "main.py").exists() and not (bdst / "main.py").exists():
        _copy_tree(bsrc, bdst, shutil.ignore_patterns("__pycache__", "*.pyc", "versions"))
    (bdst / "data").mkdir(parents=True, exist_ok=True)


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def start_local_server():
    def run():
        try:
            import uvicorn
            from backend import main as server_main
            cfg = uvicorn.Config(server_main.app, host="127.0.0.1", port=SERVER_PORT,
                                 log_level="warning", access_log=False)
            uvicorn.Server(cfg).run()
        except Exception:
            _log("server error: " + traceback.format_exc())

    t = threading.Thread(target=run, daemon=True)
    t.daemon = True
    t.start()
    return t


def check_remote(timeout=7):
    try:
        with urllib.request.urlopen(REMOTE_URL, timeout=timeout) as r:
            return 200 <= r.status < 500
    except Exception:
        return False


class Api:
    def switch_mode(self, mode):
        url = REMOTE_URL if mode == "remote" else LOCAL_URL
        try:
            webview.windows[0].load_url(url)
        except Exception:
            _log("switch error: " + traceback.format_exc())
        return url

    def reload(self):
        try:
            webview.windows[0].evaluate_js("location.reload()")
        except Exception:
            _log("reload error: " + traceback.format_exc())
        return True


TOOLBAR_JS = """
(function(){
  if (document.getElementById('_meshbar')) return;
  var bar = document.createElement('div');
  bar.id = '_meshbar';
  function mk(text, ev){
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = text;
    b.style.cssText = 'border:0;margin:0 4px;padding:4px 10px;border-radius:6px;cursor:pointer;font:12px Arial;color:#fff;background:#1a63c2;';
    b.onclick = ev;
    return b;
  }
  bar.appendChild(mk('Сайт (облако)', function(){ pywebview.api.switch_mode('remote'); }));
  bar.appendChild(mk('Локально', function(){ pywebview.api.switch_mode('local'); }));
  bar.appendChild(mk('Обновить', function(){ pywebview.api.reload(); }));
  bar.style.cssText = 'position:fixed;top:0;right:0;z-index:2147483647;display:flex;align-items:center;padding:6px;background:rgba(10,30,60,.9);border-radius:0 0 0 12px;box-shadow:0 2px 8px rgba(0,0,0,.3);';
  document.body.appendChild(bar);
})();
"""


def main():
    try:
        ensure_files()
    except Exception:
        _log("copy error: " + traceback.format_exc())
    home = _app_home()
    os.environ["MESH_BASE_DIR"] = str(home)

    try:
        root = _bundle_root()
        sys.path.insert(0, str(root))
        sys.path.insert(0, str(root / "backend"))
        import backend.main  # noqa: F401  (bundles all server dependencies)
    except Exception:
        _log("deps import error: " + traceback.format_exc())

    if not port_open(SERVER_PORT):
        try:
            start_local_server()
        except Exception:
            _log("start server error: " + traceback.format_exc())
        t0 = time.time()
        while not port_open(SERVER_PORT) and time.time() - t0 < 20:
            time.sleep(0.3)

    remote_ok = check_remote()
    url = REMOTE_URL if remote_ok else LOCAL_URL
    api = Api()

    def on_loaded(*_):
        try:
            webview.windows[0].evaluate_js(TOOLBAR_JS)
        except Exception:
            _log("inject error: " + traceback.format_exc())

    window = webview.create_window("IT Москва Колледж", url, js_api=api, min_size=(1024, 700))
    window.events.loaded += on_loaded
    if not remote_ok:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Нет доступа к Интернету.\nОткрыта локальная версия приложения.",
                                              "IT Москва Колледж", 0)
        except Exception:
            pass
    webview.start()


if __name__ == "__main__":
    main()