# -*- coding: utf-8 -*-
"""GA-3 STEP 1 — 수집.

하는 것: 공개 웹 페이지 읽기 → 기사 후보 추출 → 커버리지 필터 →
         Noise 규칙 필터 → 기계적 중복 클러스터링 → 발췌 생성.
하지 않는 것: AI 호출 0건 / 메일 발송 0건 / 저장소 쓰기 0건
             (산출물은 --out 경로에만 쓴다, 기본값은 러너 임시 디렉터리).

커버리지 도달 방식 (2026-10-07 개정 — Dry Run 진단 결과)
  최신 목록 1페이지만 읽으면 **지난 주차 기사가 0건**이 된다. 실제로 W38(3주 전)
  Dry Run 에서 그 일이 일어나 Brief 가 비고 C2·C3·C5 가 FAIL 했다.
  따라서 목록형 Source 는 **페이지네이션을 날짜 기준으로 탐색**한다:
    1 목록 HTML 의 행에 붙은 날짜(힌트)를 읽는다 — 사이트가 표시한 값만 쓴다.
    2 커버리지 구간이 시작되는 페이지를 **지수 탐색 + 이분 탐색**으로 찾는다.
    3 그 페이지부터 구간을 벗어날 때까지만 전진하며, **구간 안의 기사만** 본문을 읽는다.
  페이지네이션이 없거나 상한 안에서 구간에 닿지 못하면 `Partial Access` 로 남긴다.

URL 을 만들어내지 않는다
- 기사 URL 은 목록 페이지에 실제로 있는 링크만 쓴다.
- 날짜 템플릿 Source(`datescan`)는 **먼저 요청해 200 과 본문을 확인한 URL만** 채택한다.
  (관세청처럼 JS 네비게이션으로만 열리는 목록은 URL 을 조립하지 않고 Partial 로 남긴다 —
   조립한 URL 이 200 을 주더라도 안내 페이지였던 실측 사례가 있다.)

우회하지 않는 것
- robots.txt 를 먼저 읽고, 우리 UA 에 대한 Disallow 가 있으면 요청을 보내지 않는다.
- 봇 차단·CAPTCHA 화면을 만나면 BLOCKED 로 기록만 한다.
- 로그인·유료 구간에 접근하지 않는다. User-Agent 를 브라우저로 위장하지 않는다.
"""
import argparse
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import sources as S  # noqa: E402

UA = (
    "WIB-WeeklyBriefBot/1.0 (+https://github.com/shpark250203/"
    "weekly-intelligence-briefing; GitHub Actions; contact via repo issues)"
)
TIMEOUT = 25
MAX_BYTES = 1_500_000
POLITE_DELAY = 1.2
EXCERPT_LIMIT = 2000

CHALLENGE_RE = re.compile(
    r"captcha|cf-browser-verification|just a moment|attention required|"
    r"access denied|비정상적인 접근|자동입력 방지|접근이 차단",
    re.I,
)
ANCHOR_RE = re.compile(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
META_DATE_RES = [
    re.compile(
        r"<meta[^>]+(?:property|name)=[\"'](?:article:published_time|"
        r"article:modified_time|datePublished|pubdate|date|"
        r"og:regDate|dc\.date)[\"'][^>]+content=[\"']([^\"']+)",
        re.I,
    ),
    re.compile(
        r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+(?:property|name)="
        r"[\"'](?:article:published_time|datePublished|date)[\"']",
        re.I,
    ),
    re.compile(r"<time[^>]+datetime=[\"']([^\"']+)", re.I),
]
BYLINE_DATE_RE = re.compile(
    r"(?:입력|등록|승인|작성|기사입력|발행|公開|更新|Published)[^0-9]{0,12}"
    r"(20\d{2}[-/.년]\s?\d{1,2}[-/.월]\s?\d{1,2}[^0-9]{0,12}(?:\d{1,2}:\d{2})?)"
)

_robots_cache = {}
_last_hit = {}


def log(msg):
    print(msg, flush=True)


# ── HTTP ──────────────────────────────────────────────────────────
def _pace(domain):
    prev = _last_hit.get(domain, 0.0)
    wait = POLITE_DELAY - (time.time() - prev)
    if wait > 0:
        time.sleep(wait)
    _last_hit[domain] = time.time()


def _decode(raw, content_type):
    charset = None
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    if m:
        charset = m.group(1)
    if not charset:
        m = re.search(
            br"<meta[^>]+charset=[\"']?([\w\-]+)", raw[:4000], re.I
        )
        if m:
            charset = m.group(1).decode("ascii", "ignore")
    for enc in [charset, "utf-8", "cp949", "euc-jp", "latin-1"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def robots_allowed_impl(url):
    """robots.txt 를 읽고 우리 UA 로 허용되는지 본다. 읽을 수 없으면 허용으로 본다."""
    parts = urllib.parse.urlsplit(url)
    base = "%s://%s" % (parts.scheme, parts.netloc)
    if base not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            _pace(parts.netloc)
            rp.read()
        except Exception:
            rp = None
        _robots_cache[base] = rp
    rp = _robots_cache[base]
    if rp is None:
        return True
    try:
        return rp.can_fetch(UA, url)
    except Exception:
        return True


def robots_allowed(url):
    """테스트에서 대체 주입할 수 있도록 얇게 감싼다."""
    return robots_allowed_impl(url)


def http_get(url):
    """(status, final_url, text, note) — 예외를 던지지 않는다."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return 0, url, "", "SCHEME_NOT_ALLOWED"
    if not robots_allowed(url):
        return 0, url, "", "ROBOTS_DISALLOW"
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9")
    req.add_header("Accept-Language", "ko,en;q=0.8,ja;q=0.6")
    try:
        _pace(parts.netloc)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES)
            text = _decode(raw, resp.headers.get("Content-Type", ""))
            return resp.getcode(), resp.geturl(), text, ""
    except urllib.error.HTTPError as e:
        try:
            raw = e.read(80_000)
        except Exception:
            raw = b""
        return e.code, url, _decode(raw, ""), "HTTP_%s" % e.code
    except urllib.error.URLError as e:
        return 0, url, "", "URL_ERROR_%s" % C.sanitize(getattr(e, "reason", ""), limit=60)
    except socket.timeout:
        return 0, url, "", "TIMEOUT"
    except Exception as e:
        return 0, url, "", "ERROR_" + type(e).__name__


# ── 추출 ──────────────────────────────────────────────────────────
def _tag(el):
    return el.tag.split("}")[-1].lower()


def parse_feed(text):
    """RSS/Atom → [{title, url, published_raw, summary}]. 실패하면 []."""
    try:
        root = ET.fromstring(text.strip())
    except ET.ParseError:
        return []
    out = []
    for el in root.iter():
        if _tag(el) not in ("item", "entry"):
            continue
        title = url = pub = summary = ""
        for child in el:
            name = _tag(child)
            if name == "title":
                title = C.strip_tags("".join(child.itertext()))
            elif name == "link":
                href = child.get("href")
                url = href or (child.text or "").strip() or url
            elif name in ("pubdate", "published", "updated", "date"):
                pub = (child.text or "").strip() or pub
            elif name in ("description", "summary", "content", "encoded"):
                summary = C.strip_tags("".join(child.itertext())) or summary
        if title and url:
            out.append(
                {"title": title, "url": url.strip(),
                 "published_raw": pub, "summary": summary}
            )
    return out


def extract_links(html, base_url, article_res):
    """목록 HTML → [(절대URL, 제목)]. 중복은 URL 기준으로 한 번만."""
    return [(r["url"], r["title"])
            for r in extract_rows(html, base_url, article_res)]


# 목록 행에 붙은 날짜 힌트 — 사이트가 표시한 값만 읽는다. 추정하지 않는다.
HINT_RES = [
    re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})"),          # 2026-09-16
    re.compile(r"(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일"),         # 2026년 9월 16일
    re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b"),              # 9/16/2026 (US)
    re.compile(r"(?<![\d.])(\d{1,2})[-.](\d{1,2})\s+\d{1,2}:\d{2}"),  # 09-16 10:04
]
# 행 문맥: 이 기사 링크 뒤부터 **다음 기사 링크 앞까지**가 그 행이다.
# (국내 언론 목록은 "링크 → 제목/리드 → 기자 → 날짜 → 다음 링크" 순서가 많다.)
ROW_FORWARD_MAX = 2500
ROW_BACKWARD = 400
HINT_TOLERANCE_DAYS = 3   # 힌트로 본문 요청을 생략할 때의 안전 여유


def _hint_candidates(text, ref_year):
    """문맥에서 (위치, 날짜) 후보를 전부 모은다. 연도는 ±1년만 인정한다."""
    import datetime as _dt
    out = []
    for idx, pat in enumerate(HINT_RES):
        for m in pat.finditer(text):
            try:
                if idx == 2:                      # M/D/YYYY
                    mo, day, year = (int(m.group(1)), int(m.group(2)),
                                     int(m.group(3)))
                elif idx == 3:                    # MM-DD (연도 표기 없음)
                    year, mo, day = ref_year, int(m.group(1)), int(m.group(2))
                else:
                    year, mo, day = (int(m.group(1)), int(m.group(2)),
                                     int(m.group(3)))
                if abs(year - ref_year) > 1:
                    continue
                out.append((m.start(),
                            _dt.datetime(year, mo, day, 12, 0, tzinfo=C.KST)))
            except ValueError:
                continue
    out.sort(key=lambda x: x[0])
    return out


def parse_hint(text, ref_year):
    """문맥에서 **가장 앞**(링크에 가장 가까운) 날짜. 못 찾으면 None."""
    cands = _hint_candidates(text, ref_year)
    return cands[0][1] if cands else None


def parse_hint_last(text, ref_year):
    """문맥에서 **가장 뒤**(링크에 가장 가까운) 날짜. 못 찾으면 None."""
    cands = _hint_candidates(text, ref_year)
    return cands[-1][1] if cands else None


def row_hint(html, start, end, next_start, ref_year):
    """행의 날짜 힌트 — 링크 뒤(다음 링크 앞까지)를 먼저 보고, 없으면 링크 앞을 본다."""
    if not ref_year:
        return None
    stop = min(next_start if next_start else len(html), end + ROW_FORWARD_MAX)
    hint = parse_hint(C.strip_tags(html[end:stop]), ref_year)
    if hint is None:
        back = C.strip_tags(html[max(0, start - ROW_BACKWARD):start])
        hint = parse_hint_last(back, ref_year)
    return hint


def extract_rows(html, base_url, article_res, raw_res=(), ref_year=None):
    """목록 HTML → [{url, title, hint}].

    - `article_res` : <a href> 가 이 패턴에 맞는 링크만 기사로 본다.
    - `raw_res`     : href 가 javascript 인 목록(통계청 등)을 위해, HTML 안의
                      실제 URL 문자열 패턴을 직접 찾는다. **조립이 아니라 추출이다.**
    - `hint`        : 같은 행에 사이트가 표시한 날짜 (없으면 None). 추정하지 않는다.
    """
    html = html or ""
    pats = [re.compile(p, re.I) for p in article_res]
    hits = []

    for m in ANCHOR_RE.finditer(html):
        href, label = m.group(1).strip(), C.strip_tags(m.group(2))
        if not href or href.lower().startswith(("javascript:", "mailto:")):
            continue
        if not any(p.search(href) for p in pats):
            continue
        if len(label) < 6:
            continue
        # href 에 들어있는 HTML 엔티티를 풀어 실제 URL 형태로 만든다
        # (&amp; 를 그대로 두면 기사 URL 이 망가진 형태로 기록된다).
        href = href.replace("&amp;", "&")
        hits.append((m.start(), m.end(),
                     urllib.parse.urljoin(base_url, href), label))

    for pattern in (raw_res or ()):
        for m in re.finditer(pattern, html, re.I):
            # 추출한 문자열 그대로 절대 URL 로 만든다 (파라미터를 바꾸지 않는다).
            url = urllib.parse.urljoin(base_url, m.group(0).replace("&amp;", "&"))
            hits.append((m.start(), m.end(), url, ""))

    hits.sort(key=lambda h: h[0])
    rows, seen = [], set()
    for idx, (start, end, url, label) in enumerate(hits):
        key = url.split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        next_start = hits[idx + 1][0] if idx + 1 < len(hits) else None
        rows.append({"url": key, "title": label,
                     "hint": row_hint(html, start, end, next_start, ref_year)})
    return rows


def extract_published(html):
    for pat in META_DATE_RES:
        m = pat.search(html or "")
        if m:
            when = C.parse_datetime(m.group(1))
            if when:
                return when
    m = BYLINE_DATE_RE.search(C.strip_tags(html)[:6000])
    if m:
        when = C.parse_datetime(m.group(1))
        if when:
            return when
    return None


def make_excerpt(title, html_or_text, limit=EXCERPT_LIMIT):
    """제목 + 리드 + 숫자가 있는 문장. 본문 전체를 넣지 않는다 (설계 2-2)."""
    text = C.strip_tags(html_or_text) if "<" in (html_or_text or "") else (
        html_or_text or ""
    )
    text = re.sub(r"\s+", " ", text).strip()
    lead = text[:900]
    rest = text[900:9000]
    numeric = []
    for sent in re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+", rest):
        if re.search(r"\d", sent) and len(sent) > 15:
            numeric.append(sent.strip())
        if sum(len(x) for x in numeric) > limit - len(lead):
            break
    body = (lead + " " + " ".join(numeric)).strip()
    return C.truncate("%s. %s" % (title, body) if title else body, limit)


# ── 규칙 필터 ─────────────────────────────────────────────────────
def is_noise(title, excerpt):
    """CLAUDE.md 4-1 / 4-2 — 키워드 기반 1차 Noise 판정 (AI 호출 없음)."""
    hay = ((title or "") + " " + (excerpt or "")[:400]).lower()
    hit = next((k for k in S.NOISE_KEYWORDS if k in hay), None)
    if not hit:
        return False, ""
    if any(k in hay for k in S.NOISE_EXCEPTION_KEYWORDS):
        return False, ""
    return True, hit


def is_product_candidate(title, excerpt):
    hay = ((title or "") + " " + (excerpt or "")[:300]).lower()
    return any(k.lower() in hay for k in S.PRODUCT_KEYWORDS)


def cluster(items, threshold=0.58):
    """기계적 중복 클러스터링 — 설계 2-2 의 '계층 A'. AI 호출 0건."""
    clusters = []
    for it in items:
        toks = C.tokens(it["title"])
        norm = C.norm_title(it["title"])
        placed = False
        for ci, cl in enumerate(clusters):
            if norm and norm == cl["norm"]:
                cl["members"].append(it["id"])
                it["cluster_id"] = "CL%03d" % ci
                placed = True
                break
            if C.jaccard(toks, cl["tokens"]) >= threshold:
                cl["members"].append(it["id"])
                it["cluster_id"] = "CL%03d" % ci
                placed = True
                break
        if not placed:
            it["cluster_id"] = "CL%03d" % len(clusters)
            clusters.append({"norm": norm, "tokens": toks, "members": [it["id"]]})
    return clusters


# ── Source 처리 ──────────────────────────────────────────────────
def page_url(src, page):
    """페이지 URL 템플릿. 템플릿이 없으면 1페이지만 본다."""
    tpl = src.get("page_url")
    if not tpl:
        return None
    return tpl.replace("{page}", str(page))


def fetch_article(url, label, note):
    """기사 1건을 읽어 (title, published, excerpt) 를 만든다. 실패하면 None."""
    code, final, html, err = http_get(url)
    if code != 200 or not html:
        note.append("기사 요청 실패 %s" % (err or code))
        return None
    when = extract_published(html)
    # 제목은 기사 페이지의 <title> 을 우선한다. 목록 라벨은 리드 문장이 붙어 오는
    # 경우가 있어 보조로만 쓴다.
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        cand = C.strip_tags(m.group(1))
        # "매체명 :: 제목" / "제목 | 매체명" 형태에서 가장 긴 조각을 제목으로 본다.
        parts = [p.strip() for p in re.split(r"\s*(?:::|\||>)\s*", cand) if p.strip()]
        if parts:
            cand = max(parts, key=len)
        cand = re.sub(r"\s*-\s*[^-]{0,20}$", "", cand).strip()
        if len(cand) >= 10:
            title = cand
    if not title:
        title = (label or "").strip()
    if not title:
        return None
    title = C.truncate(title, 140)
    return {"title": title, "url": final, "published": when,
            "excerpt": make_excerpt(title, html), "dated": when is not None}


def fetch_list_page(src, url, note, attempts, ref_year):
    """목록 1페이지 → rows. 차단·실패는 기록만 하고 [] 를 돌려준다."""
    code, final, text, err = http_get(url)
    blocked = bool(text) and bool(CHALLENGE_RE.search(text[:8000]))
    attempts.append({"url": url, "http": code,
                     "note": "BOT_CHALLENGE" if blocked else (err or "")})
    if blocked:
        note.append("%s -> 봇 차단 화면 (우회하지 않음)" % url)
        return None
    if code != 200 or not text:
        note.append("%s -> %s" % (url, err or code))
        return None
    if url.endswith(".xml"):
        return [{"url": r["url"], "title": r["title"],
                 "hint": C.parse_datetime(r["published_raw"])}
                for r in parse_feed(text)]
    rows = extract_rows(text, final, src.get("article_res", []),
                        src.get("raw_link_res", ()), ref_year)
    if not rows:
        rows = extract_rows(text, final, S.GENERIC_ARTICLE_RES,
                            (), ref_year)
        if rows:
            note.append("%s -> 일반 패턴으로 링크 추출" % url)
    return rows


def span_of(rows):
    """페이지의 (최신, 최오래, 중앙값) 날짜. 힌트가 없으면 (None, None, None).

    사이드바(인기기사 등)의 날짜가 섞여도 흔들리지 않도록 **중앙값**을 함께 낸다.
    페이지 탐색 판단은 중앙값으로 한다.
    """
    dates = sorted(r["hint"] for r in rows if r.get("hint"))
    if not dates:
        return None, None, None
    return dates[-1], dates[0], dates[len(dates) // 2]


def find_window_page(src, start, end, note, attempts, ref_year, max_pages):
    """커버리지 구간이 시작되는 페이지를 지수 탐색 + 이분 탐색으로 찾는다.

    반환 (page, rows). 힌트가 없으면 (1, rows) 로 두고 본문 날짜로 판정한다.
    """
    first = fetch_list_page(src, page_url(src, 1) or src["urls"][0],
                            note, attempts, ref_year)
    if not first:
        return None, None
    _, _, median = span_of(first)
    if median is None:
        note.append("목록에 날짜 표기 없음 — 본문 날짜로 판정한다")
        return 1, first
    if median <= end:
        return 1, first            # 1페이지에 이미 구간이 걸쳐 있다
    if not src.get("page_url"):
        note.append("페이지네이션 미지원 — 최신 목록만 확인 (구간 미도달)")
        return 1, first

    # 지수 탐색 — 구간에 닿는 페이지를 넘어설 때까지 2배씩 건너뛴다.
    lo, hi, hi_rows = 1, None, None
    probe = 2
    while probe <= max_pages:
        rows = fetch_list_page(src, page_url(src, probe), note, attempts, ref_year)
        if not rows:
            break
        _, _, p_median = span_of(rows)
        if p_median is None:
            break
        if p_median <= end:
            hi, hi_rows = probe, rows
            break
        lo = probe
        probe *= 2
    if hi is None:
        note.append("페이지 상한(%d) 안에서 커버리지 구간에 닿지 못했다" % max_pages)
        return None, None

    # 이분 탐색 — 조건을 만족하는 가장 앞 페이지.
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        rows = fetch_list_page(src, page_url(src, mid), note, attempts, ref_year)
        if not rows:
            break
        _, _, p_median = span_of(rows)
        if p_median is None:
            break
        if p_median <= end:
            hi, hi_rows = mid, rows
        else:
            lo = mid
    note.append("커버리지 시작 페이지 = %d (지수+이분 탐색)" % hi)
    return hi, hi_rows


def collect_list(src, start, end):
    """목록형 Source — 커버리지 구간 페이지만 걸어가며 그 구간 기사만 읽는다."""
    items, attempts, note = [], [], []
    ref_year = start.year
    max_pages = int(src.get("max_pages", 1))
    cap = int(src.get("max_articles", 12))

    page, rows = find_window_page(src, start, end, note, attempts,
                                  ref_year, max_pages)
    if rows is None:
        # 페이지 템플릿 경로가 실패하면 기본 URL과 Fallback 2~5 를 순서대로 시도한다.
        for url in src["urls"]:
            rows = fetch_list_page(src, url, note, attempts, ref_year)
            if rows:
                page = None
                note.append("Fallback 경로 사용: %s" % url)
                break
        if not rows:
            note.append(
                "Fallback 1(검색엔진 도메인 한정 질의)은 러너에서 자동 실행하지 않는다"
            )
            return items, attempts, "Access Blocked", note

    if cap <= 0:
        note.append("목록 접근 확인. 상세 페이지는 수집 대상에서 제외 (%d건 링크)"
                    % len(rows))
        return items, attempts, "Partial Access", note

    import datetime as _dt
    slack = _dt.timedelta(days=HINT_TOLERANCE_DAYS)
    # 목록에 날짜가 없는 게시판(통계청 등)은 페이지마다 **첫 기사 1건만** 열어
    # 그 페이지의 날짜를 가늠한다. 깊은 뉴스 목록에는 쓰지 않는다(요청 폭증 방지).
    probe_allowed = bool(src.get("page_url")) and max_pages <= 12
    seen, undated, hint_skipped, pages_read, probed = set(), 0, 0, 0, 0
    skipped_newer, skipped_older = 0, 0
    reached_older = False
    while rows is not None and pages_read < max_pages and len(items) < cap:
        pages_read += 1
        _, _, median = span_of(rows)
        if median is None and probe_allowed and rows:
            probe = fetch_article(rows[0]["url"], rows[0]["title"], note)
            probed += 1
            seen.add(rows[0]["url"])
            if probe and probe["published"] is not None:
                median = probe["published"]
                if C.in_window(probe["published"], start, end):
                    items.append(probe)
                if median > end + slack:
                    # 이 페이지는 전부 구간보다 최신 — 본문을 더 읽지 않고 넘어간다.
                    note.append("페이지 %s 는 구간보다 최신(%s) — 건너뜀"
                                % (page, C.date_only(median)))
                    if page is None:
                        break
                    page += 1
                    if page > max_pages:
                        break
                    rows = fetch_list_page(src, page_url(src, page), note,
                                           attempts, ref_year)
                    continue
        for row in rows:
            if len(items) >= cap:
                break
            if row["url"] in seen:
                continue
            seen.add(row["url"])
            hint = row.get("hint")
            # 힌트는 ±여유를 두고만 쓴다. 행-날짜 대응이 어긋나도 구간 기사를
            # 놓치지 않게 하려는 것이다. 최종 판정은 본문 날짜로 한다.
            if hint is not None and not C.in_window(hint, start - slack, end + slack):
                hint_skipped += 1
                if hint > end:
                    skipped_newer += 1
                else:
                    skipped_older += 1
                continue       # 목록이 표시한 날짜가 구간 밖 — 본문을 읽지 않는다
            got = fetch_article(row["url"], row["title"], note)
            if not got:
                continue
            if got["published"] is None and hint is not None:
                got["published"] = hint      # 목록이 표시한 날짜를 쓴다 (추정 아님)
                got["dated"] = True
                got["date_from_list"] = True
            if got["published"] is None:
                undated += 1
            items.append(got)
        # 구간보다 더 과거로 넘어갔으면 멈춘다.
        if median is not None and median < start - slack:
            reached_older = True
            break
        if page is None or not src.get("page_url"):
            break
        page += 1
        if page > max_pages:
            break
        rows = fetch_list_page(src, page_url(src, page), note, attempts, ref_year)

    in_win = [i for i in items if C.in_window(i["published"], start, end)]
    if hint_skipped:
        note.append("목록 날짜로 구간 밖 %d건 건너뜀 (본문 요청 없음)" % hint_skipped)
    note.append("목록 %d페이지 / 기사 %d건 열람 (페이지 날짜 탐색 %d건)"
                % (pages_read, len(items), probed))
    newest_item = max((i["published"] for i in items if i["published"]),
                      default=None)
    if not items:
        if skipped_newer and not (skipped_older or reached_older):
            # 최신 구간만 보고 끝났다 — "기사가 없다"가 아니라 "구간 미도달"이다.
            status = "Partial Access"
            note.append("커버리지보다 최신 목록만 확인 — 구간 미도달")
        elif reached_older or skipped_older or hint_skipped:
            status = "Checked — no significant news"
            note.append("커버리지 구간을 지나갔으나 해당 기간 기사 0건")
        else:
            status = "Access Blocked"
            note.append("커버리지 구간 기사 0건")
    elif undated == len(items):
        status = "Partial Access"
        note.append("기사 %d건 접근했으나 보도일 확인 불가" % len(items))
    elif in_win:
        status = "Checked — usable articles found"
    elif newest_item is not None and newest_item > end:
        # 읽은 기사가 전부 구간보다 최신이면 "기사가 없다"가 아니라
        # "구간에 닿지 못했다"가 사실이다.
        status = "Partial Access"
        note.append(
            "열람 범위가 전부 커버리지 이후(최신 %s / 구간 종료 %s) — 구간 미도달"
            % (C.date_only(newest_item), end.date())
        )
    else:
        status = "Checked — no significant news"
        note.append("접근 %d건 / 커버리지 내 0건" % len(items))
    return items, attempts, status, note


def collect_feed(src, start, end):
    """피드형 Source. 페이지 파라미터가 있으면 구간까지 거슬러 올라간다."""
    items, attempts, note = [], [], []
    max_pages = int(src.get("max_pages", 1))
    newest_seen = None
    page, fetched_any = 1, False
    while page <= max_pages:
        url = page_url(src, page) or src["urls"][0]
        code, final, text, err = http_get(url)
        attempts.append({"url": url, "http": code, "note": err})
        if code != 200 or not text:
            note.append("%s -> %s" % (url, err or code))
            break
        feed = parse_feed(text)
        if not feed:
            note.append("%s -> FEED_PARSE_EMPTY" % url)
            break
        fetched_any = True
        page_newest, page_oldest = None, None
        for row in feed:
            when = C.parse_datetime(row["published_raw"])
            if when is not None:
                page_newest = when if page_newest is None else max(page_newest, when)
                page_oldest = when if page_oldest is None else min(page_oldest, when)
                newest_seen = when if newest_seen is None else max(newest_seen, when)
            if when is not None and not C.in_window(when, start, end):
                continue
            items.append({
                "title": row["title"], "url": row["url"], "published": when,
                "excerpt": make_excerpt(row["title"], row["summary"]),
                "dated": when is not None,
            })
        if not src.get("page_url"):
            break
        if page_oldest is not None and page_oldest < start:
            break          # 구간보다 과거까지 내려왔다
        page += 1

    if not fetched_any:
        return items, attempts, "Access Blocked", note
    note.append("피드 %d페이지 열람" % min(page, max_pages))
    if items:
        status = "Checked — usable articles found"
    elif newest_seen is not None and newest_seen > end and not src.get("page_url"):
        status = "Partial Access"
        note.append(
            "RSS 가 최신 항목만 제공해 과거 주차에 닿지 못했다 "
            "(최신 %s / 커버리지 종료 %s)"
            % (C.date_only(newest_seen), end.date())
        )
    else:
        status = "Checked — no significant news"
        note.append("커버리지 구간 항목 0건")
    return items, attempts, status, note


def collect_datescan(src, start, end):
    """날짜 템플릿 Source (예: Fed 성명 원문).

    커버리지 구간의 각 날짜로 URL 을 만들어 **요청해 보고, 200 + 본문이 확인된 것만**
    채택한다. 확인되지 않은 URL 은 버린다 — 없는 URL 을 기록하지 않는다.
    """
    import datetime as _dt
    items, attempts, note = [], [], []
    tpl = src["url_template"]
    day = start.date()
    hits = 0
    while day <= end.date():
        url = tpl.replace("{YYYYMMDD}", day.strftime("%Y%m%d"))
        code, final, html, err = http_get(url)
        attempts.append({"url": url, "http": code, "note": err or ""})
        if code == 200 and html and len(html) > 2000:
            got = fetch_article_from_html(html, final, day)
            if got:
                items.append(got)
                hits += 1
        day += _dt.timedelta(days=1)
    note.append("커버리지 %d일 중 %d일에서 원문 확인 (200 + 본문 확인된 URL만 채택)"
                % ((end.date() - start.date()).days + 1, hits))
    if items:
        return items, attempts, "Checked — usable articles found", note
    return items, attempts, "Checked — no significant news", note


def fetch_article_from_html(html, url, day):
    import datetime as _dt
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = re.sub(r"\s*[|<>-]\s*[^|]{0,40}$", "",
                       C.strip_tags(m.group(1))).strip()
    # 기관 페이지는 <title> 이 기관명뿐인 경우가 많다 — 본문 제목(h1~h3)을 쓴다.
    h = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.I | re.S)
    if h:
        head = C.strip_tags(h.group(1)).strip()
        if len(head) > len(title):
            title = head
    if not title:
        return None
    title = C.truncate(title, 140)
    when = extract_published(html) or _dt.datetime(
        day.year, day.month, day.day, 12, 0, tzinfo=C.KST)
    return {"title": title, "url": url, "published": when,
            "excerpt": make_excerpt(title, html), "dated": True}


# ── main ─────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekly-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="쉼표로 구분한 source id (디버그용)")
    args = ap.parse_args()

    start, end = C.coverage_window(args.weekly_id)
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    log("coverage: %s ~ %s (KST)" % (start.isoformat(), end.isoformat()))

    source_rows, items, next_id = [], [], 1
    for src in S.SOURCES:
        if only and src["id"] not in only:
            continue
        log("── %s (%s/%s)" % (src["name"], src["axis"], src["kind"]))
        if src["kind"] == "feed":
            raw, attempts, status, note = collect_feed(src, start, end)
        elif src["kind"] == "datescan":
            raw, attempts, status, note = collect_datescan(src, start, end)
        else:
            raw, attempts, status, note = collect_list(src, start, end)

        kept = 0
        for row in raw:
            if not C.in_window(row["published"], start, end):
                continue
            noise, hit = is_noise(row["title"], row["excerpt"])
            items.append({
                "id": "A%04d" % next_id,
                "source_id": src["id"],
                "source_name": src["name"],
                "axis": src["axis"],
                "tier": src["tier"],
                "country": src.get("country", "KR"),
                "title": row["title"],
                "url": row["url"],
                "published": C.date_only(row["published"]),
                "excerpt": row["excerpt"],
                "noise": noise,
                "noise_hit": hit,
                "product_candidate": is_product_candidate(
                    row["title"], row["excerpt"]
                ),
            })
            next_id += 1
            kept += 1

        source_rows.append({
            "id": src["id"], "name": src["name"], "axis": src["axis"],
            "tier": src["tier"], "status": status,
            "ga1_verified": bool(src.get("ga1_verified")),
            "fetched": len(raw), "in_window": kept,
            "attempts": attempts, "notes": note,
        })
        log("   status=%s fetched=%d in_window=%d" % (status, len(raw), kept))

    # 중복 클러스터링 — 판단 단위와 같은 묶음으로 센다.
    # AXIS 1 과 Tier 1 원문은 같은 선별 호출에 함께 들어가므로 한 묶음으로 본다
    # (기관 원문 + 언론 해설이 같은 사건이면 1건으로 묶여야 한다).
    def group_of(item):
        return "GENERAL" if item["axis"] in ("AXIS1", "TIER1") else item["axis"]

    for group in sorted({group_of(i) for i in items}):
        members = [i for i in items if group_of(i) == group]
        cluster(members)
        for i in members:
            i["cluster_group"] = group

    noise_count = sum(1 for i in items if i["noise"])
    clusters = {i["cluster_group"] + ":" + i["cluster_id"] for i in items}
    payload = {
        "weekly_id": args.weekly_id,
        "coverage": {"start_kst": start.isoformat(), "end_kst": end.isoformat()},
        "generated_at_utc": C.stamp_utc(),
        "collector_version": "ga3-1.0",
        "sources": source_rows,
        "items": items,
        "stats": {
            "collected_total": len(items),
            "noise_excluded": noise_count,
            "after_dedup": len(clusters),
            "product_candidates": sum(1 for i in items if i["product_candidate"]),
            "tier1_sources_with_items": len({
                i["source_id"] for i in items if i["tier"] == 1
            }),
        },
    }
    C.write_json(args.out, payload)
    log("collected: %d items / %d sources -> %s"
        % (len(items), len(source_rows), args.out))

    C.append_summary(
        "### STEP 1 — 수집\n\n"
        "| 항목 | 값 |\n|---|---|\n"
        "| 커버리지 | %s ~ %s KST |\n"
        "| 수집 기사 | %d |\n| Noise 제외(규칙) | %d |\n"
        "| 중복 제거 후 | %d |\n| 신제품 후보 | %d |\n"
        "| Tier 1 항목 확보 Source | %d |\n| AI 호출 | **0** |\n"
        % (start.date(), end.date(), len(items), noise_count, len(clusters),
           payload["stats"]["product_candidates"],
           payload["stats"]["tier1_sources_with_items"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
