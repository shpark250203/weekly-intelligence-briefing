# CLOUD RUNBOOK — 클라우드 자동 실행 운영 문서

> `delivery_setup.md`(설정 상태)와 `send_gate.md`(발송 차단 규격)의 실행 절차판이다.
> **PHASE A 시점: 어떤 클라우드 리소스도 생성되지 않았다.**

---

## 1. 현재 진행 상태

| PHASE | 내용 | 상태 |
|---|---|---|
| **A** | Git 저장소 구조 + 클라우드 실행용 파일 구성 | **완료 (로컬 전용)** |
| **B** | Cloud Workflow 생성 — `enabled: false` | **미착수** |
| **C** | 수동 Cloud 실행 1회 | 미착수 |
| **D** | 로컬 파일럿 vs Cloud 결과 QA 비교 | 미착수 |
| **E** | 월 08:00 KST 자동 실행 활성화 | 미착수 |

**아직 자동 발송되는 것은 없다.** GitHub 원격 저장소도 생성되지 않았다.

---

## 2. 실행 아키텍처

```
[본 Routine]  cron 0 23 * * 0 (UTC)  ==  매주 월요일 08:00 KST
  ├ environment : anthropic_cloud
  ├ model       : (PHASE B에서 확정 — 품질 우선, 임의 하향 금지)
  ├ sources     : git clone <private> weekly-intelligence-briefing
  │                 └ CLAUDE.md / .claude/skills/weekly-brief / 00_SYSTEM / 01_WEEKLY_BRIEFS
  ├ mcp         : Gmail 커넥터
  ├ env         : CLOUD_MODE=true, WIB_RECIPIENT=<주입>
  └ 실행
      PHASE 0~6   Brief 생성 + QA 14지표
      PHASE 6c    Compact Email(HTML) 생성
      GATE G1~G7  send_gate.md §3 — 하나라도 실패 시 발송 중단
      PHASE 7-C   Gmail 발송
      PHASE 8     아카이브 커밋 + send_ledger.csv 기록

[검증 Routine]  cron 30 0 * * 1 (UTC)  ==  매주 월요일 09:30 KST
  └ Gmail 조회 → 해당 주차 메일 부재 시 재실행 1회 → 그래도 부재 시 [FAILED]

[로컬 PC]  git pull 로 아카이브 동기화 / /weekly-brief 수동 백업 유지
```

### 2-1. 스케줄 UTC 검증

| 기준 | 값 |
|---|---|
| 목표 | 월요일 08:00 KST 시작, 09:00 이전 발송 완료 |
| 변환 | KST = UTC+9 → 월 08:00 KST − 9h = **일요일 23:00 UTC** |
| 본 Routine cron | `0 23 * * 0` (일=0) |
| 검증 Routine cron | `30 0 * * 1` (월 00:30 UTC = 월 09:30 KST) |
| 서머타임 | 한국 없음 / UTC 없음 → **연중 고정** |
| 사후 검증 | Routine 조회 결과의 next run이 **일 23:00 UTC**인지 대조 후 보고 (PHASE B) |

---

## 3. 환경변수 계약

| 변수 | 값 | 주입 위치 | 저장소 기록 |
|---|---|---|---|
| `CLOUD_MODE` | `true` (소문자 정확히) | Routine 설정 | ✕ |
| `WIB_RECIPIENT` | 수신 메일 주소 | Routine 설정 | **✕ 절대 금지** |
| `FORCE_RESEND` | `<YYYY-Www>` (선택) | 수동 실행 시에만 | ✕ |

- **수신 주소는 저장소 어디에도 두지 않는다.** 이 문서에도 실제 값을 적지 않는다.
- 로그·보고·실패 메일에서는 마스킹한다 (`s***@gmail.com`).
- Routine 설정에 주입하는 실제 값은 **PHASE B에서 사용자 확인 후** 입력한다.

### 3-1. 미검증 사항 (PHASE B에서 확인)

- [ ] Routine 설정이 **환경변수 주입을 지원**하는지. 미지원이면 대안: 수신자·모드를 **Routine 프롬프트에 기재**한다 (프롬프트는 저장소가 아닌 Routine 설정에 저장되므로 §3 원칙에 위배되지 않는다)
- [ ] 품질 기준 모델의 Routine 지정 가능 여부. **불가 시 임의 하향하지 않고 중단·보고**
- [ ] 클라우드 환경의 저장소 **쓰기(푸시) 권한**

---

## 4. Secret 취급

**이 저장소에 보관하는 Secret — 0건.**

| 필요 인증 | 조달 | 저장소 기록 |
|---|---|---|
| AI 모델 실행 | Claude Code 구독 세션 (API 키 불필요) | ✕ |
| Gmail 발송 | claude.ai Gmail 커넥터 연결 | ✕ |
| 저장소 접근·푸시 | 클라우드 환경의 GitHub 연결 권한 | ✕ |

- GitHub Secrets / Secret Manager에 **등록할 항목 없음** (GitHub Actions를 쓰지 않음).
- 커넥터 식별자(UUID)도 이 저장소에 기록하지 않는다. Routine 설정에만 존재한다.
- Secret 값을 생성·출력·커밋하지 않는다.

---

## 5. 클라우드 환경 제약

| 제약 | 영향 |
|---|---|
| **로컬 폴더 접근 불가** | 모든 입력이 저장소에 있어야 한다 |
| **Linux 환경** | Windows 전용 스크립트(`.ps1`)를 실행 경로에 두지 않는다 |
| **컨텍스트 0에서 시작** | 프롬프트가 자기완결적이어야 한다 |
| **무인 실행** | 되물을 수 없다 → 판단 불가 시 중단 (FAIL CLOSED) |
| **웹 접근 환경 상이** | 매체 접근 결과가 로컬과 다를 수 있다 → PHASE D에서 반드시 비교 |
| Routine 삭제 | CLI 불가, 웹 UI에서만 |
| 최소 실행 간격 | 1시간 (주 1회는 무관) |

---

## 6. Rollback

| 상황 | 조치 | 소요 |
|---|---|---|
| PHASE B/C 중단 | `enabled:false` 상태이므로 조치 불요 — 자동 발송 위험 0 | — |
| 활성화 후 문제 | Routine을 `enabled:false`로 업데이트 | 즉시 |
| **비상 발송 차단** | claude.ai에서 **Gmail 커넥터 연결 해제** → 발송 경로 즉시 차단 | 즉시 |
| Routine 완전 삭제 | 웹 UI `https://claude.ai/code/routines` (사용자 직접) | 수동 |
| 저장소 되돌리기 | `git revert` — 로컬 원본은 현 위치에 그대로 유지 | 즉시 |
| **PHASE A 자체 취소** | `.git` 폴더 삭제 + 이번에 추가한 파일 삭제. 기존 파일은 W38 포함 무변경 | 즉시 |
| 운영 복귀 | 로컬 `/weekly-brief` 수동 실행 (계속 유지 중) | 즉시 |

**로컬 백업 유지 원칙**: Cloud 자동화가 **최소 2회 이상 정상 실행 + QA 통과**하기 전까지
로컬 실행 방식을 삭제하거나 비활성화하지 않는다.

---

## 7. 변경 이력

| 날짜 | 변경 |
|---|---|
| 2026-09-23 | PHASE A — 최초 작성. 아키텍처·환경변수 계약·Secret 취급·Rollback 확정. 리소스 미생성 |
