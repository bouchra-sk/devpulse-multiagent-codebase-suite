
# ⚡ IBM Developer Copilot Platform

## 1. Project Overview

IBM Developer Copilot Platform is a multi-agent-based platform designed to facilitate the understanding, analysis, and improvement of software projects.

It offers two main modes:

- **Type 1: Codebase Understanding & Onboarding** — Understanding the architecture and exploring an existing codebase.
- **Type 2: Multi-Agent PR Reviewer** — Security analysis, code review, and refactoring.

The project uses Python, FastAPI, and Streamlit, with a planned integration of IBM Bob 2.0 for generative AI tasks.

---

## 2. Project Objectives

- Facilitate the onboarding of new developers into an existing project.
- Automatically understand the organization and architecture of a codebase.
- Detect security vulnerabilities and code quality issues.
- Suggest improvements based on Clean Code principles.
- Explore multi-agent architectures, RAG, Zero-Shot Prompting, and Meta-Prompting.

---

## 3. General Architecture

The platform is organized around two complementary modes.

### Type 1 — Codebase Understanding & Onboarding

This mode uses three specialized agents.

#### Agent 1: Indexing & Parsing Agent

**Role:** Receive a ZIP archive of the project, analyze its directory structure, and prepare the data required for contextual search.

**Features:**
- Extract project files.
- Analyze the directory structure (Folder Tree).
- Split the source code into chunks (Chunking).
- Index the content for RAG-based retrieval.
- Prepare the context required for codebase analysis.

**Techniques:** Parsing, Chunking, and Retrieval-Augmented Generation (RAG).

#### Agent 2: Architecture Summarizer Agent

**Role:** Analyze codebase information to produce an architectural summary of the project.

**Information analyzed:**
- Organization of folders and modules.
- Technologies and dependencies used.
- Entry points (main.py, routes, and endpoints).
- Relationships between components.
- Guidance on navigating and modifying the project.

**Planned technique:** Meta-Prompting with the role of a Software Architect, combined with RAG-based contextual retrieval.

#### Agent 3: Codebase Q&A Copilot Agent

**Role:** Answer developers' questions based on the indexed source code.

**Features:**
- Retrieve relevant information from the codebase.
- Extract relevant files and code snippets.
- Answer questions about the project's architecture and functionality.
- Display the sources used.

**Techniques:** RAG, Zero-Shot Prompting, and Few-Shot Prompting.

---

### Type 2 — Multi-Agent PR Reviewer

This mode relies on a sequential workflow involving two specialized agents.

#### Agent 4: Security & Quality Agent

**Role:** Analyze submitted code and detect security and quality issues.

**Examples of targeted issues:**
- Hardcoded credentials and passwords.
- Dangerous dynamic execution using eval().
- Potential SQL injection vulnerabilities.
- Syntax errors and code quality issues.

**Output:** A structured report containing detected rules, severity levels, affected lines, and recommendations.

**Technique:** Rule-based analysis using regular expressions and AST, depending on the implemented rules. Zero-Shot Prompting is planned for LLM-based analysis.

#### Agent 5: IBM Bob Refactoring Agent

**Role:** Receive the source code and findings from Agent 4 to propose an improved and more secure version.

**Objectives:**
- Fix detected issues.
- Improve readability and maintainability.
- Apply Clean Code principles.
- Preserve the program's functional behavior.

**Planned technique:** Role-based Meta-Prompting using the role of a Senior Software Engineer with IBM Bob 2.0.

---

## 4. System Workflow

### Type 1 — Codebase Exploration

1. The developer uploads a ZIP archive.
2. Agent 1 extracts, analyzes, and indexes the files.
3. Agent 2 uses the codebase context to generate an architectural summary.
4. Agent 3 answers questions using RAG-based retrieval.

### Type 2 — Automated Code Review

The workflow follows these steps:

```text
Python Source Code
        |
        v
+-------------------------+
| Agent 4                 |
| Security & Quality      |
| Code Audit              |
+-------------------------+
        |
        | Code + Findings
        v
+-------------------------+
| Agent 5                 |
| Refactoring Agent       |
| Improved Code           |
+-------------------------+
        |
        | Refactored Code
        v
+-------------------------+
| Streamlit Interface     |
| Display of Results      |
+-------------------------+
```

---

## 5. Technologies Used

| Category | Technologies |
|---|---|
| Main Programming Language | Python |
| Backend | FastAPI |
| Frontend | Streamlit |
| API Communication | Requests, REST API, JSON |
| Contextual Retrieval | RAG |
| Code Analysis | Parsing, Regex, AST |
| Planned Generative AI | IBM Bob 2.0 / LLM |
| Configuration Management | Environment Variables (.env) |

---

## 6. Project Structure

```text
project/
│
├── backend/
│   ├── main.py
│   │
│   ├── Agent1/
│   │   ├── parsing.py
│   │   └── rag.py
│   │
│   ├── Agent2/
│   │   └── architecture_agent.py
│   │
│   ├── Agent3/
│   │   └── ...
│   │
│   ├── Agent4/
│   │   └── ...
│   │
│   ├── Agent5/
│
├── frontend/
│   └── app.py
│
├── requirements.txt
├── .gitignore
└── README.md
```



---

## 7. Installation and Setup

### Prerequisites

- Python 3.11 or a compatible version.
- pip.
- Git.
- Visual Studio Code or IBM IDE 2.0.2.

### Step 1: Clone the Repository

```bash
git clone <GITHUB_REPOSITORY_URL>
cd <PROJECT_NAME>
```

### Step 2: Create a Virtual Environment

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Start the Backend

From the project root directory:

```bash
uvicorn backend.main:app --reload --port 8000
```

Interactive FastAPI documentation:

http://localhost:8000/docs

### Step 5: Start the Frontend

In a second terminal:

```bash
streamlit run frontend/app.py
```

Streamlit interface:

http://localhost:8501

---

## 8. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/index` | Upload and index a ZIP project |
| GET | `/health` | Check the backend status |
| GET | `/tree/{project_id}` | Retrieve the project directory tree |
| POST | `/architecture/{project_id}` | Generate an architectural summary |
| POST | `/ask/{project_id}` | Codebase questions and answers |
| POST | `/api/v1/review` | Security and quality audit |
| POST | `/api/v1/refactor` | Code refactoring |

---

## 9. User Interface

The Streamlit application provides two main pages:

### Home

Introduction to the platform and access to the workspace.

### Workspace

- Upload a ZIP project.
- Index and explore the codebase (Type 1).
- Text area for submitting Python code (Type 2).
- Display results in tabs:
  - Security Report.
  - Refactored Code.

---