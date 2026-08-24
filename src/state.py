from datetime import date, timedelta
import re
from pydantic import BaseModel, Field
from .location import resolve_message_location

class BookingState(BaseModel):
    destination: str | None = None
    check_in: date | None = None
    check_out: date | None = None
    adults: int | None = Field(default=None, ge=1, le=10)
    children: int = Field(default=0, ge=0, le=8)
    budget_per_night: int | None = Field(default=None, ge=0)
    preferences: list[str] = Field(default_factory=list)
    selected_property_id: str | None = None
    selected_room_id: str | None = None
    last_recommendations: list[dict] = Field(default_factory=list)
    last_next_action: str | None = None
    hold_id: str | None = None

    @property
    def guests(self):
        return (self.adults or 0) + self.children

    def update(self, message: str, today: date = date(2026, 8, 24)):
        text = message.lower()
        previous_constraints = (self.destination, self.check_in, self.check_out, self.adults, self.children, self.budget_per_night, tuple(self.preferences))
        location = resolve_message_location(message)
        if location and location["matched"]:
            self.destination = location["canonical_name"]
        adults = re.search(r"(\d+)\s*(?:people|guests?|persons?)", text)
        if adults:
            self.adults = int(adults.group(1))
        elif "2 friends and me" in text:
            self.adults, self.children = 3, 0
        elif "my wife and 2 kids" in text:
            self.adults, self.children = 1, 2
        else:
            word_adults = re.search(r"\b(one|two|three|four|five)\s+adults?\b", text)
            if word_adults:
                self.adults = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}[word_adults.group(1)]
        budget = re.search(r"(?:under|below|budget)\s*[₹r]?\s*([\d,]+)\s*(k)?", text)
        if budget:
            value = int(budget.group(1).replace(",", ""))
            self.budget_per_night = value * 1000 if budget.group(2) else value
        for preference in ("private pool", "private", "family", "sea view", "quiet"):
            if preference in text and preference not in self.preferences:
                self.preferences.append(preference)
        if "next weekend" in text:
            start = today + timedelta(days=(5 - today.weekday()) % 7)
            self.check_in, self.check_out = start, start + timedelta(days=2)
        dates = re.findall(r"20\d{2}-\d{2}-\d{2}", text)
        if len(dates) == 2:
            self.check_in = date.fromisoformat(dates[0])
            self.check_out = date.fromisoformat(dates[1])
        if "one more night" in text and self.check_out:
            self.check_out += timedelta(days=1)
        current_constraints = (self.destination, self.check_in, self.check_out, self.adults, self.children, self.budget_per_night, tuple(self.preferences))
        references_existing_room = any(
            room.get("room", "").lower() in text for room in self.last_recommendations
        )
        if current_constraints != previous_constraints and not references_existing_room:
            self.selected_property_id = None
            self.selected_room_id = None
            self.last_recommendations = []
            self.hold_id = None

def merge_state(state: BookingState, update: dict) -> BookingState:
    data = state.model_dump()
    for key, value in update.items():
        if value is None:
            continue
        if key == "preferences":
            data[key] = list(dict.fromkeys(data[key] + value))
        else:
            data[key] = value
    return BookingState(**data)
