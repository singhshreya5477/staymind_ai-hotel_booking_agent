# StayMind AI

A hotel-booking agent with a deterministic Python core, a FastAPI API, and a Next.js web interface.

## Run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Web application

Install backend dependencies and start the API from the repository root:

```bash
python -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

In a second terminal, install and start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The API keeps an in-memory session for the demo; a production deployment should use Redis, PostgreSQL, or another persistent session store.

Run tests with `pytest`.

## Structure

- `app.py`: chat and evaluator trace panel
- `backend/app/main.py`: FastAPI health, chat, and reset endpoints
- `frontend/app/page.tsx`: responsive chat and booking-state interface
- `src/state.py`: booking state and date resolution
- `src/location.py`: catalog-backed destination aliases and resolution
- `src/tools.py`: six grounded hotel tools and deterministic pricing
- `src/agent.py`: short deterministic agent flow
- `data/hotels.json`: fictional hotel catalog

The assignment MVP uses exactly three fictional properties across Goa, Jaipur, and Manali. JSON is the verified source for room facts, availability, pricing, and simulated holds. The agent can recognize only destinations represented by its catalog; for other locations it clearly says that verified inventory is unavailable rather than inventing results. It does not use Google Places or claim real-world hotel coverage. Relative dates use `2026-08-24` as the repeatable demo date. The trace exposes state, tool calls, tool outputs, and validation errors, never private reasoning.

Set `AGENT_MODE=hybrid` and `OPENAI_API_KEY` in a local `.env` to enable OpenAI only for complex language and tool selection. Obvious requests stay offline, and API errors or the 25-call session limit fall back automatically. Keep API keys out of source control. A licensed hotel inventory provider would be required for broader real-world booking coverage.

Special thanks to Ashish Gupta for the opportunity and guidance.
