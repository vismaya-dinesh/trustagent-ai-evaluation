
import streamlit as st

from agent.run_agent import run_agent
from sidebar import render_sidebar


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="TrustAgent | Customer Support",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# STYLING
# --------------------------------------------------

st.markdown(
    """
    <style>
    @keyframes taChatFadeIn {
        from { opacity: 0; transform: translateY(7px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2.5rem;
        animation: taChatFadeIn 0.35s ease-out;
    }

    .ta-eyebrow {
        color: #93c5fd;
        text-transform: uppercase;
        letter-spacing: 0.13em;
        font-size: 0.76rem;
        font-weight: 700;
    }

    .ta-title {
        font-size: clamp(2rem, 4vw, 2.7rem);
        font-weight: 800;
        letter-spacing: -0.04em;
        line-height: 1.15;
        margin: 0.4rem 0;
    }

    .ta-subtitle {
        color: #a7b4c8;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }

    .ta-info-card {
        background: #111b2e;
        border: 1px solid #26364e;
        border-radius: 13px;
        padding: 1rem 1.1rem;
        margin: 0.7rem 0 1rem 0;
    }

    .ta-info-heading {
        color: #f1f5f9;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }

    .ta-info-body {
        color: #a7b4c8;
        font-size: 0.9rem;
        line-height: 1.55;
    }

    [data-testid="stChatMessage"] {
        border: 1px solid rgba(100, 116, 139, 0.18);
        border-radius: 14px;
        padding: 0.9rem 1rem;
    }

    [data-testid="stChatInput"] {
        border-color: #334155;
    }

    div.stButton > button {
        border-radius: 10px;
        min-height: 2.5rem;
    }

    @media (max-width: 640px) {
        .block-container {
            padding: 1rem 0.75rem 2rem;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            transition-duration: 0.01ms !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

render_sidebar("support")


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "last_tool_trace" not in st.session_state:
    st.session_state["last_tool_trace"] = []

if "last_agent_error" not in st.session_state:
    st.session_state["last_agent_error"] = None


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.markdown(
    '<div class="ta-eyebrow">TrustAgent workspace</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="ta-title">Customer Support</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="ta-subtitle">'
    'Ask about an order and receive an answer based on verified information.'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="ta-info-card">
        <div class="ta-info-heading">🛡️ Safe, verified responses</div>
        <div class="ta-info-body">
            The assistant can look up supported order information. It will
            not claim to issue refunds, cancel orders, or change addresses
            when those actions are not supported by the available tools.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# CHAT ACTIONS
# --------------------------------------------------

action_col1, action_col2 = st.columns([1, 4])

with action_col1:
    if st.button("＋ New conversation", use_container_width=True):
        st.session_state["messages"] = []
        st.session_state["last_tool_trace"] = []
        st.session_state["last_agent_error"] = None
        st.rerun()

with action_col2:
    st.caption("Example: Where is order 102?")


# --------------------------------------------------
# DISPLAY CHAT HISTORY
# --------------------------------------------------

for message in st.session_state["messages"]:
    role = message.get("role", "assistant")
    content = message.get("content", "")

    with st.chat_message(role):
        st.markdown(content)


# --------------------------------------------------
# SUGGESTED QUESTIONS
# --------------------------------------------------

if not st.session_state["messages"]:
    st.markdown("#### Try asking")

    suggestions = [
        "Where is order 101?",
        "Where is order 102?",
        "Can you check order 103?",
    ]

    suggestion_cols = st.columns(3)

    for index, suggestion in enumerate(suggestions):
        with suggestion_cols[index]:
            if st.button(
                suggestion,
                key=f"suggestion_{index}",
                use_container_width=True,
            ):
                st.session_state["pending_question"] = suggestion
                st.rerun()


# --------------------------------------------------
# HANDLE USER INPUT
# --------------------------------------------------

typed_question = st.chat_input(
    "Ask about an order…",
)

pending_question = st.session_state.pop(
    "pending_question",
    None,
)

user_question = typed_question or pending_question

if user_question:
    user_question = user_question.strip()

    if user_question:
        st.session_state["messages"].append(
            {
                "role": "user",
                "content": user_question,
            }
        )

        with st.chat_message("user"):
            st.markdown(user_question)

        with st.chat_message("assistant"):
            status = st.status(
                "Checking the request…",
                expanded=False,
            )

            try:
                result = run_agent(user_question)

                if not isinstance(result, dict):
                    raise TypeError(
                        "run_agent() returned an unexpected result. "
                        "Expected a dictionary containing 'answer'."
                    )

                answer = result.get("answer")

                if answer is None or not str(answer).strip():
                    answer = (
                        "I couldn't produce a response for that request. "
                        "Please try rephrasing your question."
                    )
                else:
                    answer = str(answer).strip()

                tool_trace = result.get("tool_trace", [])

                if not isinstance(tool_trace, list):
                    tool_trace = [tool_trace]

                st.session_state["last_tool_trace"] = tool_trace
                st.session_state["last_agent_error"] = None

                status.update(
                    label="Request processed",
                    state="complete",
                    expanded=False,
                )

                st.markdown(answer)

                st.session_state["messages"].append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

            except Exception as exc:
                error_message = (
                    "Sorry, I couldn't process that request right now. "
                    "Please try again. If the issue continues, check that "
                    "Ollama is running and the local model is available."
                )

                st.session_state["last_agent_error"] = (
                    f"{type(exc).__name__}: {exc}"
                )

                status.update(
                    label="Unable to process the request",
                    state="error",
                    expanded=False,
                )

                st.markdown(error_message)

                st.session_state["messages"].append(
                    {
                        "role": "assistant",
                        "content": error_message,
                    }
                )


# --------------------------------------------------
# LAST TOOL TRACE
# --------------------------------------------------

if st.session_state["last_tool_trace"]:
    with st.expander("Latest tool activity"):
        for index, item in enumerate(
            st.session_state["last_tool_trace"],
            start=1,
        ):
            st.markdown(f"**Step {index}**")
            if isinstance(item, (dict, list)):
                st.json(item)
            else:
                st.write(str(item))

elif st.session_state["messages"]:
    with st.expander("Latest tool activity"):
        st.caption("No tool calls were recorded for the latest request.")


# --------------------------------------------------
# DEBUG DETAILS
# --------------------------------------------------

if st.session_state["last_agent_error"]:
    with st.expander("Technical details"):
        st.code(
            st.session_state["last_agent_error"],
            language="text",
        )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "TrustAgent · Responses are limited to information verified by "
    "the available tools."
)
