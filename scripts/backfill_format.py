"""기존 data/questions/*.json 의 코드 문제를 clang-format/ast로 재포맷하고 재검증한다.

코드 포맷 강제 기능이 추가되기 전에 생성돼 한 줄로 뭉쳐 있는 과거 날짜들을
한 번에 정리할 때 쓰는 1회성 스크립트. (매일 자동 실행되는 daily.yml과는 별개)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_code import verify_question

DATA_DIR = Path("data/questions")


def main():
    changed = 0
    for path in sorted(DATA_DIR.glob("*.json")):
        day = json.loads(path.read_text(encoding="utf-8"))
        day_changed = False
        for q in day["questions"]:
            if q.get("type") != "code":
                continue
            before = q.get("code", "")
            verify_question(q)
            if q.get("code", "") != before:
                day_changed = True
        if day_changed:
            path.write_text(
                json.dumps(day, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            changed += 1
            print(f"reformatted {path}")
    print(f"done, {changed} file(s) updated")


if __name__ == "__main__":
    main()
