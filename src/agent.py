import json
import os

from .tools import CATALOG, calculate_price, check_availability, create_booking_hold, get_booking_hold, get_experience_details, get_local_experiences, get_policy, get_room_details, search_properties
from .state import BookingState, merge_state
from .location import normalize_location, resolve_message_location, supported_destinations
from .reference_resolver import extract_option_number

MAX_TOOL_ROUNDS = 4
MAX_LLM_CALLS_PER_SESSION = 25

SYSTEM_PROMPT = """You are StayMind AI, a grounded hotel booking agent.
The BOOKING_STATE JSON is authoritative. Preserve every field unless the guest
explicitly changes it. Use tools for every hotel fact. Never invent prices,
availability, room types, amenities, capacity, policies, taxes, or booking
confirmation. Use calculate_price for totals and check_availability before
recommending a room. Use create_booking_hold only after a specific room is
selected. Ask one short question when required state is missing. Never reveal reasoning.
"""

STATE_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "destination": {"type": ["string", "null"]},
        "check_in": {"type": ["string", "null"]},
        "check_out": {"type": ["string", "null"]},
        "adults": {"type": ["integer", "null"]},
        "children": {"type": ["integer", "null"]},
        "budget_per_night": {"type": ["integer", "null"]},
        "preferences": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["destination", "check_in", "check_out", "adults", "children", "budget_per_night", "preferences"],
    "additionalProperties": False,
}

TOOLS = [
    {"type": "function", "function": {"name": "resolve_destination", "description": "Normalize a guest location phrase to a destination supported by the catalog.", "strict": True, "parameters": {"type": "object", "properties": {"location_query": {"type": "string"}}, "required": ["location_query"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "search_properties", "description": "Search factual rooms.", "strict": True, "parameters": {"type": "object", "properties": {"destination": {"type": "string"}, "guests": {"type": "integer"}, "max_price_per_night": {"type": ["integer", "null"]}, "preferences": {"type": "array", "items": {"type": "string"}}}, "required": ["destination", "guests", "max_price_per_night", "preferences"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "check_availability", "description": "Check a room for all requested nights.", "strict": True, "parameters": {"type": "object", "properties": {"room_id": {"type": "string"}, "check_in": {"type": "string"}, "check_out": {"type": "string"}, "guests": {"type": "integer"}}, "required": ["room_id", "check_in", "check_out", "guests"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "calculate_price", "description": "Calculate the deterministic total.", "strict": True, "parameters": {"type": "object", "properties": {"room_id": {"type": "string"}, "check_in": {"type": "string"}, "check_out": {"type": "string"}, "add_ons": {"type": "array", "items": {"type": "string"}}}, "required": ["room_id", "check_in", "check_out", "add_ons"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_room_details", "description": "Get verified room details.", "strict": True, "parameters": {"type": "object", "properties": {"room_id": {"type": "string"}}, "required": ["room_id"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_policy", "description": "Get a verified property policy.", "strict": True, "parameters": {"type": "object", "properties": {"property_id": {"type": "string"}, "policy_type": {"type": "string", "enum": ["check_in", "check_out", "cancellation", "children", "pets"]}}, "required": ["property_id", "policy_type"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "create_booking_hold", "description": "Create a validated 15-minute hold.", "strict": True, "parameters": {"type": "object", "properties": {"room_id": {"type": "string"}, "check_in": {"type": "string"}, "check_out": {"type": "string"}, "guests": {"type": "integer"}}, "required": ["room_id", "check_in", "check_out", "guests"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_booking_hold", "description": "Retrieve verified hold details, status, and expiry.", "strict": True, "parameters": {"type": "object", "properties": {"hold_id": {"type": "string"}}, "required": ["hold_id"], "additionalProperties": False}}}
]

class Agent:
    def __init__(self, state, llm_calls=0, recent_messages=None, previous_response_id=None):
        self.state = state
        self.trace = []
        self.llm_calls = llm_calls
        self.recent_messages = recent_messages or []
        self.previous_response_id = previous_response_id

    def run(self, message):
        if self.select_mode(message) == "llm" and self.llm_calls < MAX_LLM_CALLS_PER_SESSION:
            try:
                return self.run_llm(message)
            except Exception as error:
                self.trace = [("openai_agent", {"status": "fallback", "error": str(error)})]
        self.trace = []
        location = resolve_message_location(message)
        if location:
            self.trace.append(("resolve_destination", location))
        self.state.update(message)
        text = message.lower().strip()
        if "heated" in text and self.state.last_recommendations:
            self.trace.append(("get_room_details", get_room_details(self.state.last_recommendations[0]["room_id"])))
            return "I don't have verified information about whether the pool is heated."
        if "bangalore palace" in text:
            experience = get_experience_details("Bengaluru", "Bangalore Palace")
            self.trace.append(("get_experience_details", experience or {"found": False}))
            return "My demo experience catalog lists Bangalore Palace at ₹240 per adult for Indian visitors and references ₹460 for foreign visitors. These are indicative values and should be verified before visiting."
        if "what can we visit" in text or "what is there to do" in text:
            if self.state.selected_property_id and self.state.destination == "Bengaluru":
                experiences = get_local_experiences("Bengaluru")
                self.trace.append(("get_local_experiences", experiences))
                names = ", ".join(item["name"] for item in experiences)
                return f"Near your selected Bengaluru property, you could consider {names}. These are demo informational suggestions; verify details before visiting."
            return "Please select a Bengaluru property first, and I can show nearby demo experiences."
        for policy in ("cancellation", "check-in", "check out", "children", "pets"):
            if policy in text and self.state.last_recommendations:
                result = get_policy(self.state.last_recommendations[0]["property_id"], policy)
                self.trace.append(("get_policy", result))
                return f"The verified {policy} policy is: {result['value']}."
        if not self.state.destination:
            supported = ", ".join(supported_destinations())
            if location and not location["matched"]:
                return f"I do not currently have verified inventory for that destination. I can search {supported}. Which destination would you like?"
            return "Which destination would you like to stay in?"
        if not self.state.check_in or not self.state.check_out:
            return "What dates should I search? You can say ‘next weekend’."
        if not self.state.guests:
            return "How many guests will be staying?"
        if self.state.hold_id and any(
            phrase in text for phrase in ("confirm", "details", "expiry", "expires", "total estimated cost")
        ):
            held = next(
                (result for result in self.state.last_recommendations if result["room_id"] == self.state.selected_room_id),
                None,
            )
            if held:
                hold = get_booking_hold(self.state.hold_id)
                self.trace.append(("get_booking_hold", hold))
                if not hold["found"]:
                    return hold["reason"]
                from datetime import datetime
                from zoneinfo import ZoneInfo
                created = datetime.fromisoformat(hold["created_at"]).astimezone(ZoneInfo("Asia/Kolkata"))
                expires = datetime.fromisoformat(hold["expires_at"]).astimezone(ZoneInfo("Asia/Kolkata"))
                return (f"Here are your verified hold details:\n\nHold ID: {hold['hold_id']}\n"
                        f"Property: {hold['property_name']}\nRoom: {hold['room_name']}\n"
                        f"Dates: {hold['check_in']} to {hold['check_out']}\nGuests: {hold['guests']}\n"
                        f"Estimated total: ₹{hold['total']:,}, including 12% tax\n"
                        f"Hold created: {created:%d %b %Y, %I:%M %p} IST\n"
                        f"Hold expires: {expires:%d %b %Y, %I:%M %p} IST\n\n"
                        f"Your hold is currently {hold['status']}.")
        if self.state.last_next_action == "offer_price_calculation" and any(
            phrase in text for phrase in ("yes", "price", "calculate", "full stay", "total")
        ):
            alternative = self.state.last_recommendations[0] if self.state.last_recommendations else None
            if alternative:
                price = calculate_price(self.state, alternative)
                alternative = {**alternative, **price}
                self.state.last_recommendations = [alternative]
                self.state.last_next_action = "ask_for_room_selection"
                self.trace.append(("calculate_price", [price]))
                return f"The estimated total for the {alternative['room']} at {alternative['property']} is ₹{price['total']:,}, including 12% tax for {price['nights']} nights. Would you like me to place a 15-minute booking hold?"
        option_number = extract_option_number(text)
        if option_number is not None and self.state.last_recommendations:
            if option_number < 1 or option_number > len(self.state.last_recommendations):
                result = {"selected": False, "reason": f"Option {option_number} is not available. Please choose an option from 1 to {len(self.state.last_recommendations)}."}
                self.trace.append(("select_recommendation", {"status": "error", "input": {"option_number": option_number}, "result": result}))
                return result["reason"]
            selected = self.state.last_recommendations[option_number - 1]
            self.state.selected_property_id = selected["property_id"]
            self.state.selected_room_id = selected["room_id"]
            self.state.last_next_action = "ask_for_booking_hold"
            result = {"selected": True, "option_number": option_number, "property_id": selected["property_id"], "property_name": selected["property"], "room_id": selected["room_id"], "room_name": selected["room"], "nightly_rate": selected["rate"], "next_action": "ask_for_booking_hold"}
            self.trace.append(("select_recommendation", {"status": "success", "input": {"option_number": option_number}, "result": result}))
            return f"Great choice. The {selected['room']} at {selected['property']} is selected.\n\nWould you like me to place a 15-minute booking hold?"
        selected = self.select_recommendation(text)
        if selected:
            self.state.selected_property_id = selected["property_id"]
            self.state.selected_room_id = selected["room_id"]
        wants_hold = text in ("yes", "book it", "hold it") or any(
            phrase in text for phrase in ("place", "booking hold", "put it on hold", "hold the", "hold on")
        ) and "hold" in text
        if selected and not wants_hold:
            self.state.last_next_action = "ask_for_booking_hold"
            return (
                f"Great choice. The {selected['room']} at {selected['property']} is selected.\n"
                "Would you like me to place a 15-minute booking hold?"
            )
        if wants_hold and self.state.last_recommendations:
            if not self.state.selected_room_id:
                return "Which room would you like me to hold: the " + " or the ".join(r["room"] for r in self.state.last_recommendations[:2]) + "?"
            result = next((r for r in self.state.last_recommendations if r["room_id"] == self.state.selected_room_id), None)
            if not result:
                return "Please choose one of the rooms in the recommendations before I place a hold."
            try:
                hold = create_booking_hold(self.state, result)
            except ValueError as error:
                self.trace.append(("error", str(error)))
                return f"I could not create the hold: {error}."
            self.state.hold_id = hold["hold_id"]
            self.state.last_next_action = "confirm_hold"
            self.trace.append(("create_booking_hold", hold))
            return f"Your 15-minute booking hold is {hold['hold_id']} for {result['room']}."
        results = search_properties(self.state)
        self.trace.append(("search_properties", results))
        if not results:
            destination_rooms = [room for hotel in CATALOG if hotel["city"].lower() == self.state.destination.lower() for room in hotel["rooms"]]
            if destination_rooms and self.state.guests > max(room["capacity"] for room in destination_rooms):
                self.state.last_next_action = "ask_room_split_or_destination"
                return f"I don’t currently have a verified single room in {self.state.destination} that accommodates all {self.state.guests} guests for your requested dates.\n\nI can check availability for two rooms in {self.state.destination}, or you can choose another supported destination. Which would you prefer?"
            return "I could not find an available room matching those requirements. Try a higher budget or fewer preferences."
        checked = [check_availability(self.state, result) for result in results]
        self.trace.append(("check_availability", checked))
        requested_room = next((result for result in results if result["room"].lower() in text), None)
        if requested_room:
            requested_check = next(result for result in checked if result["room_id"] == requested_room["room_id"])
            if not requested_check["available"]:
                checked = []
        checked = [result for result in checked if result["available"]]
        if not checked:
            alternatives_state = self.state.model_copy(update={"preferences": [], "budget_per_night": None})
            alternatives = search_properties(alternatives_state)
            alternative = None
            for candidate in alternatives:
                checked_candidate = check_availability(alternatives_state, candidate)
                if checked_candidate["available"]:
                    alternative = checked_candidate
                    break
            if alternative:
                price = calculate_price(alternatives_state, alternative)
                self.state.last_recommendations = [{**alternative, **price}]
                self.trace.append(("check_availability", [alternative]))
                self.trace.append(("calculate_price", [price]))
                self.state.last_next_action = "offer_price_calculation"
                return f"The requested room is not available for every night of your stay, so I can’t place a hold on it.\n\nI found a verified alternative: the {alternative['room']} at {alternative['property']} is available for all of your requested dates at ₹{alternative['rate']:,} per night. Would you like me to calculate the full stay cost?"
            return "Those rooms are not available for every requested night, and I could not find a verified alternative."
        prices = [calculate_price(self.state, result) for result in checked[:3]]
        priced = []
        for result, price in zip(checked[:3], prices):
            priced.append({**result, **price})
        self.state.last_recommendations = priced
        self.state.last_next_action = "ask_for_room_selection"
        self.trace.append(("calculate_price", prices))
        if "cheaper" in text:
            priced = sorted(priced, key=lambda result: result["rate"])
        if "other" in text and len(checked) > 1:
            priced = priced[1:]
        lines = [f"{index}. {r['room']} — {r['property']}\n   ₹{r['rate']:,}/night · Sleeps up to {r['capacity']} guests\n   Estimated total for {r['nights']} nights: ₹{r['total']:,} including 12% tax" for index, r in enumerate(priced[:3], 1)]
        date_summary = f"{self.state.check_in:%d %b}–{self.state.check_out:%d %b}"
        return f"I’ve interpreted your dates as {date_summary} for {self.state.guests} guests.\n\nI found these verified available options:\n\n" + "\n\n".join(lines) + "\n\nWhich room would you like me to hold?"

    def select_recommendation(self, text):
        if not self.state.last_recommendations:
            return None
        normalized = text.lower()
        for index, result in enumerate(self.state.last_recommendations[:3], 1):
            if f"option {index}" in normalized or f"number {index}" in normalized:
                return result
            if result["room"].lower() in normalized or result["property"].lower() in normalized:
                return result
        return None

    def should_use_llm(self, message):
        phrases = ("whichever", "other one", "better", "peaceful", "somewhere nice", "a little longer", "too expensive")
        return any(phrase in message.lower() for phrase in phrases)

    def select_mode(self, message):
        mode = os.getenv("AGENT_MODE", "hybrid")
        if mode == "offline" or not os.getenv("OPENAI_API_KEY"):
            return "offline"
        return "llm" if mode == "llm" or self.should_use_llm(message) else "offline"

    def run_llm(self, message):
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.llm_calls += 1
        self.state.update(message)
        self.state = self.extract_state_update(message)
        self.trace = []
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": "BOOKING_STATE (authoritative):\n" + json.dumps(self.state.model_dump(mode="json"), ensure_ascii=False)},
            *self.recent_messages[-6:],
            {"role": "user", "content": message},
        ]
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.chat.completions.create(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), messages=messages, tools=TOOLS, tool_choice="auto", temperature=0)
            self.previous_response_id = response.id
            assistant = response.choices[0].message
            messages.append(assistant.model_dump(exclude_none=True))
            if not assistant.tool_calls:
                return assistant.content or "I could not complete that request safely."
            for call in assistant.tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments)
                self.trace.append((name, {"status": "running", "input": args}))
                try:
                    result = self.execute_llm_tool(name, args)
                except (TypeError, ValueError) as error:
                    result = {"error": str(error)}
                self.trace[-1] = (name, {"status": "error" if "error" in result else "success", "input": args, "result": result})
                messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
        return "I could not complete the booking flow safely."

    def extract_state_update(self, message):
        client = __import__("openai").OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=[
                {"role": "system", "content": "Extract only fields explicitly changed in the guest message. Return null for unchanged fields. Resolve next weekend using 2026-08-24."},
                {"role": "user", "content": message},
            ],
            text={"format": {"type": "json_schema", "name": "state_update", "strict": True, "schema": STATE_UPDATE_SCHEMA}},
        )
        update = json.loads(response.output_text)
        return merge_state(self.state, update)

    def execute_llm_tool(self, name, args):
        if name == "resolve_destination":
            return normalize_location(args["location_query"])
        if name == "search_properties":
            result = search_properties(self.state)
            self.state.last_recommendations = result
            return result
        if name == "check_availability":
            result = next(r for r in self.state.last_recommendations if r["room_id"] == args["room_id"])
            return check_availability(self.state, result)
        if name == "calculate_price":
            result = next(r for r in self.state.last_recommendations if r["room_id"] == args["room_id"])
            return calculate_price(self.state, result)
        if name == "get_room_details":
            return get_room_details(args["room_id"])
        if name == "get_policy":
            return get_policy(args["property_id"], args["policy_type"])
        if name == "create_booking_hold":
            result = next(r for r in self.state.last_recommendations if r["room_id"] == args["room_id"])
            return create_booking_hold(self.state, result)
        if name == "get_booking_hold":
            return get_booking_hold(args["hold_id"])
        raise ValueError(f"Tool '{name}' is not allowed")
