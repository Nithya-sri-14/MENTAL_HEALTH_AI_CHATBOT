# Mental Health Agentic Chatbot

VS Code compatible Streamlit project for:

- Patient onboarding agent
- Psychological assessment agent
- Multi-language conversation agent
- Appointment scheduling agent
- RAG-based knowledge assistant
- Automated report generation
- Patient progress tracking
- Session summarization
- Secure document management
- Admin dashboard
- Role-based access control
- Audit logs
- Cloud deployment ready layout
- Multi-agent orchestration scaffold
- Emotion and sentiment analysis
- Risk detection and escalation
- Voice interaction scaffold
- WhatsApp message preview
- Clinical recommendation engine
- Analytics dashboard
- Predictive patient retention insights

This project is designed as a safe clinical workflow platform.
It does not diagnose and it does not replace a licensed psychologist.

## Run Locally

This application features a decoupled architecture consisting of a **FastAPI backend** (Port 8000) and a **Streamlit frontend** (Port 8501). Both services are started concurrently using the root-level orchestrator runner script `run.py`.

### Prerequisites
* Python 3.10 or 3.11 is recommended.
* Verify you are in the project root directory (`mental_health_agentic_chatbot`).

---

### Setup & Run on macOS / Linux

1. **Create a Virtual Environment**:
   ```bash
   python3 -m venv .venv
   ```
2. **Activate the Environment**:
   ```bash
   source .venv/bin/activate
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Start the Stack**:
   ```bash
   python run.py
   ```
   *(This script automatically launches both the FastAPI service and the Streamlit interface, streaming logs to your console. Press `Ctrl+C` to terminate both services cleanly.)*

---

### Setup & Run on Windows

1. **Create a Virtual Environment**:
   ```cmd
   python -m venv .venv
   ```
2. **Activate the Environment**:
   * **In Command Prompt (cmd.exe)**:
     ```cmd
     .venv\Scripts\activate.bat
     ```
   * **In PowerShell**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
3. **Install Dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```
4. **Start the Stack**:
   ```cmd
   python run.py
   ```
   *(Boots the FastAPI backend on http://127.0.0.1:8000 and the Streamlit dashboard on http://127.0.0.1:8501 concurrently.)*

---

### Accessing the Portal (Pre-Seeded Accounts)

Open your browser to [http://127.0.0.1:8501](http://127.0.0.1:8501) and log in with any of the following staging credentials:

| Username | Password | Role | Features |
| :--- | :--- | :--- | :--- |
| **admin** | admin123 | **Admin** | Full access + System Configuration & Audits |
| **psychologist** | psy123 | **Psychologist** | Full access + Clinical Screens, RAG Search, Reports, and Retention Insights |
| **assistant** | asst123 | **Assistant** | Onboarding Intake, Scheduling, and Document Uploads |
| **patient** | patient123 | **Patient** | Personal Dashboard, Chat Support, and Symptom Screening |

## Add knowledge documents

You can place documents in:

- `data/knowledge_base/`

Supported formats:

- `.txt`
- `.md`
- `.pdf`
- `.docx`

You can also upload files from the app.

## Patient data

The app starts with an empty patient registry.
Import a CSV with the required columns or create patient records in the UI.

## Voice

Voice support is scaffolded with optional transcription / TTS helpers.
If audio tooling is not available, the app falls back to transcript input.

## Security and governance

Included safeguards:

- consent gate
- redaction of obvious sensitive identifiers in logs
- risk escalation rules
- audit logging
- role-based feature access
- document type filtering
- moderation checks for dangerous content

## VS Code

Use `.vscode/launch.json` to run the Streamlit app from VS Code.

## Deployment

This layout is compatible with:

- Streamlit Community Cloud
- Docker
- ngrok tunnel deployment
- Colab-like environments after installing dependencies
