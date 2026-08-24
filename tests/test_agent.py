from datetime import date
import pytest
from src.agent import Agent
from src.state import BookingState


@pytest.mark.parametrize(
    ("message", "destination", "room", "total"),
    [
        ("Goa from 2026-09-01 to 2026-09-03 for 2 people", "Goa", "Garden Suite", 26880),
        ("Jaipur from 2026-09-01 to 2026-09-03 for 2 people", "Jaipur", "Heritage Suite", 24640),
        ("Manali from 2026-09-01 to 2026-09-03 for 2 people", "Manali", "Pine View Chalet", 21280),
        ("Bengaluru from 2026-09-01 to 2026-09-03 for 2 people", "Bengaluru", "Quiet Garden Room", 19040),
    ],
)
def test_every_supported_destination_returns_grounded_search(message, destination, room, total):
    state = BookingState()
    agent = Agent(state)
    response = agent.run(message)
    trace_names = [name for name, _ in agent.trace]
    assert state.destination == destination
    assert room in response
    assert f"₹{total:,}" in response
    assert "search_properties" in trace_names
    assert "check_availability" in trace_names
    assert "calculate_price" in trace_names

def test_next_weekend():
    state = BookingState()
    Agent(state).run("Goa next weekend for 3 people under 20k with a private pool")
    assert state.check_in == date(2026, 8, 29)
    assert state.check_out == date(2026, 8, 31)

def test_missing_dates():
    response = Agent(BookingState()).run("I need Goa for 3 people")
    assert "dates" in response

def test_hold_after_search():
    state = BookingState()
    agent = Agent(state)
    agent.run("Goa next weekend for 3 people")
    response = agent.run("Private Pool Villa")
    assert "Private Pool Villa at Goa Sands Retreat is selected" in response
    response = agent.run("yes")
    assert "HOLD-" in response

def test_requires_room_selection():
    agent = Agent(BookingState())
    agent.run("Goa next weekend for 3 people")
    response = agent.run("yes")
    assert "Which room" in response

def test_alias_resolves_to_goa():
    state = BookingState()
    Agent(state).run("Find a hotel in Candolim for 2 people")
    assert state.destination == "Goa"

def test_unsupported_destination_is_grounded():
    response = Agent(BookingState()).run("Need a hotel in Udaipur for 2 people")
    assert "verified inventory" in response

def test_manali_is_catalog_supported():
    state = BookingState()
    response = Agent(state).run("Old Manali from 2026-09-01 to 2026-09-03 for 2 people")
    assert state.destination == "Manali"
    assert "Pine View Chalet" in response

def test_natural_hold_request_does_not_repeat_search():
    state = BookingState()
    agent = Agent(state)
    agent.run("Goa next weekend for 3 people")
    response = agent.run("Please place a 15-minute hold on the Private Pool Villa at Goa Sands Retreat")
    assert "HOLD-" in response

def test_hold_confirmation_returns_details():
    state = BookingState()
    agent = Agent(state)
    agent.run("Goa next weekend for 3 people")
    agent.run("Please place a 15-minute hold on the Private Pool Villa at Goa Sands Retreat")
    response = agent.run("Thanks. Please confirm the hold details, total estimated cost, dates, guest count, and expiry time.")
    assert "HOLD-" in response
    assert "₹40,320" in response
    assert "Hold created:" in response
    assert "Hold expires:" in response
    assert "currently active" in response

def test_option_two_selection_uses_last_recommendations():
    state = BookingState()
    agent = Agent(state)
    agent.run("Goa next weekend for 3 people")
    response = agent.run("I would like option 2, the Garden Suite.")
    assert state.selected_property_id == "goa-sands"
    assert state.selected_room_id == "garden-suite"
    assert "Garden Suite at Goa Sands Retreat is selected" in response
    assert "search_properties" not in response
    assert "ask_for_booking_hold" == state.last_next_action

def test_option_two_emits_selection_trace_and_supports_hold():
    state = BookingState()
    agent = Agent(state)
    agent.run("Goa next weekend for 3 people")
    response = agent.run("I would like option 2")
    assert "Garden Suite" in response
    assert agent.trace[0][0] == "select_recommendation"
    assert agent.trace[0][1]["result"]["room_id"] == "garden-suite"
    assert "HOLD-" in agent.run("Yes, please place the booking hold.")

def test_invalid_option_does_not_search():
    agent = Agent(BookingState())
    agent.run("Goa next weekend for 3 people")
    response = agent.run("Please select option 9")
    assert "not available" in response
    assert agent.trace[0][0] == "select_recommendation"

def test_bangalore_alias_searches_bengaluru():
    state = BookingState()
    response = Agent(state).run("Bangalore next weekend for 2 people, under ₹10,000/night")
    assert state.destination == "Bengaluru"
    assert "Quiet Garden Room" in response

def test_lalbagh_saves_quiet_preference_and_asks_for_dates():
    state = BookingState()
    response = Agent(state).run("Need a quiet stay near Lalbagh for two adults")
    assert state.destination == "Bengaluru"
    assert state.adults == 2
    assert "quiet" in state.preferences
    assert "dates" in response

def test_bangalore_palace_uses_demo_experience_catalog():
    agent = Agent(BookingState())
    response = agent.run("How much is Bangalore Palace entry?")
    assert "₹240" in response
    assert "₹460" in response
    assert "indicative" in response
    assert agent.trace[0][0] == "resolve_destination"

def test_local_experiences_require_selected_bengaluru_property():
    state = BookingState()
    agent = Agent(state)
    agent.run("Bangalore next weekend for 2 people")
    agent.run("option 1")
    response = agent.run("What can we visit near the hotel?")
    assert "Lalbagh Botanical Garden" in response
    assert agent.trace[-1][0] == "get_local_experiences"

def test_capacity_conflict_is_explained():
    agent = Agent(BookingState())
    response = agent.run("I need one room in Goa next weekend for 5 people")
    assert "verified single room" in response
    assert "5 guests" in response
    assert agent.state.last_next_action == "ask_room_split_or_destination"

def test_unavailable_room_gets_verified_alternative():
    agent = Agent(BookingState())
    response = agent.run("I want the Private Pool Villa in Goa from 2026-09-01 to 2026-09-03 for 3 people")
    assert "not available" in response
    assert "Garden Suite" in response
    assert agent.state.last_next_action == "offer_price_calculation"

def test_verified_alternative_can_be_priced_next_turn():
    agent = Agent(BookingState())
    agent.run("I want the Private Pool Villa in Goa from 2026-09-01 to 2026-09-03 for 3 people")
    response = agent.run("Yes, calculate the full stay cost")
    assert "₹26,880" in response
    assert "Garden Suite" in response
    assert agent.state.last_next_action == "ask_for_room_selection"
