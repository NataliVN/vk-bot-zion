import secrets
import hashlib
import base64

code_verifier = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).rstrip(b'=').decode('utf-8')

print("СКОПИРУЙТЕ ЭТИ ДВЕ СТРОКИ В БЕЗОПАСНОЕ МЕСТО:")
print(f"CODE_VERIFIER: {code_verifier}")
print(f"CODE_CHALLENGE: {code_challenge}")