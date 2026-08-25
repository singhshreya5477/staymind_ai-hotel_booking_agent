# StayMind Engineering Note

## Architecture

StayMind is a small full-stack hotel-booking application. A Next.js frontend provides the chat experience and exposes booking state, recommendations, next actions, and tool traces. A FastAPI backend owns sessions and connects the UI to the Python agent. The agent uses a fictional JSON catalog for properties, rooms, amenities, policies, and inventory.

The design deliberately separates probabilistic language understanding from deterministic booking logic. The model can interpret flexible guest language, while Python remains the source of truth for availability, capacity, pricing, policies, room selection, and booking holds.

## Model Choice

The optional LLM path uses `gpt-4.1-mini` because the task needs reliable language understanding and function selection without the cost or latency of a larger model. Simple, predictable requests use the offline deterministic flow. Complex requests can use OpenAI when `AGENT_MODE=hybrid` and an API key is configured; failures automatically fall back to the local flow.

## Agent Flow

Each message follows this sequence:

1. Load the session's validated booking state and recent messages.
2. Resolve destinations and parse dates, guests, budget, and preferences.
3. Ask for missing information when search requirements are incomplete.
4. Search catalog rooms and validate capacity and availability for every night.
5. Calculate totals in Python, including tax.
6. Resolve room references such as `option 2` from saved recommendations.
7. Revalidate availability and create a time-limited hold only after explicit selection.
8. Retrieve saved hold records for status and expiry questions.

## State Management

`BookingState` is a Pydantic model containing destination, dates, adults, children, budget, preferences, selected property and room, recommendations, next action, hold ID, hold status, and expiry. State is merged rather than rebuilt, so a change such as “one more night” preserves the known destination and preferences. Changing booking constraints clears stale recommendations and selections so old availability is never trusted.

The FastAPI demo stores sessions and the hold store in memory. Recent messages are capped to keep context compact. Production would use Redis or PostgreSQL for durable, multi-instance sessions and holds.

## Tool Calling

The agent has focused tools for destination resolution, room search, availability, deterministic pricing, room details, policies, hold creation, hold retrieval, and Bengaluru demo experiences. OpenAI function schemas use strict JSON parameters. Tool inputs and outputs are captured in a structured trace for the UI and evaluation.

## Hallucination Prevention

Hotel-specific facts are never generated from memory. Rooms must come from the catalog, availability must pass a date-by-date inventory check, capacity is validated before recommendation, and totals are calculated by Python. Unknown facts, such as whether a pool is heated, receive an explicit “not verified” response. Unsupported destinations receive the catalog's supported locations instead of invented hotels. Experience prices are clearly labeled as indicative demo information.

## Tradeoffs

The implementation favors reliability and inspectability over broad real-world coverage. JSON and in-memory storage are fast to understand and suitable for the assignment, but they are not durable or live inventory. The hybrid LLM mode provides natural language flexibility, while the offline path adds predictable behavior and avoids unnecessary API cost. The UI is intentionally operational rather than a full booking platform.

## Next Improvements

The next priorities would be persistent storage, a licensed hotel inventory provider, and stronger structured state extraction for more natural date and guest expressions. I would also add room-combination search for capacity conflicts, cancellation of existing holds, authentication, rate limiting, observability, and a larger automated evaluation set with measured tool and state accuracy.
