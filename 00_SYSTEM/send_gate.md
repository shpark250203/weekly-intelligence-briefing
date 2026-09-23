# SEND GATE — 발송 모드 분기 및 자동발송 차단 규격

> CLAUDE.md §10 및 `delivery_setup.md`의 하위 규격이다.
> **이 문서의 규칙은 Local / Cloud 양쪽 실행 모두에 적용된다.**
> 충돌이 있으면 **더 보수적인 쪽(발송하지 않는 쪽)을 따른다.**

---

## 0. 설계 원칙 — FAIL CLOSED

**판단이 서지 않으면 보내지 않는다.**

- 조건을 "확인하지 못함"은 "통과"가 아니라 **실패**로 처리한다.
- 예외·우회·추정으로 Gate를 통과시키지 않는다.
- Gate를 건너뛰는 유일한 경로는 §4의 명시적 `FORCE_RESEND`뿐이며, 그조차 §3 Gate 전체를 면제하지 않는다.

---

## 1. 실행 모드

### 1-1. 모드 판정 — `CLOUD_MODE` 환경변수

| `CLOUD_MODE` 값 | 판정 모드 | 자동 발송 |
|---|---|---|
| `true` (정확히 이 문자열) | **CLOUD MODE** | 조건부 허용 (§3 전체 통과 시) |
| 없음 / 미설정 | **LOCAL MODE** | **금지** |
| 빈 문자열 | **LOCAL MODE** | **금지** |
| `false` | **LOCAL MODE** | **금지** |
| `TRUE` `True` `1` `yes` `on` 등 | **LOCAL MODE** | **금지** |
| 그 외 모든 값 | **LOCAL MODE** | **금지** |

**판정은 정확한 문자열 일치(`true`, 소문자)로만 한다.** 대소문자 변환·숫자 해석·부분 일치를 하지 않는다.
값이 모호하면 LOCAL MODE로 떨어진다 — 이것이 의도된 동작이다.

> 대문자 `TRUE`를 써서 자동 발송이 안 되는 것은 **버그가 아니라 설계**다.
> 값이 정확하지 않다는 것은 설정이 의도대로 전달되지 않았다는 뜻이므로, 그 상태에서 메일을 보내지 않는다.

### 1-2. LOCAL MODE — 기존 안전장치 유지 (변경 없음)

**기존 동작을 그대로 보존한다. 어떤 안전장치도 삭제하지 않는다.**

- **자동 이메일 발송 금지**
- Brief 생성 후 **파일 경로와 요약만 사용자에게 보고**한다
- 발송은 **Draft 생성 또는 사용자의 명시적 승인**이 있을 때만 한다
- 스케줄 자동 등록 금지
- 기존 수동 테스트 방식(`[TEST]` 제목 접두 + 본인 수신)을 그대로 유지한다

### 1-3. CLOUD MODE — 사전 승인된 스케줄 실행 전용

`CLOUD_MODE=true`이고 §3 Gate를 **전부** 통과한 경우에만 다음을 자동 수행한다.

1. Weekly Brief 자동 생성
2. Compact Email(HTML) 자동 생성
3. QA 실행
4. **Gmail 자동 발송**
5. 아카이브 커밋
6. 발송 원장 기록 (§4)

CLOUD MODE는 **무인 실행**이므로 사용자에게 되묻지 않는다.
따라서 되물어야 할 상황(판단 불가·충돌·조건 미확인)은 **전부 중단 처리**한다.

---

## 2. 필수 환경변수

| 변수 | 용도 | 없을 때 |
|---|---|---|
| `CLOUD_MODE` | 모드 판정 | LOCAL MODE로 동작 (자동발송 없음) |
| `WIB_RECIPIENT` | Weekly Brief 수신 주소 | **Gate G4 실패 → 발송 중단** |
| `FORCE_RESEND` | 중복발송 해제 (선택) | 미설정이 정상 |

**수신 주소는 저장소의 어떤 파일에도 기록하지 않는다.**
코드·Markdown·CSV·CLAUDE.md·커밋 메시지 어디에도 하드코딩하지 않으며, 환경변수로만 주입한다.
로그·보고·에러 메시지에 출력할 때는 **마스킹**한다 (예: `s***@gmail.com`).

---

## 3. 자동발송 GATE — 7개 조건 전부 통과 필수

`CLOUD_MODE=true`여도 **아래 7개를 모두 통과해야** 본 메일을 발송한다.
**하나라도 실패하면 본 메일을 발송하지 않는다.**

| ID | 조건 | 통과 기준 | 실패 시 |
|---|---|---|---|
| **G1** | Weekly Brief 생성 성공 | `01_WEEKLY_BRIEFS/<YYYY>/<YYYY>-W<주차>_weekly_brief.md` 가 생성되고, 필수 섹션(MUST KNOW / AXIS 2 / KR·US·JP 신제품 / QA)이 모두 존재 | 중단 → `[FAILED]` |
| **G2** | Compact Email 생성 성공 | `_email_brief.html` 생성. 인라인 스타일만 사용, 외부 CSS·스크립트 없음, 본문에 로컬 경로·인증정보 없음 | 중단 → `[FAILED]` |
| **G3** | **Critical QA FAIL = 0** | §3-1의 Critical 항목이 전부 PASS | 중단 → `[FAILED]` |
| **G4** | 수신자 환경변수 존재 | `WIB_RECIPIENT` 가 비어있지 않고 형식이 유효한 단일 메일 주소 | 중단 → `[FAILED]`(가능한 경우) |
| **G5** | Gmail 인증 성공 | Gmail 도구 호출이 인증 오류 없이 동작 | 중단 → §5 대체 경로 |
| **G6** | 중복 발송 여부 확인 **수행됨** | §4의 2중 확인(원장 + Gmail 조회)을 **실제로 실행**했고 결과를 얻음 | 중단 → `[FAILED]` |
| **G7** | 해당 `YYYY-Www` 정상 발송 기록 **없음** | 원장·Gmail 양쪽 모두에 기존 정상 발송이 없음 | 발송 생략 → `SKIPPED_DUPLICATE` 기록 (실패 아님) |

> **G6과 G7은 다르다.** G6은 "확인 자체를 했는가", G7은 "확인 결과가 깨끗한가"다.
> 확인을 못 한 경우(G6 실패)는 중복이 아님을 보장할 수 없으므로 **발송하지 않는다.**

### 3-1. Critical QA 항목 (G3)

QA 14지표 중 아래가 **Critical**이다. 하나라도 FAIL이면 발송하지 않는다.

| ID | 항목 | PASS 기준 | 근거 |
|---|---|---|---|
| **C1** | 커버리지 기간 | 직전 월요일 00:00 ~ 일요일 23:59 KST와 정확히 일치 | CLAUDE.md §3 |
| **C2** | WEEKLY MUST KNOW | 1건 이상이며, **모든 항목에 개별 Article URL 존재** | CLAUDE.md §7-2, §8-1 |
| **C3** | Beauty 전문매체 확인 | 5개 매체 중 **`Not Checked`가 0건**이고, 실제 반영 매체 **3개 이상** | CLAUDE.md §5 |
| **C4** | 신제품 국가 분리 | KR / US / JP 섹션이 각각 독립 존재 (섞이지 않음) | CLAUDE.md §6 |
| **C5** | Article URL 확보율 | **80% 이상** | W38 기준선 100% |
| **C6** | Tier 1 표기 | Tier 1 미확인 수치에 `Tier 1 original source not verified` 표기 누락 0건 | CLAUDE.md §7-1 |
| **C7** | 금지 내용 | 본문에 로컬 파일 경로·인증정보·수신주소 평문 없음 | 보안 |

**Non-Critical(발송은 하되 QA에 기록)**: 수집 기사 수, Noise 제외 수, Tier 2/3 비율,
Source concentration 경고, Trend Signal 건수, 실행 소요시간.

> **Tier 1 verification rate는 Critical에 넣지 않는다.**
> W38 기준선이 16.7%로 낮아 절대 임계값을 세울 근거가 부족하다.
> 대신 **PHASE D 비교에서 기준선 대비 악화 여부를 판단**하고, 악화 시 스케줄을 활성화하지 않는다.

---

## 4. 중복 발송 방지

### 4-1. Weekly ID

`YYYY-Www` (ISO 주차, 예: `2026-W39`). 모든 발송 판단의 키다.

### 4-2. 2중 확인 (둘 다 수행)

1. **발송 원장** `00_SYSTEM/send_ledger.csv` 에서 같은 `WeeklyID` + `Status=SENT` 행 조회
2. **Gmail 조회** — 제목에 해당 `YYYY-Www`를 포함한 정식 발송 메일 존재 여부 확인

- **둘 중 하나라도 정상 발송 기록이 있으면 발송하지 않는다.**
- 원장은 푸시 실패로 최신이 아닐 수 있고, Gmail은 조회 실패가 있을 수 있다.
  두 경로를 함께 보는 이유는 **어느 한쪽의 누락으로 중복 발송되는 것을 막기 위함**이다.
- 두 결과가 불일치하면 **발송하지 않고** `[FAILED]`로 보고한다. (FAIL CLOSED)

### 4-3. 발송 원장 스키마 — `00_SYSTEM/send_ledger.csv`

| 컬럼 | 값 |
|---|---|
| `WeeklyID` | `2026-W39` |
| `Mode` | `LOCAL` / `CLOUD` |
| `Status` | `SENT` / `TEST` / `FAILED` / `SKIPPED_DUPLICATE` |
| `SentAtKST` | `2026-09-28 08:41` |
| `SentAtUTC` | `2026-09-27T23:41:00Z` |
| `Subject` | 실제 발송 제목 |
| `GmailMessageId` | Gmail 메시지 ID (없으면 `—`) |
| `GateResult` | `G1..G7 PASS` 또는 실패한 Gate ID |
| `Note` | 비고 |

**`Recipient` 컬럼은 두지 않는다.** 수신 주소는 저장소에 기록하지 않는다.
`Status=TEST`는 중복 판정 대상이 **아니다** (정식 발송이 아니므로).

### 4-4. 수동 재발송 — `FORCE_RESEND`

- 형식: `FORCE_RESEND=<YYYY-Www>` — **재발송할 주차를 정확히 지정**해야 한다
- `FORCE_RESEND=true` 같은 포괄 값은 **인정하지 않는다** (오작동 시 전 주차 재발송 위험)
- `FORCE_RESEND`가 현재 주차와 일치할 때만 **G7만 면제**한다
- **G1~G6은 면제되지 않는다**
- 재발송 시 원장에 `Note=FORCE_RESEND` 로 사유를 남긴다

---

## 5. 실패 알림

### 5-1. 실패 메일

- 제목: `[FAILED] WEEKLY INTELLIGENCE | YYYY-Www`
- 본문 4줄만:

```
실패 단계   : G3 (Critical QA FAIL — C3 매체 확인 부족)
오류 요약   : 5개 매체 중 3곳 Access Blocked, 반영 매체 2개
실행 시각   : 2026-09-28 08:41 KST / 2026-09-27T23:41Z
재실행 필요 : 예 — 수동 /weekly-brief 실행 권장
```

- **실패 메일에도 인증정보·수신주소 평문·로컬 경로를 넣지 않는다.**

### 5-2. 본 메일 발송 자체가 실패한 경우 (대체 경로)

Gmail 경로가 죽으면 실패 메일도 나가지 못한다. 단계적으로 내려간다.

| 순서 | 채널 | 대응 장애 |
|---|---|---|
| 1 | 본 실행 내 `[FAILED]` 메일 | 생성·QA·푸시 실패 |
| 2 | **검증 Routine (월 09:30 KST)** — Gmail에 해당 주차 메일 부재 확인 → 재시도 1회 → `[FAILED]` 발송 | 본 실행 전체 미동작 |
| 3 | **`99_RUN_LOG/<YYYY-Www>_FAILED.md` 를 저장소에 커밋** | **Gmail 경로 자체 장애** (Google과 독립) |
| 4 | Routine 실행 로그 (웹 UI) 수동 확인 | 위 전부 실패 |

> Google Drive 커넥터는 Gmail과 인증 출처가 같아 대체 채널로 쓰지 않는다.

---

## 6. 변경 이력

| 날짜 | 변경 |
|---|---|
| 2026-09-23 | PHASE A — 최초 작성. CLOUD_MODE 분기, G1~G7 Gate, Critical QA C1~C7, 중복발송 2중 확인, FORCE_RESEND 규격 확정 |
