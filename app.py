"""app.py – Streamlit client for the Gita Gnana MCP server.

Launches the server as a subprocess (stdio transport) and exposes a
premium chat interface.  Users can ask questions, view raw PDF
excerpts, and update the system prompt—all from the browser.
"""

from PIL import ImageChops
import asyncio
import textwrap
import os
from pathlib import Path

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Gita Gnana – Bhagavad Gita AI",
    page_icon="🪷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject custom CSS ─────────────────────────────────────────────────────────
_CSS_PATH = Path(__file__).with_name("style.css")
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

# Extra inline overrides for elements not reachable via the external file
st.markdown(
    """
    <style>
    #MainMenu, footer { visibility: hidden; }

    /* ── Chat input: ensure typed text is always visible ────────────── */
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] input,
    [data-testid="stChatInputTextArea"],
    .stChatInput textarea,
    .stChatInput input {
        background: rgba(255,255,255,0.08) !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        caret-color: #FFD700 !important;
        border: 1px solid rgba(255,215,0,0.35) !important;
        border-radius: 12px !important;
        font-size: 1rem !important;
        font-family: 'Outfit', sans-serif !important;
    }

    /* Placeholder text */
    [data-testid="stChatInput"] textarea::placeholder,
    .stChatInput textarea::placeholder {
        color: rgba(240, 242, 246, 0.5) !important;
    }

    /* Focus state glow */
    [data-testid="stChatInput"] textarea:focus,
    .stChatInput textarea:focus {
        border-color: rgba(255,215,0,0.6) !important;
        box-shadow: 0 0 8px rgba(255,215,0,0.2) !important;
        outline: none !important;
    }

    [data-testid="stChatInput"] * {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    .stExpander { border: 1px solid rgba(255,215,0,0.15); border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── FastMCP async helpers (cached per session) ────────────────────────────────
SERVER_SCRIPT = str(Path(__file__).with_name("gita_gnana_server.py"))

try:
    from fastmcp import Client as FastMCPClient  # type: ignore
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False


@st.cache_resource
def get_mcp_client():
    """Maintain a persistent connection to the MCP server."""
    client = FastMCPClient(SERVER_SCRIPT)
    # The client will be managed as a long-lived resource
    return client

async def _call_tool(tool_name: str, **params) -> str:
    """Call a tool on the persistent client."""
    client = get_mcp_client()
    # We use a short-lived connection context per call to ensure 
    # transport health in the stdio subprocess model.
    async with client:
        result = await client.call_tool(tool_name, params)
    
    if isinstance(result, list):
        return "\n".join([getattr(item, "text", str(item)) for item in result])
    return getattr(result, "text", str(result))


async def _list_tools() -> list[dict]:
    client = FastMCPClient(SERVER_SCRIPT)
    async with client:
        tools = await client.list_tools()
    if isinstance(tools, dict):
        return [{"name": k, **v} for k, v in tools.items()]
    return [{"name": t.name, "description": getattr(t, "description", "")} for t in tools]


def run(coro):
    """Run a coroutine synchronously (works inside Streamlit's thread)."""
    return asyncio.run(coro)


# ── Session state ─────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []   # list of {"role": ..., "content": ...}
if "server_ok" not in st.session_state:
    st.session_state.server_ok = HAS_FASTMCP
if "pdf_preview" not in st.session_state:
    st.session_state.pdf_preview = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🪷 Gita Gnana")
    st.markdown(
        "_An AI guide rooted exclusively in the Bhagavad Gita._",
        unsafe_allow_html=False,
    )
    st.divider()

    # ── Server status ──────────────────────────────────────────────────────────
    if not HAS_FASTMCP:
        st.error("⚠️ `fastmcp` not installed.\n\nRun:\n```\npip install fastmcp\n```")
    else:
        st.success("✅ FastMCP client ready")

    st.divider()

    # ── Source Previews ────────────────────────────────────────────────────────
    st.markdown("### 📚 Source Previews")
    if st.button("📄 PDF Excerpt", width='stretch', key="btn_pdf"):
        with st.spinner("Loading PDF text…"):
            try:
                text = run(_call_tool("get_pdf_text"))
                st.session_state.pdf_preview = text[:2000]
            except Exception as exc:
                st.session_state.pdf_preview = f"Error: {exc}"

    if st.session_state.pdf_preview:
        with st.expander("PDF excerpt", expanded=False):
            st.text(textwrap.shorten(st.session_state.pdf_preview, 1200, placeholder="…"))

    from dotenv import load_dotenv
    load_dotenv()
    
    st.divider()

    # API Key status
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        st.success("✅ API Key loaded from .env")
    else:
        st.warning("⚠️ No API Key found in .env")

    st.divider()
    if st.button("🗑️ Clear chat", width='stretch', key="btn_clear"):
        st.session_state.chat_history = []
        st.rerun()

# ── Main area ─────────────────────────────────────────────────────────────────
LOGO_PATH = r"C:\Users\Chakri\.gemini\antigravity\brain\a11ed758-e92b-4c82-b0de-2f8d8e3dcc80\gita_gnana_logo_1778507213986.png"
if Path(LOGO_PATH).exists():
    _, col_logo, _ = st.columns([1, 2, 1])
    with col_logo:
        st.image(LOGO_PATH, width='stretch')

st.markdown(
    "<h1 style='text-align:center;margin-bottom:0'>🪷 Gita Gnana</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center;color:#aaa;font-size:1.1rem'>"
    "Ask any question — answered solely from the Bhagavad Gita</p>",
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

# Render existing chat messages
for msg in st.session_state.chat_history:
    avatar = "🧘" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# Chat input
if user_input := st.chat_input("Ask a question about the Bhagavad Gita…"):
    if not HAS_FASTMCP:
        st.error("FastMCP is not installed. Cannot connect to the server.")
    else:
        # Show user message
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # Call server
        with st.chat_message("assistant", avatar="🧘"):
            with st.spinner("Contemplating the Gita…"):
                try:
                    answer = run(_call_tool("answer", question=user_input))
                except Exception as exc:
                    answer = f"⚠️ Error calling server: {exc}"

            st.markdown(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
