from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import tempfile, shutil
import subprocess

from agents import (
    run_code, debug_patch, critic_review, forecast_failures,
    generate_unit_tests, run_generated_tests
)

FILE_DIR = Path(__file__).parent.resolve()  
FILE_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Smart-Code-Lab API")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeRequest(BaseModel):
    code: str                 
    filename: str = "user.py" 
    user_prompt: str | None = None  

class AgentSelection(BaseModel):
    run: bool      = False
    debug: bool    = False
    clean: bool    = False
    forecast: bool = False
    tests: bool    = False

class AnalyzeRequest(BaseModel):
    code_request: CodeRequest
    agents:       AgentSelection

def _save_code(code: str, filename: str) -> Path:
    path = FILE_DIR / filename
    path.write_text(code, encoding="utf-8")
    return path

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    path = _save_code(req.code_request.code, req.code_request.filename)

    response = {
        "filename": path.name,
        "forecast": None,
        "run":      {},  
        "debug":    {},  
        "clean":    {"reasoning": None, "improved_code": None},
        "tests":    {"test_file": None, "pytest_output": None},
        "final_code": None,  
    }

    if req.agents.forecast:
        response["forecast"] = forecast_failures(path.read_text(encoding="utf-8"), req.code_request.user_prompt)

    if req.agents.run or req.agents.debug:
        code_path = path
        code_text = path.read_text(encoding="utf-8")

        for round_i in range(1, 6):  
            out, err = run_code(code_path)
            response["run"][f"run{round_i}"] = {"stdout": out, "stderr": err}

            if not err:
                response["final_code"] = code_text
                break  

            if req.agents.debug:
                reasoning, fixed = debug_patch(code_text, err, req.code_request.user_prompt)
                response["debug"][f"debug{round_i}"] = {
                    "reasoning": reasoning,
                    "fixed_code": fixed,
                }

                if fixed:
                    code_path.write_text(fixed, encoding="utf-8")
                    code_text = fixed
                else:
                    break  

    if req.agents.clean:
        reasoning, improved = critic_review(path.read_text(encoding="utf-8"), req.code_request.user_prompt)
        response["clean"]["reasoning"]      = reasoning
        response["clean"]["improved_code"]  = improved
        if improved:
            critic_path = path.with_name(path.stem + "_critic.py")
            critic_path.write_text(improved, encoding="utf-8")

            out, err = run_code(critic_path)
            if not err:
                final_path = path.with_name(path.stem + "_cleaned.py")
                shutil.copy(critic_path, final_path)
                response["clean"]["cleaned_file"] = final_path.name
                response["clean"]["critic_file"] = critic_path.name
            else:
                response["clean"]["error_in_critic"] = err[:500]

    if req.agents.tests:
        test_code = generate_unit_tests(path.read_text(encoding="utf-8"), path.stem, req.code_request.user_prompt)

        if test_code:
            test_file = path.with_name(f"test_{path.stem}.py")
            test_file.write_text(test_code, encoding="utf-8")

            code_path = path
            code_text = path.read_text(encoding="utf-8")
            test_history = {}
            debug_history = {}

            for round_i in range(1, 6):  
                result = subprocess.run(
                    ["pytest", str(test_file), "--disable-warnings", "-q", "--tb=short", "--maxfail=5"],
                    cwd=code_path.parent,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                test_output = result.stdout.strip()
                test_history[f"test{round_i}"] = test_output

                if "FAILED" not in test_output:
                    response["final_code"] = code_text
                    break  

                reasoning, fixed = debug_patch(code_text, test_output, req.code_request.user_prompt)
                debug_history[f"debug{round_i}"] = {
                    "reasoning": reasoning,
                    "fixed_code": fixed
                }

                if fixed:
                    code_text = fixed
                    code_path.write_text(fixed, encoding="utf-8")
                else:
                    break  

            response["tests"]["test_file"] = test_file.name
            response["tests"]["test_code"] = test_code
            response["tests"]["pytest_rounds"] = test_history
            response["debug"]["test_debugs"] = debug_history

        else:
            response["tests"]["pytest_output"] = "Test generation failed."

    return response
