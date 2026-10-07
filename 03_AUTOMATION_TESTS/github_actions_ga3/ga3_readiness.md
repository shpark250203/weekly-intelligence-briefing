# GA-3 준비 상태 — End-to-End Weekly Brief 수동 테스트

> 작성 2026-10-01. 상위 설계는 `00_SYSTEM/ga2_auth_design.md` §6.
> **이 문서는 준비 상태를 기록한다. GA-3를 실행하지 않는다.**
> 정기 `schedule`은 **활성화하지 않는다** (GA-4 사안).

---

## 0. 현재 상태 한 줄

**GA-3는 아직 실행할 수 없다. 파이프라인 코드가 저장소에 0건이고, GA-2 STEP 12가 미완이다.**

---

## 1. 완료된 것 — SMTP 경로 (GA-2)

| 단계 | 결과 | 날짜 |
|---|---|---|
| GA-1 Connectivity Probe | PASS | 2026-09-30 |
| GA-2 SMTP 연결성 (465·587 EHLO) | PASS — egress 열림 | 2026-09-30 |
| **GA-2B SMTP AUTH** | **PASS 2회 재현** | 2026-10-01 |
| **GA-2C 실제 발송 1통** | **PASS — 수신 확인** | 2026-10-01 |

**판정: GitHub Actions → Gmail SMTP 발송 경로는 End-to-End로 검증 완료.**
`GMAIL_USERNAME` · `GMAIL_APP_PASSWORD` **동결** — 수정·재발급하지 않는다.

---

## 2. 미완 — 2개의 선행 블로커

### 블로커 ① GA-2 STEP 12 — **프로브 준비 완료, 실행 대기** (2026-10-01)

`.github/workflows/gemini-probe.yml` (`GA-2 STEP 12 Gemini Probe`)를 신설했다.
**아직 실행하지 않았다 — 사용자가 GitHub Actions에서 수동 실행한다.**

| 항목 | 값 |
|---|---|
| 호출 수 | **정확히 1회** (`urlopen` 1회, 재시도 없음) — RPD 20 중 **1** 소비 |
| 모델 | Variable `GEMINI_MODEL` 우선 → 없으면 입력값(기본 `gemini-2.5-flash`). **하드코딩 없음** (§2-1) |
| Key 전달 | `x-goog-api-key` **헤더**로만. URL 쿼리에 넣지 않는다 (로그 유출 방지) |
| 프롬프트 | 고정 1줄. 기사본문·수신주소·Secret·로컬경로·발송이력 **미포함** (§2-6) |
| 트리거 | `workflow_dispatch` 전용 — `schedule` 0건 |
| 미포함 | Brief 생성 · 메일 발송 · `CLOUD_MODE` |

**1회 호출로 GA-3가 의존하는 4가지를 동시에 확인한다:**

| # | 확인 항목 | 왜 필요한가 |
|---|---|---|
| 1 | HTTP 200 | 키·네트워크·엔드포인트 |
| 2 | 모델 사용 가능 | 해당 모델 ID가 이 계정에 열려 있는지 (§2-1은 2.5 계열 접근 제한 가능성을 경고) |
| 3 | **구조화 출력** (`responseMimeType` + `responseSchema`) | §2-2가 **필수 전제**로 삼는 기능. 여기서 깨지면 7 호출 설계가 성립하지 않는다 |
| 4 | 토큰 회계 (`usageMetadata`) | §2-4 #7 사용량 계측의 기반 |

`429` 수신 시 category `QUOTA_EXCEEDED_429`로 기록하고 **재시도하지 않는다** (§2-5).

Guard 정적검사 9종이 실행 전에 돈다 — **Python 문법 검사(`py_compile`)를 가장 먼저** 두어
문법 오류로 호출 예산을 태우는 경로를 막았다. 이어서 `urlopen` 1회 /
루프 호출 부재 / 재시도·백오프 부재 / 발송코드 부재 / URL 내 key 부재 /
헤더 전송 존재 / Key 출력·길이노출 부재 / 프롬프트 민감정보 부재 /
구조화 출력 구문 3개 존재를 확인한다.

#### (참고) 이 단계가 왜 GA-3보다 먼저인가

설계(§5)는 **STEP 12까지 끝나야 GA-2 완료**라고 규정한다.
현재 `GEMINI_API_KEY`는 등록되었으나(STEP 2, 2026-09-30)
**러너에서 실제로 200을 받는지 한 번도 확인되지 않았다.**

이것을 건너뛰고 GA-3를 돌리면, 실패 시 원인이
"엔진 품질"인지 "키·네트워크"인지 **구분되지 않는다.**
GA-2B/2C에서 얻은 교훈과 같다 — **변수를 하나씩 줄여야 진단이 가능하다.**

### 블로커 ② 파이프라인 코드가 존재하지 않는다

```
저장소 내 .py 파일: 0건 (2026-10-01 확인)
```

설계 §5가 규정한 5개 STEP 중 **구현된 것이 하나도 없다.**

| STEP | 모듈 | 역할 | 현재 |
|---|---|---|---|
| 1 | `collector.py` | 수집 — AI 없음, 네트워크 읽기만 | **미작성** |
| 2 | (Gemini 호출) | 판단 — 7 호출 설계(§2-2). Secret·수신주소 접근 없음 | **미작성** |
| 3 | `build.py` | 조립 — Markdown + HTML 생성 | **미작성** |
| 4 | `gate.py` | `printenv CLOUD_MODE` 직접 조회 + G0~G7 판정 | **미작성** |
| 5 | `gmail_send.py` | STEP 4가 ALL PASS일 때만 실행 | **미작성** |

**GA-2C가 검증한 것은 "SMTP로 1통 보낼 수 있다"까지다.**
`gmail_send.py`의 발송 코드는 GA-2C에서 재사용할 수 있으나,
STEP 1~4는 전부 새로 만들어야 한다.

---

## 3. GA-3 실행 조건 (설계 §6-1 — 변경 없이 그대로)

| 항목 | 값 |
|---|---|
| 커버리지 | **2026-09-14(월) ~ 2026-09-20(일) KST = W38 고정.** 직전 주 자동 계산을 쓰지 않는다 |
| 기준선 | `2026-W38_email_brief_final.html` (rev.2 정본) + `2026-W38_weekly_brief_v2.md` §13 QA |
| 기준선 파일 | **수정 금지·덮어쓰기 금지** |
| 결과 저장 | `03_AUTOMATION_TESTS/github_actions_ga3/2026-W38_gemini.md` / `.html` |
| **발송** | **하지 않는다.** `CLOUD_MODE` 미설정 → G0 FAIL → `SKIPPED_LOCAL_MODE` |
| 실행 횟수 | **2회** (출력 변동성 측정). 7 × 2 = 14 호출 ≤ RPD 20 |
| 같은 날 추가 실행 | **금지** (§2-4) |
| `schedule` | **활성화하지 않는다** |

### 기준선 파일 존재 확인 (2026-10-01)

| 파일 | 상태 |
|---|---|
| `01_WEEKLY_BRIEFS/2026/2026-W38_email_brief_final.html` | 존재 |
| `01_WEEKLY_BRIEFS/2026/2026-W38_weekly_brief_v2.md` | 존재 |

---

## 4. 합격선 (설계 §6-2 / §6-3 — 낮추지 않는다)

### 정량 — 기준선 대비

| 항목 | W38 기준선 | GA-3 합격선 |
|---|---|---|
| 실제 반영 매체 수 | 4 / 5 | **3 이상** (B1) |
| Access Blocked 매체 | 0 | **2곳 이상 증가 금지** (B2) |
| Tier 1 직접 확인 수 | 2 | **2 이상** (B3) |
| Article URL 확보율 | 100% | **80% 이상** (B4) |
| 신제품 KR / US / JP | 5 / 4 / 4 | 각 섹션 존재 + 총 **10건 이상** (B5) |
| Critical QA C1~C7 | 전부 PASS | **FAIL 0건** (B7) |
| 최종 사용 Issue 수 | 27 | **20 이상** |
| Trend Signal 채택 | 3건 | 조건 충족 **2건 이상** |

### 신설 지표

| # | 지표 | 합격선 |
|---|---|---|
| N1 | MUST KNOW 항목 일치율 | **60% 이상** |
| N2 | 숫자 검증 실패 (출력 숫자가 본문에 없음) | **0건** |
| N3 | 규격 위반 (Price enum 이탈, Observation/Interpretation 혼입, 근거 미달 Signal) | **0건** |
| N4 | Gemini 호출 수 / RPD 429 / Fallback 사용 | **8 이하 / 0건 / 0건** |
| N5 | 2회 실행 간 MUST KNOW 변동 | **40% 이하** |

### 정성 — 자동 판정하지 않는다 (§6-4)

- Why it matters의 통찰 수준 — 기준선 HTML과 나란히 읽고 **사용자가 판정**
- 선별의 날카로움 — 추가된 항목 / 빠진 항목을 목록화해 사용자 검토
- 문체 — 기사 제목 옮기기 금지(CLAUDE.md §9) 준수 육안 확인

**PASS 조건**: B1~B7 위반 0건 **그리고** N1≥60% / N2=0 / N3=0 / N4 429=0
**그리고** 사용자의 정성 판정이 "기준선 수준".
**FAIL 시 기준을 낮춰 통과시키지 않는다.**

---

## 5. 권고 실행 순서

설계 §5의 "각 STEP 완료 보고 후 다음으로" 원칙을 따른다.

| 순서 | 내용 | 산출물 | 메일 | AI 호출 |
|---|---|---|---|---|
| **A** | **STEP 12 — Gemini 최소 호출 프로브** ← **준비 완료, 실행 대기** | 200 / 모델 / 구조화 출력 / 토큰 | 없음 | **1회** |
| **B** | STEP 1 — `collector.py` (수집만) | 수집 JSON. 매체 5곳 상태 5단계 기록 | 없음 | **0회** |
| **C** | STEP 2 — Gemini 판단 7 호출 | 구조화 출력 JSON | 없음 | 7회 |
| **D** | STEP 3 — `build.py` | `.md` + `_email_brief.html` | 없음 | 0회 |
| **E** | STEP 4 — `gate.py` | G0~G7 판정 결과. **G0 FAIL 예상** | 없음 | 0회 |
| **F** | GA-3 비교 — 기준선 대조 + 사용자 정성 판정 | 비교표 + 판정 | 없음 | 0회 |

**A를 먼저 하는 이유**: 가장 작고, 실패해도 원인이 하나(키·네트워크)로 특정된다.
B를 먼저 하면 수집 실패와 AI 실패가 섞인다.

**E에서 G0 FAIL은 정상이다.** `CLOUD_MODE`를 만들지 않았으므로 설계대로 발송이 차단된다.
GA-3는 발송을 검증하는 단계가 아니다 — 그것은 GA-2C에서 이미 끝났다.

---

## 6. GA-3에서 하지 않는 것 (경계)

- 정기 `schedule` 등록 — **GA-4 사안**
- `CLOUD_MODE` Variable 생성 — **GA-4까지 만들지 않는다** (§2-3)
- Weekly Brief 실제 발송 — G0 FAIL로 차단되는 것이 정상
- 기준선 파일 수정·덮어쓰기
- 합격선 하향
- `GMAIL_USERNAME` / `GMAIL_APP_PASSWORD` 변경

---

## 7. 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-10-01 | 최초 작성. GA-2C PASS 기록 후 GA-3 준비 상태·블로커 2건·권고 순서 정리. **GA-3 미실행** |
| 2026-10-01 | 순서 A 착수 — STEP 12 Gemini 프로브 workflow 신설(`gemini-probe.yml`). **미실행.** 블로커 ②(파이프라인 코드 0건)는 그대로 |
| 2026-10-07 | Dry Run 2회 503 실패 → Gemini 재시도 backoff 개정(단계당 3회 시도 · 60→120초). **§8-7 참조. 재실행 대기** |
| 2026-10-07 | STEP 12 PASS(`gemini-3.8-flash`) 확인 → 블로커 ① 해소. 파이프라인 9개 모듈 + GA-3 workflow 신설로 블로커 ② 해소. 발송 정책을 `[TEST]` 1통(사용자 확인 입력 필수)으로 확정. **§8 참조. GA-3 자체는 아직 미실행** |

---

## 8. GA-3 구현 (2026-10-07) — workflow·파이프라인 신설, **미실행**

STEP 12 Gemini Probe 가 **최종 PASS**(`MODEL=gemini-3.8-flash`, HTTP 200 / 모델 사용 가능 /
responseSchema / usageMetadata / Overall PASS)하고 Repository Variable `GEMINI_MODEL` 이
등록되면서 §2 의 블로커 ①이 해소됐다. 이어서 블로커 ②(파이프라인 코드 0건)를 해소했다.

### 8-1. 신설 파일

| 경로 | 역할 | AI | 메일 | 저장소 쓰기 |
|---|---|---|---|---|
| `.github/workflows/ga3-weekly-brief-e2e.yml` | GA-3 수동 실행 workflow (`workflow_dispatch` 전용) | — | — | 없음 (`contents: read`) |
| `04_PIPELINE/common.py` | 주차·커버리지·날짜 파싱·마스킹·IO | 0 | 0 | — |
| `04_PIPELINE/sources.py` | Source 레지스트리 (GA-1 검증 경로 우선, Fallback 순서) | 0 | 0 | — |
| `04_PIPELINE/collector.py` | STEP 1 수집 — robots 준수·커버리지 필터·Noise 규칙·기계적 중복 클러스터링 | **0** | 0 | 없음 |
| `04_PIPELINE/gemini_client.py` | 호출 예산·RPM 페이싱·재시도 정책 강제 | 호출 지점 1곳 | 0 | — |
| `04_PIPELINE/analyze.py` | STEP 2 — 7 호출 + 코드 측 재검증 | 7 | 0 | 없음 |
| `04_PIPELINE/build.py` | STEP 3 — Weekly Brief(.md) + Compact Email(.html) | 0 | 0 | 러너 임시 디렉터리만 |
| `04_PIPELINE/qa.py` | STEP 4 — QA 14지표 + Critical C1~C7 | 0 | 0 | 러너 임시 디렉터리만 |
| `04_PIPELINE/gate.py` | STEP 5 — G0~G7 판정, FAIL CLOSED | 0 | 0 | 없음(원장은 **읽기만**) |
| `04_PIPELINE/gmail_send.py` | STEP 6 — GA-2B/2C PASS 코드 그대로 재사용, 1통 | 0 | 1통(TEST) | 없음 |
| `04_PIPELINE/selftest.py` | 네트워크·AI·SMTP 없이 규칙 93건 검증 | 0 | 0 | 없음 |

### 8-2. 호출 예산 (사용자 GA-3 지시 반영)

| 항목 | 값 | 강제 지점 |
|---|---|---|
| 정상 실행 목표 | **7 호출** | `analyze.py` 단계 구성 |
| 권고 상한 | **8 호출** (재시도 1회 포함) | `RECOMMENDED_CAP` |
| 절대 상한 | **10 호출** | `HARD_CAP` — 초과 요청은 호출 **전에** 거부 |
| 재시도 | **503 / 429(분당 한도)만.** 단계당 **최대 3회 시도**(재시도 2회), 대기 **60초 → 120초**, 실행당 재시도 총 3회 (2026-10-07 개정 — §8-7) | `_retryable()` · `BACKOFF_SECONDS` |
| 429 일일 한도(RPD) · 구분 불가 | **재시도 없음, 즉시 중단** | 보수적 분류 |
| 그 밖의 모든 오류 | **즉시 Fail Closed** | 400/401/403/404/500/네트워크/스키마 위반 |
| RPM 5 준수 | 호출 간 **30초** 페이싱 | `PACE_SECONDS` |
| Fallback 모델 | **사용하지 않는다** | 코드·Guard 양쪽에서 차단 |

### 8-3. 발송 정책 — §3·§6 에서 **변경된 부분** (사용자 지시, 2026-10-07)

| | 2026-10-01 준비안 | **GA-3 구현 (현재)** |
|---|---|---|
| 발송 | 하지 않는다 (G0 FAIL → `SKIPPED_LOCAL_MODE`) | **QA PASS 시 `[TEST]` 메일 1통** |
| 근거 | — | `send_gate.md` §1-2 LOCAL MODE **수동 테스트 경로** (`[TEST]` 접두 + 본인 수신, 원장 Status=TEST → §4-3 중복 판정 대상 아님). GA-2C 와 같은 성격 |
| 승인 | — | `workflow_dispatch` 입력 `confirm_send` 에 **사용자가 `SEND-TEST` 를 직접 입력**한 경우에만 |
| `CLOUD_MODE` | 만들지 않는다 | **그대로 만들지 않는다.** `gate.py` 가 프로세스 환경변수를 **조회만** 하고 기록한다 |
| 정식 발송 | GA-4 | **GA-4 — 이 코드에 정식 발송 경로가 없다** |

발송 차단 Gate (하나라도 어긋나면 0통):
`G1` Brief 생성 · `G2` Email 생성(인라인 스타일만) · `G3` **Critical QA FAIL = 0** ·
`G4` `WIB_RECIPIENT` 단일 유효 주소 · `G6` 중복 확인 수행 · `G7` 같은 주차 정식 발송 기록 없음 ·
`GC` 사용자 확인 문자열 일치. `G5`(SMTP AUTH)는 발송 단계에서 판정하며
AUTH 가 PASS 가 아니면 발송 호출 자체를 하지 않는다.

**남은 규격 공백**: `G6` 의 2중 확인 중 **Gmail 조회는 러너에서 불가**(SMTP 전용)하다.
GA-3 는 Status=TEST 발송이라 §4-3 에 따라 중복 판정 대상이 아니므로 원장 확인만으로 진행한다.
**정식 발송(GA-4)에서는 Gmail 조회 경로를 붙여 G6 을 완전히 충족시켜야 한다**
(`ga2_auth_design.md` §3-5 와 같은 항목이다).

### 8-4. 자체 점검 결과 (2026-10-07, 실행 전)

| 점검 | 방법 | 결과 |
|---|---|---|
| Python 문법 | 9개 모듈 `py_compile` | **오류 0건** |
| 규칙·Gate 로직 | `selftest.py` (네트워크·AI·SMTP 미사용) | **93건 PASS / 0 FAIL** |
| 수집 파이프라인 | `http_get` 대체 주입 후 전 구간 실행 | 커버리지 필터·Noise·5단계 상태·클러스터링 정상 |
| 전 구간 통합 | 가짜 Gemini 응답으로 analyze→build→qa→gate | **7 호출 / Critical FAIL 0 / decision=SEND_TEST** |
| 미검증 숫자 삭제 | 발췌에 없는 수치를 투입 | `[수치 미검증]` 으로 치환 확인 |
| Confidence 상한 | 계절성 위험 + High 요청 | **Medium 으로 강등** 확인 |
| 발송 차단 | QA FAIL / 확인문자열 불일치 / SENT 기록 / 원장 없음 | 4경로 모두 **0통** |
| Secret·수신주소 노출 | Guard 정적 검사(그렙) 로컬 재현 | **0건** |

> 점검은 로컬에 Python 이 없어 **WASM(pyodide, Python 3.14)** 으로 실행했다.
> 러너(ubuntu-24.04, Python 3.12)에서도 같은 검사가 **STEP 0a/0b 에서 먼저** 돌고,
> 실패하면 수집·Gemini 호출·발송을 시작하지 않는다.
> 네트워크 실제 접근(실 Source 응답)과 실제 Gemini 응답 품질은 **실행해야 확인된다.**

### 8-5. 실행 방법 (사용자 수동)

1. GitHub → Actions → **GA-3 Weekly Brief E2E (Manual)** → Run workflow
2. `weekly_id` = `2026-W38` (기준선 비교 고정값)
3. 메일 없이 산출물만 보려면 `confirm_send` 를 **비워 둔다** → `SKIPPED_NO_CONFIRM`
4. 테스트 메일 1통까지 확인하려면 `confirm_send` = `SEND-TEST`
5. 산출물은 Artifact `ga3-2026-W38-output` (`2026-W38_gemini.md` / `.html` /
   `collected.json` / `analysis.json` / `qa.json` / `gate.json` / `send_result.json`)
6. 같은 날 **2회까지만** 실행한다 (RPD 20 — 설계 §2-4)

### 8-6. GA-3 가 여전히 하지 않는 것

- 정기 `schedule` 등록 (GA-4)
- `CLOUD_MODE` Variable 생성 (GA-4)
- 정식 발송 (`[WEEKLY INTELLIGENCE]` 제목 · Status=SENT)
- 기준선 파일·원장·트래커 CSV 쓰기 (workflow 마지막 Guard 가 `git status` 로 무변경 확인)
- 합격선 하향 (§4 의 B1~B7 / N1~N5 그대로)

### 8-7. Dry Run 2회 실패 → 재시도 backoff 개정 (2026-10-07)

| 회차 | 결과 |
|---|---|
| Dry Run 1 | 앞단(Selftest·수집) 정상, **STEP 2 에서 `SERVICE_UNAVAILABLE_503`** |
| Dry Run 2 | 동일 — **503 재현** |

503 은 Gemini 측 **일시적 과부하**이며 우리 요청의 결함이 아니다. 기존 정책(단계당 재시도 1회,
대기 20초)은 과부하 구간을 넘기기에 짧았다. 아래만 바꾼다.

| 항목 | 이전 | **현재** |
|---|---|---|
| 단계당 시도 | 2회 (재시도 1) | **3회 (재시도 2)** — `MAX_ATTEMPTS_PER_STAGE` |
| 대기 | 20초 고정 | **60초 → 120초** — `BACKOFF_SECONDS` (상한 180초) |
| 재시도 대상 | 503 / 429(분당) | **동일 — 변경 없음** |
| 429 일일 한도 · 구분 불가 | 재시도 없음 | **동일 — 즉시 중단** |
| 그 밖의 오류 | 즉시 Fail Closed | **동일** |
| 실행당 재시도 총량 | 3회 | **동일** (7 + 3 = `HARD_CAP` 10) |

Summary·QA 에 **attempt count / retry count / 마지막 HTTP status / final category** 를 표시한다
(성공·실패 양쪽 경로 모두).

**수정 파일은 4개뿐이다** — `gemini_client.py`(정책) · `analyze.py`(Summary 표시) ·
`qa.py`(지표 2행) · workflow 의 Guard 상수 검사. 수집 · QA 판정 · Gmail · send gate ·
`confirm_send` 로직과 W38 기준파일은 **무변경**이며 `schedule` 도 여전히 없다.

자체 점검(pyodide): py_compile 오류 0 / selftest **112 PASS · 0 FAIL**
(503 3회 시도·60→120초 backoff·400/403/500 즉시 중단·예산 1이면 재시도 없음 포함) /
Guard 전체 exit 0 / 가짜 Gemini 전구간 7호출·`SEND_TEST` 유지.
