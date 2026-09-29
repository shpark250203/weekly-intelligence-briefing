# QA 비교 — LOCAL 기준선 vs CLOUD 첫 실행

> PHASE D에서 작성한다. **PHASE A 시점에는 기준선 열만 확정되어 있다.**

---

## 1. 기준선 파일 확정

| 항목 | 값 |
|---|---|
| **기준선 (발송본 정본)** | `01_WEEKLY_BRIEFS/2026/2026-W38_email_brief_final.html` — **rev.2** |
| **기준선 (QA 수치 출처)** | `01_WEEKLY_BRIEFS/2026/2026-W38_weekly_brief_v2.md` §13 QA METRICS |
| 커버리지 | 2026-09-14(월) ~ 2026-09-20(일) KST |
| 실행 방식 | LOCAL, 수동 |

### ⚠️ rev 상태 주의

| 파일 | rev | 비고 |
|---|---|---|
| `2026-W38_email_brief_final.html` | **rev.2** | **실제 발송본 = 정본.** 범례 4분류(FACT/CLAIM/MEDIA/ANALYSIS) |
| `2026-W38_email_brief_final.md` | rev.1 | rev.2 수정 4건 미반영. 범례 3분류. **기준선이 아니다** |

- rev.2 수정 4건: ANALYSIS 태그 분리 / EARLY BEAUTY WATCHLIST 개명 / Launch Type 컬럼 추가 / 원본 기사 URL 확인
- **위 두 파일은 수정하지 않는다.** 기준선은 동결 상태로 보존한다.
- Cloud 결과는 **별도 파일**로 생성해 비교한다. 기준선 파일에 덮어쓰지 않는다.

---

## 2. 비교표 (PHASE D에서 CLOUD 열을 채운다)

| # | 항목 | LOCAL 기준선 (W38) | CLOUD 첫 실행 | 판정 |
|---|---|---|---|---|
| 1 | 전체 수집 기사 수 | 약 158건 | — | — |
| 2 | 중복 제거 후 Issue 수 | 41 | — | — |
| 3 | 최종 사용 Issue 수 | 27 | — | — |
| 4 | Noise 제외 수 | 14 (+ 카테고리 제외 12) | — | — |
| 5 | **Tier 1 verification rate** | **2/12 = 16.7%** | — | **핵심 판정 항목** |
| 6 | Tier 1 직접 확인 수 | 2 | — | — |
| 7 | Tier 2 / Tier 3 사용 수 | 5 / 14 | — | — |
| 8 | **장업신문** | `Checked — usable` (4건) | — | **핵심 판정 항목** |
| 9 | **CMN** | `Partial Access` (0건) | — | **핵심 판정 항목** |
| 10 | **뷰티누리** | `Checked — usable` (4건, Fallback ③) | — | **핵심 판정 항목** |
| 11 | **코스모닝** | `Checked — usable` (3건, Fallback ①②) | — | **핵심 판정 항목** |
| 12 | **코스인코리아** | `Checked — usable` (5건) | — | **핵심 판정 항목** |
| 13 | Beauty Source concentration | 1위 31.3% / 상위2 56.3% — 경고 없음 | — | — |
| 14 | Article URL 확보율 | 27/27 = **100%** | — | — |
| 15 | 신제품 수 KR / US / JP | 5 / 4 / 4 | — | — |
| 16 | Trend Signal Evidence 조건 | 채택 3건 (KR 4 / US 2+T1 / JP 4), 미달 5건 Watch | — | — |
| 17 | Gmail HTML 렌더링 | 정상 (2026-09-23 수신 확인) | — | — |
| 18 | 실행 소요시간 | 미측정 (수동 다회차) | — | 참고용 |

**실제 반영 매체 수**: 기준선 **4개** (목표 3개 이상 충족)

---

## 3. 스케줄 활성화 차단 기준

아래 중 하나라도 해당하면 **PHASE E(자동 실행 활성화)를 진행하지 않는다.**

| # | 차단 조건 |
|---|---|
| B1 | 5개 매체 중 **실제 반영 매체가 3개 미만** |
| B2 | `Not Checked` 또는 `Access Blocked` 매체가 **기준선(0건) 대비 2곳 이상 증가** |
| B3 | **Tier 1 verification rate가 기준선(16.7%) 대비 의미 있게 악화** — 직접 확인 수가 2건 미만이면 악화로 본다 |
| B4 | Article URL 확보율 **80% 미만** |
| B5 | 신제품 국가 분리 실패, 또는 특정 국가 섹션 누락 |
| B6 | Gmail HTML 렌더링 깨짐 |
| B7 | Critical QA(C1~C7) 중 FAIL 발생 |

차단 시 조치: 원인 분석 → **Cloud 환경의 Source 수집 방법 보완**(Fallback 경로 강화 등) → 재실행 → 재비교.

---

## 4. 판정 기록

| 항목 | 값 |
|---|---|
| CLOUD 첫 실행 일시 | — |
| CLOUD 결과 파일 | — |
| 최종 판정 | **미실시** |
| 판정자 | — |

---

# [PHASE C 회수분] CLOUD 실측 결과 — 2026-09-29

> **이 절은 아카이브 사본에만 추가되었다.** 원본 `00_SYSTEM/qa_cloud_vs_local.md`는 무변경이다.
> 위 §2 표의 CLOUD 열을 비워 둔 채, 실측값을 아래에 별도로 기록한다.
> 상세는 같은 폴더의 `cloud_qa_result.md` 참조.

| # | 항목 | LOCAL 기준선 | **CLOUD 실측** | 판정 |
|---|---|---|---|---|
| 1 | 전체 수집 기사 수 | 약 158 | **26** | ▼ |
| 2 | 중복 제거 후 Issue 수 | 41 | **12** | ▼ |
| 3 | 최종 사용 Issue 수 | 27 | **4** | ▼ |
| 4 | Noise 제외 수 | 14 (+12) | **9** | — |
| 5 | Tier 1 verification rate | 2/12 = 16.7% | **0/8 = 0.0%** | **B3 위반** |
| 6 | Tier 1 직접 확인 수 | 2 | **0** | ▼ |
| 7 | Tier 2 / Tier 3 사용 수 | 5 / 14 | 로그 미확보 | — |
| 8 | 장업신문 | Checked — usable (4) | **Access Blocked (0)** | ▼ |
| 9 | CMN | Partial Access (0) | **Access Blocked (0)** | ▼ |
| 10 | 뷰티누리 | Checked — usable (4) | **Access Blocked (0)** | ▼ |
| 11 | 코스모닝 | Checked — usable (3) | **Access Blocked (0)** | ▼ |
| 12 | 코스인코리아 | Checked — usable (5) | **Access Blocked (1, 제목 수준)** | ▼ |
| 13 | Beauty Source concentration | 31.3% / 56.3%, 경고 없음 | **100% / 100%, WARNING** | **B1 위반** |
| 14 | Article URL 확보율 | 27/27 = 100% | **4/4 = 100%** (표본 4건) | 형식상 동일 |
| 15 | 신제품 KR / US / JP | 5 / 4 / 4 | **0 / 0 / 0** | **B5 위반** |
| 16 | Trend Signal Evidence 조건 | 채택 3건, 미달 5건 Watch | **채택 0건** (산정 불가) | ▼ |
| 17 | Gmail HTML 렌더링 | 정상 (2026-09-23 수신) | **미검증** (발송 안 함) | B6 미판정 |
| 18 | 실행 소요시간 | 미측정 | **12.4분** | 참고 |

**실제 반영 매체 수**: 기준선 4곳 → CLOUD **1곳** (목표 3곳 미달)

## 차단 기준 판정 (§3)

| 기준 | 결과 |
|---|---|
| B1 반영 매체 3개 미만 | **위반** |
| B2 Blocked 2곳 이상 증가 | **위반** (0 → 5) |
| B3 Tier 1 직접 확인 2건 미만 | **위반** (2 → 0) |
| B4 URL 확보율 80% 미만 | 통과 |
| B5 신제품 국가 분리 실패 | **위반** |
| B6 Gmail 렌더링 깨짐 | 미검증 |
| B7 Critical QA FAIL | **위반** (C1·C3) |

## 판정 기록 (§4)

| 항목 | 값 |
|---|---|
| CLOUD 첫 실행 일시 | 2026-09-29 05:47:08Z ~ 05:59:29Z |
| CLOUD 결과 파일 | **MISSING** (push 403 — `MISSING_ARTIFACTS.md` 참조) |
| 최종 판정 | **PHASE E 진행 불가 (NO)** — 차단 기준 7개 중 5개 위반 |
| 원인 | 실행 환경의 network egress 전면 차단. 브리프 생성 로직 문제 아님 |
| 후속 | Claude Cloud Routine 중단(enabled:false 보존), GitHub Actions로 전환 |
