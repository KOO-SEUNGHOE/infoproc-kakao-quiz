"""로컬에서 한 번만 실행해 카카오 access_token / refresh_token을 발급받는다.

사전 준비:
- 카카오 개발자 콘솔(https://developers.kakao.com)에서 앱을 생성한다.
- 앱 설정 > 카카오 로그인 > Redirect URI에 http://localhost:8888 을 등록한다.
- 앱 설정 > 플랫폼 > Web에 https://<GitHub 아이디>.github.io 를 등록한다.
- 카카오 로그인 > 동의항목에서 "카카오톡 메시지 전송"을 사용 설정한다.
- (앱 설정에서 Client Secret을 사용 설정했다면 실행 시 함께 입력한다. 안 썼다면 빈 값으로 Enter.)
"""
import http.server
import json
import urllib.parse
import webbrowser

import requests

REDIRECT_URI = "http://localhost:8888"
AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"

_code_holder = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _code_holder["code"] = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("인증 완료! 이 창은 닫아도 됩니다.".encode("utf-8"))

    def log_message(self, *args):
        pass


def main():
    rest_api_key = input("카카오 REST API 키: ").strip()
    client_secret = input("Client Secret (사용 안 하면 Enter): ").strip() or None

    auth_url = (
        f"{AUTH_URL}?response_type=code&client_id={rest_api_key}"
        f"&redirect_uri={REDIRECT_URI}&scope=talk_message"
    )
    print(f"\n브라우저가 열립니다. 열리지 않으면 아래 주소로 직접 접속하세요:\n{auth_url}\n")
    webbrowser.open(auth_url)

    server = http.server.HTTPServer(("localhost", 8888), _CallbackHandler)
    server.handle_request()  # 리다이렉트가 올 때까지 대기 후 한 번만 처리

    code = _code_holder.get("code")
    if not code:
        raise SystemExit("인가 코드를 받지 못했습니다. 카카오 로그인 화면에서 동의했는지 확인하세요.")

    data = {
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    if client_secret:
        data["client_secret"] = client_secret

    resp = requests.post(TOKEN_URL, data=data, timeout=10)
    resp.raise_for_status()
    tokens = resp.json()

    print("\n토큰 발급 완료! 아래 값을 GitHub 저장소 Secrets에 등록하세요.\n")
    print(f"KAKAO_REST_API_KEY   = {rest_api_key}")
    print(f"KAKAO_CLIENT_SECRET  = {client_secret or '(미사용)'}")
    print(f"KAKAO_REFRESH_TOKEN  = {tokens['refresh_token']}")
    print("\n(access_token은 워크플로가 매일 refresh_token으로 새로 발급하므로 저장하지 않아도 됩니다.)")

    with open("kakao_tokens.local.json", "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)
    print("\n전체 응답은 kakao_tokens.local.json 에도 저장했습니다 (이 파일은 git에 올리지 마세요).")


if __name__ == "__main__":
    main()
