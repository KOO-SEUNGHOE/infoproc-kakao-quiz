"""Claude API로 정보처리기사 실기 문제를 생성하고, 코드/SQL 문제는 실제 실행으로 검증한다."""
import json
import os
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import anthropic

from verify_code import verify_question

CODE_LANGUAGES = ["C", "Java", "Python"]

SYSTEM_PROMPT = """\
너는 한국 정보처리기사 실기 시험 출제 위원이다. 아래 규칙을 반드시 지켜 문제를 생성하라.

- 실제 정보처리기사 실기 기출 스타일(코드 출력 예측, SQL 결과 예측, 용어 단답)을 따른다.
- 코드 출력 문제는 지정된 언어의 표준 동작만 사용한다.
  실행 결과가 컴파일러/구현체에 따라 달라질 수 있는 정의되지 않은 동작(UB), 예를 들어
  한 표현식 안에서 같은 변수를 두 번 이상 수정하는 `b = a++ + ++a;` 같은 패턴은 절대 출제하지 않는다.
  변수의 읽기와 수정 순서가 명확히 정의되는 코드만 낸다.
- 각 코드 문제는 표준 입력 없이 독립적으로 실행 가능해야 하며, 실행 결과가 결정론적이어야 한다
  (난수, 현재 시각, 메모리 주소, 스레드 순서 등에 의존하지 않는다). Java는 public class 하나만 포함한다.
- code 필드는 반드시 실제 IDE/편집기에서 보는 것처럼 줄바꿈 문자(\n)와 4칸 들여쓰기를 포함한
  여러 줄 형식으로 작성한다. 세미콜론으로 문장을 이어붙여 한 줄로 압축하지 않는다. 예시(Python):
  "def add(a, b):\n    return a + b\n\n\nresult = add(3, 4)\nprint(result)"
  이 예시처럼 함수/블록마다 줄을 나누고 들여쓰기를 넣어야 한다. C/Java도 중괄호마다 줄바꿈한다.
- SQL 문제는 schema_sql(CREATE TABLE + INSERT 포함)과 query_sql을 SQLite 문법으로 작성한다.
- 용어 단답 문제는 한 단어 또는 짧은 구로 답할 수 있는 것으로 낸다.
- 모든 문제에 대해 네가 계산한 답을 answer 필드에 채워라. 코드/SQL 문제의 answer는 실제 실행 결과와
  정확히 일치하도록 최선을 다해 계산하라. (실행 후 자동 검증되어 틀리면 실제 실행 결과로 교체된다.)
- explanation은 한국어로 2~4문장, 왜 그 답이 나오는지 핵심 논리를 설명한다.
"""

QUESTION_TOOL = {
    "name": "emit_questions",
    "description": "생성한 시험 문제 목록을 제출한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["code", "sql", "term"]},
                        "language": {"type": "string", "enum": ["C", "Java", "Python"]},
                        "title": {"type": "string"},
                        "prompt": {"type": "string"},
                        "code": {"type": "string", "description": "type=code일 때만"},
                        "schema_sql": {"type": "string", "description": "type=sql일 때만"},
                        "query_sql": {"type": "string", "description": "type=sql일 때만"},
                        "answer": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["type", "title", "prompt", "answer", "explanation"],
                },
            }
        },
        "required": ["questions"],
    },
}


def plan_counts(num_questions: int) -> dict:
    if num_questions >= 5:
        return {"code": 2, "sql": 1, "term": num_questions - 3}
    if num_questions == 4:
        return {"code": 2, "sql": 1, "term": 1}
    if num_questions == 3:
        return {"code": 1, "sql": 1, "term": 1}
    if num_questions == 2:
        return {"code": 1, "sql": 0, "term": 1}
    return {"code": 0, "sql": 0, "term": max(num_questions, 1)}


def build_user_prompt(counts: dict, code_languages: list) -> str:
    parts = [f"오늘 문제 {sum(counts.values())}개를 만들어라. 구성:"]
    if counts["code"]:
        langs = ", ".join(code_languages)
        parts.append(f"- 코드 출력 문제 {counts['code']}개 (언어: {langs}. 문제마다 서로 다른 언어 하나씩 사용)")
    if counts["sql"]:
        parts.append(f"- SQL 결과 예측 문제 {counts['sql']}개")
    if counts["term"]:
        parts.append(f"- 용어/개념 단답 문제 {counts['term']}개")
    parts.append("emit_questions 도구를 호출해 결과를 제출하라.")
    return "\n".join(parts)


def generate(num_questions: int, model: str) -> list:
    counts = plan_counts(num_questions)
    code_languages = random.sample(CODE_LANGUAGES, k=min(counts["code"], len(CODE_LANGUAGES)))
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[QUESTION_TOOL],
        tool_choice={"type": "tool", "name": "emit_questions"},
        messages=[{"role": "user", "content": build_user_prompt(counts, code_languages)}],
    )
    tool_use = next(b for b in message.content if b.type == "tool_use")
    return tool_use.input["questions"]


def main():
    num_questions = int(os.environ.get("NUM_QUESTIONS") or "5")
    model = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"
    today = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()

    questions = generate(num_questions, model)
    for i, q in enumerate(questions, start=1):
        q["id"] = i
        verify_question(q)

    out_dir = Path("data/questions")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{today.isoformat()}.json"
    out_path.write_text(
        json.dumps({"date": today.isoformat(), "questions": questions}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
