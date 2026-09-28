"""data/questions/*.json 을 읽어 GitHub Pages용 정적 사이트(docs/)를 생성한다."""
import html
import json
from pathlib import Path

DATA_DIR = Path("data/questions")
DOCS_DIR = Path("docs")

PAGE_CSS = """
:root { color-scheme: light dark; }
body { font-family: -apple-system, "Malgun Gothic", sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; line-height: 1.6; }
h1 { font-size: 1.4rem; }
.question { border: 1px solid #8883; border-radius: 10px; padding: 16px; margin: 16px 0; }
.badge { display: inline-block; font-size: .75rem; padding: 2px 8px; border-radius: 999px; background: #6363f11a; color: #6363f1; margin-bottom: 8px; }
pre { background: #80808014; padding: 12px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }
summary { cursor: pointer; font-weight: 600; margin-top: 10px; }
.answer { margin-top: 10px; padding: 12px; background: #80808014; border-radius: 8px; }
.unverified { color: #c97a00; font-size: .8rem; margin-top: 8px; }
.date-list a { display: block; padding: 10px 0; border-bottom: 1px solid #8882; text-decoration: none; }
a { color: #6363f1; }
"""

TYPE_LABEL = {"code": "코드 출력", "sql": "SQL 결과", "term": "용어 단답"}


def render_question(q: dict) -> str:
    label = TYPE_LABEL.get(q["type"], q["type"])
    lang = f' · {q["language"]}' if q.get("language") else ""
    body = f'<div class="badge">{label}{lang}</div>'
    body += f'<p>{html.escape(q["prompt"])}</p>'
    if q["type"] == "code":
        body += f'<pre><code>{html.escape(q.get("code", ""))}</code></pre>'
    elif q["type"] == "sql":
        sql_text = f'-- schema\n{q.get("schema_sql", "")}\n\n-- query\n{q.get("query_sql", "")}'
        body += f"<pre><code>{html.escape(sql_text)}</code></pre>"

    note = ""
    if not q.get("verified"):
        note = '<div class="unverified">⚠ 자동 실행 검증이 되지 않은 문제입니다. 정답이 의심되면 교재로 한 번 더 확인하세요.</div>'

    body += f"""
<details>
  <summary>정답 보기</summary>
  <div class="answer">
    <pre><code>{html.escape(str(q.get("answer", "")))}</code></pre>
    <p>{html.escape(q.get("explanation", ""))}</p>
    {note}
  </div>
</details>
"""
    return f'<div class="question"><h3>Q{q["id"]}</h3>{body}</div>'


def render_day(day: dict) -> str:
    questions_html = "\n".join(render_question(q) for q in day["questions"])
    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>정보처리기사 실기 - {day["date"]}</title>
<style>{PAGE_CSS}</style>
</head><body>
<a href="../index.html">← 전체 목록</a>
<h1>{day["date"]} 실기 문제</h1>
{questions_html}
</body></html>"""


def render_index(days: list) -> str:
    if days:
        items = "\n".join(
            f'<a href="q/{d["date"]}.html">{d["date"]} ({len(d["questions"])}문제)</a>' for d in days
        )
    else:
        items = "<p>아직 생성된 문제가 없습니다. Actions에서 workflow를 한 번 실행해보세요.</p>"
    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>정보처리기사 실기 문제은행</title>
<style>{PAGE_CSS}</style>
</head><body>
<h1>정보처리기사 실기 문제은행</h1>
<div class="date-list">{items}</div>
</body></html>"""


def main():
    (DOCS_DIR / "q").mkdir(parents=True, exist_ok=True)
    days = []
    for path in sorted(DATA_DIR.glob("*.json")):
        day = json.loads(path.read_text(encoding="utf-8"))
        days.append(day)
        (DOCS_DIR / "q" / f'{day["date"]}.html').write_text(render_day(day), encoding="utf-8")
    days.sort(key=lambda d: d["date"], reverse=True)
    (DOCS_DIR / "index.html").write_text(render_index(days), encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {len(days)} day(s) -> docs/")


if __name__ == "__main__":
    main()
