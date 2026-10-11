# Running Luna 0.1 locally (Mac or computer with Python 3.10+)

This phase stores code in GitHub only. Running it requires a Python environment. It does **not** run inside the GitHub iPad app.

1. Clone the repository and open a terminal in the project directory.
2. Create and activate a Python virtual environment: `python3 -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Start Luna: `uvicorn app:app --host 127.0.0.1 --port 8000`
5. On that same computer, open `http://127.0.0.1:8000`.

Without a model configured, Luna responds with a setup notice. To connect a **local** OpenAI-compatible model endpoint, set `LUNA_MODEL_URL` (including /v1) and `LUNA_MODEL_NAME` before launching.

**Security:** This is a local development prototype with no authentication. Never expose port 8000 publicly, use port forwarding, or bind to 0.0.0.0. Cloud memory and remote access are not yet implemented. Do not put secrets or personal conversation data into GitHub.
