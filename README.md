# Samwoo Vibe React/FastAPI Template

삼우에레코 시민 개발자를 위한 React + FastAPI + PostgreSQL 표준 템플릿입니다.

> AI 코딩 도구는 작업을 시작하기 전에 반드시 루트의 [`AGENTS.md`](AGENTS.md)를
> 먼저 읽고 따라야 합니다. 에이전트용 아키텍처·보안·DB migration·검증·배포
> 규칙은 README가 아니라 `AGENTS.md`를 기준으로 합니다.

## 기술스택

- Frontend: React 19 + Vite + TypeScript/TSX, npm
- Backend: Python 3.13 + FastAPI + SQLAlchemy 2 + Alembic + psycopg 3
- Python 패키지·가상환경: uv (`pyproject.toml` + `uv.lock`)
- Database: 로컬/중앙 PostgreSQL 17
- 배포: Docker Compose + Coolify Traefik
- React 파일·API 연결: frontend Nginx

## 기본 화면 디자인

별도의 디자인 요청이 없으면
[`SAMWOO UI Standard`](https://github.com/samwoo-vibe/samwoo-ui-standard)를 기본으로
사용합니다. 해당 표준의 디자인 토큰, 공통 컴포넌트, 회사 로고·파비콘, 라이트·다크
테마와 반응형·접근성 기준을 현재 서비스 기능에 맞게 적용합니다.

표준 저장소의 데모 문구와 예시 데이터는 가져오지 않으며, 이 템플릿의 API 연결과
Coolify 배포 설정은 유지합니다. 사용자가 다른 디자인이나 기존 화면 유지를 요청하면
SAMWOO UI Standard 대신 그 요청을 우선합니다.

## 새 서비스 만들기

처음 쓰는 경우 아래 순서대로 하나씩 따라 하면 됩니다.

### 1. 작업 폴더 준비

1. 공개 템플릿을 내려받아 Windows PC의 새 로컬 작업 폴더에 풉니다.
2. 원본 템플릿의 Git 이력이나 remote를 작업 폴더에 가져오지 않습니다.

### 2. 필요한 프로그램 설치

Node.js 22, PostgreSQL 17, uv를 준비합니다.

1. Node.js: <https://nodejs.org/en/download>에서 22 LTS를 내려받아 설치합니다.
2. PostgreSQL 17: <https://www.enterprisedb.com/downloads/postgres-postgresql-downloads>에서
   내려받아 설치합니다. 설치 중에 정하는 `postgres` 계정 비밀번호는 3단계에서 쓰니 기억해
   둡니다. 설치 마지막에 나오는 Stack Builder는 실행하지 않고 건너뜁니다.
3. `psql` 명령을 쓸 수 있도록 Path에 PostgreSQL 폴더를 추가합니다. 시스템 → 고급 시스템
   설정 → 환경 변수에서 Path를 선택하고 [편집] → [새로 만들기]를 눌러
   `C:\Program Files\PostgreSQL\17\bin`을 추가합니다.
4. uv: PowerShell에서 다음 명령을 실행합니다.

   ```powershell
   winget install --id=astral-sh.uv -e
   ```

5. Path가 바뀌었으므로 열려 있던 PowerShell과 VS Code를 모두 닫았다가 다시 엽니다.

### 3. 로컬 DB 만들기

PostgreSQL에 프로젝트 전용 로컬 DB와 role을 만듭니다. PowerShell에서 다음 명령을 실행하고,
PostgreSQL을 설치할 때 정한 `postgres` 비밀번호를 입력합니다.

```powershell
psql -U postgres
```

`postgres=#`가 보이면 아래 두 줄을 입력합니다. `<로컬 비밀번호>`와 `<DB 이름>`은 직접 정한
값으로 바꾸고, 꺾쇠(`< >`)는 지웁니다.

```sql
CREATE ROLE app_role LOGIN PASSWORD '<로컬 비밀번호>';
CREATE DATABASE <DB 이름> OWNER app_role;
```

- 로컬 비밀번호는 영문과 숫자만 쓰는 것을 권합니다. 특수문자가 들어가면 5단계의
  `DATABASE_URL` 주소가 깨질 수 있습니다.
- DB 이름은 영문 소문자로 시작하고 영문 소문자, 숫자, 밑줄(`_`)만 씁니다.
- 다 만들었으면 `\q`를 입력해 빠져나옵니다.

### 4. 설치 스크립트 실행

작업 폴더(이 `README.md`가 있는 폴더)에서 PowerShell을 열고 다음 명령을 실행합니다.
VS Code로 작업 폴더를 열었다면 VS Code 터미널에서 실행해도 됩니다.

```powershell
.\scripts\setup.ps1
```

`setup.ps1`이 `.env.example`을 복사해 `.env`를 자동으로 만들어 줍니다. `.env.example`은 배포용
ZIP을 만들 때 꼭 필요한 파일이므로 지우거나 이름을 바꾸지 않습니다.

“이 시스템에서 스크립트를 실행할 수 없으므로”라는 오류가 나오면, 같은 PowerShell 창에서
다음 명령을 먼저 실행한 뒤 다시 시도합니다. 이 설정은 그 창에서만 적용되므로, 새 PowerShell
창에서 같은 오류가 나오면 다시 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
```

### 5. `.env`에 로컬 DB 정보 입력

작업 폴더의 `.env`를 메모장이나 VS Code로 열고, `DATABASE_URL` 줄을 3단계에서 정한 값으로
고칩니다.

```text
DATABASE_URL=postgresql+psycopg://app_role:<로컬 비밀번호>@localhost:5432/<DB 이름>
```

### 6. 실행하고 개발하기

작업 폴더에서 PowerShell 창을 두 개 열고, 창마다 하나씩 실행합니다.

```powershell
# 첫 번째 창: 백엔드
.\scripts\start-backend.ps1
```

```powershell
# 두 번째 창: 프런트엔드
.\scripts\start-frontend.ps1
```

브라우저에서 `http://127.0.0.1:5173`이 열리면 준비가 끝난 것입니다. 이제 기능을 개발합니다.
끌 때는 각 PowerShell 창에서 `Ctrl+C`를 누릅니다.

프런트엔드는 `http://127.0.0.1:5173`, 프런트엔드를 통해 접근하는 API는
`http://127.0.0.1:5173/api`에서 실행됩니다. FastAPI 문서는
`http://127.0.0.1:5173/api/docs`에서 확인합니다.
로컬에서는 Vite가 React를 제공하고 `/api` 요청을 FastAPI로 전달하므로 Nginx를
설치할 필요가 없습니다. Nginx는 서버 배포용 frontend 이미지 안에서만 실행됩니다.

### 7. 배포(필요할 때만)

배포가 필요하면 AI 코딩 도구에 배포용 인계 ZIP 생성을 요청합니다. 생성된 ZIP은
배포 담당자에게 전달합니다. 배포하지 않을 때는 ZIP을 만들 필요가 없습니다.

## 실제 데이터 사용 금지

엑셀·CSV·문서·기존 시스템 추출본 등 실제 회사 데이터를 소스코드, 테스트 데이터,
정적 파일, migration 또는 Git 저장소에 넣지 마세요. 코드에 값으로 직접 적는 것도
금지합니다. 예제와 테스트에는 실제 대상과 연결되지 않는 합성 데이터만 사용합니다.

기능상 실제 데이터가 필요하면 PostgreSQL이나 실행 시 업로드 방식으로 처리하고,
로컬 파일은 저장소 밖 또는 `local-data/`에 둡니다. `local-data/`와 실제 데이터는
배포용 ZIP에도 포함되지 않습니다.

## 기본 로그인

> **이 템플릿에는 아직 로그인 화면과 로그인 API가 없습니다.** 앱을 개발할 때 AI 코딩
> 도구가 `AGENTS.md`의 「기본 로그인 인증」 규칙대로 회사 메일 로그인을 함께 만듭니다.
> 만든 앱에 로그인이 빠져 있으면 AI 코딩 도구에 “회사 메일 로그인 붙여 줘”라고 요청하세요.

별도의 로그인 방식을 요청하지 않으면, 이 템플릿으로 만드는 앱은 회사 메일 계정으로
로그인하도록 구현합니다. 별도 회원가입은 없으며 backend가 아래 IMAP 서버에 로그인을
시도해 계정을 인증합니다.

- 로그인 입력: 회사 메일 아이디 또는 전체 그룹웨어 메일 주소와 비밀번호
- 기본 메일 도메인: `samwooeleco.com` — 아이디만 입력하면 backend가 자동으로 붙입니다.
  로그인 화면 입력창 아래에 “아이디만 입력해도 됩니다.”를 표시합니다.
- 계열사 도메인: `samwootechno.com`, `samwoo.ai` 등 같은 그룹웨어(다우오피스) 메일 서버의
  주소로도 로그인할 수 있습니다. 도메인 허용 목록 없이 메일 서버 인증 결과로 판단합니다.
  메일 서버가 같은 아이디를 모든 도메인에서 같은 계정으로 인식하므로, 아이디만 입력하든
  어느 도메인의 전체 주소를 입력하든 같은 계정으로 처리합니다.
- IMAP 서버: `play.samwooeleco.com`
- 포트: `993`
- 연결: SSL/TLS
- 용도: 사이트 로그인 인증만 사용

메일함 조회나 메일 발송 기능은 만들지 않습니다. 입력한 메일 비밀번호는 인증 시도에만
사용하고 저장하거나 로그에 남기지 않습니다. 인증 성공 후에는 비밀번호가 포함되지 않은
보안 session 또는 token으로 로그인 상태를 유지합니다.

자체 로그인, SSO, OAuth 등 다른 로그인 방식을 요청한 프로젝트에는 위 IMAP 방식을
추가하지 않고 요청한 인증 방식만 적용합니다.

### 메신저 도구 창 안에서의 로그인

회사 메신저(`https://play-on.samwooeleco.com`)는 앱을 다른 사이트의 iframe(도구 창)으로
엽니다. 브라우저는 그 안에서 `SameSite=Lax`·`Strict` 쿠키를 저장하지도 보내지도 않아,
로그인한 직후 오류 없이 다시 로그아웃 상태가 됩니다. 그래서 로그인 방식과 관계없이 세션
쿠키는 다음과 같이 다룹니다.

- 운영(HTTPS): `HttpOnly; Secure; SameSite=None; Partitioned`
- 평문 HTTP 로컬 개발: `HttpOnly; SameSite=Lax`
- 로그아웃·세션 만료: 분할 쿠키와 같은 이름의 예전 비분할 쿠키를 함께 만료
- `SameSite=None`에는 CSRF 방어가 없으므로, 로그인·로그아웃을 포함한 쓰기 요청은
  `Origin`이 앱 자신의 주소(`APP_BASE_URL`)일 때만 받습니다. 메신저 주소도 거절합니다.
  `Origin`이 없으면 `Sec-Fetch-Site: cross-site`인 요청만 거절합니다.

이 처리는 `backend/app/web_session.py`에 들어 있습니다. 출처 검사는 이미 모든 요청에
연결되어 있고, 로그인을 만들 때는 이 모듈의 `set_session_cookie`·`clear_session_cookie`를
씁니다. 자세한 규칙은 `AGENTS.md`의 「기본 로그인 인증」을 따릅니다.

## 배포

배포를 원할 때만 다음 명령으로 필요한 소스코드와 배포 설정을 압축합니다.

```powershell
uv run --frozen --project backend python scripts/export_handoff.py --project-name 프로젝트명
```

생성된 `_handoff/<프로젝트명>-source.zip`을 배포 담당자에게 전달하세요. ZIP에 `.env`,
비밀번호·토큰, 로컬 DB, 업로드 파일 또는 실제 업무 데이터가 들어가면 안 됩니다.
배포 담당자가 승인본을 별도 private 저장소의 `main`에 push하면 Coolify 개발 환경에
자동 배포됩니다. 운영 배포는 별도 승인 후 진행합니다.

Coolify 배포용 `compose.yaml`에는 PostgreSQL 컨테이너가 없습니다. 중앙
PostgreSQL의 앱 전용 database·role과 `DATABASE_URL`을 프로비저너가
생성·주입합니다.

`APP_BASE_URL`에는 사용자가 실제 접속하는 앱의 공개 주소를 넣습니다. backend는 시작할 때
이 값을 검사하며, 빈 값·설정 안내 문구·주소 경로나 쿼리가 붙은 값은 거부합니다.
예시는 `https://app.example.invalid`이고, 로컬 개발은 `.env.example`의 주소를 사용합니다.
검증한 주소는 `app.state.app_base_url`에서 읽을 수 있습니다. backend는 이 주소의 origin을
기준으로 쓰기 요청의 출처를 검사하며(`backend/app/web_session.py`), 메신저 부모 주소를 앱
자신의 주소로 사용하지 않습니다. 배포 후에는 health와 화면 표시뿐 아니라 로그인 제출 요청이
출처 검사에서 차단되지 않는지, 메신저 도구 창 안에서 로그인한 뒤 새로고침해도 로그인이
유지되는지 브라우저와 허용된 메신저 삽입 환경에서 확인합니다.

이 템플릿의 `compose.yaml`, `samwoo-service.yaml`, Dockerfile과 Nginx 설정은 사내
Coolify 자동 배포 규약에 맞춰져 있습니다. 임의로 바꾸지 말고 자세한 기술 규칙은
`AGENTS.md`를 따르세요.

배포 주소 자체에는 회사 공용 HTTP Basic Auth가 적용되지 않습니다. 따라서 위 기본
IMAP 로그인 또는 사용자가 지정한 다른 인증 방식을 앱 안에 구현하고, backend API에서
권한을 검사해야 합니다. 인증 구현 전에는 실제 민감 데이터를 입력하지 마세요.
