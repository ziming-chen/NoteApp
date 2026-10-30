import base64, hashlib, hmac, json, sys, time

token_path, wordlist_path, out_path = sys.argv[1:4]
tok = open(token_path, encoding="utf-8-sig").read().strip()
header_b64, payload_b64, target_sig = tok.split(".")
signing_input = f"{header_b64}.{payload_b64}".encode()

def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

words = open(wordlist_path, encoding="utf-8-sig").read().split()
start = time.perf_counter()
found = None
tries = 0
for word in words:
    tries += 1
    sig = b64(hmac.new(word.encode(), signing_input, hashlib.sha256).digest())
    if hmac.compare_digest(sig, target_sig):
        found = word
        break
elapsed = time.perf_counter() - start

result = {
    "secret": found,
    "candidates_tried": tries,
    "candidates_total": len(words),
    "elapsed_seconds": round(elapsed, 6),
    "candidates_per_second": round(tries / elapsed, 1) if elapsed else None,
    "alice_header": json.loads(base64.urlsafe_b64decode(header_b64 + "=" * (-len(header_b64) % 4))),
    "alice_payload": json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4))),
}
open(out_path, "w", encoding="utf-8").write(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
sys.exit(0 if found else 1)
