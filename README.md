# 정보처리기사 실기 카톡 자동 출제

매일 아침 GitHub Actions가 Claude API로 정보처리기사 실기 문제를 만들고, 코드/SQL 문제는
실제로 컴파일·실행해서 정답을 검증한 뒤, 문제 페이지를 GitHub Pages에 올리고 카카오톡
"나에게 보내기"로 요약과 링크를 보내주는 서버 없는(serverless) 자동화입니다.

## 동작 방식

매일 정해진 시각에 `.github/workflows/daily.yml` 이 실행되어 아래 4단계를 순서대로 수행합니다.

1. **문제 생성** — `scripts/generate_questions.py` 가 Claude API를 호출해 실기 문제를 만듭니다.
   기본 5문제: 코드 출력 2개(C/Java/Python 중 서로 다른 언어), SQL 결과 예측 1개, 용어 단답 2개.
2. **실행 검증** — `scripts/verify_code.py` 가 코드 문제는 실제로 컴파일·실행하고, SQL 문제는
   SQLite에 스키마를 만들어 쿼리를 돌려 정답을 재계산합니다. LLM이 낸 답과 다르면 실행 결과로
   자동 교체됩니다. 단, 컴파일러마다 결과가 달라지는 미정의 동작(UB, 예: `b = a++ + ++a;`)은
   프롬프트 규칙으로 아예 출제하지 않도록 막아두었습니다. 용어 단답은 실행으로 검증할 수 없으니
   정답 옆에 "⚠ 자동 검증 안 됨" 표시가 뜨면 교재로 한 번 더 확인하세요.
3. **사이트 배포** — `scripts/build_site.py` 가 `docs/` 아래에 정적 HTML을 생성합니다. GitHub
   Pages가 이 폴더를 서빙합니다. 정답은 `<details>` 펼쳐보기라 먼저 풀어볼 수 있습니다.
4. **카톡 발송** — `scripts/send_kakao.py` 가 "나에게 보내기"로 오늘 문제 요약과 [문제 풀기]
   버튼을 보냅니다. 카카오 텍스트 메시지는 200자 제한이 있어 코드 문제를 그대로 넣으면 거의
   다 잘리기 때문에, 카톡에는 짧은 요약과 링크만 보내고 실제 문제는 웹페이지로 보여줍니다.

카카오 리프레시 토큰은 약 2개월이면 만료됩니다. 카카오가 새 리프레시 토큰을 함께 내려주면
`send_kakao.py`가 GitHub API로 `KAKAO_REFRESH_TOKEN` 시크릿을 자동으로 갱신하므로, 매일
실행되는 한 별도 조치 없이 연결이 유지됩니다.

## 비용

Anthropic API 사용료만 듭니다. 하루 5문제, 매일 발송 기준으로 월 커피 한 잔 값도 안 나올
정도의 토큰만 사용합니다.

## 직접 해야 하는 작업

### 1. 카카오 개발자 앱 만들기

1. https://developers.kakao.com 에서 애플리케이션을 생성합니다.
2. **앱 > 제품 링크 관리 > 웹 도메인** 에 `https://<GitHub 아이디>.github.io` 를 등록합니다.
   (이걸 빼먹으면 카톡 메시지의 [문제 풀기] 버튼이 열리지 않습니다. "플랫폼 키" 메뉴 안 JavaScript
   키의 "JavaScript SDK 도메인"과는 다른 항목이니 헷갈리지 마세요 — 그건 브라우저 JS SDK 전용이라
   이 프로젝트엔 필요 없습니다.)
3. **앱 > 플랫폼 키 > REST API 키** 카드를 열어 **리다이렉트 URI**에 `http://localhost:8888` 을
   등록합니다. (로컬에서 토큰을 발급받을 때만 쓰고, 실제 서비스에는 쓰이지 않습니다.)
4. **카카오 로그인 > 동의항목** 에서 "카카오톡 메시지 전송"(`talk_message`)을 사용 설정합니다.
5. 같은 REST API 키 카드 안 **클라이언트 시크릿** 섹션에서 코드를 확인해 메모해둡니다. REST API
   키는 기본적으로 클라이언트 시크릿이 **활성화된 상태로 생성**되므로, 끄지 않았다면 이 값은
   선택이 아니라 필수입니다 (안 보내면 토큰 발급이 실패합니다). 아래 `get_token.py` 실행 시,
   그리고 GitHub Secret `KAKAO_CLIENT_SECRET` 에도 이 값을 넣어야 합니다.

### 2. 로컬에서 토큰 발급

```bash
pip install requests
python get_token.py
```

REST API 키를 입력하면 브라우저가 열려 카카오 로그인 동의 화면이 뜨고, 완료되면 터미널에
`KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`, `KAKAO_REFRESH_TOKEN` 값이 출력됩니다. 이 값들을
아래 3단계에서 GitHub Secrets에 등록하세요.

### 3. GitHub 저장소 준비

1. **public** 저장소를 만들고 이 프로젝트를 푸시합니다. (Pages 무료 플랜은 public 저장소만
   지원합니다.)
2. **Settings > Pages** 에서 Source를 "Deploy from a branch", Branch를 `main` / `docs` 로
   설정합니다.
3. **Settings > Secrets and variables > Actions** 에서 아래를 등록합니다.

   **Secrets (5개)**
   | 이름 | 값 |
   |---|---|
   | `ANTHROPIC_API_KEY` | Anthropic API 키 |
   | `KAKAO_REST_API_KEY` | 카카오 앱의 REST API 키 |
   | `KAKAO_CLIENT_SECRET` | REST API 키 카드의 클라이언트 시크릿 코드 (기본 활성화라 대부분 필수, 직접 껐다면 빈 문자열) |
   | `KAKAO_REFRESH_TOKEN` | `get_token.py` 출력값 |
   | `GH_PAT` | Secrets 쓰기 권한이 있는 GitHub Personal Access Token (classic: `repo` 스코프, 또는 fine-grained: 이 저장소의 "Secrets" 쓰기 권한) — 리프레시 토큰 자동 갱신용 |

   **Variables**
   | 이름 | 값 | 설명 |
   |---|---|---|
   | `PAGES_BASE_URL` | `https://<GitHub 아이디>.github.io/<저장소 이름>` | 카톡 링크에 쓰일 Pages 주소 |
   | `NUM_QUESTIONS` | `5` (선택, 기본값 5) | 하루 출제 문제 수 |
   | `ANTHROPIC_MODEL` | `claude-sonnet-5` (선택) | 사용할 Claude 모델 |

### 4. 테스트

**Actions** 탭 > **Daily Quiz** > **Run workflow** 로 수동 실행해봅니다. 성공하면
`data/questions/`와 `docs/`에 커밋이 쌓이고, 등록한 카카오 계정으로 메시지가 옵니다.

## 발송 시간 바꾸기

`.github/workflows/daily.yml`의 `cron`은 UTC 기준입니다. 한국 시간(KST)에서 9시간을 빼서
넣으세요. 예: 아침 8시(KST)에 보내려면 `0 23 * * *`.

## 문제 수 조절

Variables의 `NUM_QUESTIONS`를 바꾸면 됩니다. 기본 구성 규칙(`scripts/generate_questions.py`의
`plan_counts`)은 5문제 이상이면 코드 2 / SQL 1 / 용어 (나머지)로, 그보다 적으면 자동으로
비율을 줄입니다.

## 로컬 구조

```
.github/workflows/daily.yml   # 매일 실행되는 워크플로
scripts/generate_questions.py # Claude API로 문제 생성
scripts/verify_code.py        # 코드/SQL 실제 실행 검증
scripts/build_site.py         # docs/ 정적 사이트 빌드
scripts/send_kakao.py         # 카톡 발송 + 리프레시 토큰 자동 갱신
scripts/update_github_secret.py # GitHub Secret 암호화 갱신 헬퍼
get_token.py                  # 로컬 1회 실행용 카카오 OAuth 스크립트
data/questions/YYYY-MM-DD.json # 날짜별 문제 원본 데이터
docs/                          # GitHub Pages로 배포되는 정적 사이트
```
