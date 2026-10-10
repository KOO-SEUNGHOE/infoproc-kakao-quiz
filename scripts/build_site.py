"""data/questions/*.json 을 읽어 GitHub Pages용 정적 사이트(docs/)를 생성한다."""
import html
import json
import re
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
.nav-link { display: inline-block; margin: 8px 0 20px; font-weight: 600; }
.term-card { border: 1px solid #8883; border-radius: 10px; padding: 16px; margin: 12px 0; }
.term-name { font-size: 1.05rem; font-weight: 700; }
.term-count { font-size: .75rem; color: #8888; margin-left: 8px; font-weight: 400; }
.term-prompt { color: #8888; font-size: .85rem; margin: 6px 0; }
.term-dates { font-size: .75rem; color: #8888; margin-top: 8px; }
.related { margin-top: 12px; padding: 10px 14px; background: #6363f10d; border-radius: 8px; }
.related-title { font-size: .8rem; font-weight: 700; color: #6363f1; margin-bottom: 4px; }
.related ul { margin: 4px 0 0; padding-left: 18px; }
.related li { font-size: .9rem; margin: 2px 0; }
"""

TYPE_LABEL = {"code": "코드 출력", "sql": "SQL 결과", "term": "용어 단답"}


def render_related_concepts(text: str) -> str:
    items = [line.strip(" -") for line in text.splitlines() if line.strip()]
    if not items:
        return ""
    lis = "\n".join(f"<li>{html.escape(item)}</li>" for item in items)
    return f"""
<div class="related">
  <div class="related-title">📎 함께 암기하기</div>
  <ul>{lis}</ul>
</div>
"""


def render_question(q: dict) -> str:
    label = TYPE_LABEL.get(q.get("type"), q.get("type", "?"))
    lang = f' · {q["language"]}' if q.get("language") else ""
    body = f'<div class="badge">{label}{lang}</div>'
    body += f'<p>{html.escape(q.get("prompt", "(문제 내용 누락)"))}</p>'
    if q.get("type") == "code":
        body += f'<pre><code>{html.escape(q.get("code", ""))}</code></pre>'
    elif q.get("type") == "sql":
        sql_text = f'-- schema\n{q.get("schema_sql", "")}\n\n-- query\n{q.get("query_sql", "")}'
        body += f"<pre><code>{html.escape(sql_text)}</code></pre>"

    note = ""
    if not q.get("verified"):
        note = '<div class="unverified">⚠ 자동 실행 검증이 되지 않은 문제입니다. 정답이 의심되면 교재로 한 번 더 확인하세요.</div>'

    related = render_related_concepts(q.get("related_concepts", "")) if q.get("type") == "term" else ""

    body += f"""
<details>
  <summary>정답 보기</summary>
  <div class="answer">
    <pre><code>{html.escape(str(q.get("answer", "")))}</code></pre>
    <p>{html.escape(q.get("explanation", ""))}</p>
    {related}
    {note}
  </div>
</details>
"""
    return f'<div class="question"><h3>Q{q.get("id", "?")}</h3>{body}</div>'


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
<a class="nav-link" href="../glossary.html">📚 지금까지 나온 용어 정리 보기</a>
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
<a class="nav-link" href="glossary.html">📚 지금까지 나온 용어 정리 보기</a>
<div class="date-list">{items}</div>
</body></html>"""


def collect_terms(days: list) -> list:
    """모든 날짜의 용어 단답 문제를 정답 기준으로 묶어서 반환한다."""
    grouped = {}
    for day in days:
        for q in day["questions"]:
            if q.get("type") != "term":
                continue
            key = re.sub(r"\s+", "", str(q.get("answer", ""))).casefold()
            if not key:
                continue
            entry = grouped.setdefault(key, {
                "answer": str(q.get("answer", "")).strip(),
                "occurrences": [],
            })
            entry["occurrences"].append({
                "date": day["date"],
                "prompt": q.get("prompt", ""),
                "explanation": q.get("explanation", ""),
                "related_concepts": q.get("related_concepts", ""),
            })
    terms = list(grouped.values())
    terms.sort(key=lambda t: t["answer"])
    return terms


def render_term_card(term: dict) -> str:
    latest = term["occurrences"][-1]
    count = len(term["occurrences"])
    count_badge = f'<span class="term-count">{count}번 출제</span>' if count > 1 else ""
    dates = ", ".join(o["date"] for o in term["occurrences"])
    related = render_related_concepts(latest.get("related_concepts", ""))
    return f"""
<div class="term-card">
  <div class="term-name">{html.escape(term["answer"])}{count_badge}</div>
  <div class="term-prompt">{html.escape(latest["prompt"])}</div>
  <p>{html.escape(latest["explanation"])}</p>
  {related}
  <div class="term-dates">출제일: {html.escape(dates)}</div>
</div>
"""


def render_glossary(terms: list) -> str:
    if terms:
        cards = "\n".join(render_term_card(t) for t in terms)
    else:
        cards = "<p>아직 나온 용어 단답 문제가 없습니다.</p>"
    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>용어 정리 - 정보처리기사 실기</title>
<style>{PAGE_CSS}</style>
</head><body>
<a href="index.html">← 전체 목록</a>
<h1>지금까지 나온 용어 정리 ({len(terms)}개)</h1>
<p>가나다 순으로 정렬돼 있어요. 여러 번 나온 용어는 그만큼 중요하다는 뜻이니 눈에 익혀두세요.</p>
{cards}
</body></html>"""


def main():
    (DOCS_DIR / "q").mkdir(parents=True, exist_ok=True)
    days = []
    for path in sorted(DATA_DIR.glob("*.json")):
        day = json.loads(path.read_text(encoding="utf-8"))
        days.append(day)
        (DOCS_DIR / "q" / f'{day["date"]}.html').write_text(render_day(day), encoding="utf-8")
    terms = collect_terms(days)
    days.sort(key=lambda d: d["date"], reverse=True)
    (DOCS_DIR / "index.html").write_text(render_index(days), encoding="utf-8")
    (DOCS_DIR / "glossary.html").write_text(render_glossary(terms), encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {len(days)} day(s), {len(terms)} term(s) -> docs/")


if __name__ == "__main__":
    main()
