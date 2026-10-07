# -*- coding: utf-8 -*-
"""GA-3 Source 레지스트리.

원칙
- GA-1 Connectivity Probe(2026-09-29 PASS)에서 접근이 확인된 경로를 우선 쓴다.
- **아래 경로·패턴·페이지 파라미터는 2026-10-07 실제 응답으로 확인한 값이다**
  (`verified` 주석). 확인하지 못한 것은 그렇게 적는다. 추정으로 적지 않는다.
- `kind`
    feed     : RSS/Atom. 제목·링크·보도일이 피드에 들어있다.
               `page_url` 이 있으면 과거 항목까지 거슬러 올라갈 수 있다(WordPress `?paged=`).
    list     : HTML 목록. `page_url` 로 커버리지 구간 페이지를 찾아 들어간다.
    datescan : 날짜 템플릿. 구간의 각 날짜로 **요청해 200 + 본문이 확인된 URL만** 채택.
- `urls` 의 2번째 이후는 Fallback 경로다(CLAUDE.md 5장 Fallback 2~5).
  Fallback 1(검색엔진 도메인 한정 질의)은 러너에서 자동 실행하지 않는다.
- `article_res` : <a href> 패턴. `raw_link_res` : href 가 javascript 인 목록에서
  HTML 안의 실제 URL 문자열을 그대로 추출하기 위한 패턴(조립이 아니다).
- `max_pages` : 목록/피드 페이지 열람 상한. `max_articles` : 기사 본문 열람 상한.
"""

# 뷰티 전문매체 5곳 — CLAUDE.md 5장. 각각 독립 확인한다.
BEAUTY_MEDIA_IDS = ["jangup", "cmn", "beautynury", "cosmorning", "cosinkorea"]

SOURCES = [
    # ── AXIS 2 — 뷰티 전문매체 5곳 (필수) ────────────────────────
    {
        # verified 2026-10-07: ?page=12&view_type=sm -> 2026-09-14/15 (W38 도달)
        "id": "jangup", "name": "장업신문", "axis": "BEAUTY", "country": "KR",
        "tier": 3, "kind": "list", "ga1_verified": True,
        "max_pages": 24, "max_articles": 40,
        "urls": [
            "https://www.jangup.com/news/articleList.html?view_type=sm",
            "https://www.jangup.com/rss/allArticle.xml",
        ],
        "page_url": ("https://www.jangup.com/news/articleList.html"
                     "?page={page}&view_type=sm"),
        "article_res": [r"/news/articleView\.html\?idxno=\d+"],
    },
    {
        # verified 2026-10-07: 기사 링크는 /sub/news/news_view.asp?news_idx=N.
        # page / pagenum / pageNum 파라미터는 **무시된다**(응답 동일) → 과거 주차는
        # 최신 목록으로 닿지 않는다. 그 사실을 Partial Access 로 기록한다.
        "id": "cmn", "name": "CMN", "axis": "BEAUTY", "country": "KR",
        "tier": 3, "kind": "list", "ga1_verified": True,
        "max_pages": 1, "max_articles": 30,
        "urls": [
            "https://www.cmn.co.kr/sub/news/news.asp",
            "https://www.cmn.co.kr/mainnews/",
        ],
        "article_res": [r"news_view\.asp\?news_idx=\d+"],
    },
    {
        # verified 2026-10-07: 목록 경로는 /news/lists/... (단수 list 아님).
        # /page/N 은 동작하지만 1페이지당 이동 폭이 작아(60페이지 ≈ 9일 전)
        # 상한 안에서 3주 전 구간에는 닿지 않을 수 있다 → Partial Access 가 정상.
        "id": "beautynury", "name": "뷰티누리", "axis": "BEAUTY", "country": "KR",
        "tier": 3, "kind": "list", "ga1_verified": True,
        "max_pages": 40, "max_articles": 30,
        "urls": [
            "https://www.beautynury.com/news/lists/cat/10",
            "https://www.beautynury.com/m/news/lists/cat/10",
        ],
        "page_url": "https://www.beautynury.com/news/lists/cat/10/page/{page}",
        "article_res": [r"/news/view/\d+"],
    },
    {
        # verified 2026-10-07: article_list_all.html?page=12 -> 2026-09-10/11
        # (section_list_all.html 은 page 파라미터가 듣지 않는다)
        "id": "cosmorning", "name": "코스모닝", "axis": "BEAUTY", "country": "KR",
        "tier": 3, "kind": "list", "ga1_verified": True,
        "max_pages": 24, "max_articles": 40,
        "urls": [
            "https://cosmorning.com/news/article_list_all.html",
            "https://cosmorning.com/news/section_list_all.html?sec_no=1",
        ],
        "page_url": "https://cosmorning.com/news/article_list_all.html?page={page}",
        "article_res": [r"/news/article\.html\?no=\d+"],
    },
    {
        # verified 2026-10-07: article_list_all.html?page=12 -> 2026-08-04/05
        "id": "cosinkorea", "name": "코스인코리아", "axis": "BEAUTY",
        "country": "KR", "tier": 3, "kind": "list", "ga1_verified": True,
        "max_pages": 24, "max_articles": 40,
        "urls": [
            "https://www.cosinkorea.com/news/article_list_all.html",
            "https://www.cosinkorea.com/news/articleList.html?view_type=sm",
        ],
        "page_url": "https://www.cosinkorea.com/news/article_list_all.html?page={page}",
        "article_res": [r"/news/article\.html\?no=\d+"],
    },

    # ── AXIS 1 — 국내 (목록 아카이브: 과거 주차 도달 가능) ───────
    {
        # verified 2026-10-07: /economy/all/3 에 /view/AKR... 링크 90건
        "id": "yna_econ", "name": "연합뉴스 경제", "axis": "AXIS1", "country": "KR",
        "tier": 2, "kind": "list", "max_pages": 40, "max_articles": 26,
        "urls": ["https://www.yna.co.kr/economy/all/1"],
        "page_url": "https://www.yna.co.kr/economy/all/{page}",
        "article_res": [r"/view/AKR\d+"],
    },
    {
        "id": "yna_ind", "name": "연합뉴스 산업", "axis": "AXIS1", "country": "KR",
        "tier": 2, "kind": "list", "max_pages": 40, "max_articles": 20,
        "urls": ["https://www.yna.co.kr/industry/all/1"],
        "page_url": "https://www.yna.co.kr/industry/all/{page}",
        "article_res": [r"/view/AKR\d+"],
    },
    {
        # verified 2026-10-07: ?page=3 에 /article/<10자리 이상> 링크 88건
        "id": "hk_econ", "name": "한국경제 경제", "axis": "AXIS1", "country": "KR",
        "tier": 2, "kind": "list", "max_pages": 40, "max_articles": 26,
        "urls": ["https://www.hankyung.com/economy"],
        "page_url": "https://www.hankyung.com/economy?page={page}",
        "article_res": [r"/article/\d{10,}"],
    },
    {
        "id": "hk_ind", "name": "한국경제 산업", "axis": "AXIS1", "country": "KR",
        "tier": 2, "kind": "list", "max_pages": 40, "max_articles": 20,
        "urls": ["https://www.hankyung.com/industry"],
        "page_url": "https://www.hankyung.com/industry?page={page}",
        "article_res": [r"/article/\d{10,}"],
    },
    {
        # verified 2026-10-07: /news/economy/?page=3 에 /news/economy/<N> 링크 34건.
        # 단 목록 행에 날짜 표기가 없어 과거 주차를 날짜로 겨냥할 수 없다
        # → max_pages 1 (최신 목록만). 과거 주차에서는 Partial Access 가 정상.
        "id": "mk_econ", "name": "매일경제 경제", "axis": "AXIS1", "country": "KR",
        "tier": 2, "kind": "list", "max_pages": 1, "max_articles": 20,
        "urls": ["https://www.mk.co.kr/news/economy/"],
        "page_url": "https://www.mk.co.kr/news/economy/?page={page}",
        "article_res": [r"/news/economy/\d+"],
    },
    {
        "id": "mk_biz", "name": "매일경제 기업", "axis": "AXIS1", "country": "KR",
        "tier": 2, "kind": "list", "max_pages": 1, "max_articles": 20,
        "urls": ["https://www.mk.co.kr/news/business/"],
        "page_url": "https://www.mk.co.kr/news/business/?page={page}",
        "article_res": [r"/news/business/\d+"],
    },
    {
        # RSS — 과거 주차에는 닿지 않는다(최신만). 현재 주차 실행에서 쓰인다.
        "id": "etnews", "name": "전자신문", "axis": "AXIS1", "country": "KR",
        "tier": 2, "kind": "feed", "max_pages": 1,
        "urls": ["https://rss.etnews.com/Section901.xml"],
    },
    {
        "id": "theguru", "name": "더구루", "axis": "AXIS1", "country": "KR",
        "tier": 2, "kind": "feed", "max_pages": 1,
        "urls": ["https://www.theguru.co.kr/rss/allArticle.xml"],
    },

    # ── AXIS 1 — 해외 ───────────────────────────────────────────
    {
        "id": "cnbc_econ", "name": "CNBC Economy", "axis": "AXIS1", "country": "US",
        "tier": 2, "kind": "feed", "max_pages": 1,
        "urls": ["https://search.cnbc.com/rs/search/combinedcms/view.xml"
                 "?partnerId=wrss25&id=20910258"],
    },
    {
        "id": "cnbc_world", "name": "CNBC World", "axis": "AXIS1", "country": "US",
        "tier": 2, "kind": "feed", "max_pages": 1,
        "urls": ["https://search.cnbc.com/rs/search/combinedcms/view.xml"
                 "?partnerId=wrss25&id=100727362"],
    },

    # ── Tier 1 — 기관 원문 (CLAUDE.md 7-1) ──────────────────────
    {
        # verified 2026-10-07: 성명 원문은 monetary<YYYYMMDD>a.htm 형식.
        # 연도 목록 페이지는 일부만 노출하므로, 구간의 날짜를 하나씩 **요청해
        # 200 + 본문이 확인된 것만** 채택한다 (media_watchlist 1-A 의 고정 경로).
        "id": "fed_monetary", "name": "Federal Reserve 통화정책 성명",
        "axis": "TIER1", "country": "US", "tier": 1, "kind": "datescan",
        "ga1_verified": True,
        "url_template": ("https://www.federalreserve.gov/newsevents/pressreleases/"
                         "monetary{YYYYMMDD}a.htm"),
        "urls": ["https://www.federalreserve.gov/newsevents/pressreleases/"
                 "2026-press.htm"],
    },
    {
        # verified 2026-10-07: 연도 목록 페이지에 monetary2026MMDDa.htm 링크 존재
        "id": "fed_press", "name": "Federal Reserve 보도자료", "axis": "TIER1",
        "country": "US", "tier": 1, "kind": "list", "ga1_verified": True,
        "max_pages": 1, "max_articles": 14,
        "urls": ["https://www.federalreserve.gov/newsevents/pressreleases/"
                 "2026-press.htm"],
        "article_res": [r"/newsevents/pressreleases/[a-z]+\d{8}[a-z]?\.htm"],
    },
    {
        # verified 2026-10-07: 기사 링크가 javascript 안에 있어 raw 패턴으로 추출.
        # 추출한 URL 을 실제로 열어 보도자료 본문(200)임을 확인했다.
        # nPage=N 으로 과거 목록 이동 가능.
        "id": "kostat", "name": "통계청(국가데이터처) 보도자료", "axis": "TIER1",
        "country": "KR", "tier": 1, "kind": "list", "ga1_verified": True,
        "max_pages": 10, "max_articles": 24,
        "urls": ["https://kostat.go.kr/board.es?mid=a10301010000&bid=207"],
        "page_url": ("https://kostat.go.kr/board.es"
                     "?mid=a10301010000&bid=207&nPage={page}"),
        "article_res": [r"board\.es\?[^\"']*act=view[^\"']*"],
        "raw_link_res": [r"/board\.es\?mid=[a-z0-9]+&bid=207&act=view&list_no=\d+"],
    },
    {
        # verified 2026-10-07: 목록 링크는 ./view.do?seq=N (상대경로), page=N 지원.
        "id": "mfds", "name": "식품의약품안전처 보도자료", "axis": "TIER1",
        "country": "KR", "tier": 1, "kind": "list", "ga1_verified": True,
        "max_pages": 10, "max_articles": 24,
        "urls": ["https://www.mfds.go.kr/brd/m_99/list.do"],
        "page_url": "https://www.mfds.go.kr/brd/m_99/list.do?page={page}",
        "article_res": [r"view\.do\?seq=\d+"],
    },
    {
        # verified 2026-10-07: 목록은 열리고 커버리지 구간 날짜도 보이지만, 개별 글이
        # href="javascript:" + data-id 로만 열린다. data-id 로 URL 을 조립해 요청해
        # 보니 200 이지만 "시스템안내" 안내 페이지였다 → **조립하지 않는다.**
        # 목록 접근 사실만 Partial Access 로 남긴다.
        "id": "customs", "name": "관세청 보도자료", "axis": "TIER1", "country": "KR",
        "tier": 1, "kind": "list", "ga1_verified": True,
        "max_pages": 1, "max_articles": 0,
        "urls": ["https://www.customs.go.kr/kcs/na/ntt/selectNttList.do"
                 "?bbsId=1362&mi=2891"],
        "article_res": [r"selectNttInfo\.do\?[^\"']*nttSn=\d+"],
    },
    {
        "id": "bok", "name": "한국은행 보도자료", "axis": "TIER1", "country": "KR",
        "tier": 1, "kind": "list", "max_pages": 6, "max_articles": 16,
        "ga1_verified": True,
        "urls": ["https://www.bok.or.kr/portal/bbs/P0000559/list.do?menuNo=200690",
                 "https://www.bok.or.kr/portal/main/main.do"],
        "page_url": ("https://www.bok.or.kr/portal/bbs/P0000559/list.do"
                     "?menuNo=200690&pageIndex={page}"),
        "article_res": [r"/portal/bbs/P0000559/view\.do\?[^\"']*nttId=\d+"],
    },
    {
        "id": "motie", "name": "산업통상자원부 보도자료", "axis": "TIER1",
        "country": "KR", "tier": 1, "kind": "list", "max_pages": 6,
        "max_articles": 16,
        "urls": ["https://www.motie.go.kr/kor/article/ATCL3f49a5a8c/list",
                 "https://www.motie.go.kr/"],
        "page_url": ("https://www.motie.go.kr/kor/article/ATCL3f49a5a8c/list"
                     "?page={page}"),
        "article_res": [r"/kor/article/[A-Za-z0-9]+/\d+/view"],
    },
    {
        "id": "dart", "name": "DART 전자공시", "axis": "TIER1", "country": "KR",
        "tier": 1, "kind": "list", "max_pages": 1, "max_articles": 12,
        "ga1_verified": True,
        "urls": ["https://dart.fss.or.kr/dsac001/mainAll.do",
                 "https://dart.fss.or.kr/"],
        "article_res": [r"/dsaf001/main\.do\?rcpNo=\d+"],
    },
    {
        "id": "ecb_press", "name": "ECB 보도자료", "axis": "TIER1", "country": "EU",
        "tier": 1, "kind": "feed", "max_pages": 1,
        "urls": ["https://www.ecb.europa.eu/rss/press.html"],
    },
    {
        "id": "boj", "name": "일본은행", "axis": "TIER1", "country": "JP",
        "tier": 1, "kind": "feed", "max_pages": 1,
        "urls": ["https://www.boj.or.jp/rss/whatsnew.xml"],
    },

    # ── NEW PRODUCT WATCH — KOREA ───────────────────────────────
    # 한국 신제품의 1차 경로는 위 뷰티 전문매체 5곳의 신제품 기사다
    # (collector 가 product_candidate 로 표시한다). 리테일러는 보조 경로이며
    # BEAUTY_MARKET_INTELLIGENCE 에서 403 전례가 있어 실패를 전제로 둔다.
    {
        "id": "oliveyoung", "name": "올리브영", "axis": "PRODUCT_KR",
        "country": "KR", "tier": 2, "kind": "list", "max_pages": 1,
        "max_articles": 0, "ga1_verified": True,
        "urls": ["https://www.oliveyoung.co.kr/store/main/main.do"],
        "article_res": [r"/store/goods/getGoodsDetail\.do\?[^\"']*goodsNo=\w+"],
    },

    # ── NEW PRODUCT WATCH — USA ─────────────────────────────────
    # verified 2026-10-07: WordPress 피드는 ?paged=N 으로 과거까지 내려간다
    # (glossy ?paged=5 -> 2026-09-01). W38 은 ?paged=3~4 구간.
    {
        "id": "glossy", "name": "Glossy", "axis": "PRODUCT_US", "country": "US",
        "tier": 3, "kind": "feed", "max_pages": 20,
        "urls": ["https://www.glossy.co/feed/"],
        "page_url": "https://www.glossy.co/feed/?paged={page}",
    },
    {
        "id": "wwd", "name": "WWD", "axis": "PRODUCT_US", "country": "US",
        "tier": 3, "kind": "feed", "max_pages": 20,
        "urls": ["https://wwd.com/feed/"],
        "page_url": "https://wwd.com/feed/?paged={page}",
    },
    {
        "id": "newbeauty", "name": "NewBeauty", "axis": "PRODUCT_US",
        "country": "US", "tier": 3, "kind": "feed", "max_pages": 20,
        "urls": ["https://www.newbeauty.com/feed/"],
        "page_url": "https://www.newbeauty.com/feed/?paged={page}",
    },
    {
        "id": "allure", "name": "Allure", "axis": "PRODUCT_US", "country": "US",
        "tier": 3, "kind": "feed", "max_pages": 1,
        "urls": ["https://www.allure.com/feed/rss"],
    },
    {
        "id": "sephora", "name": "Sephora New", "axis": "PRODUCT_US",
        "country": "US", "tier": 2, "kind": "list", "max_pages": 1,
        "max_articles": 0, "ga1_verified": True,
        "urls": ["https://www.sephora.com/new-beauty-products"],
        "article_res": [r"/product/[a-z0-9\-]+-P\d+"],
    },

    # ── NEW PRODUCT WATCH — JAPAN ───────────────────────────────
    {
        # verified 2026-10-07: 기본 목록은 200(기사 링크 271건)이지만 최신 구간만
        # 노출한다. /beauty/{page} · /beauty/2026/09 는 404 — 페이지네이션 경로를
        # 확인하지 못했다. 과거 주차에서는 Partial Access 가 정상이다.
        "id": "fashionpress", "name": "fashion-press beauty", "axis": "PRODUCT_JP",
        "country": "JP", "tier": 3, "kind": "list", "max_pages": 1,
        "max_articles": 24, "ga1_verified": True,
        "urls": ["https://www.fashion-press.net/news/calendar/beauty/",
                 "https://www.fashion-press.net/news/beauty"],
        "article_res": [r"/news/\d+"],
    },
    {
        # verified 2026-10-07: /item/new 은 404 → 루트만 쓴다 (최신 구간만 노출).
        "id": "cosmenet", "name": "@cosme", "axis": "PRODUCT_JP", "country": "JP",
        "tier": 1, "kind": "list", "max_pages": 1, "max_articles": 16,
        "ga1_verified": True,
        "urls": ["https://www.cosme.net/"],
        "article_res": [r"/products/\d+", r"/product/product_id/\d+"],
    },
    {
        "id": "shiseido", "name": "資生堂 뉴스룸", "axis": "PRODUCT_JP",
        "country": "JP", "tier": 1, "kind": "list", "max_pages": 3,
        "max_articles": 12,
        "urls": ["https://corp.shiseido.com/jp/news/"],
        "article_res": [r"/jp/news/detail\.html\?n=\d+", r"/jp/news/\d+"],
    },
    {
        "id": "kose", "name": "KOSE 뉴스룸", "axis": "PRODUCT_JP", "country": "JP",
        "tier": 1, "kind": "list", "max_pages": 3, "max_articles": 12,
        "urls": ["https://www.kose.co.jp/company/ja/news/"],
        "article_res": [r"/company/ja/news/\d+", r"/news/\d+"],
    },
    {
        "id": "kao", "name": "花王 뉴스룸", "axis": "PRODUCT_JP", "country": "JP",
        "tier": 1, "kind": "list", "max_pages": 3, "max_articles": 12,
        "urls": ["https://www.kao.com/jp/newsroom/news/"],
        "article_res": [r"/jp/newsroom/news/release/\d{4}/\d+",
                        r"/jp/newsroom/news/\d+"],
    },
]

# 기사 링크 추출이 전부 실패했을 때만 쓰는 일반 패턴 (목록 페이지 공통 형태).
GENERIC_ARTICLE_RES = [
    r"article(?:View)?\.html\?[^\"']*(?:idxno|no)=\d+",
    r"news_view\.asp\?[^\"']*\d+",
    r"/news/view/\d+",
    r"/view\.do\?[^\"']*\d+",
]

# 신제품 후보 판정 키워드 (CLAUDE.md 6장 선정 기준의 1차 필터).
PRODUCT_KEYWORDS = [
    "신제품", "출시", "런칭", "론칭", "선보", "새롭게 공개", "신상",
    "launch", "debut", "new product", "drops", "unveil", "introduces",
    "新商品", "新発売", "発売",
]

# §4-1 NOISE FILTER — 원칙적 제외.
NOISE_KEYWORDS = [
    "mou", "업무협약", "협약 체결", "맞손", "사회공헌", "봉사활동", "기부",
    "캠페인 전개", "esg 캠페인", "공모전", "수상", "대상 수상", "선정패",
    "개최", "열린다", "개막", "박람회 참가", "간담회", "위촉", "임명장",
    "채용", "공채", "인사 발령", "승진 인사", "장학금", "후원",
]

# §4-2 예외 — Noise 키워드가 있어도 아래가 함께 있으면 후보로 남긴다.
NOISE_EXCEPTION_KEYWORDS = [
    "인수", "합병", "지분", "매각", "투자", "유상증자", "증설", "수주",
    "실적", "영업이익", "매출", "적자", "흑자", "구조조정", "희망퇴직",
    "규제", "개정", "시행", "고시", "행정처분", "회수", "리콜", "과징금",
    "점유율", "상장", "ipo", "입점", "철수", "단가", "수출", "관세",
]
