# AI Travel Guide

An AI-powered travel guide that creates destination descriptions with Google
Gemini and turns them into speech with Murf. The Flask backend serves both the
frontend and API, so the deployed app uses one origin.

## Requirements

- Python 3.10 or newer
- A Google Gemini API key
- A Murf API key

## Run locally on Windows

From the project root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Backend\requirements.txt
Copy-Item Backend\.env.example Backend\.env
notepad Backend\.env
```

Add your API keys to `Backend/.env`, then start the app:

```powershell
.\.venv\Scripts\python.exe Backend\app.py
```

Open <http://localhost:5000>. Do not commit `Backend/.env`; it contains
secrets and is excluded by `.gitignore`.

## Deploy on Render

1. Push this project to a GitHub repository. Keep `Backend/.env` out of Git.
2. In Render, create a **Blueprint** and select the repository containing
   `render.yaml`.
3. Set the `GEMINI_API_KEY` and `MURF_API_KEY` values when Render requests them.
4. Deploy. Render builds and starts the Flask app using the commands in
   `render.yaml`.
5. Open the generated `https://<service-name>.onrender.com` URL. Check
   `/health` to confirm that the service reports `"configured": true`.

The live app needs valid API keys configured as Render environment variables.
Never add API keys to frontend JavaScript or commit them to the repository.
