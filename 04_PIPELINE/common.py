# -*- coding: utf-8 -*-
"""GA-3 공통 유틸 — 시간·주차·마스킹·문자열·파일 IO 만 다룬다.

이 모듈은 네트워크·AI·SMTP 를 전혀 다루지 않는다 (import 하지 않는다).
그래서 selftest 가 외부 호출 없이 이 모듈의 규칙을 그대로 검증할 수 있다.
"""
import datetime as dt
import json
import os
import re
import unicodedata

KST = dt.timezone(dt.timedelta(hours=9))

WEEKLY_ID_RE = re.compile(r"^(\d{4})-W(\d{2})$")
EMAIL_RE = re.compile(r"^[^@\s,;]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
ANY_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


# -- 주차 - 커버리지 ------------------------------------------------
def parse_weekly_id(weekly_id):
    """'2026-W38' -> (2026, 38). 형식이 다르면 예외. 보정하지 않는다."""
    m = WEEKLY_ID_RE.match((weekly_id or "").strip())
    if not m:
        raise ValueError("WEEKLY_ID_FORMAT_INVALID")
    year, week = int(m.group(1)), int(m.group(2))
    if not 1 <= week <= 53:
        raise ValueError("WEEKLY_ID_WEEK_RANGE_INVALID")
    return year, week


def coverage_window(weekly_id):
    """CLAUDE.md 3장 — 해당 ISO 주차의 월 00:00 ~ 일 23:59:59 (KST)."""
    year, week = parse_weekly_id(weekly_id)
    mon = dt.date.fromisocalendar(year, week, 1)
    sun = dt.date.fromisocalendar(year, week, 7)
    start = dt.datetime(mon.year, mon.month, mon.day, 0, 0, 0, tzinfo=KST)
    end = dt.datetime(sun.year, sun.month, sun.day, 23, 59, 59, tzinfo=KST)
    return start, end


def in_window(when, start, end):
    """when 이 커버리지 안인가. tz 없는 값은 KST 로 간주한다."""
    if when is None:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=KST)
    return start <= when <= end


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def stamp_utc():
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp_kst():
    return now_utc().astimezone(KST).strftime("%Y-%m-%d %H:%M")


# -- 날짜 파싱 ------------------------------------------------------
_DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})"),
    re.compile(r"(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일"),
]
_RFC822_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_datetime(text):
    """기사 날짜 문자열에서 datetime 을 만든다. 실패하면 None (추정하지 않는다)."""
    if not text:
        return None
    s = " ".join(str(text).split())

    # ISO 8601 (atom updated / meta article:published_time)
    m = re.search(
        r"(20\d{2})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?"
        r"\s*(Z|[+\-]\d{2}:?\d{2})?",
        s,
    )
    if m:
        y, mo, d, hh, mm = (int(m.group(i)) for i in range(1, 6))
        ss = int(m.group(6) or 0)
        tzs = m.group(7)
        tz = KST
        if tzs:
            if tzs == "Z":
                tz = dt.timezone.utc
            else:
                flat = tzs.replace(":", "")
                sign = 1 if flat[0] == "+" else -1
                tz = dt.timezone(
                    sign * dt.timedelta(hours=int(flat[1:3]), minutes=int(flat[3:5]))
                )
        try:
            return dt.datetime(y, mo, d, hh, mm, ss, tzinfo=tz)
        except ValueError:
            return None

    # RFC 822 (RSS pubDate)
    m = re.search(
        r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(20\d{2})"
        r"(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?\s*([+\-]\d{4}|GMT|UTC|KST)?",
        s,
    )
    if m and m.group(2).lower() in _RFC822_MONTHS:
        d = int(m.group(1))
        mo = _RFC822_MONTHS[m.group(2).lower()]
        y = int(m.group(3))
        hh = int(m.group(4) or 0)
        mm = int(m.group(5) or 0)
        ss = int(m.group(6) or 0)
        zone = m.group(7) or ""
        if zone in ("GMT", "UTC"):
            tz = dt.timezone.utc
        elif zone == "KST":
            tz = KST
        elif zone:
            sign = 1 if zone[0] == "+" else -1
            tz = dt.timezone(
                sign * dt.timedelta(hours=int(zone[1:3]), minutes=int(zone[3:5]))
            )
        else:
            tz = dt.timezone.utc
        try:
            return dt.datetime(y, mo, d, hh, mm, ss, tzinfo=tz)
        except ValueError:
            return None

    for pat in _DATE_PATTERNS:
        m = pat.search(s)
        if m:
            y, mo, d = (int(x) for x in m.groups()[:3])
            hm = re.search(r"(\d{1,2}):(\d{2})", s[m.end():m.end() + 12])
            hh = int(hm.group(1)) if hm else 12
            mm = int(hm.group(2)) if hm else 0
            try:
                return dt.datetime(y, mo, d, hh, mm, tzinfo=KST)
            except ValueError:
                return None
    return None


def date_only(when):
    return when.astimezone(KST).strftime("%Y-%m-%d") if when else "-"


# -- 마스킹 - 민감정보 ----------------------------------------------
def mask_email(value):
    """s***@gmail.com 형태로만 남긴다. 전체 주소를 출력하지 않는다."""
    if not value or "@" not in value:
        return "(형식 확인 불가)"
    local, _, domain = value.partition("@")
    head = local[0] if local else "?"
    return head + "***@" + domain


def sanitize(raw, secrets=(), limit=300):
    """로그 출력용 — 자격증명·메일주소를 지우고 길이를 제한한다."""
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        text = bytes(raw).decode("utf-8", "replace")
    else:
        text = str(raw)
    text = " ".join(text.split())
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, "[REDACTED]")
    text = ANY_EMAIL_RE.sub("[REDACTED-EMAIL]", text)
    if len(text) > limit:
        text = text[:limit] + " ...(truncated)"
    return text


# -- 문자열 --------------------------------------------------------
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ENTITIES = (
    ("&nbsp;", " "),
    ("&amp;", "&"),
    ("&lt;", "<"),
    ("&gt;", ">"),
    ("&quot;", '"'),
    ("&#39;", "'"),
    ("&apos;", "'"),
)


def strip_tags(html):
    if not html:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = _TAG_RE.sub(" ", text)
    for src, dst in _ENTITIES:
        text = text.replace(src, dst)
    text = re.sub(r"&[a-zA-Z#0-9]{2,8};", " ", text)
    return _WS_RE.sub(" ", text).strip()


def esc(text):
    """HTML 이스케이프 — 메일 본문 조립용."""
    out = "" if text is None else str(text)
    out = out.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return out.replace('"', "&quot;")


def norm_title(title):
    """중복 판정용 정규화 — 괄호 머리말·기호·공백 제거."""
    t = unicodedata.normalize("NFKC", title or "")
    t = re.sub(r"^\s*[\[\(【][^\]\)】]{0,20}[\]\)】]\s*", "", t)
    t = re.sub(r"[^0-9A-Za-z가-힣ㄱ-ㅎ]+", "", t)
    return t.lower()


def tokens(title):
    """제목 유사도용 토큰 집합. 한국어 조사 때문에 3자 n-gram 을 함께 쓴다."""
    t = unicodedata.normalize("NFKC", title or "").lower()
    out = set()
    for w in re.split(r"[^0-9a-z가-힣]+", t):
        if len(w) >= 2:
            out.add(w)
        if len(w) >= 4:
            for i in range(len(w) - 2):
                out.add(w[i:i + 3])
    return out


def jaccard(a, b):
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


NUM_RE = re.compile(r"\d[\d,.]*")


def numbers_in(text):
    """숫자 검증용 — 쉼표를 제거한 숫자 토큰 집합."""
    out = set()
    for m in NUM_RE.finditer(text or ""):
        v = m.group(0).replace(",", "").rstrip(".")
        if v:
            out.add(v)
    return out


def truncate(text, limit):
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "…"


# -- 파일 IO -------------------------------------------------------
def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def append_summary(markdown):
    """GITHUB_STEP_SUMMARY 에 덧붙인다. 없으면 조용히 넘어간다."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(markdown.rstrip() + "\n\n")
