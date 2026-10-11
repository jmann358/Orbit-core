# Running Luna 0.1 locally (Mac or computer with Python 3.10+)

This phase stores code in GitHub only. Running it requires a Python environment. It does **not** run inside the GitHub iPad app.

1. Clone the repository and open a terminal in the project directory.
2. Create and activate a Python virtual environment: `python3 -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Start Luna: `uvicorn app:app --host 127.0.0.1 --port 8000`
5. On that same computer, open `http://127.0.0.1:8000`.

Without a model configured, Luna responds with a setup notice. To connect a **local** OpenAI-compatible model endpoint, set `LUNA_MODEL_URL` (including /v1) and `LUNA_MODEL_NAME` before launching.

**Security:** This is a local development prototype with no authentication. Never expose port 8000 publicly, use port forwarding, or bind to 0.0.0.0. Cloud memory and remote access are not yet implemented. Do not put secrets or personal conversation data into GitHub.

## Optional cloud AI (opt-in)

Cloud AI is not enabled automatically. A supported provider is needed, and free-tier limits and availability vary. Start with Groq if its free developer tier is available to your account. Sign up directly at https://console.groq.com/keys and create an API key. Never paste the key into chat or commit it to GitHub.

On Linux, from the Orbit-core folder with the virtual environment activated:

```bash
git pull
export LUNA_MODEL_URL="https://api.groq.com/openai/v1"
export LUNA_MODEL_NAME="YOUR_AVAILABLE_GROQ_MODEL_ID"
read -rsp "Paste your API key (hidden): " LUNA_API_KEY; echo
export LUNA_API_KEY
uvicorn app:app --host 127.0.0.1 --port 8000
```

Replace YOUR_AVAILABLE_GROQ_MODEL_ID with a currently available chat model ID listed in your provider dashboard. These environment variables apply only to this terminal session; the key is not written to a file or GitHub. Cloud model requests transmit up to 20 recent messages from the current session to the chosen provider. Review the provider's privacy and retention policies before sending sensitive information. Never expose this unauthenticated prototype to the public internet. The database remains local, not in the cloud.

Other supported OpenAI-compatible HTTPS endpoints include api.openai.com, api.together.xyz, and openrouter.ai, subject to their own accounts, pricing, API paths and model IDs. Free use is not guaranteed. Local HTTP models on localhost remain supported.
