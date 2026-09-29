# WEEKLY INTELLIGENCE BRIEFING

매주 월요일 오전 9시(KST) 이전, 지난 한 주의 핵심 변화를 **Weekly Brief 1통**으로 받아보기 위한 저장소.

- **AXIS 1** — 한국·글로벌 경제·사회·산업·유통·금융·정책
- **AXIS 2** — 화장품·뷰티 산업 심층 모니터링 (전문매체 5곳 독립 확인)
- **New Product Watch** — 한국 / 미국 / 일본 **국가별 분리** 추적

---

## 구조

```
CLAUDE.md                        프로젝트 운영 원칙
.claude/skills/weekly-brief/     Brief 생성 Skill (LOCAL / CLOUD 모드 분기)
00_SYSTEM/
  source_policy.md               Source Tier·기록 규칙
  briefing_template.md           출력 양식
  media_watchlist.md             확인 대상 매체·기관
  delivery_setup.md              발송·스케줄 구성 상태
  send_gate.md                   발송 모드 분기 및 자동발송 차단 규격
  cloud_runbook.md               클라우드 실행 운영 절차
  qa_cloud_vs_local.md           QA 기준선 비교표
  source_ledger.csv              핵심 정량 데이터 누적
  send_ledger.csv                발송 기록 (중복발송 방지용)
01_WEEKLY_BRIEFS/<YYYY>/         주차별 Brief 아카이브
02_TREND_TRACKER/                국가별 Trend Signal 누적
99_RUN_LOG/                      실행·실패 로그 (Gmail 장애 시 대체 알림 채널)
```

---

## 실행

| 모드 | 방법 | 자동 발송 |
|---|---|---|
| **LOCAL** | `/weekly-brief` | **금지** — 파일 생성 후 보고만. 발송은 사용자 승인 후 |
| **CLOUD** | 스케줄 Routine | **실행 환경의** `CLOUD_MODE` 조회값이 `true`(G0) **이고** Gate G0~G7 전부 통과 시에만 |

발송 판단 규격은 `00_SYSTEM/send_gate.md`를 따른다. **FAIL CLOSED** — 판단이 서지 않으면 보내지 않는다.

---

## 보안

- **이 저장소에는 어떤 인증정보도 없다.** API 키·OAuth 토큰·앱 비밀번호를 두지 않는다.
- **수신 메일 주소를 저장소에 하드코딩하지 않는다.** 환경변수 `WIB_RECIPIENT`로만 주입한다.
- Gmail 인증은 claude.ai 커넥터가 관리하며 이 저장소에 저장되지 않는다.
- Secret 값을 로그·보고·커밋 메시지에 출력하지 않는다.

---

## 상태

| 항목 | 상태 |
|---|---|
| Brief 생성 | 수동 실행 가능 |
| Gmail 발송 | 수동 검증 완료 (2026-09-23, TEST 1회) |
| 클라우드 자동 실행 | **미설정** — PHASE A(로컬 구조 준비)까지만 완료 |
