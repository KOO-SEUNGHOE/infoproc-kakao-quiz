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

# 실제 정보처리기사 실기 출제 경향(나무위키 '정보처리기사/출제경향', 시나공 기출 분석 등)을 참고해
# 난이도와 주제 범위를 지정하는 패턴 목록. 실제 기출 문항을 그대로 쓰지 않고, 매일 이 중 일부를
# 무작위로 뽑아 "이런 유형으로 새로 출제하라"는 지시로만 사용한다.
CODE_PATTERNS_GENERAL = [
    "2~3중 중첩 반복문(for/while)을 사용한 누적 계산",
    "재귀 함수(팩토리얼, 피보나치, 재귀적 합계/탐색 등)",
    "1차원 또는 2차원 배열(리스트)의 값을 변형하며 추적하는 문제",
    "클래스와 객체(생성자, 메서드 오버라이딩, static 필드/메서드)를 활용한 문제",
    "상속과 다형성(부모/자식 클래스, 부모 메서드 호출)을 활용한 문제",
    "예외 처리(try-catch 등)가 실행 흐름에 영향을 주는 문제",
    "문자열 처리 함수(부분 문자열, 분리/결합, 치환 등)를 활용한 문제",
    "스택 또는 큐 자료구조를 직접 구현하거나 활용하는 문제",
    "연결 리스트(노드와 포인터/참조)를 순회하거나 조작하는 문제",
    "정렬 또는 탐색 알고리즘(버블 정렬, 이진 탐색 등)의 동작을 한 단계씩 추적하는 문제",
]
CODE_PATTERNS_BY_LANGUAGE = {
    "C": ["포인터와 배열의 연계 연산(포인터 산술, 배열-포인터 인덱싱)", "동적 메모리 할당(malloc)을 활용한 배열 처리"],
    "Java": ["인터페이스 또는 추상 클래스를 구현하는 문제"],
    "Python": ["리스트 컴프리헨션, 람다식, 또는 Set/Dict 연산을 활용한 문제"],
}
SQL_PATTERNS = [
    "두 테이블을 JOIN(INNER JOIN 또는 LEFT OUTER JOIN)해서 조회",
    "서브쿼리(중첩 쿼리, WHERE 절 안에 SELECT)를 포함한 조회",
    "GROUP BY와 HAVING을 함께 사용한 집계 조회",
    "여러 집계 함수(COUNT, SUM, AVG, MAX, MIN)를 복합적으로 사용한 조회",
]
TERM_TOPICS = [
    "소프트웨어공학 - 디자인 패턴",
    "소프트웨어공학 - 테스트 기법(화이트박스/블랙박스 테스트)",
    "소프트웨어공학 - 모듈 결합도와 응집도",
    "소프트웨어공학 - UML 다이어그램",
    "소프트웨어공학 - 형상 관리",
    "소프트웨어공학 - 요구사항 분석/명세 기법",
    "데이터베이스 - 정규형(1NF~BCNF)과 이상 현상",
    "데이터베이스 - 카디널리티/차수, 키(기본키·외래키·후보키)",
    "데이터베이스 - 무결성 제약조건",
    "데이터베이스 - 인덱스와 트랜잭션(ACID 특성)",
    "네트워크 - OSI 7계층과 TCP/IP 계층",
    "네트워크 - 라우팅/프로토콜(OSPF, BGP, ICMP 등)",
    "네트워크 - NAT, CIDR, 서브네팅",
    "정보보안 - 암호화(대칭키/공개키 방식), 해시",
    "정보보안 - 접근통제 모델, 인증 기술(OTP 등)",
    "정보보안 - 공격 기법(세션 하이재킹, SQL 인젝션 등)과 대응",
]

SYSTEM_PROMPT = """\
너는 한국 정보처리기사 실기 시험 출제 위원이다. 아래 규칙을 반드시 지켜 문제를 생성하라.

- 목표 난이도는 "교재 첫 장의 쉬운 예제"가 아니라 실제 정보처리기사 실기 수준이다. 최근 실기는
  단순 변수 출력이 아니라 흐름을 여러 단계 추적해야 답이 나오는 코드, JOIN/서브쿼리가 섞인 SQL,
  전공 지식이 필요한 용어가 출제된다. 사용자가 입력으로 준 "패턴"을 각 문제에 반드시 반영해
  이 수준에 맞는 난이도로 출제하라. 패턴 하나만 기계적으로 넣지 말고, 그 패턴이 실제로 결과값에
  영향을 주도록 자연스럽게 섞어 넣는다.
- 코드 출력 문제는 지정된 언어의 표준 동작만 사용한다.
  실행 결과가 컴파일러/구현체에 따라 달라질 수 있는 정의되지 않은 동작(UB), 예를 들어
  한 표현식 안에서 같은 변수를 두 번 이상 수정하는 `b = a++ + ++a;` 같은 패턴은 절대 출제하지 않는다.
  변수의 읽기와 수정 순서가 명확히 정의되는 코드만 낸다.
- 각 코드 문제는 표준 입력 없이 독립적으로 실행 가능해야 하며, 실행 결과가 결정론적이어야 한다
  (난수, 현재 시각, 메모리 주소, 스레드 순서, 해시 순서(딕셔너리/셋의 반복 순서 등)에 의존하지
  않는다). Java는 public class 하나만 포함한다. 표준 라이브러리만 사용하고 외부 패키지는 쓰지 않는다.
- code 필드는 반드시 실제 IDE/편집기에서 보는 것처럼 줄바꿈 문자(\n)와 4칸 들여쓰기를 포함한
  여러 줄 형식으로 작성한다. 세미콜론으로 문장을 이어붙여 한 줄로 압축하지 않는다. 예시(Python):
  "def add(a, b):\n    return a + b\n\n\nresult = add(3, 4)\nprint(result)"
  이 예시처럼 함수/블록마다 줄을 나누고 들여쓰기를 넣어야 한다. C/Java도 중괄호마다 줄바꿈한다.
  코드 길이는 대략 15~30줄 정도로, 한눈에 결과가 보이지 않고 한 줄씩 추적해야 답이 나오게 한다.
  단, 반복 횟수나 재귀 깊이, 배열 크기는 사람이 손으로 추적할 수 있는 범위(대략 10 이하)로 작게
  유지한다. 재귀 함수의 n 값도 10을 넘지 않게 해서 즉시 계산되고 실행이 빨리 끝나게 한다.
- SQL 문제는 schema_sql(CREATE TABLE + INSERT 포함, 필요하면 두 테이블)과 query_sql을 SQLite
  문법으로 작성한다. 사용자가 지정한 SQL 패턴(JOIN/서브쿼리/집계 등)을 실제로 활용해야 한다.
- 용어 단답 문제는 사용자가 지정한 과목 영역 안에서, 한 단어 또는 짧은 구로 답할 수 있는 개념을
  낸다. 너무 상식적이거나 쉬운 용어(예: "변수란 무엇인가") 말고, 전공 지식이 있어야 답할 수 있는
  수준으로 낸다.
- 모든 문제에 대해 네가 계산한 답을 answer 필드에 채워라. 코드/SQL 문제의 answer는 실제 실행 결과와
  정확히 일치하도록 최선을 다해 계산하라. (실행 후 자동 검증되어 틀리면 실제 실행 결과로 교체된다.)
- explanation은 상세한 해설로 작성한다 (한국어, 대략 4~8문장).
  - type=code: 변수의 초기값부터 시작해서 반복/분기마다 값이 어떻게 바뀌는지 단계별로 추적하며
    설명한다. 표나 번호 매기기(①②③ 등) 없이 자연스러운 문장으로, 하지만 각 단계를 빠짐없이 짚는다.
  - type=sql: 테이블의 각 행이 WHERE/JOIN/GROUP BY를 거치며 어떻게 필터링·결합·집계되는지
    단계별로 설명하고, 최종 결과 행이 왜 그 값인지 짚는다.
  - type=term: 정의를 정확히 설명하고, 실기에서 헷갈리기 쉬운 포인트나 다른 개념과의 차이를
    짚어준다.
- type=term 문제에는 related_concepts 필드도 채운다. 이 용어와 "세트로" 같이 외우면 좋은 연관
  개념 3~5가지를, 각 줄에 "개념명: 한 줄 설명" 형식으로 줄바꿈(\n)으로 구분해 적는다.
  (예: "1NF: 모든 속성이 원자값을 가짐\n2NF: 부분 함수 종속 제거\nBCNF: 모든 결정자가 후보키")
  단순 동의어 나열이 아니라, 시험에서 비교되거나 함께 묻는 상위/하위/유사/대조 개념으로 고른다.
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
                        "related_concepts": {
                            "type": "string",
                            "description": "type=term일 때만. 함께 암기할 연관 개념 3~5개, 줄바꿈으로 구분",
                        },
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
        for lang in code_languages:
            patterns = CODE_PATTERNS_GENERAL + CODE_PATTERNS_BY_LANGUAGE.get(lang, [])
            pattern = random.choice(patterns)
            parts.append(f"- 코드 출력 문제 ({lang}): 다음 패턴을 반영해 출제 — {pattern}")
    if counts["sql"]:
        for _ in range(counts["sql"]):
            parts.append(f"- SQL 결과 예측 문제: 다음 패턴을 반영해 출제 — {random.choice(SQL_PATTERNS)}")
    if counts["term"]:
        topics = random.sample(TERM_TOPICS, k=min(counts["term"], len(TERM_TOPICS)))
        for topic in topics:
            parts.append(f"- 용어/개념 단답 문제: 다음 과목 영역에서 출제 — {topic}")
    parts.append("emit_questions 도구를 호출해 결과를 제출하라.")
    return "\n".join(parts)


REQUIRED_FIELDS_BY_TYPE = {
    "code": {"language", "title", "prompt", "code", "answer", "explanation"},
    "sql": {"title", "prompt", "schema_sql", "query_sql", "answer", "explanation"},
    "term": {"title", "prompt", "answer", "explanation"},
}


def generate(num_questions: int, model: str) -> list:
    counts = plan_counts(num_questions)
    code_languages = random.sample(CODE_LANGUAGES, k=min(counts["code"], len(CODE_LANGUAGES)))
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=12000,
        system=SYSTEM_PROMPT,
        tools=[QUESTION_TOOL],
        tool_choice={"type": "tool", "name": "emit_questions"},
        messages=[{"role": "user", "content": build_user_prompt(counts, code_languages)}],
    )
    if message.stop_reason == "max_tokens":
        print("경고: 응답이 max_tokens에 걸려 잘렸을 수 있습니다.", file=sys.stderr)
    tool_use = next(b for b in message.content if b.type == "tool_use")
    questions = tool_use.input["questions"]

    valid = []
    for q in questions:
        required = REQUIRED_FIELDS_BY_TYPE.get(q.get("type"))
        if required is None or not required.issubset(q.keys()):
            print(f"경고: 필수 필드가 빠진 문제를 건너뜁니다: {q}", file=sys.stderr)
            continue
        valid.append(q)
    return valid


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
