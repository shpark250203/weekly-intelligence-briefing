# -*- coding: utf-8 -*-
"""GA-3 STEP 2 — Gemini 판단 (7 호출 설계, ga2_auth_design.md 2-2).

호출
  1 AXIS 1 선별+병합      2 AXIS 2 선별+병합
  3 MUST KNOW + AXIS 1 작성  4 AXIS 2 심층 작성
  5 KOREA 신제품+Signal   6 USA   7 JAPAN

코드가 판정하는 것 (모델에게 맡기지 않는다)
  - 2-of-5 Rule        : criteria_met 길이 2 이상인지
  - 숫자 검증          : 출력 숫자가 수집 발췌에 실재하는지 (없으면 삭제 + FLAG)
  - Trend Signal 조건  : A(브랜드 3건+) / B(제품 2건+ & Tier 1·2 근거) 미달 → Watch Item 강등
  - Confidence 상한    : 계절성 위험이 있고 전년 동기 비교가 없으면 High 금지
  - Price enum         : Verified / Not disclosed / Not verified 외 값 금지
  - Article URL        : 모델이 만든 URL 을 쓰지 않는다. 수집 단계의 URL 만 쓴다

발송·수신주소·Secret 을 다루지 않는다. 프롬프트에는 공개 기사 발췌와 선별 규칙만 넣는다.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
from gemini_client import (  # noqa: E402
    CallBudgetExceeded, GeminiClient, GeminiFailClosed,
)

CRITERIA = ["ECONOMIC", "INDUSTRY", "CONSUMER", "POLICY", "DURABLE"]
TAGS = ["FACT", "CLAIM", "MEDIA", "ANALYSIS"]
PRICE_STATES = ["Verified", "Not disclosed", "Not verified"]
A1_SECTIONS = ["KR_ECON", "KR_SOCIETY", "KR_INDUSTRY", "KR_RETAIL",
               "KR_FINANCE", "KR_CORP", "KR_POLICY", "OVERSEAS"]
A2_SECTIONS = ["MARKET", "BRAND", "ODM", "RETAIL", "EXPORT", "INGREDIENT",
               "REGULATION", "INVESTMENT", "DEVICE", "NEW_BRAND", "NEW_PRODUCT"]
PRICE_AMOUNT_RE = re.compile(
    r"(?:₩|\$|¥|USD|KRW|JPY)\s?[\d,]+(?:\.\d+)?|[\d,]+\s?(?:원|엔|円|달러|dollars?)"
)
INTERPRETIVE_RE = re.compile(
    r"(보인다|전망|시사|의미한다|때문에|하려는|의도|기대된다|가능성이 (높|있)|"
    r"로 읽힌다|해석)"
)

RULES = (
    "너는 산업·경제 인텔리전스 애널리스트다. 아래 규칙을 지켜 JSON 으로만 답한다.\n"
    "- 기사 제목을 옮기지 않는다. 무엇이 달라졌는지를 쓴다.\n"
    "- 주어진 발췌에 없는 숫자·사실을 만들지 않는다. 확인되지 않으면 비운다.\n"
    "- 기업 주장은 CLAIM, 공식 발표·통계는 FACT, 매체 해석은 MEDIA, "
    "너의 해석은 ANALYSIS 로 태그한다.\n"
    "- 단순 MOU·홍보·채용·수상·행사·사회공헌은 제외한다.\n"
)


# ── Schema ───────────────────────────────────────────────────────
def _str(enum=None):
    out = {"type": "STRING"}
    if enum:
        out["enum"] = list(enum)
    return out


SCHEMA_SELECT = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": _str(),
                    "keep": {"type": "BOOLEAN"},
                    "noise": {"type": "BOOLEAN"},
                    "criteria_met": {"type": "ARRAY", "items": _str(CRITERIA)},
                    "cluster_id": _str(),
                    "reason": _str(),
                },
                "required": ["id", "keep", "criteria_met", "cluster_id"],
            },
        }
    },
    "required": ["items"],
}

SCHEMA_WRITE_A1 = {
    "type": "OBJECT",
    "properties": {
        "issues": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": _str(),
                    "section": _str(A1_SECTIONS),
                    "headline": _str(),
                    "what_changed": _str(),
                    "why_it_matters": _str(),
                    "tag": _str(TAGS),
                },
                "required": ["id", "section", "headline", "what_changed",
                             "why_it_matters", "tag"],
            },
        },
        "must_know": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": _str(),
                    "rank": {"type": "INTEGER"},
                    "headline": _str(),
                    "what_changed": _str(),
                    "why_it_matters": _str(),
                },
                "required": ["id", "rank", "headline", "what_changed",
                             "why_it_matters"],
            },
        },
    },
    "required": ["issues", "must_know"],
}

SCHEMA_WRITE_A2 = {
    "type": "OBJECT",
    "properties": {
        "issues": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": _str(),
                    "section": _str(A2_SECTIONS),
                    "headline": _str(),
                    "what_changed": _str(),
                    "numbers": _str(),
                    "context": _str(),
                    "implication": _str(),
                    "tag": _str(TAGS),
                },
                "required": ["id", "section", "headline", "what_changed", "tag"],
            },
        }
    },
    "required": ["issues"],
}

SCHEMA_PRODUCT = {
    "type": "OBJECT",
    "properties": {
        "products": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "source_item_id": _str(),
                    "brand": _str(),
                    "product": _str(),
                    "category": _str(),
                    "ingredient": _str(),
                    "technology": _str(),
                    "claim": _str(),
                    "texture": _str(),
                    "price_state": _str(PRICE_STATES),
                    "price_detail": _str(),
                    "channel": _str(),
                    "launch_date": _str(),
                },
                "required": ["source_item_id", "brand", "product", "category",
                             "price_state"],
            },
        },
        "signal": {
            "type": "OBJECT",
            "properties": {
                "name": _str(),
                "observation": _str(),
                "interpretation": _str(),
                "confidence": _str(["High", "Medium", "Low"]),
                "brands": {"type": "ARRAY", "items": _str()},
                "product_count": {"type": "INTEGER"},
                "source_item_ids": {"type": "ARRAY", "items": _str()},
                "seasonality_risk": {"type": "BOOLEAN"},
                "seasonality_note": _str(),
            },
            "required": ["name", "observation", "interpretation", "confidence",
                         "brands", "product_count", "source_item_ids"],
        },
        "watch_items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"what": _str(), "why": _str()},
                "required": ["what", "why"],
            },
        },
    },
    "required": ["products"],
}


# ── 입력 조립 ────────────────────────────────────────────────────
PACK_CHAR_BUDGET = 90_000   # 호출당 입력 상한(설계 2-2)의 보수적 환산


def pack(items, excerpt_chars, max_chars=PACK_CHAR_BUDGET):
    """입력 JSON 을 만든다. 상한에 닿으면 **행 단위로** 끊는다.

    프롬프트를 글자 수로 잘라 JSON 이 깨지는 일이 없게 한다.
    끊긴 건수는 호출자가 기록한다.
    """
    rows, size, dropped = [], 2, 0
    for it in items:
        row = {
            "id": it["id"],
            "src": it["source_name"],
            "tier": it["tier"],
            "date": it["published"],
            "cluster_hint": it.get("cluster_id", ""),
            "title": it["title"],
            "excerpt": C.truncate(it["excerpt"], excerpt_chars),
        }
        chunk = len(json.dumps(row, ensure_ascii=False)) + 1
        if size + chunk > max_chars:
            dropped += 1
            continue
        rows.append(row)
        size += chunk
    return json.dumps(rows, ensure_ascii=False), dropped


def representative(members):
    """클러스터 대표 — Tier 가 낮은(권위 높은) 쪽, 같으면 먼저 보도된 쪽."""
    return sorted(members, key=lambda x: (x["tier"], x["published"]))[0]


def issue_row(issue, by_id):
    """작성 단계 입력 1행. 본문 전체가 아니라 발췌만 넣는다."""
    return {
        "id": issue["id"],
        "src": issue["source_name"],
        "tier": issue["tier"],
        "date": issue["published"],
        "title": issue["title"],
        "criteria": issue.get("criteria_met", []),
        "excerpt": C.truncate(
            " / ".join(by_id[m]["excerpt"] for m in issue["members"]), 1400),
    }


def interleave_by_media(rows, key):
    """매체별로 돌아가며 1건씩 뽑아 다시 늘어놓는다 (round-robin).

    왜 필요한가 — 입력은 Source 등록 순서대로 쌓여 있다. 상한(건수·글자 수)에
    걸려 **앞에서부터 잘리면** 뒤쪽 매체가 통째로 사라진다. 그러면 CLAUDE.md 5장의
    "5개 전문매체 중 최소 3개 이상 반영" 목표와 C3 가 데이터가 아니라 등록 순서에
    좌우된다.

    **상한값도 선별 기준도 바꾸지 않는다. 순서만 바꾼다.**
    같은 매체 안에서는 들어온 순서를 그대로 지킨다.
    """
    groups = {}
    order = []
    for r in rows:
        name = key(r)
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(r)
    out, depth = [], 0
    while len(out) < len(rows):
        progressed = False
        for name in order:
            g = groups[name]
            if depth < len(g):
                out.append(g[depth])
                progressed = True
        if not progressed:
            break
        depth += 1
    return out


def cap_issues_by_media(issues, limit):
    """AXIS 2 이슈 수 상한 — 매체를 돌아가며 남긴다.

    상한값은 cap_issues 와 같다. 각 매체 안에서는 기존과 똑같이
    Tier 가 높은(권위 있는) 쪽 · 먼저 보도된 쪽을 우선한다.
    """
    if len(issues) <= limit:
        return issues, 0
    ranked = sorted(issues, key=lambda x: (x["tier"], x["published"]))
    keep_ids = {i["id"] for i in
                interleave_by_media(ranked, lambda x: x["source_name"])[:limit]}
    return [i for i in issues if i["id"] in keep_ids], len(issues) - limit


def cap_issues(issues, limit):
    """이슈 수 상한. Tier 가 높은(권위 있는) 순서로 남긴다."""
    if len(issues) <= limit:
        return issues, 0
    ranked = sorted(issues, key=lambda x: (x["tier"], x["published"]))
    keep = ranked[:limit]
    keep_ids = {i["id"] for i in keep}
    return [i for i in issues if i["id"] in keep_ids], len(issues) - limit


def cap_by_chars(rows, max_chars):
    """글자 수 상한 — 행 단위로만 끊는다 (JSON 이 깨지지 않게)."""
    out, size, dropped = [], 2, 0
    for row in rows:
        chunk = len(json.dumps(row, ensure_ascii=False)) + 1
        if size + chunk > max_chars:
            dropped += 1
            continue
        out.append(row)
        size += chunk
    return out, dropped


def filter_by_rows(issues, rows):
    ids = {r["id"] for r in rows}
    return [i for i in issues if i["id"] in ids]


# ── 검증 ─────────────────────────────────────────────────────────
def verify_numbers(text, allowed, stats):
    """발췌에 없는 숫자는 삭제한다 (설계 2-5). 삭제 건수를 센다.

    원문 표기(쉼표·소수점) 그대로 찾아 치환한다. 한 자리 숫자는 순번·열거일 수
    있어 검증 대상에서 제외한다.
    """
    if not text:
        return text

    def repl(m):
        raw = m.group(0)
        norm = raw.replace(",", "").rstrip(".")
        if len(norm) <= 1 or norm in allowed:
            return raw
        stats["numbers_removed"] += 1
        return "[수치 미검증]"

    return C.NUM_RE.sub(repl, text)


def apply_selection(sel, pool_by_id, stats):
    """2-of-5 Rule 을 코드가 판정하고, 모델의 cluster_id 로 병합한다."""
    kept, decisions = {}, {}
    for row in (sel.get("items") or []):
        iid = (row.get("id") or "").strip()
        item = pool_by_id.get(iid)
        if not item:
            stats["unknown_ids"] += 1
            continue
        crit = []
        for c in (row.get("criteria_met") or []):
            c = (c or "").strip().upper()
            if c in CRITERIA and c not in crit:
                crit.append(c)
        keep = bool(row.get("keep")) and len(crit) >= 2 and not row.get("noise")
        decisions[iid] = {"keep": keep, "criteria_met": crit,
                          "cluster_id": (row.get("cluster_id") or
                                         item.get("cluster_id") or iid)}
        if keep:
            kept[iid] = decisions[iid]
        else:
            stats["excluded_by_rule"] += 1
    return kept, decisions


def merge_clusters(kept, pool_by_id):
    """cluster_id 가 같은 항목을 1건으로 묶는다 (CLAUDE.md 8-1 중복 병합)."""
    groups = {}
    for iid, dec in kept.items():
        groups.setdefault(dec["cluster_id"], []).append(pool_by_id[iid])
    issues = []
    for cid, members in groups.items():
        rep = representative(members)
        crit = sorted({c for m in members for c in kept[m["id"]]["criteria_met"]})
        issues.append({
            "id": rep["id"],
            "cluster_id": cid,
            "members": [m["id"] for m in members],
            "media": sorted({m["source_name"] for m in members}),
            "source_name": rep["source_name"],
            "source_id": rep["source_id"],
            "tier": rep["tier"],
            "published": rep["published"],
            "title": rep["title"],
            "url": rep["url"],
            "axis": rep["axis"],
            "criteria_met": crit,
            "tier1_backed": any(m["tier"] == 1 for m in members),
            "allowed_numbers": set().union(
                *[C.numbers_in(m["excerpt"] + " " + m["title"]) for m in members]
            ),
        })
    return sorted(issues, key=lambda x: (x["published"], x["id"]))


def check_signal(sig, products, items_by_id, stats):
    """조건 A/B 를 코드가 재계산한다. 미달이면 Signal 이 아니라 Watch Item 이다."""
    if not sig or not (sig.get("observation") or "").strip():
        return None, None
    brands = sorted({(b or "").strip() for b in (sig.get("brands") or []) if b})
    if not brands:
        brands = sorted({p["brand"] for p in products if p.get("brand")})
    ids = [i for i in (sig.get("source_item_ids") or []) if i in items_by_id]
    tiers = {items_by_id[i]["tier"] for i in ids}
    product_count = len([p for p in products if p.get("brand")])
    cond_a = len(brands) >= 3
    cond_b = product_count >= 2 and bool(tiers & {1, 2})
    if not (cond_a or cond_b):
        stats["signals_demoted"] += 1
        return None, {
            "what": "[Signal 조건 미달] " + (sig.get("name") or "관찰 항목"),
            "why": "브랜드 %d건 / 제품 %d건 / 근거 Tier %s — 조건 A·B 미달로 "
                   "Watch Item 으로 강등" % (len(brands), product_count,
                                            sorted(tiers) or "—"),
        }
    conf = (sig.get("confidence") or "Low").strip().title()
    if conf not in ("High", "Medium", "Low"):
        conf = "Low"
    reasons = []
    if conf == "High" and not (cond_a and (tiers & {1, 2})):
        conf = "Medium"
        reasons.append("조건 A + Tier 1·2 근거 미충족 → High 불가")
    if conf == "High" and sig.get("seasonality_risk"):
        conf = "Medium"
        reasons.append("계절성 위험 있고 전년 동기 비교 없음 → High 불가 (CLAUDE.md 6장)")
    observation = (sig.get("observation") or "").strip()
    if INTERPRETIVE_RE.search(observation):
        stats["spec_violations"] += 1
        reasons.append("Observation 에 해석 표현이 섞여 QA FLAG")
    return {
        "name": (sig.get("name") or "").strip() or "미명명 신호",
        "observation": observation,
        "interpretation": (sig.get("interpretation") or "").strip(),
        "confidence": conf,
        "evidence": {
            "brands": brands,
            "brand_count": len(brands),
            "product_count": product_count,
            "source_item_ids": ids,
            "source_tiers": sorted(tiers),
            "condition": "A" if cond_a else "B",
        },
        "seasonality_note": (sig.get("seasonality_note") or "").strip(),
        "adjustments": reasons,
    }, None


def clean_products(raw, items_by_id, stats):
    out = []
    for p in (raw or []):
        sid = (p.get("source_item_id") or "").strip()
        item = items_by_id.get(sid)
        if not item:
            stats["unknown_ids"] += 1
            continue
        state = (p.get("price_state") or "").strip()
        detail = (p.get("price_detail") or "").strip()
        if state not in PRICE_STATES:
            state, detail = "Not verified", detail
            stats["spec_violations"] += 1
        if state == "Verified" and not PRICE_AMOUNT_RE.search(detail):
            # 금액·통화가 없으면 Verified 로 쓸 수 없다.
            state = "Not verified"
            stats["spec_violations"] += 1
        allowed = C.numbers_in(item["excerpt"] + " " + item["title"])
        row = {
            "brand": (p.get("brand") or "").strip() or "—",
            "product": (p.get("product") or "").strip() or "—",
            "category": (p.get("category") or "").strip() or "—",
            "ingredient": (p.get("ingredient") or "").strip() or "—",
            "technology": (p.get("technology") or "").strip() or "—",
            "claim": (p.get("claim") or "").strip() or "—",
            "texture": (p.get("texture") or "").strip() or "—",
            "price_state": state,
            "price_detail": verify_numbers(detail, allowed, stats) or "—",
            "channel": (p.get("channel") or "").strip() or "—",
            "launch_date": (p.get("launch_date") or "").strip() or "—",
            "source_name": item["source_name"],
            "source_item_id": sid,
            # 국가는 모델 판단이 아니라 **수집 Source 의 국가**다 (C4 국가 분리 근거).
            "source_country": item.get("country", ""),
            "url": item["url"],      # 모델이 만든 URL 을 쓰지 않는다
            "published": item["published"],
            "tier": item["tier"],
        }
        if row["brand"] == "—" and row["product"] == "—":
            continue
        out.append(row)
    return out


def prev_week_signals(weekly_id, repo_root):
    """02_TREND_TRACKER 를 읽기만 한다 (쓰지 않는다)."""
    try:
        year, week = C.parse_weekly_id(weekly_id)
    except ValueError:
        return {}
    prev = "%04d-W%02d" % (year, week - 1) if week > 1 else ""
    path = os.path.join(repo_root, "02_TREND_TRACKER", "new_product_signals.csv")
    out = {}
    if not prev or not os.path.exists(path):
        return out
    import csv
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if (row.get("Week") or "").strip() == prev:
                out.setdefault((row.get("Country") or "").strip(), []).append(
                    (row.get("Signal") or "").strip()
                )
    return out


def vs_prev(country, signal, prev_map):
    if not signal:
        return "—"
    prev = prev_map.get(country, [])
    if not prev:
        return "New (직전 주 기록 없음)"
    toks = C.tokens(signal["name"] + " " + signal["observation"])
    for old in prev:
        if C.jaccard(toks, C.tokens(old)) >= 0.3:
            return "Continued"
    return "New"


# ── 단계 실행 ────────────────────────────────────────────────────
def run(weekly_id, collected, client, stats):
    items = collected["items"]
    by_id = {i["id"]: i for i in items}
    out = {"stages": []}

    general_pool = [i for i in items
                    if i["axis"] in ("AXIS1", "TIER1") and not i["noise"]][:140]
    # AXIS 2 후보는 **매체를 돌아가며** 늘어놓은 뒤 상한을 적용한다. 등록 순서대로
    # 앞에서 자르면 뒤쪽 매체(코스모닝·코스인코리아)가 모델 입력에 아예 닿지 못한다.
    beauty_pool = interleave_by_media(
        [i for i in items if i["axis"] == "BEAUTY" and not i["noise"]],
        lambda x: x["source_name"],
    )[:80]

    # 호출 1 — AXIS 1 선별 + 병합
    print("CALL 1/7 — AXIS 1 선별+병합 (%d건)" % len(general_pool))
    data1, drop1 = pack(general_pool, 600)
    sel1 = client.generate(
        "1_axis1_select",
        RULES + (
            "\n[작업] 아래 일반 뉴스 후보에서 WEEKLY BRIEF 에 넣을 것을 선별하고, "
            "인과관계로 묶이는 기사에 같은 cluster_id 를 부여한다.\n"
            "criteria_met 은 실제로 충족하는 것만 고른다: ECONOMIC(경제적 영향) / "
            "INDUSTRY(산업적 영향) / CONSUMER(소비자 영향) / POLICY(정책·규제 영향) / "
            "DURABLE(지속 가능성). 2개 이상 충족하지 못하면 keep=false 로 둔다.\n"
            "모든 입력 id 에 대해 한 행씩 반드시 답한다."
        ),
        data1, SCHEMA_SELECT, max_output_tokens=16384,
    )
    kept1, _ = apply_selection(sel1, {i["id"]: i for i in general_pool}, stats)
    general_issues = merge_clusters(kept1, by_id)
    out["stages"].append({"call": 1, "kept": len(kept1),
                          "issues": len(general_issues),
                          "input_dropped": drop1})

    # 호출 2 — AXIS 2 선별 + 병합
    print("CALL 2/7 — AXIS 2 선별+병합 (%d건)" % len(beauty_pool))
    data2, drop2 = pack(beauty_pool, 600)
    sel2 = client.generate(
        "2_axis2_select",
        RULES + (
            "\n[작업] 아래 화장품·뷰티 전문매체 기사에서 WEEKLY BRIEF 에 넣을 것을 "
            "선별하고 중복 보도에 같은 cluster_id 를 부여한다.\n"
            "뷰티 전문매체에 실렸다는 사실 자체는 포함 근거가 아니다. "
            "criteria_met 2개 이상을 충족해야 keep=true 다.\n"
            "모든 입력 id 에 대해 한 행씩 반드시 답한다."
        ),
        data2, SCHEMA_SELECT, max_output_tokens=16384,
    )
    kept2, _ = apply_selection(sel2, {i["id"]: i for i in beauty_pool}, stats)
    beauty_issues = merge_clusters(kept2, by_id)
    out["stages"].append({"call": 2, "kept": len(kept2),
                          "issues": len(beauty_issues),
                          "input_dropped": drop2})

    # 호출 3 — MUST KNOW 선정 + AXIS 1 작성
    # 작성 단계 입력은 이슈 수·글자 수 양쪽으로 상한을 둔다. 상한을 넘은 이슈는
    # 브리프에서도 함께 제외한다 — 본문 없이 제목만 남는 항목을 만들지 않기 위함이다.
    general_issues, drop_g = cap_issues(general_issues, 45)
    beauty_issues, drop_b = cap_issues_by_media(beauty_issues, 35)
    a1_rows = [issue_row(i, by_id) for i in general_issues]
    a1_rows, drop_g2 = cap_by_chars(a1_rows, 70_000)
    general_issues = filter_by_rows(general_issues, a1_rows)
    print("CALL 3/7 — MUST KNOW + AXIS 1 작성 (%d 이슈)" % len(general_issues))
    a1_data = json.dumps({
        "general_issues": a1_rows,
        "beauty_issue_titles": [
            {"id": i["id"], "src": i["source_name"], "title": i["title"]}
            for i in beauty_issues
        ],
    }, ensure_ascii=False)
    wr3 = client.generate(
        "3_axis1_write",
        RULES + (
            "\n[작업] (1) general_issues 각 건에 대해 section·headline·"
            "what_changed(무엇이 달라졌는가)·why_it_matters(누구에게 어떤 영향인가)를 쓴다.\n"
            "(2) general_issues 와 beauty_issue_titles 를 함께 보고 "
            "WEEKLY MUST KNOW 를 rank 1 부터 중요도 순으로 선정한다. "
            "**억지로 채우지 않는다 — 정말 중요한 것이 6건이면 6건만 쓴다. 최대 10건.** "
            "서로 인과관계로 묶인 항목은 하나로 합친다.\n"
            "숫자는 발췌에 있는 것만 쓴다. 발췌에 없으면 숫자를 쓰지 않는다."
        ),
        a1_data, SCHEMA_WRITE_A1, max_output_tokens=24576,
    )
    out["stages"].append({"call": 3, "issues_written": len(general_issues),
                          "issues_dropped_over_cap": drop_g + drop_g2})

    # 호출 4 — AXIS 2 심층 작성
    # 글자 수 상한도 앞에서부터 자른다 — 여기서도 매체를 돌아가며 넣는다.
    a2_rows = interleave_by_media(
        [issue_row(i, by_id) for i in beauty_issues], lambda r: r["src"])
    a2_rows, drop_b2 = cap_by_chars(a2_rows, 70_000)
    beauty_issues = filter_by_rows(beauty_issues, a2_rows)
    print("CALL 4/7 — AXIS 2 심층 작성 (%d 이슈)" % len(beauty_issues))
    a2_data = json.dumps(a2_rows, ensure_ascii=False)
    wr4 = client.generate(
        "4_axis2_write",
        RULES + (
            "\n[작업] 각 뷰티 이슈에 대해 section·headline·what_changed 와 함께 "
            "numbers(매출·수량·가격·점유율 — 기준연도·통화 표기), "
            "context(직전 흐름 대비 무엇이 달라졌는가), "
            "implication(누구에게 어떤 영향인가)을 쓴다.\n"
            "확인되지 않은 항목은 빈 문자열로 둔다. 추정하지 않는다."
        ),
        a2_data, SCHEMA_WRITE_A2, max_output_tokens=24576,
    )
    out["stages"].append({"call": 4, "issues_written": len(beauty_issues),
                          "issues_dropped_over_cap": drop_b + drop_b2})

    # 호출 5·6·7 — 국가별 신제품 + Trend Signal
    product_sets = {
        "KR": [i for i in items
               if i["country"] == "KR" and i["product_candidate"]
               and i["axis"] in ("BEAUTY", "PRODUCT_KR")][:40],
        "US": [i for i in items if i["axis"] == "PRODUCT_US"][:40],
        "JP": [i for i in items if i["axis"] == "PRODUCT_JP"][:40],
    }
    label = {"KR": "KOREA", "US": "USA", "JP": "JAPAN"}
    products, signals, watch = {}, {}, []
    for n, country in enumerate(("KR", "US", "JP"), start=5):
        pool = product_sets[country]
        data_p, _drop_p = pack(pool, 900)
        print("CALL %d/7 — %s 신제품+Signal (%d건)" % (n, label[country], len(pool)))
        if not pool:
            # 입력이 없으면 호출하지 않는다 — 없는 것을 만들지 않는다.
            products[country], signals[country] = [], None
            out["stages"].append({"call": n, "country": country,
                                  "skipped": "NO_INPUT_ITEMS"})
            continue
        res = client.generate(
            "%d_product_%s" % (n, country),
            RULES + (
                "\n[작업] 아래 %s 기사에서 신제품을 뽑아 표로 만들고, "
                "그 뒤 Trend Signal 을 작성한다.\n"
                "- 단순 리뉴얼·한정 패키지·색상 변경은 중요도가 낮으면 제외한다.\n"
                "- 확인되지 않은 항목은 빈 문자열로 둔다. 추정하지 않는다.\n"
                "- price_state 는 Verified(금액·용량까지 확인) / Not disclosed"
                "(출처가 공개하지 않음) / Not verified(이번에 확인하지 못함) 중 하나다.\n"
                "- Signal 의 observation 에는 **사실만** 쓴다. 해석은 interpretation "
                "에만 쓴다. 독립 브랜드 3건 이상(A) 또는 제품 2건+Tier 1·2 근거(B)를 "
                "충족하지 못하면 signal 을 비우고 watch_items 에 남긴다.\n"
                "- 매년 같은 시기에 반복되는 패턴이면 seasonality_risk=true 로 표시한다."
                % label[country]
            ),
            data_p, SCHEMA_PRODUCT, max_output_tokens=16384,
        )
        rows = clean_products(res.get("products"), by_id, stats)
        sig, demoted = check_signal(res.get("signal"), rows, by_id, stats)
        products[country] = rows
        signals[country] = sig
        if demoted:
            demoted["country"] = country
            watch.append(demoted)
        for w in (res.get("watch_items") or []):
            if (w.get("what") or "").strip():
                watch.append({"country": country,
                              "what": w.get("what", "").strip(),
                              "why": (w.get("why") or "").strip()})
        out["stages"].append({"call": n, "country": country,
                              "products": len(rows), "signal": bool(sig)})

    # ── 작성 결과 결합 + 숫자 검증 ───────────────────────────────
    a1_text = {r.get("id"): r for r in (wr3.get("issues") or [])}
    a2_text = {r.get("id"): r for r in (wr4.get("issues") or [])}

    for issue in general_issues:
        t = a1_text.get(issue["id"], {})
        allowed = issue["allowed_numbers"]
        issue["section"] = (t.get("section") or "KR_INDUSTRY")
        issue["headline"] = verify_numbers(
            (t.get("headline") or issue["title"]).strip(), allowed, stats)
        issue["what_changed"] = verify_numbers(
            (t.get("what_changed") or "").strip(), allowed, stats)
        issue["why_it_matters"] = verify_numbers(
            (t.get("why_it_matters") or "").strip(), allowed, stats)
        issue["tag"] = t.get("tag") if t.get("tag") in TAGS else "MEDIA"
        issue["written"] = bool(issue["what_changed"])

    for issue in beauty_issues:
        t = a2_text.get(issue["id"], {})
        allowed = issue["allowed_numbers"]
        issue["section"] = (t.get("section") or "BRAND")
        issue["headline"] = verify_numbers(
            (t.get("headline") or issue["title"]).strip(), allowed, stats)
        issue["what_changed"] = verify_numbers(
            (t.get("what_changed") or "").strip(), allowed, stats)
        issue["numbers"] = verify_numbers(
            (t.get("numbers") or "").strip(), allowed, stats)
        issue["context"] = verify_numbers(
            (t.get("context") or "").strip(), allowed, stats)
        issue["implication"] = verify_numbers(
            (t.get("implication") or "").strip(), allowed, stats)
        issue["tag"] = t.get("tag") if t.get("tag") in TAGS else "MEDIA"
        issue["written"] = bool(issue["what_changed"])

    pool_issues = {i["id"]: i for i in general_issues + beauty_issues}
    must_know = []
    seen_clusters = set()
    for row in sorted((wr3.get("must_know") or []),
                      key=lambda r: int(r.get("rank") or 99)):
        issue = pool_issues.get((row.get("id") or "").strip())
        if not issue or issue["cluster_id"] in seen_clusters:
            continue
        if not issue["url"].startswith("http"):
            continue  # Article URL 이 없으면 MUST KNOW 로 쓰지 않는다 (C2)
        seen_clusters.add(issue["cluster_id"])
        allowed = issue["allowed_numbers"]
        must_know.append({
            "id": issue["id"],
            "rank": len(must_know) + 1,
            "headline": verify_numbers(
                (row.get("headline") or issue["headline"]).strip(), allowed, stats),
            "what_changed": verify_numbers(
                (row.get("what_changed") or issue["what_changed"]).strip(),
                allowed, stats),
            "why_it_matters": verify_numbers(
                (row.get("why_it_matters") or issue.get("why_it_matters") or "")
                .strip(), allowed, stats),
            "tag": issue["tag"],
            "source_name": issue["source_name"],
            "published": issue["published"],
            "url": issue["url"],
            "axis": issue["axis"],
            "tier": issue["tier"],
            "tier1_backed": issue["tier1_backed"],
            "media": issue["media"],
        })
        if len(must_know) >= 10:
            break

    for issue in general_issues + beauty_issues:
        issue.pop("allowed_numbers", None)

    prev_map = prev_week_signals(
        weekly_id, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    out.update({
        "weekly_id": weekly_id,
        "generated_at_utc": C.stamp_utc(),
        "general_issues": general_issues,
        "beauty_issues": beauty_issues,
        "must_know": must_know,
        "products": products,
        "signals": {k: (dict(v, vs_prev_week=vs_prev(k, v, prev_map)) if v else None)
                    for k, v in signals.items()},
        "watch_items": watch,
        "pools": {"general": len(general_pool), "beauty": len(beauty_pool),
                  "products": {k: len(v) for k, v in product_sets.items()}},
    })
    return out


def gemini_summary_rows(usage):
    """Summary 표에 공통으로 들어가는 설정·토큰 행.

    성공·FAIL CLOSED 양쪽에서 같은 값을 보여 준다 — 잘림(MAX_TOKENS)이
    사고 예산·출력 상한과 어떻게 맞물렸는지 한 표에서 읽히게 하려는 것이다.
    """
    return (
        "| **configured thinking budget** | **%s** |\n"
        "| **configured max output tokens** | **%s** (하한 %s) |\n"
        "| **thought_tokens** | %s |\n"
        "| **output_tokens** | %s |\n"
        "| **finish_reason** | **%s** |\n"
        % (usage.get("thinking_budget"),
           usage.get("max_output_tokens"), usage.get("min_output_tokens"),
           usage.get("thought_tokens"), usage.get("tokens_out"),
           usage.get("finish_reason"))
    )


def parse_diag_table(usage):
    """구조화 출력 파싱 진단 표.

    **raw 응답 본문은 넣지 않는다.** Secret·개인정보가 섞일 수 있는 값은 담지 않고,
    구조만 보고 원인을 좁힐 수 있는 항목만 쓴다 (사용자 GA-3 지시 5).
    """
    d = usage.get("parse_diag")
    if not d:
        return ("#### 구조화 출력 진단\n\n"
                "- 파싱 단계에 도달하지 못했다 (응답 수신 전 실패).\n")
    rows = [
        ("HTTP status", d.get("http_status")),
        ("candidate count", d.get("candidate_count")),
        ("parts count", d.get("parts_count")),
        ("text_present", d.get("text_present")),
        ("json_fence_detected", d.get("json_fence_detected")),
        ("finish_reason", d.get("finish_reason") or "(없음)"),
        ("parse_error_type", "`%s`" % (d.get("parse_error_type") or "(없음)")),
        ("required_fields_missing",
         ", ".join(d.get("required_fields_missing") or []) or "없음"),
        ("실패 단계", "`%s`" % (d.get("stage") or "—")),
        ("thought tokens", usage.get("thought_tokens")),
        ("output tokens", usage.get("tokens_out")),
    ]
    out = ["#### 구조화 출력 진단 (raw 응답 미출력)", "",
           "| 항목 | 값 |", "|---|---|"]
    out += ["| %s | %s |" % (k, v) for k, v in rows]
    out.append("")
    if (d.get("parse_error_type") or "").startswith("TRUNCATED_OUTPUT_MAX_TOKENS"):
        out.append("- `finishReason=MAX_TOKENS` — 응답이 **잘려서** JSON 이 "
                   "닫히지 않았다. 파서 문제가 아니라 출력 토큰 상한 문제다.")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collected", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    collected = C.read_json(args.collected)
    weekly_id = collected["weekly_id"]
    stats = {"numbers_removed": 0, "excluded_by_rule": 0, "unknown_ids": 0,
             "signals_demoted": 0, "spec_violations": 0}

    client = None
    try:
        client = GeminiClient()
        result = run(weekly_id, collected, client, stats)
    except (GeminiFailClosed, CallBudgetExceeded) as e:
        usage = client.usage() if client else {"calls": 0}
        category = getattr(e, "category", type(e).__name__)
        detail = getattr(e, "detail", None) or str(e)
        C.write_json(args.out + ".failed.json", {
            "weekly_id": weekly_id, "category": category,
            "detail": C.sanitize(detail), "usage": usage,
            "generated_at_utc": C.stamp_utc(),
        })
        C.append_summary(
            "### STEP 2 — Gemini 분석: **FAIL CLOSED**\n\n"
            "| 항목 | 값 |\n|---|---|\n"
            "| **primary model** | `%s` |\n"
            "| **fallback model** | `%s` |\n"
            "| **model actually used** | `%s` |\n"
            "| **primary attempts** | %s |\n"
            "| **fallback attempts** | %s |\n"
            "| **fallback triggered** | **%s** |\n"
            "| **Gemini attempt count** | **%s** |\n"
            "| **retry count** | **%s** (단계당 최대 %s회 시도, backoff %s초) |\n"
            "| **마지막 HTTP status** | **%s** |\n"
            "| **final category** | **`%s`** |\n"
            "| **timeout seconds** | **%s** (단일 요청 상한) |\n"
            "| **backoff history** | %s |\n"
            "%s"
            "| 소모한 호출 수 | %s / 예산 %s (절대 상한 %s) |\n"
            "| Brief 생성·발송 | **없음** |\n"
            % (usage.get("primary_model"), usage.get("fallback_model"),
               usage.get("model_used"), usage.get("primary_attempts"),
               usage.get("fallback_attempts"),
               "YES" if usage.get("fallback_triggered") else "NO",
               usage.get("attempts"), usage.get("retries"),
               usage.get("max_attempts_per_stage"),
               usage.get("backoff_schedule"), usage.get("last_http_status"),
               usage.get("final_category") or category,
               usage.get("timeout_seconds"),
               usage.get("backoff_waits") or "없음",
               gemini_summary_rows(usage),
               usage.get("calls"), usage.get("budget"), usage.get("hard_cap"))
        )
        C.append_summary(parse_diag_table(usage))
        print("FAIL CLOSED: %s — %s" % (category, C.sanitize(detail)))
        return 2

    result["verification"] = stats
    result["usage"] = client.usage()
    C.write_json(args.out, result)

    u = result["usage"]
    C.append_summary(
        "### STEP 2 — Gemini 분석\n\n"
        "| 항목 | 값 |\n|---|---|\n"
        "| **primary model** | `%s` |\n"
        "| **fallback model** | `%s` |\n"
        "| **model actually used** | **`%s`** |\n"
        "| **primary attempts** | %d |\n"
        "| **fallback attempts** | %d |\n"
        "| **fallback triggered** | **%s** |\n"
        "| **Gemini attempt count** | **%d** |\n"
        "| **retry count** | **%d** (단계당 최대 %d회 시도, backoff %s초) |\n"
        "| **마지막 HTTP status** | **%s** |\n"
        "| **final category** | **`%s`** |\n"
        "| **timeout seconds** | %s (단일 요청 상한) |\n"
        "| **backoff history** | %s |\n"
        "%s"
        "| 호출 수 | **%d** / 예산 %d (절대 상한 %d) |\n"
        "| 토큰 (in/out/total) | %d / %d / %d |\n"
        "| 2-of-5 미달 제외 | %d |\n"
        "| 숫자 검증 삭제 | %d |\n| Signal 강등 | %d |\n| 규격 위반 교정 | %d |\n"
        "| MUST KNOW | %d |\n| 신제품 KR/US/JP | %d / %d / %d |\n"
        % (u["primary_model"], u["fallback_model"], u["model_used"],
           u["primary_attempts"], u["fallback_attempts"],
           "YES" if u["fallback_triggered"] else "NO",
           u["attempts"], u["retries"],
           u["max_attempts_per_stage"], u["backoff_schedule"],
           u["last_http_status"], u["final_category"] or "OK",
           u.get("timeout_seconds"), u["backoff_waits"] or "없음",
           gemini_summary_rows(u),
           u["calls"], u["budget"], u["hard_cap"],
           u["tokens_in"], u["tokens_out"], u["tokens_total"],
           stats["excluded_by_rule"], stats["numbers_removed"],
           stats["signals_demoted"], stats["spec_violations"],
           len(result["must_know"]), len(result["products"].get("KR", [])),
           len(result["products"].get("US", [])),
           len(result["products"].get("JP", [])))
    )
    print("analysis written -> %s (calls=%d)" % (args.out, u["calls"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
