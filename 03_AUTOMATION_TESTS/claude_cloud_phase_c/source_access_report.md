# PHASE C — Source 접근 기록 (Claude Cloud Routine)

> 2026-09-29 실행(`cse_011h11d3zvR5TTkaBokfZtLJ`)의 Source 접근 성공·실패 전수 기록.
> **GitHub Actions 전환 후 동일 도메인에 대해 같은 표를 다시 작성해 대조한다.**
> 이 표가 GA-1 연결성 프로브의 대상 목록이다.

---

## 1. 결론

| 채널 | 상태 |
|---|---|
| **WebFetch (개별 URL 직접 조회)** | **전면 차단** — 시도 전부 실패 |
| **WebSearch (서버 측 실행)** | 동작 — 제목·URL만 획득, **본문 불가** |
| Gmail MCP | 동작 |
| git clone (읽기) | 동작 |
| git push (쓰기) | **403 차단** |

오류 형식: `EGRESS_BLOCKED — Access to <domain> is blocked by the network egress proxy`

**결정적 근거**: 대조군으로 넣은 `example.com`도 차단되었다.
→ 사이트별 차단이나 봇 차단이 아니라 **실행 환경의 정책적 전면 차단**이다.

## 2. Beauty 전문매체 5곳 — 접근 상태

| # | 매체 | 시도한 URL | 결과 | 최종 상태 | 사용 기사 |
|---|---|---|---|---|---|
| 1 | **장업신문** | `www.jangup.com/news/articleList.html?view_type=sm` | `EGRESS_BLOCKED` | `Access Blocked` | 0 |
| 2 | **CMN** | `www.cmn.co.kr/sub/news/news.asp` | `EGRESS_BLOCKED` | `Access Blocked` | 0 |
| 3 | **뷰티누리** | `www.beautynury.com/news/list/cat/10` | `EGRESS_BLOCKED` | `Access Blocked` | 0 |
| 4 | **코스모닝** | `cosmorning.com/news/section_list_all.html?sec_no=1` | `EGRESS_BLOCKED` | `Access Blocked` | 0 |
| 5 | **코스인코리아** | `www.cosinkorea.com/news/articleList.html?view_type=sm`<br>`www.cosinkorea.com/news/article.html?no=58331` | `EGRESS_BLOCKED` (2건) | `Access Blocked` | **1 (제목 수준)** |

### Fallback 수행 기록 (`source_policy.md` 1~5)

| Fallback | 내용 | 수행 여부 |
|---|---|---|
| 1 | 검색엔진 도메인 한정 검색 | **5곳 전부 수행** (`allowed_domains` 지정 WebSearch) |
| 2 | 사이트 카테고리·목록 페이지 | **구조적 불가** — 사이트 자체 차단 |
| 3 | 기사 제목 기반 검색 | 부분 수행 (Fallback 1과 동일 채널) |
| 4 | 동일 이슈 공식 Source | **구조적 불가** — 기관 사이트도 차단 |
| 5 | 타 매체 Cross-check | 부분 수행 |

- 5곳 모두 Fallback 1~5를 시도한 뒤 `Access Blocked`로 확정했다. **`Not Checked` 0건.**
- Fallback 1은 연결은 되었으나 **검색 색인이 연도를 섞어 반환**해 커버리지 기간(2026-09-14~20)
  기사를 특정하기 어려웠다. 코스인코리아 1건만 "9월 3주" 주가 리뷰로 제목 수준 확보.
- 차단을 **우회하지 않았고**, 내용을 추정하지 않았다.

## 3. Tier 1 Source — 접근 상태

| 영역 | 기관 | 시도 URL | 결과 |
|---|---|---|---|
| 금리·통화 (미) | **Federal Reserve** | `www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm` | `EGRESS_BLOCKED` |
| 금리·통화 (한) | **한국은행** | `www.bok.or.kr/eng/main/main.do` | `EGRESS_BLOCKED` |
| 물가·인구·고용 | **통계청** | `kostat.go.kr/board.es?mid=a10301010000&bid=207` | `EGRESS_BLOCKED` |
| 재정·정책 | 기획재정부 | 미시도 (앞선 차단으로 불가 판정) | — |
| 수출입 | 관세청 | 미시도 | — |
| 금융시장 | 금융위/KRX | 미시도 | — |
| 화장품 규제 | 식약처 | 미시도 | — |
| 기업 실적 | DART | 미시도 | — |

**Tier 1 직접 확인 = 0건. verification rate 0/8 = 0.0%** (기준선 2/12 = 16.7%)
→ `qa_cloud_vs_local.md` §3 **B3 위반**.

`Tier 1 First` 규칙(CLAUDE.md §7-1)이 집행 불가능한 환경이었다.

## 4. 기타 도메인 (차단 범위 확인용)

| 도메인 | 목적 | 결과 |
|---|---|---|
| `en.wikipedia.org` | 일반 참조 | `EGRESS_BLOCKED` |
| `www.cosme.net` | JP 신제품 | `EGRESS_BLOCKED` |
| `www.reuters.com` | 글로벌 뉴스 | `Claude Code is unable to fetch` (다른 오류 형식) |
| **`example.com`** | **대조군** | **`EGRESS_BLOCKED`** |

## 5. 동작한 채널 — WebSearch

서버 측 실행이므로 egress 정책의 영향을 받지 않았다. 확인된 동작 예:

- `FOMC September 2026 meeting decision...` → 결과 반환 (2026-09-16 금리 결정 관련 링크)
- `한국은행 기준금리 2026년 9월...` → 결과 반환
- 도메인 한정 검색 5건 → 전부 결과 반환

**한계**: 제목·URL·짧은 스니펫만 제공하고 **본문을 제공하지 않는다.**
→ 보도일 확정, 수치 검증, 신제품 상세(성분·가격·채널) 확보가 **전부 불가능**했다.
→ 최종 사용 Issue 4건, 신제품 0건의 직접 원인.

## 6. 저장소 접근

| 동작 | 결과 |
|---|---|
| `git clone` (읽기) | 성공 — HEAD `04517a8` |
| `git push` (쓰기) | **403** — `Claude doesn't have GitHub access to this repository for your organization` |
| MCP `get_file_contents` (읽기) | 성공 |
| MCP `push_files` (쓰기) | **403** — `Resource not accessible by integration` |

원격 `01_WEEKLY_BRIEFS/2026/` 목록 확인 결과 기준선 8개 파일만 존재.
**프로브 파일을 포함해 원격에 생성된 것은 없다. 기준선 무변경 확인.**

## 7. GA-1 연결성 프로브 대상 목록

GitHub Actions 러너에서 아래를 확인한다. **여기서 막히면 GitHub Actions 전환도 성립하지 않는다.**

**Beauty 5곳**
`jangup.com` · `cmn.co.kr` · `beautynury.com` · `cosmorning.com` · `cosinkorea.com`

**Tier 1**
`bok.or.kr` · `kostat.go.kr` · `customs.go.kr` · `mfds.go.kr` · `dart.fss.or.kr` · `krx.co.kr` · `federalreserve.gov`

**신제품**
`oliveyoung.co.kr` · `sephora.com` · `ulta.com` · `cosme.net` · `fashion-press.net`

**대조군**
`example.com`

확인 항목: HTTP 상태코드 / 리다이렉트 / `robots.txt` / 응답 본문 수신 여부 / 한국 사이트의 IP 차단 징후.
