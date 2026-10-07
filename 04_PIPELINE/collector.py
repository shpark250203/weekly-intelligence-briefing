# -*- coding: utf-8 -*-
"""GA-3 STEP 1 — 수집.

하는 것: 공개 웹 페이지 읽기 → 기사 후보 추출 → 커버리지 필터 →
         Noise 규칙 필터 → 기계적 중복 클러스터링 → 발췌 생성.
하지 않는 것: AI 호출 0건 / 메일 발송 0건 / 저장소 쓰기 0건
             (산출물은 --out 경로에만 쓴다, 기본값은 러너 임시 디렉터리).

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


def robots_allowed(url):
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
        return rp.can_fetch(UA, url) or rp.can_fetch("*", url)
    except Exception:
        return True


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
    pats = [re.compile(p, re.I) for p in article_res]
    found, seen = [], set()
    for m in ANCHOR_RE.finditer(html or ""):
        href, label = m.group(1).strip(), C.strip_tags(m.group(2))
        if not href or href.lower().startswith(("javascript:", "mailto:")):
            continue
        if not any(p.search(href) for p in pats):
            continue
        absolute = urllib.parse.urljoin(base_url, href)
        key = absolute.split("#")[0]
        if key in seen:
            continue
        if len(label) < 6:
            continue
        seen.add(key)
        found.append((key, label))
    return found


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
def collect_feed(src, start, end):
    items, attempts, status, note = [], [], "Not Checked", []
    for url in src["urls"]:
        code, final, text, err = http_get(url)
        attempts.append({"url": url, "http": code, "note": err})
        if code != 200 or not text:
            note.append("%s -> %s" % (url, err or code))
            continue
        feed = parse_feed(text)
        if not feed:
            note.append("%s -> FEED_PARSE_EMPTY" % url)
            continue
        for row in feed:
            when = C.parse_datetime(row["published_raw"])
            items.append({
                "title": row["title"], "url": row["url"], "published": when,
                "excerpt": make_excerpt(row["title"], row["summary"]),
                "dated": when is not None,
            })
        break
    if items:
        in_win = [i for i in items if C.in_window(i["published"], start, end)]
        status = ("Checked — usable articles found" if in_win
                  else "Checked — no significant news")
        if not any(i["dated"] for i in items):
            status = "Partial Access"
            note.append("보도일 파싱 실패 — 커버리지 판정 불가")
    else:
        status = "Access Blocked"
    return items, attempts, status, note


def collect_list(src, start, end):
    items, attempts, note = [], [], []
    links, used_url = [], None
    for url in src["urls"]:
        code, final, text, err = http_get(url)
        blocked = bool(text) and bool(CHALLENGE_RE.search(text[:8000]))
        attempts.append({
            "url": url, "http": code,
            "note": "BOT_CHALLENGE" if blocked else (err or ""),
        })
        if blocked:
            note.append("%s -> 봇 차단 화면 (우회하지 않음)" % url)
            continue
        if code != 200 or not text:
            note.append("%s -> %s" % (url, err or code))
            continue
        if url.endswith(".xml"):
            feed = parse_feed(text)
            links = [(r["url"], r["title"]) for r in feed]
        else:
            links = extract_links(text, final, src.get("article_res", []))
            if not links:
                links = extract_links(text, final, S.GENERIC_ARTICLE_RES)
                if links:
                    note.append("%s -> 일반 패턴으로 링크 추출" % url)
        if links:
            used_url = url
            break
        note.append("%s -> 기사 링크 0건" % url)

    if not links:
        status = "Access Blocked" if attempts else "Not Checked"
        note.append(
            "Fallback 1(검색엔진 도메인 한정 질의)은 러너에서 자동 실행하지 않는다"
        )
        return items, attempts, status, note

    cap = int(src.get("max_articles", 12))
    if cap <= 0:
        # 목록은 열렸으나 본문 수집 대상이 아닌 Source (리테일러 상품 페이지 등).
        note.append("목록 접근 확인. 상품 상세는 수집 대상에서 제외 (%d건 링크)" % len(links))
        return items, attempts, "Partial Access", note

    undated = 0
    for url, label in links[:cap]:
        code, final, html, err = http_get(url)
        if code != 200 or not html:
            note.append("기사 요청 실패 %s" % (err or code))
            continue
        when = extract_published(html)
        if when is None:
            undated += 1
        title = label
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m:
            cand = C.strip_tags(m.group(1))
            cand = re.sub(r"\s*[|<>-]\s*[^|]{0,30}$", "", cand).strip()
            if len(cand) >= len(title):
                title = cand
        items.append({
            "title": title, "url": final, "published": when,
            "excerpt": make_excerpt(title, html), "dated": when is not None,
        })

    in_win = [i for i in items if C.in_window(i["published"], start, end)]
    if not items:
        status = "Access Blocked"
    elif undated == len(items):
        status = "Partial Access"
        note.append("기사 %d건 접근했으나 보도일 확인 불가 — 커버리지 판정 불가" % len(items))
    elif in_win:
        status = "Checked — usable articles found"
    else:
        status = "Checked — no significant news"
        note.append("접근 %d건 / 커버리지 내 0건" % len(items))
    if used_url and used_url != src["urls"][0]:
        note.append("Fallback 경로 사용: %s" % used_url)
    return items, attempts, status, note


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
