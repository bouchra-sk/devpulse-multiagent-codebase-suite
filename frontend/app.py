import streamlit as st
from streamlit_option_menu import option_menu
import time
import re
import requests

# ─────────────────────────────────────────────────────────────
# 0. BACKEND CONFIG
# ─────────────────────────────────────────────────────────────
# URL du backend FastAPI (Agent 1 : Indexing & Parsing Agent).
# En local, uvicorn tourne par défaut sur le port 8000.
BACKEND_URL = "http://localhost:8000"

# ─────────────────────────────────────────────────────────────
# 1. PAGE CONFIGURATION & STYLING
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IBM Developer Copilot Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3 {
        color: #F8FAFC !important;
    }
    
    .gradient-text {
        background: linear-gradient(135deg, #4A90E2 0%, #50E3C2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }

    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(12px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        margin-bottom: 20px;
    }
    
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
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# 2. SESSION STATE & HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""
if 'selected_page' not in st.session_state:
    st.session_state.selected_page = "Home"
if 'show_modal' not in st.session_state:
    st.session_state.show_modal = False
if 'last_project_id' not in st.session_state:
    st.session_state.last_project_id = None

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

# ─────────────────────────────────────────────────────────────
# 3. AUTHENTICATION DIALOG (MODAL)
# ─────────────────────────────────────────────────────────────
@st.dialog("🔐 Sign in / Register to Access Platform")
def login_modal():
    st.write("Please authenticate with a valid email or your Google account to access your workspace and history.")
    
    # Option A: Google Sign-In
    if st.button("🌐 Continue with Google", use_container_width=True):
        st.session_state.logged_in = True
        st.session_state.user_email = "developer@gmail.com"
        st.session_state.show_modal = False
        st.session_state.selected_page = "Workspace"
        st.success("Successfully logged in!")
        time.sleep(0.5)
        st.rerun()

    st.markdown("<div style='text-align: center; color: #64748B; margin: 10px 0;'>— OR —</div>", unsafe_allow_html=True)

    # Option B: Real Email Authentication
    email_input = st.text_input("Enter your real email address:", placeholder="name@company.com")
    password_input = st.text_input("Password:", type="password", placeholder="••••••••")

    if st.button("🔑 Sign In / Register with Email", use_container_width=True):
        if not email_input or not is_valid_email(email_input):
            st.error("Please enter a valid email address (e.g., user@domain.com).")
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
# 4. TOP NAVBAR
# ─────────────────────────────────────────────────────────────
col_logo, col_nav, col_auth = st.columns([3, 4, 2])

with col_logo:
    st.markdown('<h3 style="margin:0;"><span class="gradient-text">⚡ IBM Developer Copilot</span></h3>', unsafe_allow_html=True)

with col_nav:
    current_index = 0
    if st.session_state.selected_page == "Workspace":
        current_index = 1
    elif st.session_state.selected_page == "Dashboard":
        current_index = 2

    selected_page = option_menu(
        menu_title=None,
        options=["Home", "Workspace", "Dashboard"],
        icons=["house", "terminal", "grid"],
        default_index=current_index,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#50E3C2", "font-size": "14px"},
            "nav-link": {
                "font-size": "14px",
                "text-align": "center",
                "margin": "0px 4px",
                "color": "#94A3B8",
                "border-radius": "8px",
            },
            "nav-link-selected": {"background-color": "#1E293B", "color": "#50E3C2", "border": "1px solid #4A90E2"},
        }
    )
    st.session_state.selected_page = selected_page

with col_auth:
    if not st.session_state.logged_in:
        if st.button("🔑 Sign In", key="login_top_btn"):
            st.session_state.show_modal = True
    else:
        st.markdown(f"🟢 `<{st.session_state.user_email}>`", unsafe_allow_html=True)
        if st.button("Log out", key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.selected_page = "Home"
            st.rerun()

# Trigger Modal if requested
if st.session_state.show_modal and not st.session_state.logged_in:
    login_modal()

st.markdown("---")

# ─────────────────────────────────────────────────────────────
# 5. PAGE ROUTING & SECURITY CONTROLS
# ─────────────────────────────────────────────────────────────

# --- PAGE 1: LANDING PAGE ---
if st.session_state.selected_page == "Home":
    col_hero = st.columns([1, 1], gap="large")
    
    with col_hero[0]:
        st.markdown("""
        <div style="padding-top: 20px;">
            <h1 style="font-size: 3rem; line-height: 1.2;">
                All-in-One <br><span class="gradient-text">Developer Copilot</span>
            </h1>
            <p style="font-size: 1.1rem; color: #94A3B8; margin-top: 20px;">
                Upload your codebase once to explore architecture, ask context questions, perform security audits, and generate PyTests.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("🚀 Start Analyzing Now", use_container_width=True):
                if not st.session_state.logged_in:
                    st.session_state.show_modal = True
                    st.rerun()
                else:
                    st.session_state.selected_page = "Workspace"
                    st.rerun()
        

    with col_hero[1]:
        st.markdown("""
        <div class="glass-card" style="text-align: center; padding: 40px;">
            <h3 class="gradient-text">🤖 Agentic AI Capabilities</h3>
            <p style="color: #94A3B8; font-size: 0.95rem; text-align: left; margin-top: 15px;">
                • <b>Codebase Q&A:</b> Deep context awareness using RAG.<br>
                • <b>PR Reviewer:</b> Vulnerability checks & Clean Code refactoring.<br>
                • <b>Auto-Test Suite:</b> Automatic PyTest execution generation.
            </p>
        </div>
        """, unsafe_allow_html=True)


# --- PAGE 2: WORKSPACE (RESTRICTED TO LOGGED IN USERS) ---
elif st.session_state.selected_page == "Workspace":
    if not st.session_state.logged_in:
        st.warning("🔒 Access Restricted! You must sign in with a valid email to access the Workspace.")
        if st.button("🔑 Sign In Now"):
            st.session_state.show_modal = True
            st.rerun()
    else:
        st.subheader("⚡ Unified Developer Workspace")
        st.caption(f"Connected as: {st.session_state.user_email}")

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "📁 Upload Code Files or Project Folder (.zip, .py, .js, .java, .cpp)",
            accept_multiple_files=True,
            type=["py", "js", "java", "cpp", "ts", "zip"]
        )
        
        code_text_input = st.text_area("OR Paste Code Snippet Directly:", height=120, placeholder="def example_function(): ...")
        st.markdown('</div>', unsafe_allow_html=True)

        if uploaded_files or code_text_input.strip():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("### 🎯 Select Execution Goal")
            
            action_mode = st.radio(
                "What would you like the agents to do?",
                [
                    "🔍 Option 1: Understand Codebase & Ask Questions (Onboarding Mode)",
                    "🛠️ Option 2: Security Audit, Auto-Fix Code & Generate PyTests (PR Reviewer Mode)",
                    "⚡ Option 3: Full AI Execution (Both Onboarding + Code Review)"
                ],
                index=0
            )
            st.markdown('</div>', unsafe_allow_html=True)

            if "Option 1" in action_mode:
                st.markdown("### 💬 Codebase Q&A & Architecture Assistant")

                # L'Agent 1 (backend) attend un .zip du projet.
                # On isole le premier fichier .zip parmi ceux uploadés.
                zip_file = next(
                    (f for f in (uploaded_files or []) if f.name.lower().endswith(".zip")),
                    None,
                )

                if uploaded_files and zip_file is None:
                    st.warning(
                        "Pour cette étape, l'Agent d'indexation a besoin d'un fichier "
                        "**.zip** du projet complet (pas de fichiers individuels)."
                    )

                if st.button(
                    "🔍 Indexer le projet",
                    use_container_width=True,
                    disabled=zip_file is None,
                ):
                    if zip_file is None:
                        st.error("Sélectionne d'abord un fichier .zip avant d'indexer.")
                    else:
                        with st.spinner("Extraction, découpage et indexation du code en cours..."):
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
                                st.session_state.last_project_id = result["project_id"]

                                st.success(
                                    f"Projet indexé : {result['nb_files_indexed']} fichiers, "
                                    f"{result['nb_chunks_indexed']} chunks."
                                )
                                with st.expander("📂 Arborescence du projet"):
                                    st.code(result["folder_tree"], language="text")

                            except requests.exceptions.ConnectionError:
                                st.error(
                                    "Impossible de contacter le backend. Vérifie que le serveur "
                                    "tourne bien (`uvicorn main:app --reload --port 8000`)."
                                )
                            except Exception as e:
                                st.error(f"Erreur lors de l'indexation : {e}")

                st.markdown("---")
                user_question = st.text_input(
                    "Pose une question sur ce codebase :",
                    placeholder="ex: Comment fonctionne l'authentification ?",
                )
                if st.button("Poser la question", use_container_width=True):
                    if st.session_state.last_project_id is None:
                        st.warning("Indexe d'abord un projet avant de poser une question.")
                    elif not user_question.strip():
                        st.warning("Écris une question avant de cliquer sur le bouton.")
                    else:
                        with st.spinner(
                            "Recherche RAG & génération de la réponse par l'Agent 3..."
                        ):
                            try:
                                response = requests.post(
                                    f"{BACKEND_URL}/ask/{st.session_state.last_project_id}",
                                    json={"question": user_question},
                                    timeout=120,
                                )
                                response.raise_for_status()
                                result = response.json()
                                st.markdown("### 🤖 Réponse de l'Agent 3 (Copilot Q&A)")
                                st.write(result["answer"])
                            except requests.exceptions.ConnectionError:
                                st.error(
                                    "Impossible de contacter le backend. Vérifie que le serveur "
                                    "FastAPI fonctionne sur le port 8000."
                                )
                            except requests.exceptions.HTTPError as error:
                              response_error = error.response

                              if response_error is not None:
                               status_code = response_error.status_code
                               error_text = response_error.text

                               st.error(
                                  f"Erreur HTTP ({status_code}) : {error_text}"
                                     )
                              else:
                               st.error(f"Erreur HTTP : {error}")
                            except requests.exceptions.RequestException as error:
                                st.error(f"Erreur lors de la requête vers l'Agent 3 : {error}")
                            except KeyError:
                                st.error(
                                    "Réponse invalide du backend : le champ 'answer' est absent."
                                )

            elif "Option 2" in action_mode:
                if st.button("⚡ Run Security Audit & Generate Tests", use_container_width=True):
                    with st.spinner("Running review pipeline..."):
                        time.sleep(1)
                        st.success("Review & Test Generation Complete!")

            elif "Option 3" in action_mode:
                if st.button("🚀 Run Full Multi-Agent Suite", use_container_width=True):
                    with st.spinner("Running full agent execution..."):
                        time.sleep(1.5)
                        st.success("All tasks completed successfully!")


# --- PAGE 3: DASHBOARD & HISTORY (RESTRICTED TO LOGGED IN USERS) ---
elif st.session_state.selected_page == "Dashboard":
    if not st.session_state.logged_in:
        st.error("🔒 History Protected! Please sign in with your email to view your previously uploaded folders and reviews.")
        if st.button("🔑 Sign In to View History"):
            st.session_state.show_modal = True
            st.rerun()
    else:
        st.subheader("📊 Your Uploaded Folders & Past Reviews")
        st.caption(f"Showing saved history for {st.session_state.user_email}")
        
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        
        reviews_data = [
            {"Folder/File Name": "src/auth_service/", "Language": "Python", "Date": "2026-09-20", "Status": "Analyzed"},
            {"Folder/File Name": "frontend/components/", "Language": "TypeScript", "Date": "2026-09-19", "Status": "Analyzed"},
            {"Folder/File Name": "payment_gateway.zip", "Language": "Java", "Date": "2026-09-15", "Status": "Reviewed"},
        ]
        
        for item in reviews_data:
            col_f, col_l, col_d, col_s, col_act = st.columns([3, 1, 1, 1, 2])
            col_f.write(f"📁 **{item['Folder/File Name']}**")
            col_l.write(item['Language'])
            col_d.write(item['Date'])
            col_s.write(f"🟢 {item['Status']}")
            if col_act.button("Open Folder History", key=item['Folder/File Name']):
                st.info(f"Loading history for {item['Folder/File Name']}...")
            st.markdown("<hr style='margin: 5px 0; border-color: #334155;'>", unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)