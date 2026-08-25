# StayMind Engineering Note

## Architecture

StayMind is a small full-stack hotel-booking app. The Next.js frontend handles the conversation and shows the current booking state, recommendations, next action, and tool trace. FastAPI connects the frontend to the Python agent and manages sessions. Hotel details come from a fictional JSON catalog containing properties, rooms, amenities, policies, and inventory.

The main design decision is to keep language understanding separate from booking logic. The model can understand flexible guest messages, but Python remains responsible for availability, capacity, pricing, policies, room selection, and booking holds.

## Model Choice

The optional LLM path uses `gpt-4.1-mini`. It is capable enough for language understanding and tool selection without adding unnecessary cost or latency. Simple requests use the deterministic offline flow. More flexible requests can use OpenAI when `AGENT_MODE=hybrid` and an API key is configured. If the API call fails, the agent falls back to the local flow.

## Agent Flow

For each message, the agent:

1. Loads the session's validated state and recent messages.
2. Resolves the destination and extracts dates, guests, budget, and preferences.
3. Asks a concise question if search details are missing.
4. Searches the catalog and checks capacity and availability for every night.
5. Calculates the total in Python, including tax.
6. Resolves references such as `option 2` from saved recommendations.
7. Rechecks availability and creates a time-limited hold after explicit selection.
8. Retrieves the saved hold when the guest asks about its status or expiry.

## State Management

`BookingState` is a Pydantic model containing the destination, dates, guests, budget, preferences, selected property and room, recommendations, next action, and hold details. State is merged rather than rebuilt, so a message like “one more night” keeps the existing destination and preferences. When booking constraints change, stale recommendations and selections are cleared so old availability is never trusted.

For the demo, FastAPI keeps sessions and holds in memory, and recent messages are capped to keep the context small. A production version should use Redis or PostgreSQL so sessions survive restarts and work across multiple instances.

## Tool Calling

The agent uses small, focused tools for destination resolution, room search, availability, pricing, room details, policies, hold creation, hold retrieval, and Bengaluru demo experiences. OpenAI function schemas use strict JSON parameters. Every tool input and result is captured in a structured trace so the UI and tests can show what happened.

## Hallucination Prevention

The model is never trusted to invent hotel facts. Rooms must come from the catalog, availability is checked night by night, capacity is validated before recommendation, and totals are calculated by Python. If the catalog does not say whether a pool is heated, the agent says that detail is not verified. Unsupported destinations receive the supported catalog locations instead of invented hotels. Experience prices are clearly labeled as indicative demo information.

## Tradeoffs

I chose reliability and inspectability over broad real-world coverage. JSON and in-memory storage are easy to understand and fit the assignment, but they are not durable and do not represent live inventory. Hybrid mode makes the conversation more flexible, while offline mode keeps basic requests predictable and inexpensive. The UI focuses on the booking workflow rather than trying to be a complete booking platform.

## Next Improvements

Next, I would add persistent storage, a licensed hotel inventory provider, and stronger structured extraction for natural date and guest expressions. I would also support room combinations for capacity conflicts, hold cancellation, authentication, rate limiting, better observability, and a larger evaluation set with measured state and tool accuracy.
