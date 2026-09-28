"""코드/SQL 문제의 정답을 실제 실행 결과로 검증한다."""
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_TIMEOUT = 10


class VerificationError(Exception):
    pass


def _run(cmd, cwd=None):
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=RUN_TIMEOUT,
    )
    if result.returncode != 0:
        raise VerificationError(result.stderr.strip() or f"exit code {result.returncode}")
    return result.stdout


def run_python(code: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "main.py"
        path.write_text(code, encoding="utf-8")
        return _run([sys.executable, str(path)], cwd=d)


def run_c(code: str) -> str:
    if not shutil.which("gcc"):
        raise VerificationError("gcc가 설치되어 있지 않습니다.")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "main.c"
        src.write_text(code, encoding="utf-8")
        binary = Path(d) / "main"
        compile_result = subprocess.run(
            ["gcc", "-std=c11", "-O0", "-o", str(binary), str(src)],
            capture_output=True, text=True, timeout=RUN_TIMEOUT,
        )
        if compile_result.returncode != 0:
            raise VerificationError(compile_result.stderr.strip())
        return _run([str(binary)], cwd=d)


def run_java(code: str) -> str:
    match = re.search(r"public\s+class\s+(\w+)", code)
    if not match:
        raise VerificationError("public class 선언을 찾을 수 없습니다.")
    class_name = match.group(1)
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / f"{class_name}.java"
        src.write_text(code, encoding="utf-8")
        compile_result = subprocess.run(
            ["javac", str(src)], cwd=d, capture_output=True, text=True, timeout=RUN_TIMEOUT,
        )
        if compile_result.returncode != 0:
            raise VerificationError(compile_result.stderr.strip())
        return _run(["java", "-cp", d, class_name], cwd=d)


RUNNERS = {"c": run_c, "java": run_java, "python": run_python}


def run_code(language: str, code: str) -> str:
    runner = RUNNERS.get(language.lower())
    if runner is None:
        raise VerificationError(f"지원하지 않는 언어: {language}")
    return runner(code).rstrip("\n")


def run_sql(schema_sql: str, query_sql: str) -> str:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_sql)
        cursor = conn.execute(query_sql)
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description] if cursor.description else []
        lines = [" | ".join(columns)] if columns else []
        lines += [" | ".join(str(v) for v in row) for row in rows]
        return "\n".join(lines) if lines else "(결과 없음)"
    finally:
        conn.close()


def verify_question(question: dict) -> dict:
    """question을 실제로 실행해 answer를 실행 결과로 덮어쓰고 verified 플래그를 채운다.
    LLM이 처음 제시한 답이 실행 결과와 다르면 llm_answer에 원래 답을 남겨 대조할 수 있게 한다.
    """
    qtype = question.get("type")
    try:
        if qtype == "code":
            actual = run_code(question["language"], question["code"])
        elif qtype == "sql":
            actual = run_sql(question["schema_sql"], question["query_sql"])
        else:
            question["verified"] = False
            return question

        if actual.strip() != str(question.get("answer", "")).strip():
            question["llm_answer"] = question.get("answer")
        question["answer"] = actual
        question["verified"] = True
    except Exception as exc:  # LLM 출력은 신뢰할 수 없는 경계이므로 광범위하게 잡아 unverified로 표시
        question["verified"] = False
        question["verification_error"] = str(exc)
    return question
