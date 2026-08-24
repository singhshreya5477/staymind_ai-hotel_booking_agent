import streamlit as st
from dotenv import load_dotenv
from src.agent import Agent
from src.state import BookingState

load_dotenv()
st.set_page_config(page_title="StayMind AI", layout="wide")
st.title("StayMind AI")
st.caption("Hotel booking assistant")
if "state" not in st.session_state:
    st.session_state.state = BookingState()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "trace" not in st.session_state:
    st.session_state.trace = []
if "llm_calls" not in st.session_state:
    st.session_state.llm_calls = 0
agent = Agent(st.session_state.state, st.session_state.llm_calls)
left, right = st.columns([1.5, 1])
with left:
    for role, text in st.session_state.messages:
        with st.chat_message(role):
            st.write(text)
    prompt = st.chat_input("Tell me where and when you want to stay")
    if prompt:
        st.session_state.messages.append(("user", prompt))
        response = agent.run(prompt)
        st.session_state.state = agent.state
        st.session_state.llm_calls = agent.llm_calls
        st.session_state.trace = agent.trace
        st.session_state.messages.append(("assistant", response))
        st.rerun()
with right:
    st.subheader("Current state")
    state = st.session_state.state
    st.json({"destination": state.destination, "check_in": str(state.check_in) if state.check_in else None, "check_out": str(state.check_out) if state.check_out else None, "adults": state.adults, "children": state.children, "guests": state.guests, "budget_per_night": state.budget_per_night, "preferences": state.preferences, "hold_id": state.hold_id})
    st.subheader("Tool trace")
    for name, result in st.session_state.trace:
        st.write(name)
        st.json(result)
