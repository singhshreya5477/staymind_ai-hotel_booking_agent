# StayMind AI

Grounded conversational hotel-booking agent with a FastAPI backend and Next.js frontend.

**Live app:** <https://staymind.netlify.app/>

## Features

- Natural-language hotel search across Goa, Jaipur, Manali, and Bengaluru
- Catalog-backed availability, capacity, pricing, and policies
- Deterministic totals with 12% tax
- Room selection and 15-minute booking holds
- Persistent session state, tool traces, and hold verification
- Optional OpenAI function calling with offline fallback

## Run the web app

From the repository root:

```bash
python -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

## Deploy on Netlify

1. Deploy the FastAPI backend on a Python host such as Render or Railway.
2. In Netlify, import this repository and keep the included `netlify.toml` settings.
3. Add the environment variable `NEXT_PUBLIC_API_URL` with your deployed backend URL, for example `https://your-api.onrender.com`. Do not leave it empty or set to `localhost` on Netlify.
4. Set the backend variable `FRONTEND_ORIGINS` to your Netlify URL, for example `https://your-site.netlify.app`, then redeploy the API.

Netlify hosts the Next.js frontend. The FastAPI service, in-memory sessions, and fictional catalog run separately.

Run tests with:

```bash
python -m pytest
```

The original Streamlit demo can be started with `streamlit run app.py`.

## Project structure

```text
backend/     FastAPI API
frontend/    Next.js interface
src/         Agent, state, tools, location, and hold logic
data/       Fictional hotel catalog and inventory
tests/       Automated regression tests
```

## Scope

The JSON catalog is the source of truth for hotel facts. Unsupported destinations receive an honest “no verified inventory” response. Bengaluru also includes demo-only local experience suggestions, clearly labeled as informational. Holds and sessions are in memory for this demo; production use would require a persistent store and licensed hotel inventory.

To enable the optional OpenAI path, add `OPENAI_API_KEY` and `AGENT_MODE=hybrid` to a local `.env` file. Never commit API keys.
