import push_service as p

print("HAS_VAPID", p.HAS_VAPID, "| HAS_WEBPUSH", p.HAS_WEBPUSH)
pub = p.get_vapid_public_key()
print("pub b64 len", len(pub))

v = p.get_vapid_instance()
print("inst", type(v).__name__)

sub = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/fake-token",
    "keys": {
        "p256dh": "BElg0RJuY8QJy3Bz3Wm2Z9z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8x8y8z8",
        "auth": "x8y8z8x8y8z8x8y8z8x8y8z8",
    },
}

try:
    from pywebpush import webpush
    result = webpush(
        subscription_info=sub,
        data="test",
        vapid_private_key=v,
        vapid_claims={"sub": "mailto:admin@meshcollege.ru"},
        content_encoding="aes128gcm",
        curl=True,
    )
    print("CURL-OK, contains Authorization:", "Authorization" in str(result))
except Exception as exc:
    print("ERR:", type(exc).__name__, str(exc)[:200])
