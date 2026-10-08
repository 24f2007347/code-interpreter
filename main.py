import os
import re
import subprocess
import sys
import tempfile
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Code Interpreter with AI Error Analysis")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = "openai/gpt-4.1-nano"
EXEC_TIMEOUT_SECONDS = 10


class CodeRequest(BaseModel):
    code: str


class ErrorAnalysis(BaseModel):
    error_type: str
    error_message: str
    line_number: Optional[int] = None
    explanation: str


def execute_python_code(code: str) -> dict:
    """Run Python code in a separate interpreter; capture stdout, stderr, traceback, error line."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "user_code.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                timeout=EXEC_TIMEOUT_SECONDS,
                stdin=subprocess.DEVNULL,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            return {
                "success": False,
                "stdout": out,
                "stderr": f"TimeoutError: execution exceeded {EXEC_TIMEOUT_SECONDS} seconds",
                "traceback": f"TimeoutError: execution exceeded {EXEC_TIMEOUT_SECONDS} seconds",
                "line_number": None,
            }

        stderr = proc.stderr.replace(path, "<user_code>")
        if proc.returncode == 0:
            return {
                "success": True,
                "stdout": proc.stdout,
                "stderr": stderr,
                "traceback": "",
                "line_number": None,
            }

        # Last reference to the user's file in the traceback is the failing line.
        lines = re.findall(r'File "<user_code>", line (\d+)', stderr)
        line_number = int(lines[-1]) if lines else None
        return {
            "success": False,
            "stdout": proc.stdout,
            "stderr": stderr,
            "traceback": stderr,
            "line_number": line_number,
        }


def _fallback_analysis(traceback_text: str, line_number: Optional[int]) -> ErrorAnalysis:
    last = traceback_text.strip().splitlines()[-1] if traceback_text.strip() else "Error"
    err_type, _, err_msg = last.partition(":")
    return ErrorAnalysis(
        error_type=err_type.strip() or "Error",
        error_message=err_msg.strip(),
        line_number=line_number,
        explanation=f"The code raised {err_type.strip() or 'an error'}"
        + (f" on line {line_number}." if line_number else "."),
    )


def analyze_error(code: str, traceback_text: str, line_number: Optional[int]) -> ErrorAnalysis:
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ["AIPIPE_TOKEN"],
            base_url="https://aipipe.org/openai/v1",
        )
        completion = client.beta.chat.completions.parse(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze Python errors. Given code and its traceback, return the "
                        "error type, error message, the line number in the user's code where "
                        "the error occurred, and a short plain-English explanation with a fix."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Code:\n{code}\n\nTraceback:\n{traceback_text}\n\n"
                        f"The failing line number in the code is: {line_number}"
                    ),
                },
            ],
            response_format=ErrorAnalysis,
        )
        analysis = completion.choices[0].message.parsed
        if analysis is None:
            raise ValueError("empty parse")
        if line_number is not None:
            analysis.line_number = line_number  # trust the real traceback line
        return analysis
    except Exception:
        return _fallback_analysis(traceback_text, line_number)


@app.post("/code-interpreter")
def code_interpreter(req: CodeRequest):
    result = execute_python_code(req.code)

    if result["success"]:
        return {
            "success": True,
            "output": result["stdout"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "result": result["stdout"],
            "error": [],
        }

    analysis = analyze_error(req.code, result["traceback"], result["line_number"])
    return {
        "success": False,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "traceback": result["traceback"],
        "result": result["traceback"],
        "error": [result["line_number"]] if result["line_number"] is not None else [],
        "analysis": analysis.model_dump(),
    }


@app.get("/health")
def health():
    return {"status": "ok"}
