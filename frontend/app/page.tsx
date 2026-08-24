"use client";

import { FormEvent, useState } from "react";

type State = {
  destination: string | null;
  check_in: string | null;
  check_out: string | null;
  adults: number | null;
  children: number;
  guests: number;
  budget_per_night: number | null;
  preferences: string[];
  hold_id: string | null;
};
type Trace = { action: string; status?: string; input?: unknown; result?: unknown; error?: string };
type Recommendation = { room: string; property: string; rate: number; total?: number; capacity: number };
type ApiResponse = { session_id: string; assistant_message: string; booking_state: State; recommendations: Recommendation[]; trace: Trace[]; next_action: string };
type Message = { role: "user" | "assistant"; content: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const initialState: State = {
  destination: null, check_in: null, check_out: null, adults: null, children: 0,
  guests: 0, budget_per_night: null, preferences: [], hold_id: null,
};

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [state, setState] = useState(initialState);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [nextAction, setNextAction] = useState("ask for booking details");
  const [trace, setTrace] = useState<Trace[]>([]);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hi, I’m StayMind. Tell me where and when you’d like to stay, and I’ll find a verified option." },
  ]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const message = input.trim();
    if (!message || loading) return;
    setInput("");
    setLoading(true);
    setMessages((current) => [...current, { role: "user", content: message }]);
    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      if (!response.ok) throw new Error("The booking agent is unavailable.");
      const data: ApiResponse = await response.json();
      setSessionId(data.session_id);
      setState(data.booking_state);
      setRecommendations(data.recommendations);
      setNextAction(data.next_action.replaceAll("_", " "));
      setTrace(data.trace);
      setMessages((current) => [...current, { role: "assistant", content: data.assistant_message }]);
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", content: error instanceof Error ? error.message : "Something went wrong." }]);
    } finally {
      setLoading(false);
    }
  }

  const text = (value: string | null) => value || "Not provided";
  const dates = state.check_in && state.check_out ? `${state.check_in} → ${state.check_out}` : "Not provided";

  return (
    <main className="shell">
      <header className="topbar">
        <div><p className="eyebrow">StayMind / hotel intelligence</p><h1 className="title">Find your next stay.</h1></div>
        <span className="status">Agent online</span>
      </header>

      <div className="grid">
        <section className="panel chat">
          <div className="chat-head"><span>Conversation</span><span className="session">{sessionId ? "Session active" : "New session"}</span></div>
          <div className="messages">
            {messages.map((message, index) => <div className={`message ${message.role}`} key={index}><span className="avatar">{message.role === "user" ? "You" : "✦"}</span><div className="bubble">{message.content}</div></div>)}
            {loading && <div className="message assistant"><span className="avatar">✦</span><div className="bubble loading">Checking verified inventory<span>···</span></div></div>}
          </div>
          <form className="composer" onSubmit={send}><input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Goa next weekend for 3 people" aria-label="Message" /><button className="send" disabled={loading} aria-label="Send message">↑</button></form>
        </section>

        <aside className="side">
          <section className="panel details"><div className="section-label">01 / live state</div><h2 className="section-title">Booking details</h2><dl className="facts">
            <div className="fact"><dt>Destination</dt><dd>{text(state.destination)}</dd></div>
            <div className="fact"><dt>Dates</dt><dd>{dates}</dd></div>
            <div className="fact"><dt>Guests</dt><dd>{state.guests ? `${state.guests} total` : "Not provided"}</dd></div>
            <div className="fact"><dt>Budget</dt><dd>{state.budget_per_night ? `₹${state.budget_per_night.toLocaleString()}/night` : "Not provided"}</dd></div>
            <div className="fact"><dt>Preferences</dt><dd>{state.preferences.length ? state.preferences.join(", ") : "None yet"}</dd></div>
            {state.hold_id && <div className="fact"><dt>Active hold</dt><dd className="hold-value">{state.hold_id}</dd></div>}
          </dl></section>

          <section className="panel next"><div className="section-label">02 / workflow</div><h2 className="section-title">Next action</h2><p>{nextAction}</p></section>

          {recommendations.length > 0 && <section className="panel options"><div className="section-label">03 / verified inventory</div><h2 className="section-title">Recommended rooms</h2><div className="option-list">{recommendations.map((item, index) => <div className="option" key={item.room}><span className="option-number">0{index + 1}</span><div><strong>{item.room}</strong><small>{item.property} · sleeps {item.capacity}</small><small>₹{item.rate.toLocaleString()}/night · ₹{item.total?.toLocaleString()} estimated</small></div></div>)}</div></section>}

          <section className="panel activity"><div className="section-label">04 / audit trail</div><h2 className="section-title">Agent activity</h2>{trace.length ? <div className="trace">{trace.map((item, index) => <details className="trace-item" key={`${item.action}-${index}`}><summary><span className={item.status === "error" ? "error" : "ok"}>{item.status === "error" ? "×" : "✓"}</span>{item.action}</summary><pre>{JSON.stringify({ input: item.input, result: item.result, error: item.error }, null, 2)}</pre></details>)}</div> : <p className="empty">Tool calls and validation results will appear here.</p>}</section>
        </aside>
      </div>
    </main>
  );
}
