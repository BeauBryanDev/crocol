import hashlib
import hmac
import json

MIN_KEY_BYTES = 32
CLOCK_SKEW_S = 300


def canonical(record: dict) -> bytes:
    """Stable bytes of a record without its signature (ASCII-escaped)."""
    body = {key: value for key, value in record.items() if key != "sig"}

    return json.dumps(body, sort_keys=True, 
                      ensure_ascii=True,
                      separators=(",", ":")).encode("ascii")


def record_ts(record: dict) -> int:

    return record["ts"]


class MemorySigner:
    """HMAC-SHA256 over memory records the browser keeps between turns."""

    def __init__(self, key: bytes, max_age_s: int) -> None:
        if len(key) < MIN_KEY_BYTES:
            raise ValueError("memory key too short")
        self._key = key
        self._max_age_s = max_age_s

    def digest(self, record: dict) -> str:

        return hmac.new(self._key, canonical(record),
                        hashlib.sha256).hexdigest()

    def sign(self, record: dict) -> dict:

        return {**record, "sig": self.digest(record)}

    def valid(self, record: dict, now: int) -> bool:
        """Untampered and fresh; anything else is dropped, never trusted."""
        sig = record.get("sig")
        ts = record.get("ts")
        if not isinstance(sig, str) or not isinstance(ts, int):
            return False
        if ts > now + CLOCK_SKEW_S or now - ts > self._max_age_s:
            return False

        return hmac.compare_digest(sig, self.digest(record))

    def verified(self, records: list[dict], now: int,
                 keep: int) -> list[dict]:
        """The newest `keep` valid records, oldest first, without sig."""
        kept = []
        for record in records:
            if self.valid(record, now):
                kept.append({k: v for k, v in record.items() if k != "sig"})

        kept.sort(key=record_ts)
        return kept[-keep:] if keep > 0 else []
