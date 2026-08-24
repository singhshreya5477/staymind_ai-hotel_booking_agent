from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agent import Agent
from src.state import BookingState

app = FastAPI(title="StayMind AI Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    assistant_message: str
    booking_state: dict
    recommendations: list[dict]
    trace: list[dict]
    next_action: str


def serialize_state(state: BookingState) -> dict:
    data = state.model_dump(mode="json")
    data["guests"] = state.guests
    return data


def serialize_trace(trace: list[tuple[str, dict]]) -> list[dict]:
    serialized = []
    for action, payload in trace:
        if isinstance(payload, dict):
            serialized.append({"action": action, **payload})
        else:
            serialized.append({"action": action, "status": "success", "result": payload})
    return serialized


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid4())
    session = SESSIONS.setdefault(session_id, {"state": BookingState(), "messages": [], "llm_calls": 0, "previous_response_id": None})
    agent = Agent(session["state"], session["llm_calls"], session["messages"][-6:], session.get("previous_response_id"))
    assistant_message = agent.run(request.message)
    session.update({"state": agent.state, "llm_calls": agent.llm_calls, "previous_response_id": agent.previous_response_id})
    session["messages"].extend([
        {"role": "user", "content": request.message},
        {"role": "assistant", "content": assistant_message},
    ])
    session["messages"] = session["messages"][-10:]
    return ChatResponse(
        session_id=session_id,
        assistant_message=assistant_message,
        booking_state=serialize_state(agent.state),
        recommendations=agent.state.last_recommendations,
        trace=serialize_trace(agent.trace),
        next_action=agent.state.last_next_action or ("complete" if agent.state.hold_id else "ask_for_booking_details"),
    )


@app.post("/api/reset")
def reset(request: ChatRequest):
    session_id = request.session_id or str(uuid4())
    SESSIONS[session_id] = {"state": BookingState(), "messages": [], "llm_calls": 0, "previous_response_id": None}
    return {"session_id": session_id}