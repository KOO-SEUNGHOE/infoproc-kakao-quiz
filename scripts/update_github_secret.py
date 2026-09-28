"""GitHub Actions repo secret을 API로 갱신한다 (libsodium sealed box 암호화)."""
import base64

import requests
from nacl import encoding, public


def _encrypt(public_key_b64: str, secret_value: str) -> str:
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def update_secret(owner: str, repo: str, github_token: str, secret_name: str, secret_value: str):
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }
    base = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets"

    key_resp = requests.get(f"{base}/public-key", headers=headers, timeout=10)
    key_resp.raise_for_status()
    key_data = key_resp.json()

    encrypted_value = _encrypt(key_data["key"], secret_value)
    put_resp = requests.put(
        f"{base}/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_value, "key_id": key_data["key_id"]},
        timeout=10,
    )
    put_resp.raise_for_status()
