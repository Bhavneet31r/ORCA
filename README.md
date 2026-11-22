# ORCA Prompt-Engineering Prototype

ORCA is a Flask app for ocean-science questions and location-aware coastal information.

## Run locally

```powershell
Set-Location "E:\STUDY\ORCA"
& ".\.venv\bin\python.exe" .\main.py
```

Open http://127.0.0.1:5000/ and the Prompt Laboratory at
http://127.0.0.1:5000/prompt-lab.

## Gemini 2.5 Flash

Set `GEMINI_API_KEY` in the server environment, or set `GOOGLE_API_KEY`.
The key is never stored in project source or sent by the browser.

The lab demonstrates:
- Zero-shot prompting
- Few-shot prompting
- Role and task prompting
- Structured output
- Prompt-injection defense
- Uncertainty and safety constraints

## Prompt evidence

- `/api/prompt-engineering` returns the version log and test table.
- `/api/prompt-run` executes the Gemini-backed or explicit-not-configured fallback.
- `prompt_engineering.py` contains three intentionally different prompt versions.
- The prompt lab contains 12 normal, edge, and invalid test inputs.
