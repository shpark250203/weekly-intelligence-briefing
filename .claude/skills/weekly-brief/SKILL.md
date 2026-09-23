---
name: weekly-brief
description: 지난 한 주의 국내외 주요 이슈(AXIS 1 — 경제·사회·산업·유통·금융·기업·정책·해외)와 화장품/뷰티 산업 동향(AXIS 2 — 장업신문·CMN·뷰티누리·코스모닝·코스인코리아 필수 모니터링), 그리고 한국·미국·일본 신제품을 국가별로 분리 조사해 Weekly Intelligence Brief 1건을 작성하는 Skill. "/weekly-brief"로 실행하며, 인자로 주차나 기간을 줄 수 있다(예 "/weekly-brief 2026-W39"). 인자가 없으면 직전 월~일을 커버리지로 잡는다.
---

# WEEKLY INTELLIGENCE BRIEF SKILL

**Version**: 1.1

매주 월요일 오전 9시 이전에 받아볼 **Weekly Brief 1건**을 작성한다.
`$ARGUMENTS`가 있으면 커버리지 주차로 해석한다(`2026-W39`, `9/14~9/20` 등). 없으면 **직전 월~일**.

---

## 실행 모드 — 시작 시 가장 먼저 판정한다

발송 관련 규격은 `00_SYSTEM/send_gate.md`를 따른다. **이 Skill은 그 규격을 넘어설 수 없다.**

### 모드 판정 (FAIL CLOSED)

환경변수 `CLOUD_MODE`가 **정확히 소문자 `true`** 일 때만 CLOUD MODE다.

| `CLOUD_MODE` | 모드 |
|---|---|
| `true` | **CLOUD MODE** |
| 없음 / 빈값 / `false` / `TRUE` / `1` / `yes` / 그 외 전부 | **LOCAL MODE** |

대소문자 변환·숫자 해석·부분 일치를 하지 않는다. **값이 모호하면 LOCAL MODE로 떨어진다.**
LOCAL MODE에서는 **어떤 경우에도 자동 발송하지 않는다.**

### LOCAL MODE (기본값 · 기존 동작 유지)

- **자동 이메일 발송 금지**
- Brief 생성 후 **파일 경로와 요약만 보고**
- 발송은 **Draft 생성 또는 사용자의 명시적 승인** 후에만
- 스케줄 자동 등록 금지
- 기존 수동 테스트 방식(`[TEST]` 제목 접두 + 본인 수신) 유지

### CLOUD MODE (사전 승인된 스케줄 실행 전용)

- 무인 실행이므로 **사용자에게 되묻지 않는다.**
- 되물어야 할 상황(판단 불가·충돌·조건 미확인)은 **전부 중단 처리**한다.
- 자동 발송은 `send_gate.md` §3의 **Gate G1~G7을 전부 통과한 경우에만** 한다.
- **수신 주소는 환경변수 `WIB_RECIPIENT`로만 받는다.** 어떤 파일에도 기록하지 않고, 출력 시 마스킹한다.

---

## CORE PRINCIPLE

이 Skill의 목적은 뉴스 수집이 아니라 **"이번 주 반드시 알아야 할 변화"의 선별**이다.

- 기사 제목을 옮기지 않는다. **무엇이 달라졌는지**를 쓴다.
- 분량을 채우기 위해 항목을 늘리지 않는다. 변화가 없으면 없다고 쓴다.
- **이번 주 사실은 이번 주에 직접 수집한 Source로 쓴다.** 기억이나 과거 결론으로 채우지 않는다.
- `BEAUTY_MARKET_INTELLIGENCE` 프로젝트는 **자동으로 참조하지 않는다.** 필요할 때만, 참조 사실을 밝히고 쓴다.

---

## 시작 시 반드시 읽는 파일

1. `CLAUDE.md`
2. `00_SYSTEM/source_policy.md`
3. `00_SYSTEM/briefing_template.md`
4. `00_SYSTEM/media_watchlist.md`
5. `02_TREND_TRACKER/new_product_signals.csv` — **직전 주 Signal 대조용(필수)**
6. `01_WEEKLY_BRIEFS/<YYYY>/` 의 **직전 주 Brief** — 중복 제거 및 `[후속]` 판단용

---

## PHASE 0 — 커버리지 확정

1. 오늘 날짜로 커버리지 기간을 계산한다. 기본은 **직전 월요일 00:00 ~ 일요일 23:59 KST**.
2. ISO 주차를 구한다. 파일명: `01_WEEKLY_BRIEFS/<YYYY>/<YYYY>-W<주차>_weekly_brief.md`
3. 같은 주차 파일이 이미 있으면 **덮어쓰지 않는다.**
   - **LOCAL MODE** — 사용자에게 갱신 여부를 확인한다.
   - **CLOUD MODE** — 되물을 수 없으므로 확인하지 않는다. `_cloud` 접미사를 붙여
     `<YYYY>-W<주차>_weekly_brief_cloud.md` 로 **새 파일을 만든다.** 기존 파일은 손대지 않는다.
     (PHASE D 비교용 파일도 이 규칙을 따른다 — 기준선 파일을 절대 덮어쓰지 않는다)

---

## PHASE 1 — AXIS 1 수집 (일반 인텔리전스)

CLAUDE.md §4 포함 범위 8개 영역을 훑는다.

**국내**: 경제 / 사회 / 산업 / 유통·이커머스 / 증권·금융 / 주요 기업 / 정책·규제
**해외**: 미국 / 중국 / 일본 / 유럽

### 1-1. NOISE FILTER 적용 (먼저 버린다)

다음은 **원칙적으로 제외**한다 — 단순 MOU·업무협약 / 홍보성 보도자료 / 단순 채용 /
ESG 캠페인 / 사회공헌 / 행사 개최 / 수상 / 단순 신제품 홍보 / 의미 없는 인사 /
단발성 사건사고 / 추측성 전망.

**예외** — 시장 구조를 바꿀 규모의 투자 / 대규모 M&A / 실제 매출·실적 영향 /
정책·규제 변화 / 산업 구조 변화 / 대규모 고용·구조조정 / 주요 유통채널 변화 /
소비자 행동 변화 / 시장점유율 변화 중 하나에 해당하면 포함 가능.

### 1-2. 2-of-5 RULE 적용

남은 후보에 대해 아래 5개 중 **최소 2개 이상** 충족을 확인한다.

1. 경제적 영향 2. 산업적 영향 3. 소비자 영향 4. 정책·규제 영향 5. 지속 가능성

**1개 이하면 제외하고, 제외 건수를 센다**(QA `제외된 Noise 기사 수`).
단순 화제성만으로 포함하지 않는다.

> 영역당 1~3건이면 충분하다. **전부 채우려 하지 않는다.**

### 1-3. TIER 1 FIRST

금리·환율·지수·수출입·물가·실적 수치는 **한국은행·통계청·관세청·KRX·DART 원문을 먼저 찾는다.**
찾으면 `Tier 1 verified`, 매체 경유만이면 `Tier 1 via Tier 2`,
못 찾으면 `Tier 1 original source not verified`를 수치 옆에 표기한다.

---

## PHASE 2 — AXIS 2 수집 (뷰티 산업)

### 2-1. 필수 매체 5곳을 각각 **독립적으로** 확인한다

**장업신문 / CMN / 뷰티누리 / 코스모닝 / 코스인코리아**

- **한 매체에서 많이 확보했다고 다른 매체를 생략하지 않는다.**
- 각 매체 상태를 5단계로 기록: `Checked — usable articles found` /
  `Checked — no significant news` / `Partial Access`(범위 명시) / `Access Blocked` / `Not Checked`
- **Access Blocked면 Fallback 1~5를 순서대로 시도한 뒤에만 확정한다.**
  ① 도메인 한정 검색 ② 카테고리·목록 페이지(페이지네이션) ③ 기사 제목 검색
  ④ 동일 이슈의 공식 Source ⑤ 다른 전문매체 Cross-check
- 차단을 우회하지 않고, 접근 못 한 내용을 추정하지 않는다.
- 5개 매체의 **중복 보도는 하나로 병합**하고, 가장 원 출처에 가까운 것을 Source로 삼는다.
- AXIS 2 후보에도 **§1-1 Noise Filter와 §1-2 2-of-5 Rule을 동일하게 적용한다.**
  전문매체에 실렸다는 사실 자체는 포함 근거가 아니다.

### 2-1b. SOURCE CONCENTRATION 점검

실제 사용한 기사 수를 매체별로 세고 비중을 계산한다.

- 1개 매체 **50% 초과** → `SOURCE CONCENTRATION WARNING` 기록
- 2개 매체 합계 **80% 초과** → `SOURCE CONCENTRATION WARNING` 기록
- 목표: 5개 중 **최소 3개 매체가 실제 반영**
- 단, 그 주에 중요한 기사가 없는 매체를 억지로 넣지 않는다
  → `Checked — no significant news`가 올바른 처리

### 2-2. 11개 범위로 분류한다

화장품 시장 / 브랜드·기업 / ODM·OEM / 유통 / 수출·글로벌 / 원료·기술 / 규제 / 투자·M&A /
뷰티 디바이스 / 신규 브랜드 / 주요 신제품

### 2-3. 심층 처리

AXIS 2는 "무슨 일이 있었다"에서 멈추지 않는다. 각 항목에 가능한 범위에서 덧붙인다.

- **숫자** (기준연도·통화 표기)
- **맥락** (직전 흐름 대비 무엇이 달라졌는가)
- **시사점** — `[판단]`으로 표시

수출·규제·투자 금액 등 정량 수치는 **Tier 1~2로 Cross-check**를 시도하고,
못 하면 `Cross-check 미실시`로 적는다.

---

## PHASE 3 — NEW PRODUCT WATCH (국가별 분리)

**KOREA / USA / JAPAN을 절대 섞지 않는다.** 각각 별도 섹션·별도 표.

국가별 소스는 `00_SYSTEM/media_watchlist.md` §5를 따른다.

### 선정 기준

실제 출시 / 공식 출시 발표 / 주요 Retailer 신규 등록 / 신뢰할 수 있는 전문매체 기사 중 하나.
**단순 리뉴얼·한정 패키지·색상 변경은 중요도가 낮으면 제외**(성분·기술·가격대·채널 중 유의미한 변화가 있으면 포함).

### 제품당 기록 항목

Brand / Product / Category / 성분 / 기술 / 효능(Claim) / 제형 / **Price** / 채널 / 출시일 / Source / **Article URL**

- **확인되지 않은 항목은 `—`로 비운다.** `미확인`을 반복 표기하지 않는다. 추정하지 않는다.
- **Price는 필수 필드가 아니다.** `Verified` / `Not disclosed` / `Not verified` 3단계로 구분하고,
  **가격을 못 찾았다고 제품을 제외하지 않는다.**
- `Not disclosed`가 다수인 것은 **Trend Signal이 아니라 Coverage Log에 기록**한다.
- 효능(Claim)은 **브랜드가 실제 사용한 표현 그대로** 적는다. 의역하지 않는다.
- **Article URL을 기록한다.** 확보 실패 시 `Not verified`.
- 국가별 3~8건이 적정하다. 중요도 순으로 자른다.

### Trend Signal (국가마다 필수)

**생성 조건 — 둘 중 하나를 충족해야 Signal로 인정한다.**

| 조건 | 내용 |
|---|---|
| **A** | 독립된 브랜드/제품 **3건 이상**에서 동일 신호 |
| **B** | 제품 **2건 이상 + Tier 1/2 시장·산업 근거** |

**단일 제품·단일 기사로는 Signal을 만들지 않는다.** 조건 미달 관찰은 §12 `Watch Item`으로 보낸다.

**Signal마다 아래 4개를 반드시 분리 기록한다.**

- **Observation** — 관찰된 사실만. 해석 금지
- **Evidence Count** — 브랜드 수 / 제품 수 / 근거 출처
- **Interpretation** — 해석
- **Confidence** — High / Medium / Low
  - `High` — 조건 A 충족 **이고** 근거에 Tier 1/2 포함
  - `Medium` — 조건 A 또는 B 충족, 근거가 Tier 3 중심
  - `Low` — 조건은 충족하나 비교 시점 데이터 없음 또는 계절성과 미분리

**계절성 주의** — 매년 반복되는 패턴(가을 신상 일괄 출시 등)은 전년 동기 비교 없이 High를 주지 않는다.
**URL 없는 기사를 근거로 High를 주지 않는다.**

**직전 주 대비**: `02_TREND_TRACKER/new_product_signals.csv`와 대조해 `New / Continued / Faded` 판정.

> 신호가 없으면 **"이번 주 유의미한 Signal 없음"**. 억지로 만들지 않는다.

---

## PHASE 4 — CROSS-COUNTRY READ

3개국을 나란히 놓고 본다. 공통 / 한국만 / 미국만 / 일본만 / 시차 관찰.
공통점이 없으면 "이번 주 국가 간 공통 신호 없음"이라고 쓴다.

---

## PHASE 5 — 작성

`00_SYSTEM/briefing_template.md` 양식을 그대로 따른다.

### WEEKLY MUST KNOW

**가장 마지막에 쓴다.** 전체를 다 모은 뒤 중요도 순으로 고른다.

- **7~10개를 억지로 채우지 않는다.** 정말 중요한 게 6개면 6개만.
- 각 후보 필수 조건: ① 커버리지 기간 내 실제 발생 ② Source 확인(개별 기사 URL)
  ③ §1-2 2-of-5 Rule 충족 ④ **다른 선정 뉴스와 중복 아님**
- **인과관계로 묶인 항목은 1건으로 병합한다** (예: 금리 인상 ↔ 그로 인한 환율 급등).
- **기사량이 많다고 중요 뉴스로 선정하지 않는다.**
- 국내 실물·사회 축에 충족 항목이 있으면 **최소 1건은 반영한다.**

### 표기 규칙 (source_policy §2)

`(사실)` / `(회사 발표)` / `(언론 해석)` / `[판단]` 을 구분한다. 추정은 `[추정]`.

### 분량

이메일 한 통으로 읽히는 수준. 길이보다 **선별**이 중요하다.

---

## PHASE 6 — 기록

1. **Brief 저장**: `01_WEEKLY_BRIEFS/<YYYY>/<YYYY>-W<주차>_weekly_brief.md`
2. **핵심 수치 기록**: `00_SYSTEM/source_ledger.csv`에 한 행씩 추가
   (시장 규모·수출입·실적·점유율·투자금액·가격·조사 비율)
3. **Trend Signal 기록**: `02_TREND_TRACKER/new_product_signals.csv`에 국가별로 추가

   | 컬럼 | 값 |
   |---|---|
   | `Week` | `2026-W39` |
   | `Country` | `KR` / `US` / `JP` |
   | `SignalType` | `Ingredient` / `Technology` / `Claim` / `Format` / `Price` / `Channel` |
   | `Signal` | 신호 내용 (예: `PDRN 고함량`) |
   | `BrandCount` | 확인된 브랜드 수 |
   | `Brands` | 브랜드명 (세미콜론 구분) |
   | `SignalStrength` | `Strong` / `Moderate` / `Weak` |
   | `VsPrevWeek` | `New` / `Continued` / `Faded` |
   | `Note` | 비고 |

4. **Coverage Log 작성**: 확인 / Not Checked / Access Blocked를 구분해 남긴다.
5. 접근 차단이 있었으면 `00_SYSTEM/media_watchlist.md` §6에 추가한다.

---

## PHASE 6b — QA METRICS 보고 (필수)

브리프 저장 후 아래 14개를 본문과 **별도로** 보고한다.

1. 전체 수집 기사 수
2. 중복 제거 후 Issue 수
3. 최종 사용 Issue 수
4. **제외된 Noise 기사 수** (§1-1·§1-2로 걸러낸 수)
5. **Tier 1 직접 확인 수**
6. **Tier 1 verification rate** = Tier 1 verified ÷ 핵심 정량 주장 수
7. Tier 2 사용 수
8. Tier 3 사용 수
9. Beauty 전문매체 5개 각각의 상태 (5단계)
10. **Beauty Source concentration** + 경고 여부
11. **개별 Article URL 확보율**
12. Korea / USA / Japan 신제품 수
13. **Trend Signal별 Evidence Count**
14. Access Blocked Source (Fallback 시도 결과 포함)

---

## PHASE 7-L — 발송 (LOCAL MODE)

**메일 발송은 자동으로 하지 않는다.**

1. 작성 완료 후 사용자에게 **파일 경로와 THIS WEEK IN 5 LINES를 보고**한다.
2. 발송 여부는 사용자가 결정한다.
3. 발송 설정 상태는 `00_SYSTEM/delivery_setup.md`를 따른다.

---

## PHASE 7-C — 발송 (CLOUD MODE 전용)

**`CLOUD_MODE=true`가 아니면 이 PHASE를 실행하지 않는다.** 판정이 애매하면 PHASE 7-L로 간다.

### 7-C-1. Compact Email 생성

`_email_brief.html` 을 만든다. 인라인 스타일만 사용하고 외부 CSS·스크립트를 넣지 않는다.
**로컬 파일 경로·인증정보·수신주소 평문을 본문에 넣지 않는다.**

### 7-C-2. GATE 검사 — `send_gate.md` §3

발송 직전 G1~G7을 순서대로 검사하고 **결과를 전부 기록**한다.

| ID | 조건 |
|---|---|
| G1 | Weekly Brief 생성 성공 (필수 섹션 전부 존재) |
| G2 | Compact Email 생성 성공 |
| G3 | **Critical QA FAIL = 0** (C1~C7, `send_gate.md` §3-1) |
| G4 | `WIB_RECIPIENT` 존재 및 형식 유효 |
| G5 | Gmail 인증 성공 |
| G6 | 중복 발송 확인을 **실제로 수행**함 (원장 + Gmail 2중) |
| G7 | 해당 `YYYY-Www` 정상 발송 기록 **없음** |

- **하나라도 실패하면 본 메일을 발송하지 않는다.**
- G7만 실패하면 `SKIPPED_DUPLICATE`로 기록한다 (실패 아님, 실패 메일도 보내지 않는다).
- G1~G6 실패는 `[FAILED] WEEKLY INTELLIGENCE | YYYY-Www` 알림 대상이다.

### 7-C-3. 중복 발송 확인 (2중)

1. `00_SYSTEM/send_ledger.csv` 에서 같은 `WeeklyID` + `Status=SENT` 조회
2. Gmail에서 제목에 해당 `YYYY-Www`를 포함한 정식 발송 메일 조회

- 둘 중 하나라도 기록이 있으면 **발송하지 않는다.**
- 두 결과가 **불일치하면 발송하지 않고** `[FAILED]`로 보고한다.
- `Status=TEST`는 중복 판정 대상이 아니다.
- `FORCE_RESEND=<YYYY-Www>`가 현재 주차와 정확히 일치할 때만 **G7만 면제**한다.
  `FORCE_RESEND=true` 같은 포괄 값은 인정하지 않는다.

### 7-C-4. 발송 및 기록

1. 제목: `[WEEKLY INTELLIGENCE] <YYYY>-W<주차> 경제 · 산업 · 유통 · Beauty Weekly Brief`
2. 수신: `WIB_RECIPIENT`
3. 발송 후 `00_SYSTEM/send_ledger.csv` 에 한 행 추가
   (`Recipient` 컬럼은 두지 않는다 — 수신 주소를 저장소에 남기지 않는다)
4. 아카이브 커밋

### 7-C-5. 실패 처리

- `[FAILED] WEEKLY INTELLIGENCE | YYYY-Www` — 실패 단계 / 오류 요약 / 실행 시각 / 재실행 필요 여부 **4줄만**
- 메일 발송 경로 자체가 죽은 경우 → `99_RUN_LOG/<YYYY-Www>_FAILED.md` 를 저장소에 커밋한다
- 실패 메일에도 인증정보·수신주소 평문·로컬 경로를 넣지 않는다

---

## 하지 않는 것

- 기사 제목 나열
- 보도자료 복사
- 확인되지 않은 수치 인용
- 국가별 신제품 섞기
- Trend Signal 생략
- 지난 주 내용 반복 (후속 진전이 있으면 `[후속]`으로 표시)
- 분량을 위한 항목 늘리기
- 사용자 승인 없는 메일 발송·스케줄 등록
- **LOCAL MODE에서의 자동 발송** (예외 없음)
- `CLOUD_MODE` 값이 정확한 `true`가 아닌데 자동 발송
- Gate G1~G7 중 하나라도 실패했는데 발송
- 수신 주소를 파일·커밋·로그에 평문으로 남기기
- 기준선 파일(`2026-W38_email_brief_final.*`) 수정·덮어쓰기

---

## 완료 체크리스트

- [ ] 커버리지 기간이 명시되었는가
- [ ] 필수 매체 5곳의 확인 여부가 Coverage Log에 기록되었는가
- [ ] 모든 숫자에 Source와 보도일이 붙었는가
- [ ] 보도일과 데이터 기준연도를 구분했는가
- [ ] 신제품이 KR/US/JP로 분리되었는가
- [ ] 각 국가에 Trend Signal이 작성되었는가
- [ ] 직전 주 Signal과 대조했는가
- [ ] source_ledger.csv / new_product_signals.csv에 기록했는가
- [ ] THIS WEEK IN 5 LINES가 변화 서술인가
- [ ] 실행 모드를 판정했는가 (기본값 = LOCAL)
- [ ] CLOUD MODE인 경우 Gate G1~G7 결과를 전부 기록했는가
- [ ] CLOUD MODE인 경우 send_ledger.csv에 발송 결과를 기록했는가
