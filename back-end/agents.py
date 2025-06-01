# pip install -q radon gitpython requests rich
# pip install pytest pytest-cov

from __future__ import annotations
import os, subprocess, json, textwrap, tempfile, requests, shutil, time
from pathlib import Path
import os, subprocess, shutil, textwrap, tempfile, requests
from pathlib import Path
import difflib

# ----------------------------- Settings -------------------------------
FILE_PATH = Path("Test.py")                  
MAX_ROUNDS = 4
MODEL_ID   = "gpt-4o"                   
BASE_URL   = "https://api.tapsage.com/api/v1/wrapper/openai_chat_completion/chat/completions"
API_KEY    = "sorry😂"
HEADERS    = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
PISTON_URL = "https://emkc.org/api/v2/piston/execute"

# ----------------------------- RunnerAgent ----------------------------
def run_code(file_path: Path) -> tuple[str, str]:
    payload = {
        "language": "python",
        "version": "3.10.0",
        "files": [{"name": file_path.name, "content": file_path.read_text(encoding="utf-8")}],
    }

    res = requests.post(PISTON_URL, json=payload, timeout=120).json()
    out = res["run"]["stdout"].strip()
    err = res["run"]["stderr"].strip()

    return out, err

# ----------------------------- LLM Helper ----------------------------
def llm(messages: list[dict[str,str]], temperature: float = 0.2) -> str:
    payload = {"model": MODEL_ID, "messages": messages, "temperature": temperature}
    r = requests.post(BASE_URL, headers=HEADERS, json=payload, timeout=120)
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]

def debug_patch(code: str, trace: str, user_prompt: str | None = None) -> tuple[str, str] | tuple[None, None]:
    if user_prompt:
        extra = f"""
        If the user prompt below contains instructions relevant to debugging, incorporate them thoughtfully.
        Otherwise, ignore it and proceed normally.

        User Prompt:
        \"\"\"
        {user_prompt}
        \"\"\"
        """
    else:
        extra = "" 

    messages = [
        {"role": "system", "content": "You are DebuggerAgent, a careful Python bug fixer."},
        {"role": "user", "content": textwrap.dedent(extra + f"""
            The following code throws an error. Do the following:
            1. Give your reasoning for the fix, wrapped in ```reasoning
            2. Provide the full fixed version of the file wrapped in ```python

            ## Code
            ```python
            {code}
            ```

            ## Traceback
            ```
            {trace}
            ```
        """)}
    ]

    reply = llm(messages)

    reasoning, fixed_code = None, None
    blocks = reply.split("```")

    for b in blocks:
        if b.strip().startswith("reasoning"):
            reasoning = b.strip()[len("reasoning"):].strip()
        elif b.strip().startswith("python"):
            fixed_code = b.strip()[len("python"):].strip()

    return reasoning, fixed_code

def critic_review(code: str, user_prompt: str | None = None) -> tuple[str, str | None]:
    if user_prompt:
        extra = f"""
        If the user prompt below contains instructions relevant to critic review, incorporate them thoughtfully.
        Otherwise, ignore it and proceed normally.

        User Prompt:
        \"\"\"
        {user_prompt}
        \"\"\"
        """
    else:
        extra = ""

    messages = [
        {"role": "system", "content": "You are CriticAgent, a senior Python code reviewer and improver."},
        {"role": "user", "content": textwrap.dedent(extra + f"""
        Please do the following for the provided Python code:
        1. Analyze its quality in terms of:
           - Structure and modularity
           - Naming conventions
           - Readability and maintainability
           - Logical clarity and best practices

        2. Provide suggestions and explain them inside a ```reasoning block.

        3. If you can improve the code, return a full improved version inside a ```python block.

        Code:
        ```python
        {code}
        ```
        """)}
    ]

    reply = llm(messages)

    reasoning, improved_code = None, None
    blocks = reply.split("```")

    for b in blocks:
        if b.strip().startswith("reasoning"):
            reasoning = b.strip()[len("reasoning"):].strip()
        elif b.strip().startswith("python"):
            improved_code = b.strip()[len("python"):].strip()

    return reasoning or "(No reasoning provided)", improved_code


def apply_diff(file_path: Path, diff_text: str) -> bool:
    try:
        original = file_path.read_text(encoding="utf-8").splitlines(keepends=True)

        diff_lines = diff_text.splitlines(keepends=True)

        patched = list(difflib.restore(diff_lines, 1))  # 1 → نسخه پچ‌شده

        file_path.write_text("".join(patched))

        print("✅ Patch applied successfully (no Git).")
        return True
    except Exception as e:
        print(f"❌ Patch failed: {e}")
        return False

def try_run_and_fix_critic_code(original_code: str):
    reasoning, improved = critic_review(original_code)

    print("\n📚 CriticAgent reasoning:")
    print(reasoning)

    if not improved:
        print("🤷 No improved version provided.")
        return

    critic_path = FILE_PATH.with_name(FILE_PATH.stem + "_critic.py")
    critic_path.write_text(improved)
    print(f"💾 Critic code written to: {critic_path}")

    for attempt in range(1, MAX_ROUNDS + 1):
        print(f"\n🧪 Trying Critic code – Attempt {attempt}")
        out, err = run_code(critic_path)

        if not err:
            print("✅ Critic version ran successfully!")
            final_path = FILE_PATH.with_name(FILE_PATH.stem + "_cleaned.py")
            shutil.copy(critic_path, final_path)
            print(f"🎉 Final cleaned version saved to: {final_path}")
            break
        else:
            print("🔴 Error in Critic code:")
            print(err[:500])
            print("🤖 Passing to DebuggerAgent...")
            reasoning, fixed = debug_patch(critic_path.read_text(), err)
            if fixed:
                critic_path.write_text(fixed)
                print("✅ Patch applied to Critic code.")
                continue
            else:
                print("🚫 DebuggerAgent failed to fix Critic code.")
                break

def run_generated_tests(test_file_path: Path) -> None:
    print(f"\n🧪 Running tests in: {test_file_path.name}")
    result = subprocess.run(
        ["pytest", "--maxfail=5", "--disable-warnings", "-q", str(test_file_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    print(result.stdout)

from typing import Tuple
def forecast_failures(code: str, user_prompt: str | None = None) -> str:
    if user_prompt:
        extra = f"""
        If the user prompt below contains instructions relevant to forecasting, incorporate them thoughtfully.
        Otherwise, ignore it and proceed normally.

        User Prompt:
        \"\"\"
        {user_prompt}
        \"\"\"
        """
    else:
        extra = ""

    messages = [
        {
            "role": "system",
            "content": "You are ForecastAgent, an advanced static code analyzer. Your goal is to predict the most likely runtime failures before execution, based on real logic and structure of the code."
        },
        {
            "role": "user",
            "content": textwrap.dedent(extra + f"""
                Given this Python code, identify the most **probable runtime errors or logical flaws** that may arise during execution, including:

                - Exceptions likely to occur (e.g. NameError, IndexError, ZeroDivisionError)
                - Unintended logic that might produce wrong output
                - Dangerous patterns (e.g. unguarded input use, bad recursion, unbounded loops)

                Only include issues that are **actually likely in this code**, not generic type-safety warnings.

                For each issue:
                - Identify the line (or lines)
                - Explain why this is a problem
                - Propose a specific mitigation or refactor if appropriate

                Return your answer in Markdown format titled: `### ForecastAgent Risk Report`.

                Code:
                ```python
                {code}
                ```
            """)
        }
    ]

    return llm(messages).strip()

def generate_unit_tests(code: str, module_name: str, user_prompt: str | None = None) -> str:
    """Generates test code with optional user guidance."""
    if user_prompt:
        extra = f"""
        If the user prompt below contains instructions relevant to test cases, edge cases, or testing logic, incorporate it.
        Otherwise, ignore it.

        User Prompt:
        \"\"\"
        {user_prompt}
        \"\"\"
        """
    else:
        extra = ""
    base_instruction = f""" {extra}\n\n
    Generate minimal Pytest-style unit tests that validate the correctness of this code.
    Ensure the tests import from the correct module name: `{module_name}`.
    Return only the complete test file code in ```python ... ```.

    Code:
    ```python
    {code}
    ```
    """

    if user_prompt:
        base_instruction = user_prompt.strip() + "\n\n" + base_instruction.strip()

    messages = [
        {"role": "system", "content": "You are AutoTestAgent, a senior Python unit test generator."},
        {"role": "user", "content": textwrap.dedent(base_instruction)}
    ]
    reply = llm(messages)

    try:
        return next(seg for seg in reply.split("```") if seg.strip().startswith("python")).strip()[6:].strip()
    except StopIteration:
        return None

def refine_code_until_tests_pass(code: str, test_file: Path) -> str | None:
    """سعی می‌کنه کد را طوری اصلاح کنه که همهٔ تست‌ها پاس شوند."""
    current_code = code
    for attempt in range(1, MAX_ROUNDS + 1):
        print(f"\n🔁 Attempt {attempt}: Running tests...")
        tmp_path = FILE_PATH.with_name(FILE_PATH.stem + f"_refined.py")
        tmp_path.write_text(current_code)

        # اجرای تست روی نسخه فعلی
        result = subprocess.run(
            ["pytest", str(test_file), "--disable-warnings", "-q", "--tb=short", "--maxfail=3"],
            cwd=tmp_path.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        print(result.stdout)

        if "FAILED" not in result.stdout:
            print("✅ All tests passed!")
            return current_code

        print("❌ Some tests failed. Sending to DebuggerAgent...")
        reasoning, fixed_code = debug_patch(current_code, result.stdout)

        if fixed_code:
            current_code = fixed_code
        else:
            print("⚠️ DebuggerAgent failed to fix test failures.")
            break

    return None

def main():
    if not FILE_PATH.exists():
        raise FileNotFoundError(FILE_PATH)

    print("🧠 Pre-run Failure Forecasting...\n")
    forecast = forecast_failures(FILE_PATH.read_text(encoding="utf-8"))
    print("📊 Failure Forecast Report:")
    print(forecast)

    for round_i in range(1, MAX_ROUNDS + 1):
        print(f"\n=== Round {round_i} – RunnerAgent ===")
        out, err = run_code(FILE_PATH)

        if err:
            print("🔴 Error detected:\n", err[:500])
            print("\n🤖 DebuggerAgent thinking ...")
            reasoning, fixed_code = debug_patch(FILE_PATH.read_text(), err)

            print("\n📚 Reasoning from DebuggerAgent:")
            print(reasoning or "(No reasoning)")
            print("\n📄 Fixed code preview:")
            print(fixed_code[:500] + "..." if fixed_code else "(No code)")

            if fixed_code:
                FILE_PATH.write_text(fixed_code)
                print("✅ Fixed code written to file.")
                continue
            else:
                print("⚠️ No fix provided by DebuggerAgent.")
                break
        else:
            print("✅ Code ran successfully! Output:\n", out)
            break
    else:
        print("🚫 Reached max rounds without success.")
        return

    try_run_and_fix_critic_code(FILE_PATH.read_text(encoding="utf-8"))

    module_name = FILE_PATH.stem  
    test_code = generate_unit_tests(FILE_PATH.read_text(encoding="utf-8"), module_name)

    if test_code:
        test_file = FILE_PATH.with_name(f"test_{FILE_PATH.stem}.py")
        test_file.write_text(test_code,encoding="utf-8")
        print(f"✅ Test code saved to: {test_file}")
        run_generated_tests(test_file)
    else:
        print("⚠️ AutoTestAgent failed to generate tests.")

if __name__ == "__main__":
    main()
