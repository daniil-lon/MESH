import os
import json
import base64
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
_KEYS_DIR = Path(os.getenv("MESH_KEYS_DIR") or BASE_DIR)
_KEYS_DIR.mkdir(parents=True, exist_ok=True)
KEYS_FILE = _KEYS_DIR / "vapid_keys.json"
SUBS_FILE = _KEYS_DIR / "subscriptions.json"

try:
    from py_vapid import Vapid02 as _V2
    HAS_VAPID = True
except ImportError:
    HAS_VAPID = False

try:
    from cryptography.hazmat.primitives import serialization as _ser
    HAS_SER = True
except ImportError:
    HAS_SER = False

try:
    from pywebpush import webpush, WebPushException
    HAS_WEBPUSH = True
except ImportError:
    HAS_WEBPUSH = False

_vapid_obj = None
_vapid_public_b64url = ""
_subscriptions = set()


def _pub_b64url(v) -> str:
    raw = v.public_key.public_bytes(
        _ser.Encoding.X962, _ser.PublicFormat.UncompressedPoint
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _priv_pem(v) -> str:
    return v.private_key.private_bytes(
        _ser.Encoding.PEM, _ser.PrivateFormat.PKCS8, _ser.NoEncryption()
    ).decode()


def _get_obj():
    global _vapid_obj, _vapid_public_b64url
    if _vapid_obj is not None:
        return _vapid_obj
    if not HAS_VAPID or not HAS_SER:
        return None

    env_priv = os.getenv("VAPID_PRIVATE_PEM")
    env_pub = os.getenv("VAPID_PUBLIC_B64URL")
    if env_priv and env_pub:
        try:
            v = _V2.from_pem(env_priv.encode())
            _vapid_obj, _vapid_public_b64url = v, env_pub
            return v
        except Exception:
            pass

    if KEYS_FILE.exists():
        try:
            data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
            priv, pub = data.get("private_pem"), data.get("public_b64url")
            if priv and pub:
                v = _V2.from_pem(priv.encode())
                _vapid_obj, _vapid_public_b64url = v, pub
                return v
        except Exception:
            pass

    v = _V2()
    v.generate_keys()
    _vapid_obj = v
    _vapid_public_b64url = _pub_b64url(v)
    try:
        KEYS_FILE.write_text(
            json.dumps(
                {"private_pem": _priv_pem(v), "public_b64url": _vapid_public_b64url},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    return v


def get_vapid_public_key() -> str:
    if not HAS_VAPID or not HAS_SER:
        return ""
    if _vapid_obj is None:
        _get_obj()
    return _vapid_public_b64url or ""


def get_vapid_instance():
    if not HAS_VAPID or not HAS_SER:
        return None
    if _vapid_obj is None:
        _get_obj()
    return _vapid_obj


def get_vapid_private_pem() -> str:
    v = get_vapid_instance()
    if v is None:
        return ""
    return _priv_pem(v)


def _load_subs():
    if _subscriptions or not SUBS_FILE.exists():
        return
    try:
        for item in json.loads(SUBS_FILE.read_text(encoding="utf-8")):
            _subscriptions.add(json.dumps(item, sort_keys=True))
    except Exception:
        pass


def _save_subs():
    try:
        SUBS_FILE.write_text(
            json.dumps(
                [json.loads(s) for s in _subscriptions], ensure_ascii=False
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def add_subscription(subscription: dict, user: str = ""):
    _load_subs()
    entry = {
        "login": user,
        "sub": subscription,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    key = json.dumps(entry, sort_keys=True)
    if key in _subscriptions:
        return
    _subscriptions.add(key)
    _save_subs()


def remove_subscription(subscription: dict):
    _load_subs()
    ec = json.dumps({"login": "", "sub": subscription}, sort_keys=True)
    for key in list(_subscriptions):
        try:
            item = json.loads(key)
            if json.dumps(item.get("sub"), sort_keys=True) == json.dumps(subscription, sort_keys=True):
                _subscriptions.discard(key)
        except Exception:
            continue
    _save_subs()


def list_subscriptions():
    _load_subs()
    return [json.loads(s) for s in _subscriptions]


def remove_user_subscriptions(user: str):
    _load_subs()
    removed = 0
    for key in list(_subscriptions):
        try:
            item = json.loads(key)
            if item.get("login") == user:
                _subscriptions.discard(key)
                removed += 1
        except Exception:
            continue
    if removed:
        _save_subs()
    return removed


def send_push(payload: dict, ttl: int = 3600, user: str = ""):
    v = get_vapid_instance()
    if v is None or not HAS_WEBPUSH:
        return {"ok": False, "sent": 0, "failed": 0, "error": "WebPush не настроен"}

    subject = os.getenv("PUSH_SUBJECT", "mailto:admin@meshcollege.ru")
    sent = failed = 0
    for entry in list_subscriptions():
        sub = entry.get("sub")
        if not isinstance(sub, dict) or not sub.get("endpoint"):
            continue
        if user and entry.get("login") != user:
            continue
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=v,
                vapid_claims={"sub": subject},
                ttl=ttl,
            )
            sent += 1
        except WebPushException as exc:
            if getattr(exc, "response", None) is not None:
                resp = exc.response
                if resp.status_code in (404, 410):
                    remove_subscription(sub)
            failed += 1
        except Exception:
            failed += 1

    return {"ok": True, "sent": sent, "failed": failed}


send_push_to_subscriptions = send_push
