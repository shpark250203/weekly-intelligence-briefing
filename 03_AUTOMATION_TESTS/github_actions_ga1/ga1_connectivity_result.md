# GA-1 — GitHub Actions Connectivity Probe 결과

> PHASE C(Claude Cloud Routine)에서 **network egress 전면 차단**으로 중단된 뒤,
> GitHub Actions 실행 환경이 Weekly Brief의 Source에 실제로 접근 가능한지 확인한 실측 기록이다.
> 대조군은 `03_AUTOMATION_TESTS/claude_cloud_phase_c/`다.

---

## 1. 실행 정보

| 항목 | 값 |
|---|---|
| 실행일 | **2026-09-29 (KST)** |
| Workflow | `.github/workflows/connectivity-probe.yml` |
| 트리거 | `workflow_dispatch` (수동 전용 — schedule 없음) |
| Repo HEAD | `ee14dbe` |
| Runner | GitHub-hosted Ubuntu |
| 프로브 대상 | 21건 (Tier 1 10 / Beauty 5 / 신제품 5 / 대조군 1) |
| API 호출 | **0건** (AI API·Gmail 모두 사용하지 않음) |
| Secret 사용 | **0건** (`secrets` 컨텍스트 미참조) |
| 비용 | **0원** (Actions 무료 한도 내, 외부 유료 API 0건) |

---

## 2. 판정 — **PASS**

| 판정 | 건수 |
|---|---|
| PASS | **15** |
| PARTIAL | 2 |
| BLOCKED | 3 |
| ERROR | **0** |
| SKIPPED | 1 |
| 합계 | 21 |

### 2-1. 기준 대조

| 기준 | 요구 | 결과 | 판정 |
|---|---|---|---|
| **Beauty PASS** (B1 — AXIS 2 성립) | 3 / 5 이상 | **5 / 5** | **PASS** |
| **Tier 1 PASS** (B3 — Tier 1 First 집행) | 2 / 10 이상 | **7 / 10** | **PASS** |
| 대조군 `example.com` | PASS | PASS (환경 전체 차단 아님) | **PASS** |
| ERROR | — | 0 | **PASS** |

### 2-2. PHASE C 대비

| 항목 | PHASE C (Claude Cloud Routine) | GA-1 (GitHub Actions) |
|---|---|---|
| 외부 웹 접근 | **전면 차단** (`EGRESS_BLOCKED`, `example.com`까지) | **가능** |
| Beauty 전문매체 5곳 | 5곳 전부 접근 불가 | **5곳 전부 PASS** |
| Tier 1 원문 | 0건 | **7건** |

→ `cloud_test_summary.md` §8의 **최대 리스크(한국 언론사가 해외·데이터센터 IP를 차단할 가능성)가
해소되었다.** GitHub-hosted runner의 Azure IP 대역에서 5개 뷰티 전문매체 전부와
Tier 1 기관 7곳에 정상 접근했다.

---

## 3. 기록의 한계 (정직하게 남긴다)

- **매체별 상세 표(도메인·HTTP·bytes·latency)는 이 저장소에 보존되지 않았다.**
  Workflow가 결과를 `$GITHUB_STEP_SUMMARY`에만 출력하고 artifact로 업로드하지 않기 때문이다.
  위 §2 수치는 해당 실행의 Step Summary 집계값을 확정 기록한 것이다.
- 따라서 **PARTIAL 2건 / BLOCKED 3건 / SKIPPED 1건이 각각 어느 Source인지는 이 문서로 특정할 수 없다.**
  추정하지 않는다. 필요 시 GitHub Actions 실행 로그(Step Summary)를 직접 확인한다.
- **개선 사항(GA-3 이후 반영 권고)**: results.tsv를 `actions/upload-artifact`로 올리거나
  이 폴더에 커밋해, 매체별 결과를 주차 간 비교 가능하게 만든다.

---

## 4. 재현성 고정

| 날짜 | 조치 |
|---|---|
| 2026-09-30 | `runs-on`을 `ubuntu-latest` → **`ubuntu-24.04`** 로 고정. `ubuntu-latest`가 차기 LTS로 이동할 때 OS·curl·openssl·awk 구현이 바뀌어 판정 기준이 흔들리는 것을 막는다. **프로브 대상·판정 로직은 무변경** |

> GA-1을 다시 돌려 이 문서의 수치와 비교할 때, 러너 이미지가 고정되어 있어야 차이의 원인을
> "환경 변화"와 "Source 측 변화"로 분리할 수 있다.

---

## 5. 다음 단계

| PHASE | 내용 | 상태 |
|---|---|---|
| **GA-1** | 연결성 실측 | **PASS (2026-09-29)** |
| **GA-2** | AI API · Gmail API 인증 설계 및 Secret 준비 | 진행 중 — `00_SYSTEM/ga2_auth_design.md` |
| **GA-3** | 실제 Brief 생성 + 발송 End-to-End (수동 트리거) | 미착수 |
| **GA-4** | schedule 활성화 + `CLOUD_MODE` 주입 | 미착수 |

**GA-2 시점에 하지 않는 것**: Brief 실제 생성, Gmail 실제 발송, End-to-End 실행,
`schedule:` 활성화, `CLOUD_MODE=true` 설정. Claude Cloud Routine은 `enabled:false` 유지.
