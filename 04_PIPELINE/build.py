# -*- coding: utf-8 -*-
"""GA-3 STEP 3 — 조립. Weekly Brief(.md) + Compact Email(.html) 을 만든다.

- 양식은 00_SYSTEM/briefing_template.md 를 따른다.
- 내용이 없는 섹션은 지우지 않고 `No Significant News` / `Not Checked` 로 남긴다.
- 이메일 HTML 은 **인라인 스타일만** 쓴다. 외부 CSS·스크립트·이미지를 넣지 않는다 (G2).
- 본문에 로컬 경로·인증정보·수신 주소를 넣지 않는다 (C7).
- 기준선 파일(01_WEEKLY_BRIEFS/...)을 쓰지 않는다. 산출물은 --out-dir 아래에만 만든다.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

QA_PLACEHOLDER = "<!-- QA_METRICS_PLACEHOLDER -->"
QA_EMAIL_PLACEHOLDER = "<!-- QA_EMAIL_PLACEHOLDER -->"
TIER1_NOTE = "Tier 1 original source not verified"

A1_TITLES = [
    ("KR_ECON", "1. 국내 경제"),
    ("KR_SOCIETY", "2. 국내 사회"),
    ("KR_INDUSTRY", "3. 국내 산업"),
    ("KR_RETAIL", "4. 유통 / Retail / E-commerce"),
    ("KR_FINANCE", "5. 증권 / 금융시장"),
    ("KR_CORP", "6. 주요 기업 동향"),
    ("KR_POLICY", "7. 정부 정책 / 규제"),
    ("OVERSEAS", "8. 해외 (US / CN / JP / EU)"),
]
A2_TITLES = [
    ("MARKET", "1. 화장품 시장"),
    ("BRAND", "2. 브랜드 / 기업"),
    ("ODM", "3. ODM / OEM"),
    ("RETAIL", "4. 유통"),
    ("EXPORT", "5. 수출 / 글로벌 진출"),
    ("INGREDIENT", "6. 원료 / 기술"),
    ("REGULATION", "7. 규제"),
    ("INVESTMENT", "8. 투자 / M&A"),
    ("DEVICE", "9. 뷰티 디바이스"),
    ("NEW_BRAND", "10. 신규 브랜드"),
    ("NEW_PRODUCT", "11. 주요 신제품 (개요)"),
]
COUNTRY_TITLES = [("KR", "KOREA"), ("US", "USA"), ("JP", "JAPAN")]

BRAND = "#8a5a2b"
INK = "#1c1b19"
MUTED = "#6b6862"
LINE = "#e5e1da"


# ── 공통 조립 ────────────────────────────────────────────────────
def tier1_suffix(issue):
    """정량 수치가 있는데 Tier 1 근거가 없으면 표기를 붙인다 (CLAUDE.md 7-1)."""
    text = " ".join(str(issue.get(k) or "") for k in
                    ("what_changed", "numbers", "why_it_matters", "headline"))
    has_number = bool(C.numbers_in(text))
    if has_number and not issue.get("tier1_backed"):
        return " *(%s)*" % TIER1_NOTE
    return ""


def source_label(issue):
    media = issue.get("media") or [issue.get("source_name")]
    return "%s (%s)" % (" · ".join(m for m in media if m), issue.get("published"))


def price_text(p):
    if p["price_state"] == "Verified":
        return "Verified — %s" % p["price_detail"]
    return p["price_state"]


# ── Markdown ─────────────────────────────────────────────────────
def build_markdown(a, collected):
    start = collected["coverage"]["start_kst"][:10]
    end = collected["coverage"]["end_kst"][:10]
    L = []
    add = L.append

    add("# WEEKLY INTELLIGENCE BRIEF — %s" % a["weekly_id"])
    add("")
    add("**Coverage**: %s(월) ~ %s(일) KST" % (start, end))
    add("**Issued**: %s KST" % C.stamp_kst())
    add("**Run**: GA-3 End-to-End 수동 테스트 (GitHub Actions · Gemini 엔진)")
    add("")
    add("> 이 문서는 GA-3 검증 산출물이다. 기준선 파일을 덮어쓰지 않는다.")
    add("")
    add("---")
    add("")

    # THIS WEEK IN 5 LINES
    add("## THIS WEEK IN 5 LINES")
    add("")
    if a["must_know"]:
        for row in a["must_know"][:5]:
            add("%d. **%s** — %s ([%s](%s), %s)"
                % (row["rank"], row["headline"], row["what_changed"],
                   row["source_name"], row["url"], row["published"]))
    else:
        add("이번 주는 특기할 변화가 없었다. (선별 기준을 충족한 항목 없음)")
    add("")
    add("---")
    add("")

    # WEEKLY MUST KNOW
    add("# WEEKLY MUST KNOW")
    add("")
    if a["must_know"]:
        for row in a["must_know"]:
            add("### %d. %s" % (row["rank"], row["headline"]))
            add("")
            add("- **무엇이 달라졌는가**: %s" % row["what_changed"])
            add("- **Why it matters**: %s" % row["why_it_matters"])
            add("- **판정**: `%s` · Tier %s%s"
                % (row["tag"], row["tier"],
                   "" if row["tier1_backed"] else " · " + TIER1_NOTE))
            add("- **Source**: [%s](%s) — %s"
                % (row["source_name"], row["url"], row["published"]))
            add("")
    else:
        add("No Significant News — 선별 기준(2-of-5)을 충족한 항목이 없다.")
        add("")
    add("---")
    add("")

    # AXIS 1
    add("# AXIS 1 — GENERAL WEEKLY INTELLIGENCE")
    add("")
    for key, title in A1_TITLES:
        add("## %s" % title)
        add("")
        rows = [i for i in a["general_issues"] if i.get("section") == key]
        if not rows:
            add("No Significant News")
            add("")
            continue
        for i in rows:
            add("- **%s** — %s%s" % (i["headline"], i["what_changed"],
                                     tier1_suffix(i)))
            if i.get("why_it_matters"):
                add("  - **[판단]** %s" % i["why_it_matters"])
            add("  - `%s` · [%s](%s)" % (i["tag"], source_label(i), i["url"]))
        add("")
    add("---")
    add("")

    # AXIS 2
    add("# AXIS 2 — BEAUTY INDUSTRY INTELLIGENCE")
    add("")
    add("> 매체 커버리지: 장업신문 / CMN / 뷰티누리 / 코스모닝 / 코스인코리아 "
        "— 상태는 COVERAGE LOG 참조")
    add("")
    for key, title in A2_TITLES:
        add("## %s" % title)
        add("")
        rows = [i for i in a["beauty_issues"] if i.get("section") == key]
        if not rows:
            add("No Significant News")
            add("")
            continue
        for i in rows:
            add("- **%s** — %s%s" % (i["headline"], i["what_changed"],
                                     tier1_suffix(i)))
            if i.get("numbers"):
                add("  - **숫자**: %s" % i["numbers"])
            if i.get("context"):
                add("  - **맥락**: %s" % i["context"])
            if i.get("implication"):
                add("  - **[판단] 시사점**: %s" % i["implication"])
            add("  - `%s` · [%s](%s)" % (i["tag"], source_label(i), i["url"]))
        add("")
    add("---")
    add("")

    # NEW PRODUCT WATCH
    add("# NEW PRODUCT WATCH")
    add("")
    add("> 국가별로 분리한다. 확인되지 않은 항목은 `—`로 비우고 추정하지 않는다.")
    add("")
    for code, label in COUNTRY_TITLES:
        add("## %s NEW PRODUCT WATCH" % label)
        add("")
        rows = a["products"].get(code) or []
        if rows:
            add("| Brand | Product | Category | 성분 | 기술 | 효능(Claim) | 제형 "
                "| Price | 채널 | 출시일 | Source | Article URL |")
            add("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for p in rows:
                add("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                    % (p["brand"], p["product"], p["category"], p["ingredient"],
                       p["technology"], p["claim"], p["texture"], price_text(p),
                       p["channel"], p["launch_date"], p["source_name"],
                       "[기사](%s)" % p["url"] if p["url"].startswith("http")
                       else "Not verified"))
        else:
            add("Not Checked / No Significant News — 이번 회차에 선정 기준을 충족한 "
                "신제품을 확인하지 못했다.")
        add("")
        add("### Trend Signal — %s" % label)
        add("")
        sig = (a.get("signals") or {}).get(code)
        if sig:
            add("| Signal | Observation (사실만) | Evidence Count | "
                "Interpretation (해석) | Confidence |")
            add("|---|---|---|---|---|")
            ev = sig["evidence"]
            add("| %s | %s | 브랜드 %d개 / 제품 %d건 / 근거 %d건 (조건 %s, Tier %s) "
                "| %s | %s |"
                % (sig["name"], sig["observation"], ev["brand_count"],
                   ev["product_count"], len(ev["source_item_ids"]),
                   ev["condition"], ev["source_tiers"] or "—",
                   sig["interpretation"], sig["confidence"]))
            add("")
            add("- **직전 주 대비**: %s" % sig.get("vs_prev_week", "—"))
            add("- **계절성 검토**: %s" % (sig.get("seasonality_note") or "미검증"))
            if sig.get("adjustments"):
                add("- **코드 교정**: %s" % " / ".join(sig["adjustments"]))
        else:
            add("이번 주 유의미한 Signal 없음 — 조건 A(브랜드 3건+)·"
                "B(제품 2건+ & Tier 1·2 근거) 미충족.")
        add("")
    add("---")
    add("")

    # CROSS-COUNTRY READ
    add("# CROSS-COUNTRY READ")
    add("")
    live = [code for code, _ in COUNTRY_TITLES if (a["products"].get(code) or [])]
    if len(live) >= 2:
        add("- **관찰된 국가**: %s" % ", ".join(live))
        for code, label in COUNTRY_TITLES:
            rows = a["products"].get(code) or []
            cats = sorted({p["category"] for p in rows if p["category"] != "—"})
            add("- **%s**: %s" % (label, ", ".join(cats) if cats else "—"))
        add("- **시차 관찰**: 1회 관측으로는 판단하지 않는다. 다음 주차 누적 후 평가.")
    else:
        add("이번 주 국가 간 공통 신호 없음 — 비교 가능한 국가가 2개 미만이다.")
    add("")
    add("---")
    add("")

    # WATCH LIST
    add("# WATCH LIST — 다음 주 확인 필요")
    add("")
    add("| # | 확인할 것 | 왜 | 언제까지 |")
    add("|---|---|---|---|")
    watch = a.get("watch_items") or []
    if watch:
        for n, w in enumerate(watch[:12], start=1):
            add("| %d | [%s] %s | %s | 다음 회차 |"
                % (n, w.get("country", "—"), w.get("what", ""), w.get("why", "")))
    else:
        add("| 1 | 이번 회차에 남긴 Watch Item 없음 | — | — |")
    add("")
    add("---")
    add("")

    # COVERAGE LOG
    add("# COVERAGE LOG")
    add("")
    add("| 소스 | 상태 | 사용 기사 수 | Fallback 시도 / 비고 |")
    add("|---|---|---|---|")
    used_by_source = {}
    for i in a["general_issues"] + a["beauty_issues"]:
        for m in i.get("media", []):
            used_by_source[m] = used_by_source.get(m, 0) + 1
    for s in collected["sources"]:
        note = " / ".join(s.get("notes") or []) or "—"
        add("| %s | %s | %d | %s |"
            % (s["name"], s["status"], used_by_source.get(s["name"], 0),
               C.truncate(note, 180)))
    add("")
    price_cov = []
    for code, label in COUNTRY_TITLES:
        rows = a["products"].get(code) or []
        v = sum(1 for p in rows if p["price_state"] == "Verified")
        price_cov.append("%s %d/%d" % (label[:2], v, len(rows)))
    add("**Price 커버리지**: %s (Verified 기준)" % " · ".join(price_cov))
    add("")
    add("> Fallback 1(검색엔진 도메인 한정 질의)은 자동 실행하지 않았다. "
        "목록 페이지·페이지네이션·대체 경로(Fallback 2~5)만 시도했다.")
    add("")
    add("---")
    add("")

    add("# QA METRICS")
    add("")
    add(QA_PLACEHOLDER)
    add("")
    add("---")
    add("")

    # SOURCES
    add("# SOURCES")
    add("")
    add("## AXIS 1")
    add("")
    for i in a["general_issues"]:
        add("- [%s](%s) — %s, %s, Tier %s"
            % (C.truncate(i["headline"], 90), i["url"], i["source_name"],
               i["published"], i["tier"]))
    if not a["general_issues"]:
        add("- No Significant News")
    add("")
    add("## AXIS 2")
    add("")
    for i in a["beauty_issues"]:
        add("- [%s](%s) — %s, %s, Tier %s"
            % (C.truncate(i["headline"], 90), i["url"], i["source_name"],
               i["published"], i["tier"]))
    if not a["beauty_issues"]:
        add("- No Significant News")
    add("")
    add("## New Product Watch")
    add("")
    seen = set()
    for code, _ in COUNTRY_TITLES:
        for p in (a["products"].get(code) or []):
            if p["url"] in seen:
                continue
            seen.add(p["url"])
            add("- [%s %s](%s) — %s, %s, Tier %s"
                % (p["brand"], p["product"], p["url"], p["source_name"],
                   p["published"], p["tier"]))
    if not seen:
        add("- Not Checked")
    add("")
    return "\n".join(L) + "\n"


# ── Compact Email HTML ──────────────────────────────────────────
def _tag_chip(tag):
    colors = {"FACT": "#2f6b4f", "CLAIM": "#a0522d",
              "MEDIA": "#5a6b8a", "ANALYSIS": "#6b4f8a"}
    color = colors.get(tag, MUTED)
    return (
        '<span style="border:1px solid %s;color:%s;border-radius:3px;'
        'padding:0 4px;font-size:10px;font-weight:700;">%s</span>'
        % (color, color, C.esc(tag))
    )


def _section_head(title):
    return (
        '<tr><td style="padding:20px 22px 2px;"><div style="font-size:17px;'
        'font-weight:700;border-bottom:1px solid %s;padding-bottom:6px;">%s'
        "</div></td></tr>" % (LINE, C.esc(title))
    )


def build_html(a, collected):
    start = collected["coverage"]["start_kst"][:10]
    end = collected["coverage"]["end_kst"][:10]
    H = []
    add = H.append

    add("<!doctype html>")
    add('<html lang="ko"><head><meta charset="utf-8">')
    add('<meta name="viewport" content="width=device-width, initial-scale=1">')
    add("<title>[TEST] WEEKLY INTELLIGENCE %s</title></head>" % C.esc(a["weekly_id"]))
    add('<body style="margin:0;padding:0;background:#f4f2ee;">')
    add('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f4f2ee;"><tr><td align="center" '
        'style="padding:16px 12px;">')
    add('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" '
        'style="max-width:640px;background:#ffffff;border-radius:10px;'
        "overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "'Malgun Gothic','Apple SD Gothic Neo',sans-serif;color:%s;\">" % INK)

    # Header
    add('<tr><td style="padding:22px 22px 15px;border-bottom:3px solid %s;">' % BRAND)
    add('<div style="font-size:11px;letter-spacing:.14em;color:%s;font-weight:700;">'
        "WEEKLY INTELLIGENCE · GA-3 TEST</div>" % BRAND)
    add('<div style="font-size:23px;font-weight:700;margin:5px 0;">%s</div>'
        % C.esc(a["weekly_id"]))
    add('<div style="font-size:13px;color:%s;">분석기간 <strong style="color:%s;">'
        "%s ~ %s</strong></div>" % (MUTED, INK, start, end))
    add('<div style="font-size:11.5px;color:%s;margin-top:9px;line-height:1.8;">'
        "%s 공식 발표·통계 · %s 기업 주장(미검증) · %s 매체 해석 · %s 본 브리프의 해석"
        "</div>" % (MUTED, _tag_chip("FACT"), _tag_chip("CLAIM"),
                    _tag_chip("MEDIA"), _tag_chip("ANALYSIS")))
    add("</td></tr>")

    # MUST KNOW
    add(_section_head("1. WEEKLY MUST KNOW"))
    if a["must_know"]:
        circled = "①②③④⑤⑥⑦⑧⑨⑩"
        for row in a["must_know"]:
            mark = circled[row["rank"] - 1] if row["rank"] <= 10 else str(row["rank"])
            add('<tr><td style="padding:12px 22px 0;">')
            add('<div style="font-size:15px;font-weight:700;color:%s;">%s %s</div>'
                % (BRAND, mark, C.esc(row["headline"])))
            add('<div style="font-size:13.8px;line-height:1.6;margin-top:4px;">'
                "%s %s</div>" % (C.esc(row["what_changed"]), _tag_chip(row["tag"])))
            if row["why_it_matters"]:
                add('<div style="font-size:13.3px;color:#4a4842;margin-top:5px;">'
                    "%s <strong>Why:</strong> %s</div>"
                    % (_tag_chip("ANALYSIS"), C.esc(row["why_it_matters"])))
            add('<div style="font-size:12.3px;margin-top:3px;">'
                '<a href="%s" style="color:%s;">%s (%s)</a>%s</div>'
                % (C.esc(row["url"]), BRAND, C.esc(row["source_name"]),
                   C.esc(row["published"]),
                   "" if row["tier1_backed"] else
                   ' <span style="color:%s;font-size:11px;">· %s</span>'
                   % (MUTED, TIER1_NOTE)))
            add("</td></tr>")
    else:
        add('<tr><td style="padding:12px 22px 0;font-size:13.5px;">'
            "이번 주는 특기할 변화가 없었다 — 선별 기준을 충족한 항목이 없다.</td></tr>")

    # AXIS 1
    add(_section_head("2. AXIS 1 — 경제 · 산업 · 유통 · 정책 · 해외"))
    if a["general_issues"]:
        for key, title in A1_TITLES:
            rows = [i for i in a["general_issues"] if i.get("section") == key]
            if not rows:
                continue
            add('<tr><td style="padding:11px 22px 0;">')
            add('<div style="font-size:12px;font-weight:700;color:%s;'
                'letter-spacing:.06em;">%s</div>' % (MUTED, C.esc(title)))
            for i in rows:
                add('<div style="font-size:13.6px;line-height:1.6;margin-top:5px;">'
                    "<strong>%s</strong> — %s %s</div>"
                    % (C.esc(i["headline"]), C.esc(i["what_changed"]),
                       _tag_chip(i["tag"])))
                if i.get("why_it_matters"):
                    add('<div style="font-size:12.8px;color:#4a4842;">%s %s</div>'
                        % (_tag_chip("ANALYSIS"), C.esc(i["why_it_matters"])))
                add('<div style="font-size:12px;"><a href="%s" style="color:%s;">'
                    "%s</a></div>"
                    % (C.esc(i["url"]), BRAND, C.esc(source_label(i))))
            add("</td></tr>")
    else:
        add('<tr><td style="padding:12px 22px 0;font-size:13.5px;">'
            "No Significant News</td></tr>")

    # AXIS 2
    add(_section_head("3. AXIS 2 — BEAUTY INDUSTRY"))
    if a["beauty_issues"]:
        for key, title in A2_TITLES:
            rows = [i for i in a["beauty_issues"] if i.get("section") == key]
            if not rows:
                continue
            add('<tr><td style="padding:11px 22px 0;">')
            add('<div style="font-size:12px;font-weight:700;color:%s;'
                'letter-spacing:.06em;">%s</div>' % (MUTED, C.esc(title)))
            for i in rows:
                add('<div style="font-size:13.6px;line-height:1.6;margin-top:5px;">'
                    "<strong>%s</strong> — %s %s</div>"
                    % (C.esc(i["headline"]), C.esc(i["what_changed"]),
                       _tag_chip(i["tag"])))
                for lab, key2 in (("숫자", "numbers"), ("맥락", "context")):
                    if i.get(key2):
                        add('<div style="font-size:12.8px;color:#4a4842;">'
                            "<strong>%s</strong> %s</div>"
                            % (lab, C.esc(i[key2])))
                if i.get("implication"):
                    add('<div style="font-size:12.8px;color:#4a4842;">%s %s</div>'
                        % (_tag_chip("ANALYSIS"), C.esc(i["implication"])))
                add('<div style="font-size:12px;"><a href="%s" style="color:%s;">'
                    "%s</a></div>"
                    % (C.esc(i["url"]), BRAND, C.esc(source_label(i))))
            add("</td></tr>")
    else:
        add('<tr><td style="padding:12px 22px 0;font-size:13.5px;">'
            "No Significant News</td></tr>")

    # NEW PRODUCT WATCH
    add(_section_head("4. NEW PRODUCT WATCH (국가별 분리)"))
    for code, label in COUNTRY_TITLES:
        rows = a["products"].get(code) or []
        add('<tr><td style="padding:12px 22px 0;">')
        add('<div style="font-size:13px;font-weight:700;color:%s;">%s — %d건</div>'
            % (BRAND, label, len(rows)))
        if rows:
            add('<table role="presentation" width="100%" cellpadding="0" '
                'cellspacing="0" style="font-size:12.2px;margin-top:5px;">')
            for p in rows:
                add('<tr><td style="padding:4px 0;border-bottom:1px solid %s;">'
                    "<strong>%s</strong> %s<br>"
                    '<span style="color:%s;">%s · %s · %s</span><br>'
                    '<a href="%s" style="color:%s;">%s</a></td></tr>'
                    % (LINE, C.esc(p["brand"]), C.esc(p["product"]), MUTED,
                       C.esc(p["category"]), C.esc(price_text(p)),
                       C.esc(p["channel"]), C.esc(p["url"]), BRAND,
                       C.esc(p["source_name"])))
            add("</table>")
        else:
            add('<div style="font-size:12.5px;color:%s;margin-top:4px;">'
                "이번 회차 선정 기준 충족 신제품 미확인</div>" % MUTED)
        sig = (a.get("signals") or {}).get(code)
        if sig:
            ev = sig["evidence"]
            add('<div style="font-size:12.5px;margin-top:6px;">'
                "<strong>Trend Signal</strong> — %s<br>"
                '<span style="color:#4a4842;">Observation: %s</span><br>'
                '<span style="color:#4a4842;">Interpretation: %s</span><br>'
                '<span style="color:%s;">Evidence 브랜드 %d / 제품 %d / 근거 %d '
                "· 조건 %s · Confidence <strong>%s</strong> · 직전 주 %s</span></div>"
                % (C.esc(sig["name"]), C.esc(sig["observation"]),
                   C.esc(sig["interpretation"]), MUTED, ev["brand_count"],
                   ev["product_count"], len(ev["source_item_ids"]),
                   ev["condition"], C.esc(sig["confidence"]),
                   C.esc(sig.get("vs_prev_week", "—"))))
        else:
            add('<div style="font-size:12.5px;color:%s;margin-top:6px;">'
                "<strong>Trend Signal</strong> — 이번 주 유의미한 Signal 없음 "
                "(조건 A·B 미충족)</div>" % MUTED)
        add("</td></tr>")

    # Coverage + QA
    add(_section_head("5. COVERAGE & QA"))
    add('<tr><td style="padding:12px 22px 0;font-size:12.4px;line-height:1.7;">')
    beauty = [s for s in collected["sources"] if s["axis"] == "BEAUTY"]
    add("<strong>Beauty 전문매체 5곳</strong><br>")
    for s in beauty:
        add("· %s — %s<br>" % (C.esc(s["name"]), C.esc(s["status"])))
    add("<br><strong>QA</strong><br>")
    add(QA_EMAIL_PLACEHOLDER)
    add("</td></tr>")

    # Footer
    add('<tr><td style="padding:18px 22px 22px;color:%s;font-size:11.5px;'
        'line-height:1.7;border-top:1px solid %s;">' % (MUTED, LINE))
    add("이 메일은 <strong>GA-3 End-to-End 수동 테스트</strong> 산출물이다 "
        "(제목에 [TEST] 표기). 정기 발송이 아니며 스케줄은 활성화되지 않았다.<br>")
    add("Coverage %s ~ %s KST · Issued %s KST" % (start, end, C.stamp_kst()))
    add("</td></tr>")

    add("</table></td></tr></table></body></html>")
    return "\n".join(H) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collected", required=True)
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    collected = C.read_json(args.collected)
    a = C.read_json(args.analysis)
    weekly = a["weekly_id"]

    md_path = os.path.join(args.out_dir, "%s_gemini.md" % weekly)
    html_path = os.path.join(args.out_dir, "%s_gemini.html" % weekly)

    C.write_text(md_path, build_markdown(a, collected))
    C.write_text(html_path, build_html(a, collected))

    print("brief  -> %s" % md_path)
    print("email  -> %s" % html_path)
    C.append_summary(
        "### STEP 3 — 조립\n\n"
        "- Weekly Brief: `%s`\n- Compact Email: `%s`\n"
        "- 기준선 파일(01_WEEKLY_BRIEFS) 쓰기: **없음**\n"
        % (os.path.basename(md_path), os.path.basename(html_path))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
