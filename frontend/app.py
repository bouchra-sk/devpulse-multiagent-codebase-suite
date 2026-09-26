import time
import re
import requests
import streamlit as st
from streamlit_option_menu import option_menu

# ─────────────────────────────────────────────────────────────
# 0. BACKEND CONFIGURATION
# ─────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:8000"

# ─────────────────────────────────────────────────────────────
# 1. PAGE CONFIGURATION & STYLES
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IBM Developer Copilot Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* Main app background */
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3 {
        color: #F8FAFC !important;
    }

    /* 1. FIX LABELS: target the REAL Streamlit container (stWidgetLabel) */
    [data-testid="stWidgetLabel"] p {
        color: #FFFFFF !important;
        font-size: 1.15rem !important;
        font-weight: 600 !important;
    }

    /* 2. FIX MODAL (st.dialog): dark background + high-contrast white text */
    div[data-testid="stDialog"] {
        background-color: rgba(15, 23, 42, 0.8) !important;
    }
    div[data-testid="stDialog"] > div {
        background-color: #1E293B !important;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
    }
    div[data-testid="stDialog"] p,
    div[data-testid="stDialog"] label,
    div[data-testid="stDialog"] h1,
    div[data-testid="stDialog"] h2,
    div[data-testid="stDialog"] h3,
    div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p {
        color: #F8FAFC !important;
    }

    /* 3. Radio group title ("What should the agents run?") */
    div[data-testid="stRadio"] > label [data-testid="stWidgetLabel"] p {
        color: #50E3C2 !important;
        font-size: 1.2rem !important;
        font-weight: 700 !important;
    }

    /* 4. Radio button options (Option 1, Option 2, Option 3) */
    div[data-testid="stRadio"] div[role="radiogroup"] label p {
        color: #F8FAFC !important;
        font-size: 1.05rem !important;
        font-weight: 500 !important;
    }

    /* Glassmorphism cards */
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(12px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        margin-bottom: 20px;
    }
    
    .gradient-text {
        background: linear-gradient(135deg, #4A90E2 0%, #50E3C2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #4A90E2 0%, #3B82F6 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 10px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #50E3C2 0%, #10B981 100%);
        color: #0F172A;
        box-shadow: 0 6px 20px rgba(80, 227, 194, 0.4);
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Fix text visibility in code input */
[data-testid="stTextArea"] textarea {
    background-color: #ffffff !important;
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    caret-color: #000000 !important;

    font-family: Consolas, "Courier New", monospace !important;
    font-size: 15px !important;
    line-height: 1.5 !important;
}

/* Placeholder text */
[data-testid="stTextArea"] textarea::placeholder {
    color: #64748B !important;
    opacity: 1 !important;
}
</style>
""", unsafe_allow_html=True)
# ─────────────────────────────────────────────────────────────
# 2. SESSION STATE & UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "Home"
if "show_modal" not in st.session_state:
    st.session_state.show_modal = False
if "last_project_id" not in st.session_state:
    st.session_state.last_project_id = None


def is_valid_email(email: str) -> bool:
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None


# ─────────────────────────────────────────────────────────────
# 3. AUTHENTICATION MODAL
# ─────────────────────────────────────────────────────────────
@st.dialog("🔐 Log In / Sign Up to the platform")
def login_modal():
    st.write(
        "Please authenticate with a valid email address or your Google account to access your workspace."
    )

    if st.button("🌐 Continue with Google", use_container_width=True):
        st.session_state.logged_in = True
        st.session_state.user_email = "developer@gmail.com"
        st.session_state.show_modal = False
        st.session_state.selected_page = "Workspace"
        st.success("Login successful!")
        time.sleep(0.5)
        st.rerun()

    st.markdown(
        "<div style='text-align: center; color: #64748B; margin: 10px 0;'>— OR —</div>",
        unsafe_allow_html=True,
    )

    email_input = st.text_input(
        "Enter your email address:", placeholder="name@company.com"
    )
    password_input = st.text_input(
        "Password:", type="password", placeholder="••••••••"
    )

    if st.button("🔑 Log In / Sign Up with Email", use_container_width=True):
        if not email_input or not is_valid_email(email_input):
            st.error("Please enter a valid email address.")
        elif len(password_input) < 6:
            st.error("Password must be at least 6 characters long.")
        else:
            st.session_state.logged_in = True
            st.session_state.user_email = email_input
            st.session_state.show_modal = False
            st.session_state.selected_page = "Workspace"
            st.success("Authentication successful!")
            time.sleep(0.5)
            st.rerun()


# ─────────────────────────────────────────────────────────────
# 4. TOP NAVIGATION BAR
# ─────────────────────────────────────────────────────────────
col_logo, col_nav, col_auth = st.columns([3, 4, 2])

with col_logo:
    st.markdown(
        '<h3 style="margin:0;"><span class="gradient-text">⚡ IBM Developer Copilot</span></h3>',
        unsafe_allow_html=True,
    )

with col_nav:
    current_index = 0
    if st.session_state.selected_page == "Workspace":
        current_index = 1
    
    selected_page = option_menu(
        menu_title=None,
        options=["Home", "Workspace"],
        icons=["house", "terminal", "grid"],
        default_index=current_index,
        orientation="horizontal",
        styles={
            "container": {
                "padding": "0!important",
                "background-color": "transparent",
            },
            "icon": {"color": "#50E3C2", "font-size": "14px"},
            "nav-link": {
                "font-size": "14px",
                "text-align": "center",
                "margin": "0px 4px",
                "color": "#94A3B8",
                "border-radius": "8px",
            },
            "nav-link-selected": {
                "background-color": "#1E293B",
                "color": "#50E3C2",
                "border": "1px solid #4A90E2",
            },
        },
    )
    st.session_state.selected_page = selected_page

with col_auth:
    if not st.session_state.logged_in:
        if st.button("🔑 Log In", key="login_top_btn"):
            st.session_state.show_modal = True
    else:
        st.markdown(
            f"🟢 `<{st.session_state.user_email}>`", unsafe_allow_html=True
        )
        if st.button("Log Out", key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.selected_page = "Home"
            st.rerun()

if st.session_state.show_modal and not st.session_state.logged_in:
    login_modal()

st.markdown("---")

# ─────────────────────────────────────────────────────────────
# 5. PAGE ROUTING
# ─────────────────────────────────────────────────────────────

# --- PAGE 1: HOME ---
if st.session_state.selected_page == "Home":
    col_hero = st.columns([1, 1], gap="large")

    with col_hero[0]:
        st.markdown(
            """
        <div style="padding-top: 20px;">
            <h1 style="font-size: 3rem; line-height: 1.2;">
                All-in-One <br><span class="gradient-text">Developer Copilot</span>
            </h1>
            <p style="font-size: 1.1rem; color: #94A3B8; margin-top: 20px;">
                Upload your codebase once to explore its architecture, ask contextual questions, run security audits.
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        c1, _ = st.columns([1, 1])
        with c1:
            if st.button("🚀 Start the analysis", use_container_width=True):
                if not st.session_state.logged_in:
                    st.session_state.show_modal = True
                    st.rerun()
                else:
                    st.session_state.selected_page = "Workspace"
                    st.rerun()

    with col_hero[1]:
        st.markdown(
            """
        <div class="glass-card" style="text-align: center; padding: 40px;">
            <h3 class="gradient-text">🤖 Agentic AI Capabilities</h3>
            <p style="color: #94A3B8; font-size: 0.95rem; text-align: left; margin-top: 15px;">
                • <b>Codebase Q&A:</b> Advanced contextual understanding via RAG.<br>
                • <b>PR Reviewer:</b> Vulnerability detection and Clean Code refactoring.<br>
                • <b>Auto-Test Suite:</b> Automatic generation and execution of PyTest tests.
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )


# --- PAGE 2: WORKSPACE ---
elif st.session_state.selected_page == "Workspace":
    if not st.session_state.logged_in:
        st.warning(
            "🔒 Restricted access! You must log in to access the Workspace."
        )
        if st.button("🔑 Log In"):
            st.session_state.show_modal = True
            st.rerun()
    else:
        st.subheader("⚡ Developer Workspace")
        st.caption(f"Logged in as: {st.session_state.user_email}")

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "📁 Upload your code files or project archive ",
            accept_multiple_files=True,
            type=["zip"],
        )

        code_text_input = st.text_area(
            "OR paste a code snippet directly:",
            height=120,
            placeholder="def example_function(): ...",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if uploaded_files or code_text_input.strip():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("### 🎯 Choose the desired action")

            action_mode = st.radio(
                "What should the agents run?",
                [
                    "🔍 Option 1: Understand the project & Ask questions (Onboarding)",
                    "🛠️ Option 2: Security audit, Refactoring (PR Reviewer)",
                ],
                index=0,
            )
            st.markdown("</div>", unsafe_allow_html=True)

            if "Option 1" in action_mode:
                st.markdown(
                    "### 💬 Architecture Assistant & Q&A"
                )

                zip_file = next(
                    (
                        f
                        for f in (uploaded_files or [])
                        if f.name.lower().endswith(".zip")
                    ),
                    None,
                )

                if uploaded_files and zip_file is None:
                    st.warning(
                        "For RAG indexing, please provide a **.zip** file containing the project."
                    )

                if st.button(
                    "🔍 Index the project",
                    use_container_width=True,
                    disabled=zip_file is None,
                ):
                    if zip_file is None:
                        st.error(
                            "Select a .zip file before indexing."
                        )
                    else:
                        with st.spinner(
                            "Extracting, chunking, and indexing the code..."
                        ):
                            try:
                                response = requests.post(
                                    f"{BACKEND_URL}/index",
                                    files={
                                        "file": (
                                            zip_file.name,
                                            zip_file.getvalue(),
                                            "application/zip",
                                        )
                                    },
                                    timeout=120,
                                )
                                response.raise_for_status()
                                result = response.json()
                                st.session_state.last_project_id = result[
                                    "project_id"
                                ]

                                st.success(
                                    f"Project indexed successfully: {result['nb_files_indexed']} files, "
                                    f"{result['nb_chunks_indexed']} chunks."
                                )
                                with st.expander(
                                    "📂 Indexed project structure"
                                ):
                                    st.code(
                                        result["folder_tree"], language="text"
                                    )

                            except requests.exceptions.ConnectionError:
                                st.error(
                                    "Unable to reach the backend server. Check that FastAPI is running on port 8000."
                                )
                            except Exception as e:
                                st.error(f"Error during indexing: {e}")

                st.markdown("---")
                user_question = st.text_input(
                    "Ask a question about the codebase:",
                    placeholder="e.g., How does the database management work?",
                )

                if st.button("Ask the question", use_container_width=True):
                    if st.session_state.last_project_id is None:
                        st.warning(
                            "Index a .zip project first before asking a question."
                        )
                    elif not user_question.strip():
                        st.warning("Please enter a valid question.")
                    else:
                        with st.spinner(
                            "Retrieving information & generating the answer..."
                        ):
                            try:
                                response = requests.post(
                                    f"{BACKEND_URL}/ask/{st.session_state.last_project_id}",
                                    json={"question": user_question},
                                    timeout=120,
                                )
                                response.raise_for_status()
                                result = response.json()

                                st.markdown("### 🤖 Copilot's Answer")
                                st.write(result.get("answer", ""))

                                sources = result.get("sources", [])
                                if sources:
                                    st.caption(
                                        f"{len(sources)} source file(s):"
                                    )
                                    for src in sources:
                                        snippets = src.get("snippets", [])
                                        label = f"📄 {src.get('file', 'Unknown file')}"
                                        if len(snippets) > 1:
                                            label += f" ({len(snippets)} snippets)"
                                        with st.expander(label):
                                            for i, snippet in enumerate(snippets, start=1):
                                                if len(snippets) > 1:
                                                    st.caption(f"Snippet {i}/{len(snippets)}")
                                                st.code(snippet, language="python")

                            except requests.exceptions.ConnectionError:
                                st.error(
                                    "Connection error with the backend server (port 8000)."
                                )
                            except requests.exceptions.HTTPError as error:
                                st.error(f"HTTP Error: {error}")
                            except Exception as error:
                                st.error(f"Unexpected error: {error}")

            elif "Option 2" in action_mode:
                st.markdown("### 🛠️ PR Reviewer: Security Audit")

                if not code_text_input.strip():
                    st.warning(
                        "Paste a code snippet in the text box above to run the "
                        "audit — Option 2 works on pasted code, not on an "
                        "indexed .zip project."
                    )
                elif st.button(
                    "⚡ Run the audit & refactoring",
                    use_container_width=True,
                ):
                    original_code = code_text_input.strip()

                    # Step 1/3: Agent 4 — Security & Quality Agent
                    with st.spinner("Step 1/2: Security and quality audit..."):
                        try:
                            review_resp = requests.post(
                                f"{BACKEND_URL}/api/v1/review",
                                json={"code": original_code, "language": "python"},
                                timeout=60,
                            )
                            review_resp.raise_for_status()
                            review_result = review_resp.json()
                        except requests.exceptions.ConnectionError:
                            st.error("Unable to reach the backend (port 8000).")
                            st.stop()
                        except requests.exceptions.HTTPError as error:
                            st.error(f"Error during audit: {error}")
                            st.stop()

                    findings = review_result.get("findings", [])

                    # Step 2/3: Agent 5 — Refactoring Agent
                    with st.spinner("Step 2/2: Refactoring the code..."):
                        try:
                            refactor_resp = requests.post(
                                f"{BACKEND_URL}/api/v1/refactor",
                                json={"code": original_code, "findings": findings},
                                timeout=120,
                            )
                            refactor_resp.raise_for_status()
                            refactor_result = refactor_resp.json()
                        except requests.exceptions.ConnectionError:
                            st.error("Unable to reach the backend (port 8000).")
                            st.stop()
                        except requests.exceptions.HTTPError as error:
                            st.error(f"Error during refactoring: {error}")
                            st.stop()

                    refactored_code = refactor_result.get("refactored_code", original_code)

                    
                    st.success("Pipeline complete: audit → refactoring.")

                    tab1, tab2 = st.tabs(
                        ["🔍 Security Report", "✨ Refactored Code"]
                    )

                    with tab1:
                        summary = review_result.get("summary", {})
                        col_a, col_b = st.columns(2)
                        col_a.metric("Quality score", f"{summary.get('score', '?')}/100")
                        col_b.metric("Risk level", str(summary.get("risk_level", "?")).upper())

                        if not findings:
                            st.success("✅ No issues detected.")
                        else:
                            for f in findings:
                                severity = f.get("severity", "low")
                                icon = "🔴" if severity == "high" else "🟠" if severity == "medium" else "🟡"
                                st.markdown(
                                    f"{icon} **[{f.get('rule_id')}] {f.get('title')}** "
                                    f"(line {f.get('line')})"
                                )
                                st.caption(f.get("recommendation", ""))
                                st.code(f.get("code", ""), language="python")

                    with tab2:
                        if refactor_result.get("mocked"):
                            st.info(refactor_result.get("changes_summary", ""))
                        else:
                            st.write(refactor_result.get("changes_summary", ""))
                        st.code(refactored_code, language="python")

                    
                        
                      
                           


        st.markdown("</div>", unsafe_allow_html=True)