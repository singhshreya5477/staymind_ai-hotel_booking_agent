from datetime import datetime, timedelta, timezone
from uuid import uuid4

HOLDS: dict[str, dict] = {}


def create_hold_record(**details) -> dict:
    created_at = datetime.now(timezone.utc)
    hold = {
        "hold_id": f"HOLD-{uuid4().hex[:8].upper()}",
        **details,
        "created_at": created_at.isoformat(),
        "expires_at": (created_at + timedelta(minutes=15)).isoformat(),
        "status": "active",
    }
    HOLDS[hold["hold_id"]] = hold
    return hold


def get_hold_record(hold_id: str) -> dict | None:
    hold = HOLDS.get(hold_id)
    if hold is None:
        return None
    if datetime.now(timezone.utc) >= datetime.fromisoformat(hold["expires_at"]):
        hold["status"] = "expired"
    return hold