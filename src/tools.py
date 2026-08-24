import json
from datetime import date, timedelta
from pathlib import Path
from .hold_store import create_hold_record, get_hold_record

CATALOG = json.loads((Path(__file__).parent.parent / "data/hotels.json").read_text())
INVENTORY = json.loads((Path(__file__).parent.parent / "data/inventory.json").read_text())

def _room(room_id):
    for hotel in CATALOG:
        for room in hotel["rooms"]:
            if room["id"] == room_id:
                return hotel, room
    raise ValueError("Unknown room")

def search_properties(state):
    if not state.destination or not state.guests:
        return []
    matches = []
    for hotel in CATALOG:
        if hotel["city"].lower() != state.destination.lower():
            continue
        for room in hotel["rooms"]:
            fits_preferences = all(p in room["amenities"] or p == "private" and "villa" in room["id"] for p in state.preferences)
            if room["capacity"] >= state.guests and (not state.budget_per_night or room["rate"] <= state.budget_per_night) and fits_preferences:
                matches.append({"property_id": hotel["id"], "property": hotel["name"], "room_id": room["id"], "room": room["name"], "rate": room["rate"], "capacity": room["capacity"], "amenities": room["amenities"]})
    return matches

def check_availability(state, result):
    if state.check_out <= state.check_in or state.check_in < date(2026, 8, 24):
        raise ValueError("Dates must be future dates with checkout after check-in")
    nights = (state.check_out - state.check_in).days
    blocked = INVENTORY.get(result["room_id"], [])
    available = all((state.check_in + timedelta(days=i)).isoformat() not in blocked for i in range(nights))
    return {**result, "available": available, "nights": nights}

def calculate_price(state, result):
    nights = result["nights"]
    subtotal = result["rate"] * nights
    tax = round(subtotal * 0.12)
    return {"room_id": result["room_id"], "nightly": result["rate"], "nights": nights, "subtotal": subtotal, "add_ons": 0, "tax": tax, "total": subtotal + tax}

def get_room_details(room_id):
    hotel, room = _room(room_id)
    return {"property_id": hotel["id"], "property": hotel["name"], **room}

def get_policy(property_id, policy_type):
    for hotel in CATALOG:
        if hotel["id"] == property_id:
            return {"property_id": property_id, "type": policy_type, "value": hotel.get("policies", {}).get(policy_type, "unknown")}
    raise ValueError("Unknown property")

def create_booking_hold(state, result):
    if not result or not state.check_in or not state.check_out or not state.guests:
        raise ValueError("Booking details are incomplete")
    checked = check_availability(state, result)
    if not checked["available"]:
        raise ValueError("Room is not available for every requested night")
    return create_hold_record(
        property_id=result["property_id"], property_name=result["property"],
        room_id=result["room_id"], room_name=result["room"],
        check_in=state.check_in.isoformat(), check_out=state.check_out.isoformat(),
        guests=state.guests, total=result.get("total", calculate_price(state, checked)["total"]), currency="INR",
    )


def get_booking_hold(hold_id):
    hold = get_hold_record(hold_id)
    return {"found": False, "reason": "No booking hold was found with that ID."} if hold is None else {"found": True, **hold}
