
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
DASHBOARD_PATH = ROOT / "dashboard.py"
SUPPORT_PATH = ROOT / "pages" / "1_Customer_Support.py"


def inject_sidebar_styles():
    st.markdown(
        """
        <style>
        /* Hide Streamlit's automatic page navigation.
           Keep the custom navigation rendered below. */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        [data-testid="stSidebar"] {
            background: #0b1120;
            border-right: 1px solid #202b40;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.3rem;
        }

        .ta-brand {
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: -0.04em;
            color: #f8fafc;
            margin-bottom: 0.2rem;
        }

        .ta-brand-subtitle {
            font-size: 0.78rem;
            color: #94a3b8;
            margin-bottom: 1.4rem;
        }

        .ta-sidebar-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin: 1.1rem 0 0.5rem;
        }

        .ta-nav-active {
            display: block;
            padding: 0.72rem 0.85rem;
            margin: 0.25rem 0;
            border-radius: 0.65rem;
            background: #172554;
            border: 1px solid #294b9b;
            color: #eff6ff !important;
            font-weight: 650;
        }

        [data-testid="stSidebar"] [data-testid="stPageLink"] a {
            border-radius: 0.65rem;
            transition: background 0.15s ease;
        }

        [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {
            background: #172033;
        }

        .ta-status-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #34d399;
            margin-right: 7px;
        }

        .ta-sidebar-note {
            color: #94a3b8;
            font-size: 0.78rem;
            line-height: 1.55;
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


def render_sidebar(current_page: str):
    """Render the shared dark-only sidebar with one page navigation."""
    inject_sidebar_styles()

    current_page = current_page.strip().lower()

    with st.sidebar:
        # Brand
        st.markdown(
            """
            <div class="ta-brand">🛡️ TrustAgent</div>
            <div class="ta-brand-subtitle">
                AI Agent Reliability &amp; Evaluation
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Navigation
        st.markdown(
            '<div class="ta-sidebar-label">Workspace</div>',
            unsafe_allow_html=True,
        )

        if current_page == "dashboard":
            st.markdown(
                '<div class="ta-nav-active">📊 &nbsp; Dashboard</div>',
                unsafe_allow_html=True,
            )
        else:
            st.page_link(
                str(DASHBOARD_PATH),
                label="Dashboard",
                icon="📊",
                use_container_width=True,
            )

        if current_page in {"support", "customer_support"}:
            st.markdown(
                '<div class="ta-nav-active">💬 &nbsp; Customer Support</div>',
                unsafe_allow_html=True,
            )
        else:
            st.page_link(
                str(SUPPORT_PATH),
                label="Customer Support",
                icon="💬",
                use_container_width=True,
            )

        # Agent status
        st.divider()

        st.markdown(
            '<div class="ta-sidebar-label">Agent status</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="ta-sidebar-note">
                <span class="ta-status-dot"></span>
                Local agent workspace
                <br><br>
                <b>Model</b><br>
                Ollama · Qwen2.5 3B
                <br><br>
                <b>Data</b><br>
                Local SQLite database
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Safety policy
        st.divider()

        with st.expander("Safety policy"):
            st.markdown(
                """
                - Use verified order information only.
                - Do not invent order details or tool results.
                - Do not promise unsupported refunds or cancellations.
                - Do not claim an address was changed unless a supported
                  tool confirms the change.
                - Avoid exposing unnecessary customer information.
                """
            )

        st.caption("TrustAgent · Dark mode")
