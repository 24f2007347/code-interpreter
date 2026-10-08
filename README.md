# Code Interpreter with AI Error Analysis

A minimal FastAPI service that runs submitted Python code and, when the code fails,
asks an OpenAI-compatible model (via AIPipe) to analyze the error.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/code-interpreter` | Run Python code. Body: `{"code": "print(2 + 3)"}` |
| GET | `/health` | Returns `{"status": "ok"}` |

### Success response
The AI model is **not** called. `output` is exactly the code's stdout.

```json
{"success": true, "output": "5\n", "stdout": "5\n", "stderr": "", "result": "5\n", "error": []}
```

### Error response
```json
{
  "success": false,
  "stdout": "",
  "stderr": "Traceback (most recent call last):\n  File \"<user_code>\", line 2, in <module>\n...",
  "traceback": "...",
  "result": "...",
  "error": [2],
  "analysis": {
    "error_type": "ZeroDivisionError",
    "error_message": "division by zero",
    "line_number": 2,
    "explanation": "..."
  }
}
```

`error` is the list of line numbers (taken from the real traceback of the user's code).

## Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Set AIPIPE_TOKEN

The token is read from the environment and is never stored in code.

```bash
export AIPIPE_TOKEN="your-token-here"        # macOS/Linux
$env:AIPIPE_TOKEN="your-token-here"          # Windows PowerShell
```

## Run locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Test

```bash
# success
curl -X POST http://localhost:8000/code-interpreter \
  -H "Content-Type: application/json" \
  -d '{"code": "print(2 + 3)"}'

# error (calls the AI)
curl -X POST http://localhost:8000/code-interpreter \
  -H "Content-Type: application/json" \
  -d '{"code": "x = 1\nprint(x / 0)"}'

# health
curl http://localhost:8000/health
```

Run the automated tests (no token needed):

```bash
pip install pytest httpx
pytest -q
```

## Deploy on Render

1. Push these files to a GitHub repository.
2. On Render: **New +** > **Web Service** > connect the repo.
3. Settings:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Under **Environment**, add `AIPIPE_TOKEN` = your AIPipe token.
5. Deploy. Your endpoint to submit is:
   `https://<your-service-name>.onrender.com/code-interpreter`
