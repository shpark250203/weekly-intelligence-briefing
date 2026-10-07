# -*- coding: utf-8 -*-
"""GA-3 Source 레지스트리.

원칙
- GA-1 Connectivity Probe(2026-09-29 PASS)에서 접근이 확인된 경로를 우선 쓴다.
  `ga1_verified: True` 가 그 표시다. 나머지는 이번 실행에서 처음 시도하는 경로이며,
  실패하면 **추정하지 않고 Coverage Log 에 상태 그대로 기록한다.**
- `kind`
    feed : RSS/Atom. 제목·링크·보도일이 피드에 들어있어 기사 본문 요청이 필요 없다.
    list : HTML 목록. 기사 링크를 뽑고, 보도일은 기사 페이지에서 확인한다.
- `urls` 는 **Fallback 순서**다. 앞의 경로가 막히면 다음 경로를 시도하고 시도 이력을 남긴다.
  CLAUDE.md 5장 Fallback 1(검색엔진 도메인 한정 질의)은 자동 실행하지 않는다 —
  러너에서 검색엔진을 긁지 않기 위함이며, 그 사실을 Coverage Log 에 명시한다.
- `tier` 는 source_policy.md 의 Tier 다. Tier 1 은 기관 원문이다.
"""

# 뷰티 전문매체 5곳 — CLAUDE.md 5장. 각각 독립 확인한다.
BEAUTY_MEDIA_IDS = ["jangup", "cmn", "beautynury", "cosmorning", "cosinkorea"]

SOURCES = [
    # ── AXIS 2 — 뷰티 전문매체 5곳 (필수) ────────────────────────
    {
        "id": "jangup", "name": "장업신문", "axis": "BEAUTY", "country": "KR",
        "tier": 3, "kind": "list", "ga1_verified": True, "max_articles": 24,
        "urls": [
            "https://www.jangup.com/news/articleList.html?view_type=sm",
            "https://www.jangup.com/news/articleList.html?page=2&view_type=sm",
            "https://www.jangup.com/rss/allArticle.xml",
        ],
        "article_res": [r"/news/articleView\.html\?idxno=\d+"],
    },
    {
        "id": "cmn", "name": "CMN", "axis": "BEAUTY", "country": "KR",
        "tier": 3, "kind": "list", "ga1_verified": True, "max_articles": 24,
        "urls": [
            "https://www.cmn.co.kr/sub/news/news.asp",
            "https://www.cmn.co.kr/mainnews/",
        ],
        "article_res": [
            r"news_view\.asp\?[^\"']*",
            r"/sub/news/[^\"']*idx=\d+",
            r"/mainnews/[^\"']*\d+",
        ],
    },
    {
        "id": "beautynury", "name": "뷰티누리", "axis": "BEAUTY", "country": "KR",
        "tier": 3, "kind": "list", "ga1_verified": True, "max_articles": 24,
        "urls": [
            "https://www.beautynury.com/news/list/cat/10",
            "https://www.beautynury.com/m/news/list/cat/10",
            "https://www.beautynury.com/news/list/cat/10/page/2",
        ],
        "article_res": [r"/news/view/\d+", r"/m/news/view/\d+"],
    },
    {
        "id": "cosmorning", "name": "코스모닝", "axis": "BEAUTY", "country": "KR",
        "tier": 3, "kind": "list", "ga1_verified": True, "max_articles": 24,
        "urls": [
            "https://cosmorning.com/news/section_list_all.html?sec_no=1",
            "https://cosmorning.com/",
        ],
        "article_res": [r"/news/article\.html\?no=\d+"],
    },
    {
        "id": "cosinkorea", "name": "코스인코리아", "axis": "BEAUTY", "country": "KR",
        "tier": 3, "kind": "list", "ga1_verified": True, "max_articles": 24,
        "urls": [
            "https://www.cosinkorea.com/news/articleList.html?view_type=sm",
            "https://www.cosinkorea.com/news/articleList.html?page=2&view_type=sm",
        ],
        "article_res": [
            r"/news/article\.html\?no=\d+",
            r"/news/articleView\.html\?idxno=\d+",
        ],
    },

    # ── AXIS 1 — 국내 (Tier 2 피드) ──────────────────────────────
    {"id": "yna_econ", "name": "연합뉴스 경제", "axis": "AXIS1", "country": "KR",
     "tier": 2, "kind": "feed", "urls": ["https://www.yna.co.kr/rss/economy.xml"]},
    {"id": "yna_ind", "name": "연합뉴스 산업", "axis": "AXIS1", "country": "KR",
     "tier": 2, "kind": "feed", "urls": ["https://www.yna.co.kr/rss/industry.xml"]},
    {"id": "hk_econ", "name": "한국경제 경제", "axis": "AXIS1", "country": "KR",
     "tier": 2, "kind": "feed", "urls": ["https://www.hankyung.com/feed/economy"]},
    {"id": "hk_ind", "name": "한국경제 산업", "axis": "AXIS1", "country": "KR",
     "tier": 2, "kind": "feed", "urls": ["https://www.hankyung.com/feed/industry"]},
    {"id": "mk_econ", "name": "매일경제 경제", "axis": "AXIS1", "country": "KR",
     "tier": 2, "kind": "feed", "urls": ["https://www.mk.co.kr/rss/30100041/"]},
    {"id": "mk_corp", "name": "매일경제 기업", "axis": "AXIS1", "country": "KR",
     "tier": 2, "kind": "feed", "urls": ["https://www.mk.co.kr/rss/50100032/"]},
    {"id": "etnews", "name": "전자신문", "axis": "AXIS1", "country": "KR",
     "tier": 2, "kind": "feed", "urls": ["https://rss.etnews.com/Section901.xml"]},
    {"id": "theguru", "name": "더구루", "axis": "AXIS1", "country": "KR",
     "tier": 2, "kind": "feed", "urls": ["https://www.theguru.co.kr/rss/allArticle.xml"]},

    # ── AXIS 1 — 해외 (Tier 2 피드) ──────────────────────────────
    {"id": "cnbc_econ", "name": "CNBC Economy", "axis": "AXIS1", "country": "US",
     "tier": 2, "kind": "feed",
     "urls": ["https://search.cnbc.com/rs/search/combinedcms/view.xml"
              "?partnerId=wrss25&id=20910258"]},
    {"id": "cnbc_world", "name": "CNBC World", "axis": "AXIS1", "country": "US",
     "tier": 2, "kind": "feed",
     "urls": ["https://search.cnbc.com/rs/search/combinedcms/view.xml"
              "?partnerId=wrss25&id=100727362"]},

    # ── Tier 1 — 기관 원문 (CLAUDE.md 7-1) ──────────────────────
    {"id": "fed_press", "name": "Federal Reserve 보도자료", "axis": "TIER1",
     "country": "US", "tier": 1, "kind": "feed", "ga1_verified": True,
     "urls": ["https://www.federalreserve.gov/feeds/press_all.xml",
              "https://www.federalreserve.gov/feeds/press_monetary.xml"]},
    {"id": "ecb_press", "name": "ECB 보도자료", "axis": "TIER1", "country": "EU",
     "tier": 1, "kind": "feed", "urls": ["https://www.ecb.europa.eu/rss/press.html"]},
    {"id": "boj", "name": "일본은행", "axis": "TIER1", "country": "JP",
     "tier": 1, "kind": "feed", "urls": ["https://www.boj.or.jp/rss/whatsnew.xml"]},
    {"id": "bok", "name": "한국은행 보도자료", "axis": "TIER1", "country": "KR",
     "tier": 1, "kind": "list", "max_articles": 12, "ga1_verified": True,
     "urls": ["https://www.bok.or.kr/portal/bbs/P0000559/list.do?menuNo=200690",
              "https://www.bok.or.kr/portal/main/main.do"],
     "article_res": [r"/portal/bbs/P0000559/view\.do\?[^\"']*nttId=\d+"]},
    {"id": "kostat", "name": "통계청 보도자료", "axis": "TIER1", "country": "KR",
     "tier": 1, "kind": "list", "max_articles": 12, "ga1_verified": True,
     "urls": ["https://kostat.go.kr/board.es?mid=a10301010000&bid=207"],
     "article_res": [r"board\.es\?[^\"']*act=view[^\"']*"]},
    {"id": "customs", "name": "관세청 보도자료", "axis": "TIER1", "country": "KR",
     "tier": 1, "kind": "list", "max_articles": 12, "ga1_verified": True,
     "urls": ["https://www.customs.go.kr/kcs/na/ntt/selectNttList.do"
              "?bbsId=1362&mi=2891"],
     "article_res": [r"selectNttInfo\.do\?[^\"']*nttSn=\d+"]},
    {"id": "mfds", "name": "식품의약품안전처 보도자료", "axis": "TIER1",
     "country": "KR", "tier": 1, "kind": "list", "max_articles": 12,
     "ga1_verified": True,
     "urls": ["https://www.mfds.go.kr/brd/m_99/list.do"],
     "article_res": [r"/brd/m_99/view\.do\?[^\"']*seq=\d+"]},
    {"id": "motie", "name": "산업통상자원부 보도자료", "axis": "TIER1",
     "country": "KR", "tier": 1, "kind": "list", "max_articles": 12,
     "urls": ["https://www.motie.go.kr/kor/article/ATCL3f49a5a8c/list",
              "https://www.motie.go.kr/"],
     "article_res": [r"/kor/article/[A-Za-z0-9]+/\d+/view"]},
    {"id": "dart", "name": "DART 전자공시", "axis": "TIER1", "country": "KR",
     "tier": 1, "kind": "list", "max_articles": 12, "ga1_verified": True,
     "urls": ["https://dart.fss.or.kr/dsac001/mainAll.do",
              "https://dart.fss.or.kr/"],
     "article_res": [r"/dsaf001/main\.do\?rcpNo=\d+"]},

    # ── NEW PRODUCT WATCH — KOREA ───────────────────────────────
    # 한국 신제품의 1차 경로는 위 뷰티 전문매체 5곳의 신제품 기사다
    # (collector 가 product_candidate 로 표시한다). 리테일러는 보조 경로이며
    # BEAUTY_MARKET_INTELLIGENCE 에서 403 전례가 있어 실패를 전제로 둔다.
    {"id": "oliveyoung", "name": "올리브영", "axis": "PRODUCT_KR", "country": "KR",
     "tier": 2, "kind": "list", "max_articles": 0, "ga1_verified": True,
     "urls": ["https://www.oliveyoung.co.kr/store/main/main.do"],
     "article_res": [r"/store/goods/getGoodsDetail\.do\?[^\"']*goodsNo=\w+"]},

    # ── NEW PRODUCT WATCH — USA ─────────────────────────────────
    {"id": "glossy", "name": "Glossy", "axis": "PRODUCT_US", "country": "US",
     "tier": 3, "kind": "feed", "urls": ["https://www.glossy.co/feed/"]},
    {"id": "wwd", "name": "WWD", "axis": "PRODUCT_US", "country": "US",
     "tier": 3, "kind": "feed", "urls": ["https://wwd.com/feed/"]},
    {"id": "allure", "name": "Allure", "axis": "PRODUCT_US", "country": "US",
     "tier": 3, "kind": "feed", "urls": ["https://www.allure.com/feed/rss"]},
    {"id": "newbeauty", "name": "NewBeauty", "axis": "PRODUCT_US", "country": "US",
     "tier": 3, "kind": "feed", "urls": ["https://www.newbeauty.com/feed/"]},
    {"id": "sephora", "name": "Sephora New", "axis": "PRODUCT_US", "country": "US",
     "tier": 2, "kind": "list", "max_articles": 0, "ga1_verified": True,
     "urls": ["https://www.sephora.com/new-beauty-products"],
     "article_res": [r"/product/[a-z0-9\-]+-P\d+"]},

    # ── NEW PRODUCT WATCH — JAPAN ───────────────────────────────
    {"id": "fashionpress", "name": "fashion-press beauty", "axis": "PRODUCT_JP",
     "country": "JP", "tier": 3, "kind": "list", "max_articles": 20,
     "ga1_verified": True,
     "urls": ["https://www.fashion-press.net/news/calendar/beauty/",
              "https://www.fashion-press.net/news/beauty"],
     "article_res": [r"/news/\d+"]},
    {"id": "cosmenet", "name": "@cosme", "axis": "PRODUCT_JP", "country": "JP",
     "tier": 1, "kind": "list", "max_articles": 16, "ga1_verified": True,
     "urls": ["https://www.cosme.net/item/new", "https://www.cosme.net/"],
     "article_res": [r"/products/\d+", r"/product/product_id/\d+"]},
    {"id": "shiseido", "name": "資生堂 뉴스룸", "axis": "PRODUCT_JP", "country": "JP",
     "tier": 1, "kind": "list", "max_articles": 12,
     "urls": ["https://corp.shiseido.com/jp/news/"],
     "article_res": [r"/jp/news/detail\.html\?n=\d+", r"/jp/news/\d+"]},
    {"id": "kose", "name": "KOSE 뉴스룸", "axis": "PRODUCT_JP", "country": "JP",
     "tier": 1, "kind": "list", "max_articles": 12,
     "urls": ["https://www.kose.co.jp/company/ja/news/"],
     "article_res": [r"/company/ja/news/\d+", r"/news/\d+"]},
    {"id": "kao", "name": "花王 뉴스룸", "axis": "PRODUCT_JP", "country": "JP",
     "tier": 1, "kind": "list", "max_articles": 12,
     "urls": ["https://www.kao.com/jp/newsroom/news/"],
     "article_res": [r"/jp/newsroom/news/release/\d{4}/\d+", r"/jp/newsroom/news/\d+"]},
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
