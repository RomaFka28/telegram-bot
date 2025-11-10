from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qsl


def parse_init_data(raw: str) -> dict:
    data = {}
    for key, value in parse_qsl(raw, keep_blank_values=True):
        data[key] = value
    return data


def verify_init_data(raw: str, bot_token: str) -> dict:
    data = parse_init_data(raw)
    if "hash" not in data:
        raise ValueError("Hash missing in init data")
    received_hash = data.pop("hash")
    check_list = [f"{k}={v}" for k, v in sorted(data.items())]
    check_string = "\n".join(check_list)
    secret_key = hashlib.sha256(f"WebAppData{bot_token}".encode()).digest()
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if calculated_hash != received_hash:
        raise ValueError("Invalid init data hash")
    # restore hash for consumers if needed
    data["hash"] = received_hash
    return data
