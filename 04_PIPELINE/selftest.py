# -*- coding: utf-8 -*-
"""GA-3 셀프테스트 — 네트워크·AI·SMTP 를 전혀 쓰지 않는다.

workflow 의 첫 단계에서 돌린다. 여기서 깨지면 수집도 Gemini 호출도 시작하지 않는다
(호출 예산과 러너 시간을 태우기 전에 막는 것이 목적이다).

검증 대상
  1 커버리지 주차 계산 / 날짜 파싱 / 마스킹
  2 Noise 규칙 · 중복 클러스터링
  3 2-of-5 Rule 집행 · 숫자 검증 삭제
  4 Trend Signal 조건 A·B · Confidence 상한 · Price enum
  5 Gemini 호출 예산 상한 · 재시도 허용 범위 (호출은 하지 않는다)
  6 Brief·Email 조립 · QA Critical 판정
  7 발송 Gate 의 FAIL CLOSED 3경로 (QA FAIL / 확인문자열 불일치 / 정상)
"""
import datetime as dt

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze  # noqa: E402
import build  # noqa: E402
import collector  # noqa: E402
import common as C  # noqa: E402
import gate  # noqa: E402
import gemini_client as G  # noqa: E402
import qa as QA  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("%s %s%s" % ("  ok  " if cond else " FAIL ", name,
                       "" if cond or not detail else " — " + detail))


# ── 1. 시간·주차·마스킹 ──────────────────────────────────────────
def test_time():
    start, end = C.coverage_window("2026-W38")
    check("W38 커버리지 시작 = 2026-09-14 00:00 KST",
          start == dt.datetime(2026, 9, 14, 0, 0, 0, tzinfo=C.KST), str(start))
    check("W38 커버리지 종료 = 2026-09-20 23:59:59 KST",
          end == dt.datetime(2026, 9, 20, 23, 59, 59, tzinfo=C.KST), str(end))
    bad = False
    try:
        C.coverage_window("2026-W")
    except ValueError:
        bad = True
    check("잘못된 주차 표기는 예외", bad)
    check("경계 내 판정", C.in_window(
        dt.datetime(2026, 9, 20, 23, 59, 0, tzinfo=C.KST), start, end))
    check("경계 밖 판정", not C.in_window(
        dt.datetime(2026, 9, 21, 0, 0, 1, tzinfo=C.KST), start, end))
    check("RFC822 날짜 파싱",
          C.date_only(C.parse_datetime("Wed, 16 Sep 2026 09:30:00 +0900"))
          == "2026-09-16")
    check("ISO 날짜 파싱",
          C.date_only(C.parse_datetime("2026-09-18T14:05:00+09:00"))
          == "2026-09-18")
    check("한국어 날짜 파싱",
          C.date_only(C.parse_datetime("입력 2026년 9월 17일 11:20")) == "2026-09-17")
    check("미확인 날짜는 None", C.parse_datetime("지난주") is None)
    check("메일 마스킹", C.mask_email("someone@example.org") == "s***@example.org")
    s = C.sanitize("pw=supersecretvalue to someone@example.org",
                   secrets=("supersecretvalue",))
    check("sanitize 가 Secret·메일주소를 지운다",
          "supersecretvalue" not in s and "someone@example.org" not in s, s)


# ── 2. Noise · 클러스터링 ────────────────────────────────────────
def test_filters():
    noise, _ = collector.is_noise("A사-B사 업무협약 MOU 체결", "양사는 협약을 맺었다")
    check("MOU 기사는 Noise", noise)
    noise2, _ = collector.is_noise(
        "A사, B사와 업무협약 체결하고 지분 51% 인수",
        "인수 금액은 1,200억원이며 영업이익에 반영된다")
    check("Noise 키워드 + 예외 사유(인수·지분)면 유지", not noise2)
    check("신제품 후보 판정",
          collector.is_product_candidate("브랜드 X, 신제품 세럼 출시", ""))

    items = [
        {"id": "A1", "title": "화장품 수출 7월 13.5억 달러 최대치"},
        {"id": "A2", "title": "7월 화장품 수출 13.5억 달러로 최대치 기록"},
        {"id": "A3", "title": "기준금리 0.25%p 인상 결정"},
    ]
    clusters = collector.cluster(items)
    check("유사 제목은 같은 클러스터",
          items[0]["cluster_id"] == items[1]["cluster_id"])
    check("다른 주제는 다른 클러스터",
          items[2]["cluster_id"] != items[0]["cluster_id"])
    check("클러스터 수 2개", len(clusters) == 2, str(len(clusters)))


# ── 2-A. 수집 파서 (네트워크 없이 샘플 마크업으로) ──────────────
RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Sample</title>
<item><title>화장품 수출 13.5억 달러</title>
<link>https://news.example.org/a/1</link>
<pubDate>Wed, 16 Sep 2026 09:30:00 +0900</pubDate>
<description>7월 수출이 13.5억 달러로 집계됐다.</description></item>
<item><title>두 번째 기사</title><link>https://news.example.org/a/2</link>
<pubDate>Mon, 21 Sep 2026 08:00:00 +0900</pubDate></item>
</channel></rss>"""

ATOM_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>FOMC statement</title>
<link rel="alternate" href="https://www.example.org/press/a.htm"/>
<updated>2026-09-16T18:00:00Z</updated>
<summary>The Committee raised the target range by 25 basis points.</summary>
</entry></feed>"""

LIST_SAMPLE = """<html><body><ul>
<li><a href="/news/articleView.html?idxno=12345">업계 첫 ODM 수주 1,200억원 계약</a></li>
<li><a href="/news/articleView.html?idxno=12345">중복 링크 같은 기사</a></li>
<li><a href="/news/articleView.html?idxno=12346">신제품 세럼 출시</a></li>
<li><a href="/about.html">회사소개</a></li>
<li><a href="/news/articleView.html?idxno=12347">짧음</a></li>
</ul></body></html>"""

ARTICLE_META = """<html><head>
<meta property="article:published_time" content="2026-09-17T11:20:00+09:00">
<title>신제품 출시 — 샘플신문</title></head>
<body><p>브랜드가 신제품을 선보였다. 가격은 32,000원이다.</p></body></html>"""

ARTICLE_BYLINE = """<html><head><title>수출 기사</title></head><body>
<span class="date">입력 2026.09.16 10:20</span>
<p>7월 화장품 수출은 13.5억 달러로 전년 대비 37.8% 늘었다.</p>
</body></html>"""


def test_parsers():
    rss = collector.parse_feed(RSS_SAMPLE)
    check("RSS 항목 2건 파싱", len(rss) == 2, str(len(rss)))
    check("RSS 제목·링크 추출",
          rss[0]["title"].startswith("화장품 수출")
          and rss[0]["url"] == "https://news.example.org/a/1")
    check("RSS 보도일 파싱",
          C.date_only(C.parse_datetime(rss[0]["published_raw"])) == "2026-09-16")

    atom = collector.parse_feed(ATOM_SAMPLE)
    check("Atom link href 추출",
          len(atom) == 1 and atom[0]["url"].endswith("/press/a.htm"),
          str(atom))

    links = collector.extract_links(
        LIST_SAMPLE, "https://www.jangup.com/news/articleList.html",
        [r"/news/articleView\.html\?idxno=\d+"])
    urls = [u for u, _ in links]
    check("목록에서 기사 링크만 추출", len(links) == 2, str(urls))
    check("상대경로를 절대 URL 로 변환",
          urls[0].startswith("https://www.jangup.com/news/articleView.html"))
    check("같은 기사 URL 중복 제거", len(set(urls)) == len(urls))
    check("짧은 링크 라벨 제외", all("idxno=12347" not in u for u in urls))

    check("meta 보도일 추출",
          C.date_only(collector.extract_published(ARTICLE_META)) == "2026-09-17")
    check("기사 본문 '입력' 날짜 추출",
          C.date_only(collector.extract_published(ARTICLE_BYLINE)) == "2026-09-16")
    check("날짜가 없으면 None", collector.extract_published(
        "<html><body><p>본문</p></body></html>") is None)

    ex = collector.make_excerpt("제목", ARTICLE_BYLINE, limit=300)
    check("발췌에 제목과 숫자 문장이 들어간다",
          ex.startswith("제목") and "13.5" in ex, ex[:80])
    check("발췌 길이 상한 준수", len(ex) <= 301, str(len(ex)))
    check("발췌에 태그가 남지 않는다", "<" not in ex)

    text = collector._decode("한글 본문".encode("utf-8"),
                             "text/html; charset=utf-8")
    check("Content-Type charset 디코딩", "한글" in text)
    text2 = collector._decode(
        b'<meta charset="utf-8">' + "한글".encode("utf-8"), "")
    check("meta charset 디코딩", "한글" in text2)


# ── 3. 2-of-5 · 숫자 검증 ───────────────────────────────────────
def test_selection_and_numbers():
    pool = {
        "A1": {"id": "A1", "cluster_id": "CL000", "tier": 2,
               "published": "2026-09-16", "source_name": "매체A",
               "source_id": "a", "title": "t1", "url": "https://x/1",
               "axis": "AXIS1", "excerpt": "수출 13.5억 달러"},
        "A2": {"id": "A2", "cluster_id": "CL001", "tier": 3,
               "published": "2026-09-17", "source_name": "매체B",
               "source_id": "b", "title": "t2", "url": "https://x/2",
               "axis": "AXIS1", "excerpt": "내용"},
    }
    stats = {"numbers_removed": 0, "excluded_by_rule": 0, "unknown_ids": 0,
             "signals_demoted": 0, "spec_violations": 0}
    sel = {"items": [
        {"id": "A1", "keep": True, "criteria_met": ["ECONOMIC", "INDUSTRY"],
         "cluster_id": "CL000"},
        {"id": "A2", "keep": True, "criteria_met": ["CONSUMER"],
         "cluster_id": "CL001"},
        {"id": "ZZ", "keep": True, "criteria_met": ["ECONOMIC", "POLICY"],
         "cluster_id": "CL009"},
    ]}
    kept, _ = analyze.apply_selection(sel, pool, stats)
    check("criteria 2개 이상만 채택", list(kept.keys()) == ["A1"], str(kept.keys()))
    check("2-of-5 미달은 제외 집계", stats["excluded_by_rule"] == 1)
    check("없는 id 는 무시하고 집계", stats["unknown_ids"] == 1)

    issues = analyze.merge_clusters(kept, pool)
    check("클러스터 병합 결과 1건", len(issues) == 1)

    allowed = C.numbers_in("수출 13.5억 달러, 전년 대비 37.8% 증가")
    out = analyze.verify_numbers("수출 13.5억 달러로 99.9% 늘었다", allowed, stats)
    check("발췌에 있는 숫자는 유지", "13.5" in out, out)
    check("발췌에 없는 숫자는 삭제", "99.9" not in out, out)
    out2 = analyze.verify_numbers("매출 1,200억원", C.numbers_in("매출 1,200억원"),
                                  stats)
    check("쉼표 표기 숫자 검증", "1,200" in out2, out2)
    out3 = analyze.verify_numbers("매출 1,200억원", C.numbers_in("매출 300억원"), stats)
    check("쉼표 표기 미검증 숫자 삭제", "1,200" not in out3, out3)


# ── 4. Trend Signal · Price ─────────────────────────────────────
def test_signal_and_price():
    stats = {"numbers_removed": 0, "excluded_by_rule": 0, "unknown_ids": 0,
             "signals_demoted": 0, "spec_violations": 0}
    items = {
        "P1": {"id": "P1", "tier": 3, "source_name": "매체A", "country": "KR",
               "url": "https://x/1", "published": "2026-09-16",
               "excerpt": "세럼 32,000원", "title": "신제품"},
        "P2": {"id": "P2", "tier": 1, "source_name": "기관", "country": "KR",
               "url": "https://x/2", "published": "2026-09-17",
               "excerpt": "크림 45,000원", "title": "신제품"},
    }
    products = [{"brand": "브랜드1"}, {"brand": "브랜드2"}]
    sig, demoted = analyze.check_signal(
        {"name": "s", "observation": "두 브랜드가 같은 성분을 썼다",
         "interpretation": "i", "confidence": "High", "brands": ["브랜드1"],
         "product_count": 2, "source_item_ids": ["P1"]},
        products, items, stats)
    check("브랜드 1건·Tier3 근거는 Signal 조건 미달 → 강등",
          sig is None and demoted is not None)
    check("강등 건수 집계", stats["signals_demoted"] == 1)

    sig2, _ = analyze.check_signal(
        {"name": "s2", "observation": "세 브랜드가 동일 성분을 표기했다",
         "interpretation": "i", "confidence": "High",
         "brands": ["b1", "b2", "b3"], "product_count": 3,
         "source_item_ids": ["P1", "P2"]},
        [{"brand": "b1"}, {"brand": "b2"}, {"brand": "b3"}], items, stats)
    check("조건 A + Tier1 근거면 High 유지",
          sig2 and sig2["confidence"] == "High", sig2 and sig2["confidence"])

    sig3, _ = analyze.check_signal(
        {"name": "s3", "observation": "세 브랜드가 가을 신제품을 냈다",
         "interpretation": "i", "confidence": "High",
         "brands": ["b1", "b2", "b3"], "product_count": 3,
         "source_item_ids": ["P1", "P2"], "seasonality_risk": True},
        [{"brand": "b1"}, {"brand": "b2"}, {"brand": "b3"}], items, stats)
    check("계절성 위험이면 High 금지 → Medium",
          sig3 and sig3["confidence"] == "Medium", sig3 and sig3["confidence"])

    before = stats["spec_violations"]
    rows = analyze.clean_products([
        {"source_item_id": "P1", "brand": "브랜드1", "product": "세럼",
         "category": "스킨케어", "price_state": "Verified", "price_detail": "미정"},
        {"source_item_id": "P2", "brand": "브랜드2", "product": "크림",
         "category": "스킨케어", "price_state": "WhoKnows", "price_detail": ""},
        {"source_item_id": "없음", "brand": "x", "product": "y",
         "category": "z", "price_state": "Verified", "price_detail": "10,000원"},
    ], items, stats)
    check("금액 없는 Verified 는 Not verified 로 교정",
          rows[0]["price_state"] == "Not verified", rows[0]["price_state"])
    check("enum 이탈 Price 는 Not verified 로 교정",
          rows[1]["price_state"] == "Not verified", rows[1]["price_state"])
    check("규격 위반 건수 집계", stats["spec_violations"] - before == 2)
    check("출처 id 가 없는 제품은 버린다", len(rows) == 2, str(len(rows)))
    check("Article URL 은 수집 단계 값만 사용",
          rows[0]["url"] == "https://x/1")


# ── 5. 호출 예산 · 재시도 정책 (호출 없음) ──────────────────────
def test_budget():
    os.environ["GEMINI_API_KEY"] = "selftest-not-a-real-key"
    os.environ["GEMINI_MODEL"] = "selftest-model"
    os.environ["AI_CALL_BUDGET"] = "50"
    client = G.GeminiClient(pace=0)
    check("예산은 절대 상한 10 을 넘지 못한다", client.budget == G.HARD_CAP,
          str(client.budget))
    os.environ["AI_CALL_BUDGET"] = "8"
    client8 = G.GeminiClient(pace=0)
    check("예산 8 설정은 그대로 적용", client8.budget == 8, str(client8.budget))
    check("목표 호출 수 7 / 권고 상한 8",
          G.TARGET_CALLS == 7 and G.RECOMMENDED_CAP == 8)
    check("단계당 재시도 1회 / 실행당 총 3회",
          G.MAX_RETRIES_PER_STAGE == 1 and G.MAX_RETRIES_TOTAL == 3)

    client8.calls = 8
    budget_blocked = False
    try:
        client8._reserve("x")
    except G.CallBudgetExceeded:
        budget_blocked = True
    check("예산 초과 요청은 호출 전에 거부", budget_blocked)

    check("503 은 재시도 허용", G.GeminiClient._retryable("SERVICE_UNAVAILABLE_503"))
    check("429 분당 한도는 재시도 허용",
          G.GeminiClient._retryable("QUOTA_EXCEEDED_PER_MINUTE"))
    check("429 일일 한도는 재시도 금지",
          not G.GeminiClient._retryable("QUOTA_EXCEEDED_PER_DAY"))
    check("429 구분 불가는 재시도 금지 (보수적)",
          not G.GeminiClient._retryable("QUOTA_EXCEEDED_UNKNOWN"))
    for cat in ("API_KEY_INVALID", "AUTH_FORBIDDEN", "MODEL_NOT_FOUND",
                "SERVER_ERROR_500", "BAD_REQUEST_400", "NETWORK_ERROR",
                "STRUCTURED_OUTPUT_PARSE_FAILED"):
        check("%s 은 즉시 Fail Closed" % cat, not G.GeminiClient._retryable(cat))
    cl = G.GeminiClient(pace=0)
    check("429 본문이 PerDay 면 일일 한도로 분류",
          cl._classify(429, '{"error":{"details":[{"quotaId":'
                            '"GenerateRequestsPerDayPerProject"}]}}')
          == "QUOTA_EXCEEDED_PER_DAY")
    check("429 본문이 PerMinute 면 분당 한도로 분류",
          cl._classify(429, '{"quotaId":"GenerateRequestsPerMinute"}')
          == "QUOTA_EXCEEDED_PER_MINUTE")
    check("retryDelay 를 90초 이내로 제한",
          cl._retry_delay('"retryDelay": "600s"') <= 90)
    for key in ("GEMINI_API_KEY", "GEMINI_MODEL", "AI_CALL_BUDGET"):
        os.environ.pop(key, None)


# ── 6·7. 조립 · QA · Gate ───────────────────────────────────────
def fixture(weekly="2026-W38", good_url=True, misplace=False):
    start, end = C.coverage_window(weekly)
    collected = {
        "weekly_id": weekly,
        "coverage": {"start_kst": start.isoformat(), "end_kst": end.isoformat()},
        "generated_at_utc": C.stamp_utc(),
        "sources": [
            {"id": sid, "name": name, "axis": "BEAUTY", "tier": 3,
             "status": "Checked — usable articles found", "fetched": 5,
             "in_window": 2, "attempts": [], "notes": []}
            for sid, name in (("jangup", "장업신문"), ("cmn", "CMN"),
                              ("beautynury", "뷰티누리"))
        ] + [
            {"id": "cosmorning", "name": "코스모닝", "axis": "BEAUTY", "tier": 3,
             "status": "Checked — no significant news", "fetched": 4,
             "in_window": 0, "attempts": [], "notes": []},
            {"id": "cosinkorea", "name": "코스인코리아", "axis": "BEAUTY",
             "tier": 3, "status": "Partial Access", "fetched": 2,
             "in_window": 0, "attempts": [], "notes": ["보도일 확인 불가"]},
            {"id": "fed_press", "name": "Federal Reserve 보도자료",
             "axis": "TIER1", "tier": 1,
             "status": "Checked — usable articles found", "fetched": 3,
             "in_window": 1, "attempts": [], "notes": []},
        ],
        "items": [],
        "stats": {"collected_total": 120, "noise_excluded": 18,
                  "after_dedup": 64, "product_candidates": 22,
                  "tier1_sources_with_items": 2},
    }

    def issue(iid, axis, section, src, tier, t1, url):
        return {
            "id": iid, "cluster_id": "CL_" + iid, "members": [iid],
            "media": [src], "source_name": src, "source_id": src, "tier": tier,
            "published": "2026-09-16", "title": "원문 제목", "url": url,
            "axis": axis, "criteria_met": ["ECONOMIC", "INDUSTRY"],
            "tier1_backed": t1, "section": section,
            "headline": "무엇이 달라졌는가 %s" % iid,
            "what_changed": "지표가 3.5% 움직였다", "why_it_matters": "조달비용 전제가 바뀐다",
            "numbers": "3.5%", "context": "직전 주 대비", "implication": "브랜드 영향",
            "tag": "FACT", "written": True,
        }

    general = [issue("A1", "AXIS1", "KR_ECON", "Federal Reserve 보도자료", 1,
                     True, "https://example.org/a1"),
               issue("A2", "AXIS1", "OVERSEAS", "CNBC Economy", 2, False,
                     "https://example.org/a2")]
    beauty = [issue("B1", "BEAUTY", "EXPORT", "뷰티누리", 3, False,
                    "https://example.org/b1"),
              issue("B2", "BEAUTY", "BRAND", "장업신문", 3, False,
                    "https://example.org/b2"),
              issue("B3", "BEAUTY", "ODM", "CMN", 3, False,
                    "https://example.org/b3")]

    def product(brand, src, url, country):
        return {"brand": brand, "product": "제품", "category": "스킨케어",
                "ingredient": "성분", "technology": "—", "claim": "보습",
                "texture": "세럼", "price_state": "Verified",
                "price_detail": "32,000원 / 30ml", "channel": "올리브영",
                "launch_date": "2026-09-16", "source_name": src,
                "source_item_id": "X", "source_country": country, "url": url,
                "published": "2026-09-16", "tier": 3}

    signal = {
        "name": "성분 표기 강화", "observation": "세 브랜드가 동일 성분을 표기했다",
        "interpretation": "성분 경쟁이 표기 단계로 내려왔다", "confidence": "Medium",
        "evidence": {"brands": ["b1", "b2", "b3"], "brand_count": 3,
                     "product_count": 3, "source_item_ids": ["P1", "P2"],
                     "source_tiers": [1, 3], "condition": "A"},
        "seasonality_note": "전년 동기 비교 없음", "adjustments": [],
        "vs_prev_week": "New (직전 주 기록 없음)",
    }
    analysis = {
        "weekly_id": weekly,
        "generated_at_utc": C.stamp_utc(),
        "stages": [],
        "general_issues": general,
        "beauty_issues": beauty,
        "must_know": [{
            "id": "A1", "rank": 1, "headline": "연준이 금리를 올렸다",
            "what_changed": "25bp 인상", "why_it_matters": "조달비용 전제가 바뀐다",
            "tag": "FACT", "source_name": "Federal Reserve 보도자료",
            "published": "2026-09-16",
            "url": "https://example.org/a1" if good_url else "",
            "axis": "AXIS1", "tier": 1, "tier1_backed": True,
            "media": ["Federal Reserve 보도자료"],
        }],
        "products": {
            "KR": [product("브랜드1", "뷰티누리", "https://example.org/p1",
                           "JP" if misplace else "KR"),
                   product("브랜드2", "장업신문", "https://example.org/p2", "KR")],
            "US": [product("BrandUS", "Glossy", "https://example.org/p3", "US")],
            "JP": [product("BrandJP", "@cosme", "https://example.org/p4", "JP")],
        },
        "signals": {"KR": signal, "US": None, "JP": None},
        "watch_items": [{"country": "US", "what": "확인 항목", "why": "근거 부족"}],
        "pools": {"general": 40, "beauty": 20,
                  "products": {"KR": 12, "US": 6, "JP": 5}},
        "verification": {"numbers_removed": 1, "excluded_by_rule": 31,
                         "unknown_ids": 0, "signals_demoted": 1,
                         "spec_violations": 0},
        "usage": {"model": "selftest-model", "calls": 7, "retries": 0,
                  "budget": 10, "hard_cap": 10, "tokens_in": 1000,
                  "tokens_out": 500, "tokens_total": 1500,
                  "fallback_model_used": False, "log": []},
    }
    return collected, analysis


def run_pipeline_offline(tmp, collected, analysis, confirm, extra_env=None):
    out_dir = os.path.join(tmp, "out")
    os.makedirs(out_dir, exist_ok=True)
    cpath = os.path.join(tmp, "collected.json")
    apath = os.path.join(tmp, "analysis.json")
    C.write_json(cpath, collected)
    C.write_json(apath, analysis)

    argv = sys.argv
    try:
        sys.argv = ["build.py", "--collected", cpath, "--analysis", apath,
                    "--out-dir", out_dir]
        build.main()
        sys.argv = ["qa.py", "--collected", cpath, "--analysis", apath,
                    "--out-dir", out_dir]
        QA.main()
        env_backup = {}
        env = {"WIB_RECIPIENT": "selftest@example.org",
               "GA3_CONFIRM_SEND": confirm}
        env.update(extra_env or {})
        for k, v in env.items():
            env_backup[k] = os.environ.get(k)
            os.environ[k] = v
        os.environ.pop("CLOUD_MODE", None)
        sys.argv = ["gate.py", "--weekly-id", collected["weekly_id"],
                    "--out-dir", out_dir, "--repo-root", tmp]
        gate.main()
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    finally:
        sys.argv = argv
    return out_dir


def write_ledger(tmp, rows):
    path = os.path.join(tmp, "00_SYSTEM", "send_ledger.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    header = ("WeeklyID,Mode,Status,SentAtKST,SentAtUTC,Subject,"
              "GmailMessageId,GateResult,Note")
    C.write_text(path, header + "\n" + "".join(r + "\n" for r in rows))


def test_build_qa_gate():
    tmp = tempfile.mkdtemp(prefix="ga3-selftest-")
    try:
        collected, analysis = fixture()
        write_ledger(tmp, [])
        out = run_pipeline_offline(tmp, collected, analysis, "SEND-TEST")

        with open(os.path.join(out, "2026-W38_gemini.md"), "r",
                  encoding="utf-8") as fh:
            md = fh.read()
        with open(os.path.join(out, "2026-W38_gemini.html"), "r",
                  encoding="utf-8") as fh:
            html = fh.read()
        qa_json = C.read_json(os.path.join(out, "qa.json"))
        gate_json = C.read_json(os.path.join(out, "gate.json"))

        for label in ("KOREA", "USA", "JAPAN"):
            check("신제품 %s 섹션 독립 존재" % label,
                  ("## %s NEW PRODUCT WATCH" % label) in md)
        check("QA 자리표시자가 채워졌다", build.QA_PLACEHOLDER not in md)
        check("이메일 QA 자리표시자가 채워졌다",
              build.QA_EMAIL_PLACEHOLDER not in html)
        check("이메일에 외부 CSS·스크립트·이미지 없음",
              not any(m in html.lower()
                      for m in ("<link", "<script", "<img", "@import")))
        check("이메일 제목에 TEST 표기", "[TEST]" in html)
        check("Tier 1 미확인 표기 삽입",
              build.TIER1_NOTE in md)
        check("Trend Signal 미생성 국가는 문구로 명시",
              "이번 주 유의미한 Signal 없음" in md)
        check("Critical QA 전부 PASS",
              qa_json["critical_fails"] == [], str(qa_json["critical_fails"]))
        check("Article URL 확보율 100%", qa_json["url_rate"] == 100.0,
              str(qa_json["url_rate"]))
        check("Beauty 반영 매체 3곳 이상",
              sum(1 for r in qa_json["beauty_rows"] if r["used"] > 0) >= 3)
        check("Gate 결정 = SEND_TEST", gate_json["decision"] == "SEND_TEST",
              gate_json["decision"])
        check("Gate 모드 = LOCAL (CLOUD_MODE 미설정)",
              gate_json["mode"] == "LOCAL")
        check("발송 등급 = TEST", gate_json["send_class"] == "TEST")
        check("G0 는 발송 차단 목록에 없다 (GA-3 는 TEST 전용)",
              "G0_cloud_mode_true" not in gate_json["failed_gates"])
        check("제목에 TEST 와 주차 포함",
              "[TEST]" in gate_json["subject"] and "2026-W38" in gate_json["subject"])

        # 확인 문자열 불일치 → 발송하지 않는다
        out2 = run_pipeline_offline(tmp, collected, analysis, "send")
        g2 = C.read_json(os.path.join(out2, "gate.json"))
        check("확인 문자열 불일치 → SKIPPED_NO_CONFIRM",
              g2["decision"] == "SKIPPED_NO_CONFIRM", g2["decision"])

        # Critical QA FAIL → 발송 차단
        collected_b, analysis_b = fixture(good_url=False)
        out3 = run_pipeline_offline(tmp, collected_b, analysis_b, "SEND-TEST")
        qa3 = C.read_json(os.path.join(out3, "qa.json"))
        g3 = C.read_json(os.path.join(out3, "gate.json"))
        check("MUST KNOW URL 누락은 C2 FAIL",
              "C2_must_know_urls" in qa3["critical_fails"],
              str(qa3["critical_fails"]))
        check("Critical FAIL 이면 발송 차단",
              g3["decision"] == "BLOCKED_G3_critical_qa", g3["decision"])

        # 국가 섹션이 섞이면 C4 FAIL
        collected_c, analysis_c = fixture(misplace=True)
        out_c = run_pipeline_offline(tmp, collected_c, analysis_c, "SEND-TEST")
        qa_c = C.read_json(os.path.join(out_c, "qa.json"))
        g_c = C.read_json(os.path.join(out_c, "gate.json"))
        check("JP Source 제품이 KR 섹션에 있으면 C4 FAIL",
              "C4_country_split" in qa_c["critical_fails"],
              str(qa_c["critical_fails"]))
        check("C4 FAIL 이면 발송 차단",
              g_c["decision"] == "BLOCKED_G3_critical_qa", g_c["decision"])

        # 같은 주차 정식 발송 기록이 있으면 보내지 않는다
        write_ledger(tmp, ["2026-W38,CLOUD,SENT,2026-09-21 08:40,"
                           "2026-09-20T23:40:00Z,[WEEKLY INTELLIGENCE] 2026-W38,"
                           "x,G1..G7 PASS,정상 발송"])
        out4 = run_pipeline_offline(tmp, collected, analysis, "SEND-TEST")
        g4 = C.read_json(os.path.join(out4, "gate.json"))
        check("같은 주차 SENT 기록이 있으면 G7 FAIL",
              g4["decision"] == "BLOCKED_G7_no_duplicate", g4["decision"])

        # 원장을 못 읽으면 G6 FAIL (FAIL CLOSED)
        os.remove(os.path.join(tmp, "00_SYSTEM", "send_ledger.csv"))
        out5 = run_pipeline_offline(tmp, collected, analysis, "SEND-TEST")
        g5 = C.read_json(os.path.join(out5, "gate.json"))
        check("원장을 읽지 못하면 G6 FAIL",
              g5["decision"] == "BLOCKED_G6_duplicate_check_done", g5["decision"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("== GA-3 selftest (네트워크·AI·SMTP 미사용) ==")
    test_time()
    test_filters()
    test_parsers()
    test_selection_and_numbers()
    test_signal_and_price()
    test_budget()
    test_build_qa_gate()
    print("")
    print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("실패 항목:")
        for name in FAIL:
            print(" - %s" % name)
        return 1
    summary = "### STEP 0 — Selftest\n\n- 통과 **%d건** / 실패 0건\n" % len(PASS)
    C.append_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
