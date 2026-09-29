# PHASE C — Claude Cloud Routine Dry Test 요약

> Claude Cloud Routine 방식의 **최종 평가 기록**이다.
> 향후 GitHub Actions 방식의 품질을 비교할 때 이 문서를 대조군으로 쓴다.
> **이 폴더의 모든 수치는 실행 로그에서 직접 확인한 값이다. 추정치를 넣지 않았다.**

---

## 1. 테스트 날짜

| 항목 | 값 |
|---|---|
| 실행일 | **2026-09-29 (KST)** |
| Routine 세션 시작 | `2026-09-29T05:46:54Z` |
| Brief 생성 구간 | `2026-09-29T05:47:08Z` ~ `05:59:29Z` |
| 세션 종료 | `2026-09-29T06:01:47Z` |
| 커버리지 (고정) | **2026-09-14(월) ~ 2026-09-20(일) KST = 2026-W38** |

커버리지를 W38로 **고정**한 것은 로컬 기준선과 같은 기간을 재현해 품질을 비교하기 위함이다.
직전 주 자동 계산을 쓰지 않았다.

## 2. 실행 환경

| 항목 | 값 |
|---|---|
| 실행 방식 | Claude Cloud Routine (Anthropic 클라우드 격리 세션) |
| Routine ID | `trig_01EesXpJxwYJpf15p8pYHbJE` |
| 세션 ID | `cse_011h11d3zvR5TTkaBokfZtLJ` |
| Environment | `env_01USMbVyQWX2Hr558eDVvwg6` (anthropic_cloud) |
| 모델 | `claude-opus-5` |
| 작업 디렉터리 | `/home/user/weekly-intelligence-briefing` |
| Source | GitHub private repo, clone 성공 |
| Repo HEAD | `04517a8` (G0 신설 커밋 반영 확인) |
| 트리거 | 수동 `run` (스케줄 아님) |
| Routine enabled | **false** (테스트 전·후 모두 유지) |

## 3. 실행 성공 / 실패

**실행 자체는 성공. 품질 측정 목적은 실패.**

| 지표 | 값 |
|---|---|
| 결과 | `is_error=false` |
| turns | 59 |
| 세션 소요 | 887초 |
| Brief 생성 소요 | **12.4분 (741초)** |
| permission_denials | 1건 |

- 산출물 2개는 **컨테이너 내부에서 생성 완료**되었고 커밋(`4f1ac8e`)까지 되었다.
- 그러나 **push가 403으로 거부**되어 저장소로 나오지 못했다 (§9 참조).
- permission_denials 1건은 프록시 상태 조회(`curl "$HTTPS_PROXY/__agentproxy/status"`)가
  분류기에 의해 `[Exfil Scouting]`으로 차단된 것이다. 실행은 우회하지 않고 다른 경로로 진행했다.

## 4. Gmail 인증 상태

**VALID — 이번 PHASE에서 처음 실증되었다.**

별도 진단 세션(`cse_01LU1TYvHHPv2CyCCVMH4W3j`, 2026-09-29 05:44~05:45Z) 결과:

```
Gmail Connector = CONNECTED
Gmail Auth      = VALID
Send Capability = AVAILABLE   (호출하지 않음)
WIB_RECIPIENT   = NOT SET
CLOUD_MODE      = NOT SET
Repo HEAD       = 04517a8
Web Access      = OK
```

- `list_labels` 1회 호출이 인증 오류 없이 응답 → 토큰 유효 확인.
- **claude.ai Gmail 커넥터가 클라우드 Routine 세션에서 실제로 재사용된다는 사실이 확인되었다.**
  PHASE B에서 "설정 수준 준비 완료 / 런타임 미검증"으로 남겨둔 항목이 해소되었다.
- PHASE C 본 실행에서도 `search_threads` 조회가 정상 동작했다 (G6 통과).

> **결론: Gmail 인증은 Cloud Routine 중단 사유가 아니다.** 인증은 문제없이 동작했다.

## 5. 실제 Gmail 발송 여부

**발송 0건. 본 메일·실패 메일 모두 보내지 않았다.**

| 방어선 | 상태 |
|---|---|
| Routine `enabled` | false |
| `send_message` / `create_draft` 도구 | **allowed_tools에서 제거 — 세션에 아예 없음** |
| G0 (runtime `CLOUD_MODE`) | FAIL → `SKIPPED_LOCAL_MODE` |
| `send_gate.md` §5-0 | G0 FAIL은 실패가 아니므로 실패 메일도 미발송 |

실행 로그 전수 확인 결과 `send_message`·`create_draft` 호출 **0건**.
Gmail 호출은 진단 세션의 `list_labels` 1회, 본 실행의 `search_threads` 1회뿐이다.

> **G0 보완이 실전에서 검증되었다.** 프롬프트에 어떤 문장이 있어도 runtime 환경변수가 없으면
> 발송이 차단된다는 설계가 실제 무인 실행에서 의도대로 동작했다.

## 6. Network Egress 문제 — 중단의 결정적 사유

**이 클라우드 환경은 외부 웹 접근이 전면 차단되어 있다.**

- WebFetch 시도가 **전부 실패**했다 (실행 보고 기준 14건, 로그에서 도메인 확인된 것 13건).
- 오류 유형: `EGRESS_BLOCKED — Access to <domain> is blocked by the network egress proxy`
- 차단 대상에 **대조군으로 넣은 `example.com`까지 포함**되었다.
  → 특정 매체 차단이 아니라 **환경 전체 차단**이다.
- 유일하게 동작한 경로는 **WebSearch(서버 측 실행)** 이며,
  기사 제목·URL은 주지만 **본문을 주지 않는다.**
  그 결과 보도일·수치·신제품 정보를 **하나도 검증하지 못했다.**
- `/root/.ccr/README.md`가 이 응답을 조직 정책 거부로 규정하므로 **우회를 시도하지 않았다.**

도메인별 상세는 `source_access_report.md` 참조.

## 7. PHASE E 판정

# **NO — 자동 실행 활성화 불가**

`qa_cloud_vs_local.md` §3 차단 기준 **7개 중 5개 위반**:

| 기준 | 내용 | 결과 |
|---|---|---|
| B1 | 실제 반영 매체 3개 미만 | **위반** — 1곳 |
| B2 | Access Blocked 기준선 대비 2곳 이상 증가 | **위반** — 0곳 → 5곳 |
| B3 | Tier 1 직접 확인 2건 미만 | **위반** — 2건 → 0건 |
| B4 | Article URL 확보율 80% 미만 | 통과 (100%, 단 표본 4건) |
| B5 | 신제품 국가 분리 실패·섹션 누락 | **위반** — KR/US/JP 전부 0건 |
| B6 | Gmail HTML 렌더링 깨짐 | 미검증 (발송하지 않음) |
| B7 | Critical QA FAIL 발생 | **위반** — C1·C3 FAIL |

**단, 이것은 브리프 생성 로직의 품질 저하가 아니다.**
동일한 Skill·규격으로 로컬에서는 158건을 수집했다. 차이는 전적으로 실행 환경의 네트워크 정책이다.
입력이 차단된 상태에서 산출물이 빈 것은 오히려 정직한 결과이며,
실행 세션이 없는 내용을 지어내지 않고 `Access Blocked`로 확정한 것은 규격 준수다.

## 8. GitHub Actions 전환 사유

| # | 사유 | 근거 |
|---|---|---|
| 1 | **네트워크 egress 전면 차단** (결정적) | WebFetch 14건 전부 실패. `example.com`까지 차단 |
| 2 | Tier 1 원문 접근 불가 | 연준·한국은행·통계청 전부 차단 → `Tier 1 First` 규칙 집행 불가 |
| 3 | 뷰티 전문매체 5곳 전부 접근 불가 | AXIS 2 심층 처리가 성립하지 않음 |
| 4 | 저장소 쓰기 권한 없음 | git push 403, MCP push_files 403 → 아카이브 커밋 불가 |
| 5 | 환경변수 주입 경로 부재 | Routine API가 `environment_variables`를 폐기 (`send_gate.md` §2-1) |

→ GitHub Actions는 **공개 인터넷 접근**, `GITHUB_TOKEN` 기반 **저장소 쓰기**,
**Secrets 기반 환경변수 주입**을 모두 제공하므로 1·4·5를 동시에 해소한다.

> ⚠️ **다만 1번이 GitHub Actions에서 해결된다는 보장은 아직 없다.**
> GitHub 호스팅 러너는 Azure IP 대역이며, 한국 언론사가 해외·데이터센터 IP를 차단할 가능성이 있다.
> **PHASE GA-1(연결성 실측)에서 반드시 먼저 확인해야 한다.**

## 9. 산출물 회수 실패 기록

| 경로 | 결과 |
|---|---|
| `git push -u origin main` | **403** — `Claude doesn't have GitHub access to this repository for your organization` |
| GitHub MCP 읽기 (`get_file_contents`) | 동작 |
| GitHub MCP 쓰기 (`push_files`) | **403** — `Resource not accessible by integration` |

클라우드 세션의 GitHub 연동은 **읽기 전용**이었다. 쓰기 경로가 존재하지 않았다.
쓰기 가능성 확인 시 `_PROBE.html`이라는 별도 파일명을 사용해 실제 산출물 파일명을 덮어쓸 위험을 차단했고,
tree 생성 단계에서 실패해 **원격에는 아무것도 생성되지 않았다** (원격 디렉터리 목록으로 확인).

→ 커밋 `4f1ac8e`는 컨테이너에만 존재했고 **회수되지 않았다.**
   본문 파일 2개의 상태는 `MISSING_ARTIFACTS.md` 참조.

## 10. 보존 원칙

- 로컬 W38 기준선 파일 8개 — **무변경**
- `00_SYSTEM/qa_cloud_vs_local.md` 원본 — **무변경** (이 폴더에는 사본을 두고 CLOUD 실측을 덧붙였다)
- Cloud Routine — `enabled: false` 유지, 삭제하지 않음
- 이 폴더의 모든 수치는 실행 로그 직접 확인값. **확인되지 않은 항목은 `로그 미확보`로 표기했다.**
