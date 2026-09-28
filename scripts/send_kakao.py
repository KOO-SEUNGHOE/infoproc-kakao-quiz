"""카카오톡 '나에게 보내기'로 오늘의 문제 요약과 링크를 발송한다.

매 실행마다 refresh_token으로 access_token을 새로 발급받는다. 이때 카카오가 refresh_token을
새 값으로 함께 내려주면(로테이션), GitHub Secret(KAKAO_REFRESH_TOKEN)을 API로 자동 갱신해
다음 실행에서도 연결이 끊기지 않도록 한다.
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from update_github_secret import update_secret

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def refresh_access_token(rest_api_key: str, refresh_token_value: str, client_secret: str | None) -> dict:
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token_value,
    }
    if client_secret:
        data["client_secret"] = client_secret
    resp = requests.post(TOKEN_URL, data=data, timeout=10)
    resp.raise_for_status()
    return resp.json()


def send_memo(access_token: str, text: str, link_url: str) -> dict:
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": "문제 풀기",
    }
    resp = requests.post(
        SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def build_summary(day: dict) -> str:
    counts = {}
    for q in day["questions"]:
        counts[q["type"]] = counts.get(q["type"], 0) + 1
    label = {"code": "코드", "sql": "SQL", "term": "용어"}
    summary = ", ".join(f"{label.get(t, t)} {n}" for t, n in counts.items())
    return f"[오늘의 정보처리기사 실기 문제]\n{day['date']} · {len(day['questions'])}문제 ({summary})\n지금 풀어보세요!"


def main():
    today = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    day = json.loads(Path(f"data/questions/{today}.json").read_text(encoding="utf-8"))

    rest_api_key = os.environ["KAKAO_REST_API_KEY"]
    client_secret = os.environ.get("KAKAO_CLIENT_SECRET") or None
    current_refresh_token = os.environ["KAKAO_REFRESH_TOKEN"]
    pages_base_url = os.environ["PAGES_BASE_URL"].rstrip("/")

    tokens = refresh_access_token(rest_api_key, current_refresh_token, client_secret)
    access_token = tokens["access_token"]

    link_url = f"{pages_base_url}/q/{day['date']}.html"
    send_memo(access_token, build_summary(day), link_url)
    print("카카오톡 발송 완료")

    new_refresh_token = tokens.get("refresh_token")
    if new_refresh_token and new_refresh_token != current_refresh_token:
        owner, repo = os.environ["GITHUB_REPOSITORY"].split("/")
        update_secret(owner, repo, os.environ["GH_PAT"], "KAKAO_REFRESH_TOKEN", new_refresh_token)
        print("KAKAO_REFRESH_TOKEN 시크릿을 갱신했습니다.")


if __name__ == "__main__":
    main()
