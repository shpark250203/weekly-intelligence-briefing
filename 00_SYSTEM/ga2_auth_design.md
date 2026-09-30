# GA-2 — AI 엔진 · Gmail 발송 인증 설계 (rev.4 — Gemini 2.5 Free Tier + SMTP App Password)

> GitHub Actions에서 Weekly Brief를 **생성·발송하기 전에** 필요한 인증과 실행 구조를 준비하는 설계 문서다.
> `send_gate.md`(발송 차단 규격)와 `cloud_runbook.md`(운영 절차)의 하위 문서이며, **두 문서를 넘어설 수 없다.**
> 선행 조건: `03_AUTOMATION_TESTS/github_actions_ga1/ga1_connectivity_result.md` (GA-1 PASS).

## rev.2 변경 사유 (2026-09-30)

**목표가 "월 운영비 0원"으로 확정되었다.** rev.1의 Anthropic 종량 과금 방식(1회 $9~19)을 폐기하고
**GitHub Actions + Gemini API Free Tier + Gmail API** 조합으로 재설계했다.

- **Anthropic API Key를 만들지 않는다.** Anthropic Billing·Workspace 설정도 하지 않는다.
- **W38 rev.2 품질 기준은 그대로 유지한다.** 품질 기준을 낮추는 것은 이 변경의 범위가 아니다.

## rev.4 변경 사유 (2026-09-30)

**Gmail 발송을 OAuth에서 App Password + SMTP로 전환한다.** 사유·트레이드오프·구조는 §3.
OAuth 설계는 **삭제하지 않고 §3-D에 보존**한다. AI 엔진(§1·§2)·GA-1·QA Gate·중복발송 방지·
Fail Closed 구조는 **무변경**이다.

## GA-2에서 하지 않는 것 (경계)

- Gemini API Key 발급 ✕
- Weekly Brief 실제 생성 ✕
- Gmail 실제 발송 ✕ (Draft 포함 ✕)
- End-to-End 실행 ✕
- `schedule:` 활성화 ✕
- `CLOUD_MODE=true` 설정 ✕
- W38 기준선 파일 수정 ✕
- Claude Cloud Routine — `enabled:false` 유지

**이 문서에는 어떤 Secret 값도 적지 않는다.** 이름만 정의한다.

---

# 1. 핵심 전제 — 엔진 교체는 Key 교체가 아니다

**W38 rev.2 품질은 모델이 아니라 하네스에서 나왔다.**
`CLAUDE.md` + `/weekly-brief` Skill + Claude Code의 에이전트 루프(수집→판단→재수집 60~120턴)의 조합이다.
Gemini API는 **모델만** 제공한다. 루프·도구·파일 접근은 제공하지 않는다.

→ 따라서 **수집·정리 계층을 우리가 직접 만들고, Gemini에게는 판단만 맡긴다.**

**GA-1이 이 설계의 전제를 이미 실증했다.** 러너에서 5개 뷰티 전문매체 전부와 Tier 1 7곳에
평문 HTTP로 접근된다(PASS 15 / ERROR 0). 즉 **에이전트형 WebFetch 없이 결정론적 수집기로 대체 가능**하다.

## 1-1. 2계층 구조

```
[계층 A] 수집·정제 — Python, AI 호출 0건, quota 소모 0
  A1 5개 매체 + Tier 1 + 신제품 Source 목록 페이지 수집 (robots.txt 준수, 식별 UA, 지연)
  A2 기사 파싱 → id / 매체 / 제목 / 보도일자 / 개별 기사 URL / 본문 발췌
  A3 커버리지 기간 필터 (직전 월 00:00 ~ 일 23:59 KST) — Python이 계산
  A4 기계적 중복 제거 — URL 정규화 + 제목 정규화 + n-gram 유사도 클러스터링
  A5 규칙 기반 Noise 제외 — CLAUDE.md §4-1 카테고리 키워드 (MOU·수상·채용·ESG 캠페인 등)
  → _work/<YYYY-Www>/articles.jsonl  (약 150~250건)

[계층 B] 판단 — Gemini, 구조화 출력(JSON Schema), 배치 호출
  B1 2-of-5 Rule 판정 + AXIS 분류        (배치 ~40건/호출)
  B2 Issue 병합 (인과관계 묶음)            (1~2 호출)
  B3 Issue별 요약 + Why it matters         (배치 ~8건/호출)
  B4 AXIS 2 심층 처리 (숫자·맥락·시사점)   (1~2 호출)
  B5 신제품 추출 — 국가별 독립 호출         (KR/US/JP 각 1 호출)
  B6 Trend Signal — 국가별 독립 호출        (KR/US/JP 각 1 호출)

[계층 C] 검증·조립 — Python, AI 호출 0건
  C1 숫자 검증 · URL 대조 · QA 14지표 산출 · Markdown/HTML 조립
```

## 1-2. 이 구조가 품질을 지키는 방식 (중요)

**Critical QA 항목 다수가 "모델이 기억해야 하는 규칙"에서 "코드가 강제하는 제약"으로 이동한다.**

| Critical | rev.1 (에이전트) | rev.2 (2계층) |
|---|---|---|
| **C1** 커버리지 기간 | 모델이 준수 | **Python이 계산·필터** → 구조적 보장 |
| **C4** 신제품 국가 분리 | 모델이 섞지 않아야 함 | **국가별 독립 호출** → 섞일 수 없음 |
| **C5** Article URL 확보율 | 모델이 URL을 정확히 옮겨야 함 | **URL은 수집기 출력에서만 온다. 모델은 id만 반환** → **URL 환각 불가능** |
| **C6** Tier 1 표기 | 모델이 판단 | **실제 fetch 로그로 집계** → 모델이 주장할 수 없음 |
| **C2** MUST KNOW URL | 모델이 채움 | id → URL 매핑을 코드가 채움 |
| 신제품 Price 3단계 | 모델이 표기 규칙 준수 | **JSON Schema enum 강제** (`Verified`/`Not disclosed`/`Not verified`) |
| Trend Signal 조건 A/B | 모델이 자제 | **Evidence Count를 코드가 계산 → 미달이면 Signal 자체를 버리고 Watch Item으로 강제 이동** |
| Observation ↔ Interpretation 분리 | 서술 규칙 | **Schema의 별도 필드** → 섞일 수 없음 |
| 숫자 신뢰 | 모델 자제에 의존 | **출력의 모든 숫자가 제공 본문에 존재하는지 사후 검증**, 불일치는 FLAG |

**그래서 남는 위험은 하나로 좁혀진다 — 판단의 날카로움.**
2-of-5 선별의 정확도, Why it matters의 통찰, Trend Signal 해석의 깊이.
이것이 **GA-3에서 실측해야 할 유일한 핵심 항목**이다(§6).

## 1-3. 감수하는 위험 — 구현 이원화

Actions 실행 경로는 Python 파이프라인, 로컬 수동 실행 경로는 `/weekly-brief` Skill이 된다.
**같은 규격의 구현이 둘이 되므로 규칙 drift 위험이 생긴다.**

| 완화 | 내용 |
|---|---|
| 단일 규칙 소스 | 매체 목록·Noise 키워드·2-of-5 기준·Price enum·Signal 조건을 `00_SYSTEM/rules/*.yaml`로 추출해 **파이프라인과 Skill이 같은 파일을 참조**한다 (GA-3 설계 항목, 권고) |
| 상시 대조 | GA-3 비교(§6)를 엔진·규칙 변경 시마다 재실행 |
| 로컬 경로 보존 | `cloud_runbook.md` §6 — 자동화 2회 이상 정상 실행 + QA 통과 전까지 로컬 실행을 삭제·비활성화하지 않는다 |

---

# 2. Gemini API 설계

## 2-1. 확정 모델 — 계정 실측 한도 기준 (2026-09-30, AI Studio 직접 확인)

**설계는 공식 문서의 일반론이 아니라 이 계정에 실제로 부여된 한도를 기준으로 한다.**

| 모델 | RPM | TPM | **RPD** | Tier | 역할 |
|---|---|---|---|---|---|
| **`gemini-2.5-flash`** | 5 | 250,000 | **20** | Free | **Primary** — 모든 판단 단계 |
| **`gemini-2.5-flash-lite`** | 10 | 250,000 | **20** | Free | **Fallback** — §2-5의 제한된 조건에서만 |
| Gemini 2 / 2 Flash-Lite | 0 | 0 | 0 | — | **사용 불가** (한도 0) |

### 이 실측이 설계에 강제한 변경

| 항목 | rev.2 (문서 일반론 기준) | **rev.3 (실측 기준)** |
|---|---|---|
| 주 모델 | `gemini-3.8-flash` | **`gemini-2.5-flash`** — 이 계정 목록에 3.x가 없다 |
| 1회 호출 예산 | 22~26 | **7 (목표) / 8 (권고 상한) / 10 (절대 상한)** |
| 병목 | RPD(수치 미공개) | **RPD 20 — 확정된 하드 제약** |

> **rev.2의 호출 설계(22~26)는 RPD 20을 초과한다.** 즉 그대로 실행하면 1회 실행이 완주하지 못한다.
> §2-2를 **"적은 수의 큰 호출"** 로 전면 재편했다.

**TPM 250K가 넉넉한 것이 이 재편을 가능하게 한다.** 이 계정의 제약은 토큰이 아니라 호출 횟수다.
따라서 **호출당 투입 토큰을 최대화하고 호출 수를 최소화**하는 것이 정답이다.

**모델 ID를 코드에 하드코딩하지 않는다.** Repository Variable `GEMINI_MODEL` / `GEMINI_MODEL_FALLBACK`
로 주입한다 — 무료 제공 모델과 한도는 변경되며, 특히 공식 문서는 Gemini 2.5 계열 접근을
**기존 사용자로 제한**하는 중이라고 안내한다. 향후 이 계정에서 2.5가 사라지거나 3.x가 열리면
**코드 수정 없이 Variable만 교체**한다. GA-3 실행 시마다 실제 한도를 재확인해 이 표를 갱신한다.

## 2-2. RPD 20 안에서 5개 작업을 처리하는 방식 — **7 호출 설계**

### 설계 원칙 3개

1. **RPD가 유일한 병목이다.** TPM 250K·컨텍스트 1M은 남는다 → **호출당 토큰을 최대로 채운다.**
2. **뉴스 1건당 1호출을 절대 하지 않는다.** 모든 판단은 배치다.
3. **판단 종류가 같으면 같은 호출에 합친다.** 선별과 병합은 같은 목록 위의 판단이므로 한 호출이다.
   요약과 Why it matters는 같은 Issue 위의 서술이므로 한 호출이다.

### 호출 계획 — 정상 실행 **7회**

| 호출 | 단계 | 입력 | 출력 (JSON Schema) | 모델 |
|---|---|---|---|---|
| **1** | **AXIS 1 선별 + 병합** | 규칙 필터 통과 일반 기사 전량 (~120건 × 발췌 600자) | `{id, axis, criteria_met[], cluster_id, keep}` | Primary |
| **2** | **AXIS 2 선별 + 병합** | 뷰티 기사 전량 (~60건) | 동일 + `media` | Primary |
| **3** | **MUST KNOW 선정 + AXIS 1 작성** | 채택 Issue 본문 + **AXIS 2 채택 제목 목록**(교차 선정용, 제목만이라 저렴) | Issue별 `{무엇이_달라졌는가, why_it_matters, tag, must_know_rank}` | Primary |
| **4** | **AXIS 2 심층 작성** | 채택 뷰티 Issue 본문 | `{무엇이_달라졌는가, 숫자, 맥락, 시사점, tag}` | Primary |
| **5** | **KOREA 신제품 + Trend Signal** | KR 신제품 Source | 제품 배열 + Signal `{observation, evidence, interpretation, confidence}` | Primary |
| **6** | **USA 신제품 + Trend Signal** | US Source | 동일 | Primary |
| **7** | **JAPAN 신제품 + Trend Signal** | JP Source | 동일 | Primary |

**5개 작업이 어디에 배치되었는가**

| 작업 | 호출 |
|---|---|
| 뉴스 중요도 선별 | 1, 2 (2-of-5는 `criteria_met` 길이 ≥ 2 로 **코드가 판정**. 모델은 근거만 제시) |
| 중복 제거 | 1차 계층 A 기계적 클러스터링(**호출 0**) → 인과관계 병합 판단만 1, 2에 포함 |
| 요약 | 3, 4 |
| **Why it matters** | **3, 4 — 요약과 같은 호출의 별도 필드** (호출 분리 금지) |
| **Trend Signal** | 5, 6, 7 — **국가별 독립 호출로 C4 구조적 보장.** Evidence Count는 코드가 재계산하고, 조건 A(3건+)·B(2건+Tier 1/2) 미달이면 **Signal을 폐기하고 Watch Item으로 강등** |

### 호출 예산 (확정)

| 구분 | 값 |
|---|---|
| 정상 실행 | **7회** |
| 권고 상한 | **8회** (재시도 1회 포함) |
| **절대 상한 (`AI_CALL_BUDGET`)** | **10회** — RPD 20의 **50%**. 초과 시 코드가 즉시 중단 |
| 재시도 | **단계당 최대 1회**, 실행당 총 3회 |
| 같은 날 재실행 여유 | 7회 실행 후에도 **13회 남음** → 실패 시 같은 날 1회 재실행 가능 |

### RPM · TPM 준수 (호출 수만 지키면 되는 게 아니다)

| 한도 | 실측 | 준수 방식 |
|---|---|---|
| RPM 5 | 분당 5회 | **호출 간 30초 이상 간격**을 코드가 강제 (7회 × 30초 = 3.5분) |
| TPM 250K | 분당 25만 토큰 | **호출당 입력 100K 토큰 상한.** 30초 간격이면 분당 최대 2호출 = 200K < 250K |
| thinking 토큰 | 출력에 포함 | TPM 계산에 포함해 여유를 둔다. thinking을 끄지 않는다(품질) |

**호출당 100K 토큰**은 기사 발췌 600자(≈400토큰) 기준 **약 250건**에 해당한다. 넉넉하다.

### 구조화 출력을 반드시 쓴다

`responseMimeType: "application/json"` + `responseSchema` 를 모든 호출에 적용한다.

- 파싱이 결정론적이 되고, §1-2의 Schema 강제 효과가 나온다.
- **자유 서술 출력을 쓰지 않는다.** 서술형은 규격 위반을 조용히 통과시킨다.
- Schema 위반 응답은 재시도 1회 → 실패 시 해당 단계 실패(§2-5).

### 컨텍스트 절약

- 본문 전체를 넣지 않는다. **발췌(제목 + 리드 + 숫자가 있는 문단, 상한 2,000자)** 만 넣는다.
- 같은 기사를 여러 단계에 재투입하지 않는다. 단계 간에는 **id로만** 참조한다.

## 2-3. GitHub Secret 이름

| Secret 이름 | 용도 | GA-2에서 등록 |
|---|---|---|
| **`GEMINI_API_KEY`** | Gemini API 인증 | **등록 대상** |
| **`GMAIL_CLIENT_ID`** | OAuth Client ID | 등록 대상 |
| **`GMAIL_CLIENT_SECRET`** | OAuth Client Secret | 등록 대상 |
| **`GMAIL_REFRESH_TOKEN`** | 장기 인증 | 등록 대상 |
| **`WIB_RECIPIENT`** | 수신 주소 (저장소 기록 금지) | 등록 대상 |
| `ANTHROPIC_API_KEY` | **Fallback 전용** (§7) | **만들지 않는다.** 이름만 예약 |

### Secret이 아닌 것 — Repository Variable

| Variable | 값 | 생성 시점 |
|---|---|---|
| `AI_ENGINE` | `gemini` | GA-3 |
| `GEMINI_MODEL` | `gemini-2.5-flash` | GA-3 |
| `GEMINI_MODEL_FALLBACK` | `gemini-2.5-flash-lite` | GA-3 |
| `AI_CALL_BUDGET` | **`10`** (RPD 20의 50%) | GA-3 |
| `CLOUD_MODE` | `true` (정확히 소문자) | **GA-4 — 그전까지 만들지 않는다** |

Secret은 로그에서 자동 마스킹되지만 위 4건은 비밀이 아니므로 Variable이 맞다.
**둘 다 저장소 파일 밖에 있다** — 이것이 G0(`send_gate.md` §1-1-1)가 요구하는 조건이다.

## 2-4. 무료 사용량 초과 방지 (6중)

| # | 수단 | 성격 |
|---|---|---|
| 1 | **Google Cloud 프로젝트에 결제(Billing)를 연결하지 않는다** | **0원의 근본 보장.** 결제 수단이 없으면 초과 시 과금이 아니라 429가 난다. 구조적으로 청구가 불가능하다 |
| 2 | **호출 배치화** (§2-2) | 1회 **7 호출**. 뉴스 1건당 1호출을 금지한다 |
| 3 | **자체 호출 예산 카운터** | 코드가 호출 수를 세고 `AI_CALL_BUDGET`=**10** 초과 시 **즉시 중단**. RPD 20에 부딪히기 전에 우리가 먼저 멈춘다 |
| 4 | **재시도 총량 제한** | **단계당 최대 1회**, 실행당 총 3회. 재시도 폭주로 RPD를 태우는 경로를 막는다 |
| 5 | **RPM·TPM 페이싱** | 호출 간 **30초 이상 간격**, 호출당 입력 **100K 토큰 상한** (§2-2) |
| 6 | **주 1회 + 동시 실행 금지** | `concurrency` 그룹. GA-4까지 `workflow_dispatch` 전용 |
| 7 | **사용량 계측 기록** | 실행마다 호출 수·토큰·429 발생을 `99_RUN_LOG/`에 남겨 추세를 본다 |

### RPD 20 소진 시나리오 점검

| 시나리오 | 호출 소모 | 남은 RPD | 판정 |
|---|---|---|---|
| 정상 실행 1회 | 7 | 13 | 안전 |
| 실패 후 같은 날 재실행 | 7 + 7 = 14 | 6 | 허용 |
| 3회 실행 | 21 | **초과** | **금지 — 같은 날 2회까지만** |
| 절대 상한까지 소모한 실행 1회 | 10 | 10 | 재실행 1회 여지 있음 |

**같은 주차를 같은 날 3회 이상 실행하지 않는다.** 2회 실패 시 그날은 중단하고 다음 날 또는 로컬 수동 실행으로 간다.

> **⚠ 한도 수치는 계정별로 다르고 변동된다.**
> 공식 문서(`ai.google.dev/gemini-api/docs/rate-limits`, 2026-09-30 확인)는 모델별 무료 한도를
> 공개하지 않고 **"AI Studio에서 본인 한도를 확인하라"** 고만 안내한다.
> §2-1의 표는 **2026-09-30 사용자가 AI Studio에서 직접 확인한 실측값**이다.
> **GA-3 실행 시마다 재확인하고, 달라졌으면 §2-1과 `AI_CALL_BUDGET`을 함께 갱신한다.**
> RPD가 7 미만으로 줄면 이 설계는 성립하지 않으므로 **즉시 보고하고 중단한다.**
>
> **미확인 항목 1건**: RPD 20이 **모델별 독립인지, 프로젝트 합산인지** 확인되지 않았다.
> AI Studio가 모델별로 표시하므로 독립으로 보이나 **[추정]이다.**
> 설계는 이에 의존하지 않는다 — Primary만으로 7회를 완주하도록 구성했고,
> Fallback 사용은 §2-5의 제한된 조건뿐이다. GA-3에서 실측 확인한다.

## 2-5. Quota 초과 시 Fail Closed

**판단이 서지 않으면 보내지 않는다** (`send_gate.md` §0).

| 상황 | 처리 |
|---|---|
| **429 — 분당 한도(RPM/TPM)** | 서버가 준 `retryDelay` 만큼 대기 후 **1회만** 재시도 |
| **429 — 일일 한도(RPD 20)** | **재시도 금지. 즉시 중단.** 오늘은 회복되지 않는다. 대기 루프를 만들지 않는다 |
| 400 / 401 / 403 (키·요청 오류) | **재시도 금지.** 즉시 중단 |
| 500 / 503 | **1회만** 재시도 후 중단 |
| 자체 호출 예산(10) 초과 | 즉시 중단 (§2-4 #3) — quota에 닿기 전에 우리가 멈춘다 |
| Schema 위반 응답 | 1회 재시도 → 실패 시 해당 단계 실패 |
| `finishReason: SAFETY` 등 응답 차단 | 해당 배치 실패로 처리. **내용을 지어내지 않는다.** 실패 배치가 전체의 20% 초과면 실행 중단 |
| 숫자 검증 실패 (출력 숫자가 본문에 없음) | 해당 수치를 삭제하고 QA에 FLAG. 건수가 3건 초과면 **G3 FAIL** |

### Fallback 모델(`gemini-2.5-flash-lite`)을 쓸 수 있는 조건 — 제한적으로만

두 요구가 동시에 걸려 있다. ① Fallback 모델을 둔다 ② **W38 rev.2 품질을 유지한다.**
둘을 함께 만족시키는 유일한 방법은 **단계별로 허용 여부를 다르게 두는 것**이다.

| 호출 | Fallback 허용 | 이유 |
|---|---|---|
| **1, 2** (선별 + 병합) | **허용** | 출력이 `id`·`criteria_met`·`cluster_id` 뿐이고 **코드가 전부 재검증**한다. 품질이 서술에 있지 않다 |
| **3, 4** (요약 + Why it matters) | **금지** | 이 문장들이 곧 산출물의 품질이다. 여기서 모델을 낮추면 조용한 품질 저하다 → **Fail Closed** |
| **5, 6, 7** (신제품 + Trend Signal) | **금지** | Trend Signal의 해석·Confidence 판정은 품질의 핵심이다 → **Fail Closed** |

- Fallback을 **1회라도 사용한 실행은 QA에 `FALLBACK_MODEL_USED` 로 기록**하고,
  **§6의 품질 비교 대상에서 제외**한다. 다른 모델의 결과를 기준선과 비교하면 비교가 무의미해진다.
- Fallback은 **모델을 낮추는 행위**이므로, 허용 구간에서도 **자동 반복하지 않는다.**
  같은 주차에 2회 이상 Fallback이 발동하면 실행을 중단하고 보고한다.

**공통 처리 — 금지 사항이 핵심이다**

1. **작성 단계에서 모델을 낮춰 완주하지 않는다.** 호출 3~7의 Primary 실패는 **실행 실패**다.
2. **Anthropic 유료 경로로 자동 전환하지 않는다.** 자동 전환은 사용자가 승인하지 않은 지출이다. §7의 전환은 **수동 결정 전용**이다.
3. **부분 생성본을 발송하지 않는다.** Brief 미완성 → G1 FAIL → 발송 단계 미실행.
4. **무한 재시도·대기 루프를 만들지 않는다.** 단계당 1회, 실행당 3회가 전부다.
5. workflow는 0이 아닌 종료코드로 끝나고, `99_RUN_LOG/<YYYY-Www>_FAILED.md` 를 커밋한다
   (`send_gate.md` §5-2 순서 3 — Gmail과 독립된 알림 채널). 기록에 **소모한 호출 수와 429 종류**를 남긴다.

## 2-6. ⚠ 무료 티어 데이터 사용 — 기록

**공식 Pricing 문서(2026-09-30 확인) 기준, 무료 티어는 제출한 콘텐츠가 Google 제품 개선에 사용된다.**

| 티어 | "used to improve our products" |
|---|---|
| **Free tier** | **Yes** |
| Paid tier | No |

이 프로젝트가 **수용하는 위험이며, 수용 가능한 이유**는 다음과 같다.

- Gemini 프롬프트에 들어가는 것은 **공개된 언론 기사 본문 발췌와 선별 규칙**뿐이다. 비공개 정보가 아니다.
- 따라서 유출 위험의 실질은 "이 프로젝트가 어떤 기사를 어떤 기준으로 본다"는 **관심사 노출**에 한정된다.

**프롬프트에 절대 넣지 않는 것** (설계 제약, 코드로 강제)

- `WIB_RECIPIENT` (수신 주소) — 발송 계층에만 존재하고 AI 계층에 전달되지 않는다
- 모든 Secret 값
- 로컬 파일 경로·저장소 디렉터리 구조
- `send_ledger.csv` 내용, 발송 이력
- 개인정보·비공개 사업 정보

**이 조건이 수용 불가로 바뀌는 경우**: 유료 티어(데이터 사용 No) 또는 §7의 Anthropic 경로로 전환한다.
**무료 티어를 쓰는 동안 이 사실을 잊지 않기 위해 이 절을 문서에 고정한다.**

---

# 3. Gmail 발송 설계 — SMTP + App Password (rev.4 채택)

## 3-1. 전환 결정 (2026-09-30)

**OAuth `gmail.send` 방식을 중단하고 App Password + SMTP로 전환한다.**

| 방식 | rev.1~3 | **rev.4** |
|---|---|---|
| ① Gmail API OAuth + refresh token | 채택 | **DEPRECATED** (§3-D에 원문 보존) |
| **② SMTP + App Password** | 기각 | **채택** |
| ③ 서비스 계정 + 도메인 위임 | 불가 | 불가 — 개인 Gmail에는 쓸 수 없다 (Workspace 전용) |

**전환 사유 (사용자 결정)**: 주 1회 개인 계정 발송이라는 용도에 비해
OAuth External + Production 게시 + Branding/Verification 절차의 운영 부담이 과도하다.

**전환 시점의 사실**: OAuth Client는 생성되었으나 **refresh token은 발급된 적이 없다.**
GitHub Secrets에 OAuth 관련 값이 등록된 적도 없다. → **폐기해야 할 자격증명이 0건이다.**

### 감수하는 트레이드오프 (기록)

| | OAuth `gmail.send` | **App Password (채택)** |
|---|---|---|
| 권한 범위 | 보내기 전용 | **넓음** — SMTP 발송 + (IMAP/POP 활성 시) 읽기까지 같은 값으로 가능 |
| 유출 시 영향 | 낮음 | **중** |
| 개별 폐기 | 가능 | **가능 — 즉시**, 계정 비밀번호 변경 불필요 |
| 만료 | Production이면 무기한 | 없음 (계정 비밀번호 변경 시 무효) |
| 운영 복잡도 | 높음 (토큰 갱신·게시·검증) | **낮음** (표준 `smtplib`) |

**권한 범위가 넓어지는 것을 개별 폐기 가능성으로 상쇄한다**는 판단이다.
**실제 Gmail 계정 비밀번호는 어떤 경우에도 사용하지 않는다.** App Password만 쓴다.

## 3-2. SMTP 연결 규격

| 항목 | 값 |
|---|---|
| 호스트 | `smtp.gmail.com` |
| **주 포트** | **465 — 암시적 TLS (`smtplib.SMTP_SSL`)** |
| 대체 포트 | 587 — STARTTLS (465가 차단된 경우에만) |
| TLS 컨텍스트 | `ssl.create_default_context()` — **인증서·호스트명 검증을 끄지 않는다** |
| 인증 | SMTP AUTH — `GMAIL_USERNAME` + `GMAIL_APP_PASSWORD` (공백 제거한 16자) |
| 본문 | `email.message.EmailMessage`, UTF-8, 인라인 스타일 HTML |
| 타임아웃 | 30초 |
| 재시도 | **없음.** 실패 = Fail Closed |
| 구현 | Python 표준 라이브러리만 (`smtplib`·`ssl`·`email`). **외부 패키지 0개** |

**465를 주 포트로 두는 이유**: 연결 시점부터 암호화되어 **평문 구간이 존재하지 않는다.**
587(STARTTLS)은 평문으로 시작해 승격하므로 이론상 다운그레이드 여지가 있다.

### 금지 사항

| 금지 | 이유 |
|---|---|
| `check_hostname=False` / `verify_mode=CERT_NONE` | 중간자 공격에 노출된다 |
| 25번 포트 / 평문 SMTP | 자격증명이 평문으로 나간다 |
| `smtp.set_debuglevel(1)` | **App Password가 로그에 출력된다** |
| 예외 메시지 원문 출력 | 자격증명이 섞여 나올 수 있다 → **예외 유형만** 기록 (`SMTPAuthenticationError` 등) |

### SMTP 연결성 실측 — GA-2 Probe 결과 (2026-09-30)

`.github/workflows/smtp-probe.yml` 수동 실행 결과.

| Port | Mode | Result | EHLO 250 | AUTH 광고 | TLS 검증 |
|---|---|---|---|---|---|
| 465 | 암시적 TLS | PARTIAL | **yes** | **yes** | UNKNOWN |
| 587 | STARTTLS | PARTIAL | **yes** | **yes** | UNKNOWN |

**판정: SMTP egress는 열려 있다. 차단이 아니다.**
두 포트 모두 TCP 연결·TLS 핸드셰이크·`EHLO` 250 응답·`AUTH` 확장 광고까지 정상 확인되었다.

**`TLS 검증 = UNKNOWN`은 프로브의 결함이지 TLS 실패가 아니다.**
`openssl s_client -quiet` 옵션이 `Verification: OK` 출력까지 억제해 파싱하지 못했다.
TLS 핸드셰이크 자체는 성공했다(성공하지 않았다면 EHLO 응답을 받을 수 없다).

### ⚠ 남은 미검증 — AUTH (GA-2B에서 확인)

**인증까지 가능한지는 아직 확인되지 않았다.** 데이터센터 IP에서의 Gmail 로그인 거부 가능성이 남아 있다.

→ `.github/workflows/smtp-auth-probe.yml` (**GA-2B**)로 확인한다.
   587/STARTTLS + `ssl.create_default_context()` 실검증 + `login()` + `NOOP` + `QUIT`.
   **`sendmail()`·`send_message()`를 호출하지 않으며, 실행 전 정적 검사로 그 부재를 재확인한다.**
   이 프로브가 TLS 검증 UNKNOWN 항목도 함께 해소한다.

## 3-3. Secret 구성

| Secret | 용도 | 상태 |
|---|---|---|
| **`GMAIL_USERNAME`** | 발신 계정 (본인 Gmail 주소) | 등록 대상 |
| **`GMAIL_APP_PASSWORD`** | App Password 16자 (**공백 제거 후 저장**) | 등록 대상 |
| **`WIB_RECIPIENT`** | 수신 주소 — 저장소 기록 금지 (`CLAUDE.md` §10-2) | 등록 대상 |
| ~~`GMAIL_CLIENT_ID`~~ | — | **DEPRECATED — 등록된 적 없음. 등록하지 않는다** |
| ~~`GMAIL_CLIENT_SECRET`~~ | — | **DEPRECATED — 동일** |
| ~~`GMAIL_REFRESH_TOKEN`~~ | — | **DEPRECATED — 동일** |

`GMAIL_USERNAME`은 메일 주소이므로 **Variable이 아니라 Secret으로 둔다** (주소 비기록 원칙).

## 3-4. App Password 무효화·폐기 (G5 FAIL 처리)

| 원인 | 결과 |
|---|---|
| Google 계정 비밀번호 변경 | **모든 App Password가 한꺼번에 무효화된다** → 재발급 필요 |
| 2단계 인증 해제 | App Password 기능 자체가 사라진다 |
| 해당 App Password 삭제 | 그 항목만 즉시 무효 — **비상 발송 차단 수단** |

- 무효화 시 SMTP AUTH가 `SMTPAuthenticationError`로 실패한다 → **G5 FAIL → 발송 중단**
  → `99_RUN_LOG/<YYYY-Www>_FAILED.md` 커밋. **재시도로 뚫지 않는다.**
- App Password 이름을 **`WIB GitHub Actions`** 로 지어, 폐기 시 어느 항목인지 즉시 판별한다.
- 폐기 경로: `https://myaccount.google.com/apppasswords` → 해당 항목 삭제.
  **계정 비밀번호를 바꿀 필요가 없다** — 다른 앱·기기에 영향을 주지 않는다.

---

## 3-D. DEPRECATED — OAuth 설계 원문 (2026-09-30 중단 · 삭제하지 않고 보존)

> **아래 D-1~D-4는 rev.1~rev.3의 OAuth 설계다. 현재 사용하지 않는다.**
> 삭제하지 않는 이유는 ① 판단 이력 보존 ② 향후 OAuth로 되돌릴 경우의 참고다.
> **이 구간의 절차를 실행하지 않는다.** 실행 절차는 §3-1~3-4와 §5를 따른다.

### D-1. 전제 — 기존 커넥터 인증은 재사용하지 않는다 *(DEPRECATED)*

`delivery_setup.md` §5-2에 기록된 대로, claude.ai Gmail 커넥터의 자격증명은 Anthropic 서버 측에 있고
내보낼 수 없다. **GitHub Actions에서는 재사용이 불가능하다.**
따라서 **자체 Gmail API OAuth 구조**를 새로 만든다 (§5-2 표의 방식 ①).

| 방식 | 판정 (당시) |
|---|---|
| **① Gmail API OAuth + refresh token** | 채택 — 권한을 `gmail.send` 하나로 좁힐 수 있다 |
| ② SMTP + 앱 비밀번호 | 기각 — 계정 전체 발송 권한이며 범위를 좁힐 수 없다 |
| ③ 서비스 계정 + 도메인 위임 | **불가** — 개인 Gmail 계정에는 쓸 수 없다 (Workspace 전용) |

### D-2. 구성 요소 *(DEPRECATED)*

| # | 항목 | 값 · 설정 |
|---|---|---|
| 1 | Google Cloud Project | **STEP 2에서 Gemini Key를 발급한 것과 동일한 프로젝트** (§5 프로젝트 구성 결정). **결제 연결하지 않는다** (§2-4 #1) |
| 2 | Gmail API | 해당 프로젝트에서 **활성화** |
| 3 | OAuth Consent Screen | User type **External** / 앱 이름 / 지원 이메일 = 본인 |
| 4 | Scope | **`https://www.googleapis.com/auth/gmail.send` 단 1개** |
| 5 | Publishing status | **Production으로 게시(Publish)** — §3-3 참조 |
| 6 | OAuth Client | Application type **Desktop app** → Client ID + Client Secret |
| 7 | Refresh Token | 로컬에서 **1회만** 동의 흐름 실행 (`access_type=offline`, `prompt=consent`) |
| 8 | Access Token | 실행 시마다 refresh token으로 **자동 발급** (유효 1시간). 저장하지 않는다 |
| 9 | 발송 | `users.messages.send` — base64url MIME (UTF-8, HTML 본문) |

> Gemini API Key와 Gmail OAuth는 **같은 Google Cloud 프로젝트에 둘 수 있다.**
> 단 Gemini Key는 AI Studio에서 발급하며, 어느 쪽도 **결제 연결을 요구하지 않는다.**

### 권한 범위가 실제로 무엇을 뜻하는가

`gmail.send`는 **보내기 전용**이다. 받은메일함 읽기·삭제·라벨 변경·설정 변경이 **불가능**하다.
유출 시 영향은 "내 계정 이름으로 메일이 나갈 수 있다"로 제한된다.

### D-3. Publishing status를 Production으로 올려야 하는 이유 *(DEPRECATED)*

**OAuth 앱이 `Testing` 상태면 refresh token이 약 7일 후 만료된다.**
주 1회 무인 실행에서는 **거의 매번 만료된 토큰으로 실행된다는 뜻**이다.

| 상태 | refresh token 수명 | 주 1회 무인 실행 |
|---|---|---|
| Testing | **약 7일** | **사용 불가** |
| Production (미검증) | 만료되지 않음 (계정 보안 이벤트·scope 변경·비밀번호 변경 시 무효화) | **사용 가능** |

- `gmail.send`는 민감(sensitive) scope이므로, 미검증 앱을 Production으로 게시하면
  동의 화면에 **"확인되지 않은 앱" 경고**가 한 번 표시된다. 본인 계정 1건 사용에는 문제가 없다
  (미검증 앱은 사용자 100명 한도). **Google 검증 심사를 받을 필요는 없다.**
- 게시하지 않고 진행하면 Fail Closed에 걸려 매주 발송이 멈춘다. **게시는 선택이 아니다.**

### D-4. Refresh Token이 무효화되는 경우 *(DEPRECATED)*

| 원인 | 대응 |
|---|---|
| Google 계정 비밀번호 변경 | refresh token 재발급 필요 |
| Scope 변경 · OAuth Client 삭제·재생성 | 재발급 필요 |
| 계정에서 앱 액세스 철회 | 재발급 필요 — **비상 발송 차단 수단으로도 쓸 수 있다** |
| Testing 상태 방치 | 약 7일 만료 (§3-3) |

무효화 시 access token 발급이 `400 invalid_grant`로 실패한다 → **G5 FAIL → 발송 중단**
→ `99_RUN_LOG/<YYYY-Www>_FAILED.md` 커밋. **재시도로 뚫지 않는다.**

— DEPRECATED 구간 끝 —

---

## 3-5. ⚠ 해결이 필요한 규격 충돌 — G6 중복발송 2중 확인 **(SMTP 전환 후에도 유효)**

**`send_gate.md` §4-2는 중복 확인을 ① 발송 원장 ② Gmail 조회 의 2중으로 요구한다.
그런데 `gmail.send` scope로는 Gmail을 조회할 수 없다.**

그대로 두면 G6(확인 자체를 수행했는가)이 **영구 FAIL**이 되어 FAIL CLOSED에 의해 절대 발송되지 않는다.

| 선택지 | 내용 | 판정 |
|---|---|---|
| **가. 2번째 채널을 원격 git tag로 교체** | 발송 직전 `sent/<YYYY-Www>` 태그를 원격에 push. **이미 있으면 push가 실패**하므로 원자적 잠금이 된다. 원장(파일)과 태그(ref)는 서로 다른 경로이며, Gmail 조회보다 오히려 강한 보장 | **권고** |
| 나. 읽기 scope 추가 (`gmail.readonly`) | 받은메일함 전체 읽기 권한 — 최소권한 원칙 위배 | 비권고 |
| 다. `gmail.metadata` 추가 | 제목 검색(`q` 파라미터)이 이 scope에서 지원되지 않아 목적을 달성하지 못함 | 불가 |

→ **이것은 `send_gate.md` §4-2 개정이 필요한 사항이다. GA-2에서 문서를 고치지 않는다.**
   GA-3 착수 시 사용자 승인을 받아 개정한다. 승인 전에는 발송 단계를 구성하지 않는다.

---

# 4. 발송 권한을 AI에게 주지 않는다 (구조적 분리)

PHASE C에서 검증된 방어선을 GitHub Actions에서도 그대로 유지한다.

```
STEP 1  수집 :  collector.py          — AI 없음, 네트워크는 읽기만
STEP 2  판단 :  gemini 호출            — 메일 도구·Secret 접근 없음. WIB_RECIPIENT를 보지 못한다
STEP 3  조립 :  build.py              — Markdown + HTML 생성
STEP 4  게이트:  gate.py              — printenv CLOUD_MODE 직접 조회 + G0~G7 판정
STEP 5  발송 :  gmail_send.py         — STEP 4가 ALL PASS일 때만 if: 조건으로 실행
```

- **AI 계층은 메일을 보낼 수 없다.** 프롬프트에 무엇이 쓰여 있어도 발송 코드·자격증명에 닿지 않는다.
- `WIB_RECIPIENT`는 STEP 5 스텝의 `env:`에만 주입한다. STEP 2에는 전달하지 않는다.
- `CLOUD_MODE`는 **워크플로 YAML에 하드코딩하지 않는다.** `env: CLOUD_MODE: ${{ vars.CLOUD_MODE }}`
  로만 주입한다 — 발송 권한은 저장소 밖에 있어야 한다. GA-4까지 이 Variable을 만들지 않는다.

---

# 5. 사용자가 직접 해야 하는 작업 (한 단계씩)

**각 STEP 완료 보고 후 다음 STEP으로 넘어간다. 한꺼번에 진행하지 않는다.**

| STEP | 내용 | 상태 |
|---|---|---|
| ~~1~~ | ~~AI Studio 실제 한도·사용 가능 모델 확인 (발급 없음)~~ | **완료 2026-09-30** → §2-1에 기록 |
| ~~2~~ | ~~Gemini API Key 발급 + GitHub Secret `GEMINI_API_KEY` 등록~~ | **완료 2026-09-30** — Free Tier 유지, Billing 미연결 확인 |
| ~~3~~ | ~~Gmail API 활성화 (STEP 2와 동일 프로젝트, 결제 미연결)~~ | **완료 2026-09-30** — Status: Enabled |
| ~~4~~ | ~~OAuth Consent Screen → Production Publish~~ | **DEPRECATED** — 동의 화면 생성까지만 완료(2026-09-30). 게시 미완. **더 진행하지 않는다** |
| ~~5~~ | ~~OAuth Client (Desktop app) 생성~~ | **DEPRECATED** — 클라이언트는 생성되었으나 **사용하지 않는다** |
| ~~6~~ | ~~로컬 동의 흐름 → refresh token 확보~~ | **DEPRECATED — 실행되지 않았다. 발급된 토큰 0건** |
| ~~7~~ | ~~GitHub Secrets 3건 (OAuth)~~ | **DEPRECATED — 등록된 적 없음** |
| **8** | **2단계 인증(2SV) 활성 확인** | **완료 2026-09-30 — ON** |
| **9** | **App Password 생성** (`WIB GitHub Actions`) → **즉시** GitHub Secret 3건 등록: `GMAIL_USERNAME` · `GMAIL_APP_PASSWORD` · `WIB_RECIPIENT` | 진행 중 |
| ~~10~~ | ~~SMTP 연결성 프로브 — TCP+EHLO만~~ | **완료 2026-09-30** — 465·587 모두 EHLO 250 + AUTH 광고 확인. **egress 열림** (§3-2) |
| **11** | **GA-2B SMTP AUTH 프로브** — 587/STARTTLS + TLS 실검증 + `login()` + NOOP + QUIT. **발송 없음** | 진행 중 |
| **12** | Gemini 최소 호출 200 확인 (Brief 생성 없이) | 대기 |

STEP 12까지 끝나면 GA-2 완료다. **여기서도 Brief는 생성되지 않고 메일은 나가지 않는다.**

> STEP 9에서 생성과 등록을 **하나의 단계로 묶는 이유**: App Password는 **생성 직후 한 번만 표시**되고
> 이후 다시 볼 수 없다. 중간에 어딘가 적어 두는 상태를 만들지 않기 위해 즉시 Secret에 넣는다.

### OAuth 잔여물 처리 (선택 — 지금 하지 않아도 무방)

| 대상 | 상태 | 권고 |
|---|---|---|
| OAuth Client (Desktop app) | 생성됨, 토큰 0건 | **방치해도 위험 없음.** 정리하려면 Google Auth Platform → 클라이언트에서 삭제 |
| Gmail API 활성화 | 활성 | **그대로 둔다** — SMTP와 무관하며 해가 없다 |
| 동의 화면 (Testing) | 미게시 | 그대로 둔다 |
| `get_refresh_token.ps1` | 저장소 밖 임시 폴더 | **사용하지 않는다.** 삭제 여부는 사용자 지시에 따른다 |

### 프로젝트 구성 결정 (2026-09-30)

Gemini API Key와 Gmail OAuth를 **단일 Google Cloud 프로젝트**에 둔다 (별도 `wib-mailer` 프로젝트를 만들지 않는다).

| 근거 | 내용 |
|---|---|
| 회수 단순화 | 비상 시 프로젝트 하나만 보면 된다 — Key 폐기·OAuth 액세스 철회가 한 곳 |
| 결제 경계 유지 | **이 프로젝트에 결제를 연결하지 않는 한** 두 API 모두 Free 범위를 벗어날 수 없다 |
| 권한 경계 유지 | 프로젝트를 나눠도 권한은 좁아지지 않는다. 실질 경계는 **scope(`gmail.send` 1개)** 와 **결제 미연결**이다 |

**프로젝트 ID·프로젝트명은 저장소에 기록하지 않는다.** 비밀값은 아니나, 수신 주소·커넥터 UUID와
같은 기준(식별자 비기록)을 적용한다. 필요한 값은 실행 환경과 GitHub Secrets에만 둔다.

---

# 6. GA-3 — W38 rev.2 대비 품질 비교 방식

## 6-1. 조건 고정

| 항목 | 값 |
|---|---|
| 커버리지 | **2026-09-14(월) ~ 2026-09-20(일) KST = W38 고정** (직전 주 자동 계산을 쓰지 않는다) |
| 기준선 | `2026-W38_email_brief_final.html` (**rev.2 = 정본**) + `2026-W38_weekly_brief_v2.md` §13 QA |
| 결과 저장 | `03_AUTOMATION_TESTS/github_actions_ga3/2026-W38_gemini.md` / `.html` |
| **기준선 파일** | **수정 금지·덮어쓰기 금지** (`qa_cloud_vs_local.md` §1) |
| 발송 | **하지 않는다.** `CLOUD_MODE` 미설정 상태로 실행 → G0 FAIL → `SKIPPED_LOCAL_MODE` |
| 실행 횟수 | **2회** — 동일 입력에 대한 출력 변동성을 본다. 7 × 2 = **14 호출 ≤ RPD 20** 이므로 같은 날 실행 가능하되, **그날 추가 실행은 금지** (§2-4) |

## 6-2. 정량 비교 — 기존 기준선 표를 그대로 쓴다

`qa_cloud_vs_local.md` §2의 18행 비교표에 **GEMINI 열을 추가**한다. 핵심 대조값:

| 항목 | W38 기준선 | GA-3 합격선 |
|---|---|---|
| 실제 반영 매체 수 | 4 / 5 | **3 이상** (B1) |
| Access Blocked 매체 | 0 | **2곳 이상 증가 금지** (B2) |
| Tier 1 직접 확인 수 | 2 | **2 이상** (B3) |
| Article URL 확보율 | 100% | **80% 이상** (B4) — 구조상 100% 기대 |
| 신제품 KR / US / JP | 5 / 4 / 4 | 각 섹션 존재 + 총 10건 이상 (B5) |
| Critical QA C1~C7 | 전부 PASS | **FAIL 0건** (B7) |
| 최종 사용 Issue 수 | 27 | 20 이상 |
| Trend Signal 채택 | 3건 (조건 충족) | Evidence 조건 충족 Signal 2건 이상 |

## 6-3. 신설 지표 — 이번 엔진 교체에서만 의미 있는 것

| # | 지표 | 합격선 |
|---|---|---|
| N1 | **MUST KNOW 항목 일치율** — 기준선 선정 항목과 겹치는 비율 | **60% 이상** |
| N2 | **숫자 검증 실패 건수** — 출력 숫자가 제공 본문에 없는 경우 | **0건** |
| N3 | **규격 위반 건수** — Price enum 이탈, Observation/Interpretation 혼입, 근거 미달 Signal 생성 | **0건** |
| N4 | **Gemini 호출 수 / 429 발생 수** | **호출 8 이하** / RPD 429 **0건** / `FALLBACK_MODEL_USED` **0건** |
| N5 | 2회 실행 간 MUST KNOW 변동 | **40% 이하** |

## 6-4. 정성 판정 — 사용자가 직접 한다

정량으로 잡히지 않는 것이 이번 교체의 진짜 위험이다(§1-2).

| 항목 | 방법 |
|---|---|
| **Why it matters의 통찰 수준** | 기준선 HTML과 GA-3 HTML을 **나란히 읽고** 사용자가 판정 |
| **선별의 날카로움** | 기준선에 없는데 Gemini가 넣은 항목 / 기준선에 있는데 빠진 항목을 각각 목록화해 사용자 검토 |
| 문체 — 기사 제목 옮기기 금지(§9) 준수 | 육안 확인 |

## 6-5. 최종 판정

**PASS 조건** — 다음을 모두 만족.

1. B1~B7 위반 **0건**
2. N1 ≥ 60%, N2 = 0, N3 = 0, N4 RPD 429 = 0
3. **사용자의 정성 판정이 "기준선 수준"** (이 항목은 자동 판정하지 않는다)

**FAIL 시** → §7의 Fallback 검토. **기준을 낮춰 통과시키지 않는다.**

---

# 7. 품질 미달 시 Anthropic 복귀 Fallback 구조

## 7-1. 엔진 어댑터 — 지금부터 이 형태로 만든다

품질 미달이 확인된 뒤에 구조를 바꾸면 늦다. **처음부터 엔진을 갈아끼울 수 있게 만든다.**

```
pipeline/
  collector.py        # 계층 A — 엔진과 무관
  prompts/*.md        # 작업별 프롬프트 — 엔진과 무관
  schemas/*.json      # 출력 JSON Schema — 엔진과 무관
  engines/
    base.py           # judge(task, payload, schema) -> dict
    gemini.py         # GEMINI_API_KEY 사용
    anthropic.py      # ANTHROPIC_API_KEY 사용 (구현만 두고 비활성)
  build.py            # 계층 C — 엔진과 무관
```

**프롬프트·Schema·수집기·조립기는 엔진에 의존하지 않는다.** 교체 대상은 `engines/` 한 폴더뿐이다.

## 7-2. 전환 절차 (코드 수정 0)

| # | 조치 |
|---|---|
| 1 | Anthropic Console에서 Key 발급 + 전용 Workspace + spend limit 설정 |
| 2 | GitHub Secret `ANTHROPIC_API_KEY` 등록 |
| 3 | Repository Variable `AI_ENGINE` 을 `gemini` → **`anthropic`** 으로 변경 |
| 4 | 같은 W38 조건으로 GA-3 재실행 → §6 비교 |

되돌리기는 3번을 `gemini`로 바꾸는 것뿐이다.

## 7-3. 전환을 검토하는 조건 (자동 전환 아님)

| 조건 | 판단 |
|---|---|
| GA-3 최종 판정 FAIL | 전환 검토 |
| 운영 중 Critical QA FAIL이 2주 연속 | 전환 검토 |
| RPD 429로 발송 실패가 2주 연속 | 전환 검토 |
| 무료 티어 데이터 사용 정책(§2-6)이 수용 불가로 바뀜 | 전환 또는 유료 티어 |

**어떤 경우에도 자동 전환하지 않는다.** 사용자 승인 후 수동 전환한다(§2-5 공통 처리 2).

## 7-4. Anthropic 경로의 비용 — rev.1보다 훨씬 낮다 **[추정]**

2계층 구조에서는 에이전트 루프(80~120턴)가 사라지고 **호출 22~26건**만 남는다.

| | rev.1 (에이전트) | rev.2 구조에서 Anthropic 사용 시 |
|---|---|---|
| 1회 | $9 ~ $19 | **약 $2 ~ $6** |
| 월 4~5회 | $36 ~ $95 | **약 $8 ~ $30** |

→ **Fallback이 현실적인 선택지가 된다.** 품질 미달 시 "0원이냐 포기냐"가 아니라
   "0원이냐 월 1~4만원이냐"의 선택이 된다. 실측은 전환 시 첫 실행에서 측정한다.

## 7-5. 항상 유지되는 최후 경로

**로컬 `/weekly-brief` 수동 실행.** `cloud_runbook.md` §6에 따라 자동화가 2회 이상 정상 실행 +
QA 통과하기 전까지 삭제·비활성화하지 않는다. 엔진 논쟁과 무관하게 이 경로는 살아 있다.

---

# 8. SECURITY

| 원칙 | 이 설계에서의 이행 |
|---|---|
| Secret 저장소 저장 금지 | 값은 GitHub Secrets · 실행 환경에만. 이 문서에도 이름만 있다 |
| Markdown에 Secret 기록 금지 | 본 문서 · GA-1 기록 · 커밋 메시지 전부 값 0건 |
| 로그에 Token·Key 출력 금지 | access token·API Key를 `echo` 하지 않는다. `set -x` 금지. Actions 자동 마스킹에 **의존하지 않는다** |
| 최소권한 | **App Password 1건**(발송 전용 용도로 생성·개별 폐기 가능) · Gemini Key는 전용 프로젝트 · `permissions:`는 최소값. **계정 비밀번호는 사용하지 않는다** |
| TLS 강제 | SMTP 465 암시적 TLS + 인증서·호스트명 검증 유지. **검증 비활성화 금지** (§3-2) |
| **AI 프롬프트 최소노출** | 수신 주소·Secret·로컬 경로·발송 이력을 **프롬프트에 넣지 않는다** (§2-6). 무료 티어는 데이터가 제품 개선에 쓰이므로 이 제약이 특히 중요하다 |
| `.gitignore` 확인 | `client_secret*` · `credentials*.json` · `token*.json` · `refresh_token*` · `.env*` 차단 규칙 **이미 존재**(확인 완료). `_work/` 중간 산출물 차단 규칙은 **GA-3에서 추가**한다 |
| GitHub Secrets 사용 | Secret **4건**(`GEMINI_API_KEY`·`GMAIL_USERNAME`·`GMAIL_APP_PASSWORD`·`WIB_RECIPIENT`) + Variable 4건. 그 외 경로 없음 |
| `CLOUD_MODE`는 마지막에만 | Repository Variable을 **GA-4에서 처음 생성**한다. 그전까지 존재하지 않으므로 G0가 구조적으로 FAIL이며 발송이 불가능하다 |
| 수신 주소 | `WIB_RECIPIENT` Secret만. 발송 스텝에만 주입. 로그·보고에서 마스킹 (`s***@gmail.com`) |
| 결제 미연결 | Google Cloud 프로젝트에 결제를 연결하지 않는다 — **과금 경로 자체를 없앤다** |
| App Password 로컬 잔존 방지 | 생성 직후 **바로 GitHub Secret에 입력**한다. 메모장·문서·스크린샷·셸 히스토리에 남기지 않는다 |
| 유출 시 대응 | `https://myaccount.google.com/apppasswords` 에서 **`WIB GitHub Actions` 항목만 삭제** → 즉시 무효. 계정 비밀번호 변경 불필요 |

---

# 9. 변경 이력

| 날짜 | 변경 |
|---|---|
| 2026-09-30 | **rev.1** — GA-2 최초 작성. AI는 Claude Code 헤드리스 + `claude-opus-5`, Gmail은 자체 OAuth `gmail.send`. Secret 5건, 비용 [추정] 및 4중 상한, Fail Closed, G6 규격 충돌 발견 |
| 2026-09-30 | **rev.4** — **Gmail 발송을 OAuth `gmail.send` → App Password + SMTP로 전환** (사용자 결정: 개인 계정 주 1회 발송에 OAuth Production 심사 절차가 과도). §3을 SMTP 규격(465 암시적 TLS, 인증서 검증 유지, 표준 `smtplib`, 재시도 없음)으로 교체하고 **OAuth 설계는 §3-D에 DEPRECATED로 보존(삭제하지 않음)**. Secret을 `GMAIL_USERNAME`·`GMAIL_APP_PASSWORD`·`WIB_RECIPIENT` 3건으로 교체(OAuth 3건은 **등록된 적 없음**, refresh token **발급 0건**). 권한 범위 확대 트레이드오프와 개별 폐기 경로를 명시. **⚠ 러너의 SMTP 아웃바운드(465/587) 미검증 — GA-3에서 파이프라인 구현보다 먼저 프로브**. G5 정의가 "SMTP AUTH 성공"으로 바뀌므로 `send_gate.md` 개정 필요(승인 후 GA-3). **Gemini 설계(§1·§2)·GA-1·QA Gate·중복발송 방지·Fail Closed는 무변경** |
| 2026-09-30 | **rev.3** — **AI Studio 실측 한도 반영 (STEP 1 완료).** 이 계정의 Free Tier는 `gemini-2.5-flash` / `gemini-2.5-flash-lite` **RPM 5·10 / TPM 250K / RPD 20**이며 Gemini 3.x·2.0은 사용 불가. rev.2의 22~26 호출 설계가 **RPD 20을 초과**하므로 **7 호출 설계**로 전면 재편(선별+병합 통합, 요약+Why it matters 동일 호출, 신제품+Signal 국가별 통합). `AI_CALL_BUDGET` 30→**10**(RPD 50%), 재시도 단계당 1회·실행당 3회, **RPM/TPM 페이싱**(30초 간격·호출당 100K 상한) 신설. Primary=`gemini-2.5-flash`, Fallback=`gemini-2.5-flash-lite`이며 **Fallback은 선별·병합 단계에만 허용**하고 작성·Signal 단계는 Fail Closed(품질 유지). RPD 소진 시나리오·같은 날 2회 제한 명문화. 무료 티어 데이터 사용 사실을 **CLAUDE.md §10-2에도 명시** |
| 2026-09-30 | **rev.2** — **월 운영비 0원 목표로 AI 엔진 재설계.** Anthropic 종량 과금 폐기, **Gemini Free Tier + `gemini-3.8-flash`** 채택(공식 문서 무료 확인). 에이전트 루프 → **2계층 구조**(결정론적 수집 + Gemini 판단 배치 호출)로 전환, Critical QA C1·C4·C5·C6을 코드 강제로 이동. `GEMINI_API_KEY` 신설, 호출 예산·결제 미연결 등 **6중 초과 방지**, RPD Fail Closed, **무료 티어 데이터 사용 사실 기록(§2-6)**, GA-3 품질 비교 방식(§6) 및 **엔진 어댑터 Fallback 구조(§7)** 신설. **Gmail 설계(§3)는 rev.1 유지.** Key 발급·등록·생성·발송은 하지 않음 |
