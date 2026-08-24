import json
import re
from pathlib import Path

DESTINATIONS = json.loads(
    (Path(__file__).parent.parent / "data/destinations.json").read_text(encoding="utf-8")
)["destinations"]


def normalize_location(raw_location: str | None) -> dict:
    if not raw_location:
        return {"matched": False, "canonical_name": None, "reason": "No destination was provided."}
    normalized = re.sub(r"\s+", " ", raw_location.lower().strip())
    for destination in DESTINATIONS:
        aliases = [destination["canonical_name"].lower(), *destination["aliases"]]
        if normalized in aliases:
            return {"matched": True, "canonical_name": destination["canonical_name"], "reason": None}
    return {"matched": False, "canonical_name": None, "reason": f"No verified inventory exists for '{raw_location}'."}


def resolve_message_location(message: str) -> dict | None:
    text = re.sub(r"\s+", " ", message.lower()).strip()
    aliases = sorted(
        {alias for destination in DESTINATIONS for alias in [destination["canonical_name"].lower(), *destination["aliases"]]},
        key=len,
        reverse=True,
    )
    for alias in aliases:
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text):
            return normalize_location(alias)
    location = re.search(r"(?:in|near|at)\s+([a-z][a-z ]{2,30}?)(?:\s+for|\s+from|\s+next|\s+tomorrow|\s*$|\.)", text)
    return normalize_location(location.group(1).strip()) if location else None


def supported_destinations() -> list[str]:
    return [destination["canonical_name"] for destination in DESTINATIONS]