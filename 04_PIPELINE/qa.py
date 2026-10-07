# -*- coding: utf-8 -*-
"""GA-3 STEP 4 — QA. CLAUDE.md 8-2 의 14지표와 send_gate.md 3-1 의 Critical C1~C7.

- 지표를 계산하고 Brief·Email 의 QA 자리표시자를 채운다.
- Critical 이 하나라도 FAIL 이면 gate.py 가 발송을 막는다 (G3). QA 는 판정만 한다.
- 기준을 낮춰 통과시키지 않는다.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import sources as S  # noqa: E402
from build import (  # noqa: E402
    COUNTRY_TITLES, QA_EMAIL_PLACEHOLDER, QA_PLACEHOLDER, TIER1_NOTE,
)

FORBIDDEN_PATTERNS = [
    # 윈도우 경로는 역슬래시 형태만 본다. `https:/` 를 오탐하지 않기 위함이다.
    (r"(?<![A-Za-z])[A-Za-z]:\\", "로컬 경로(윈도우)"),
    (r"/home/runner|/Users/|RUNNER_TEMP", "로컬 경로(러너)"),
    (r"GMAIL_APP_PASSWORD|APP_PASSWORD|GEMINI_API_KEY|x-goog-api-key|Bearer\s",
     "인증정보 흔적"),
    (r"WIB_RECIPIENT", "수신자 환경변수명"),
]
EXTERNAL_ASSET_RE = re.compile(
    r"<link\b|<script\b|<img\b|url\(|@import|srcset=", re.I
)


def pct(n, d):
    return 0.0 if not d else round(100.0 * n / d, 1)


def collect_qa(collected, analysis, md, html):
    weekly = analysis["weekly_id"]
    general = analysis["general_issues"]
    beauty = analysis["beauty_issues"]
    used = general + beauty
    products = analysis["products"]
    signals = analysis.get("signals") or {}
    sources = collected["sources"]

    # ── 1~8 ─────────────────────────────────────────────────────
    m_collected = collected["stats"]["collected_total"]
    m_after_dedup = collected["stats"]["after_dedup"]
    m_used = len(used)
    m_noise = (collected["stats"]["noise_excluded"]
               + analysis["verification"]["excluded_by_rule"])

    quant_issues = [i for i in used
                    if C.numbers_in(" ".join(str(i.get(k) or "") for k in
                                             ("what_changed", "numbers",
                                              "why_it_matters", "headline")))]
    tier1_direct = sum(1 for i in used if i.get("tier1_backed"))
    tier1_rate = pct(sum(1 for i in quant_issues if i.get("tier1_backed")),
                     len(quant_issues))
    tier2_used = sum(1 for i in used if i["tier"] == 2)
    tier3_used = sum(1 for i in used if i["tier"] == 3)

    # ── 9~10 Beauty 매체 ────────────────────────────────────────
    beauty_rows = []
    used_by_media = {}
    for i in beauty:
        for mname in i.get("media", []):
            used_by_media[mname] = used_by_media.get(mname, 0) + 1
    for sid in S.BEAUTY_MEDIA_IDS:
        src = next((s for s in sources if s["id"] == sid), None)
        name = src["name"] if src else sid
        beauty_rows.append({
            "name": name,
            "status": src["status"] if src else "Not Checked",
            "used": used_by_media.get(name, 0),
        })
    reflected = [r for r in beauty_rows if r["used"] > 0]
    not_checked = [r for r in beauty_rows if r["status"] == "Not Checked"]
    total_beauty_used = sum(r["used"] for r in beauty_rows) or 0
    ranked = sorted(beauty_rows, key=lambda r: -r["used"])
    top1 = pct(ranked[0]["used"], total_beauty_used) if ranked else 0.0
    top2 = pct(sum(r["used"] for r in ranked[:2]), total_beauty_used)
    concentration_warning = top1 > 50.0 or top2 > 80.0

    # ── 11 Article URL 확보율 ───────────────────────────────────
    url_targets = [i.get("url", "") for i in used]
    for code, _ in COUNTRY_TITLES:
        url_targets += [p.get("url", "") for p in (products.get(code) or [])]
    url_ok = sum(1 for u in url_targets if (u or "").startswith("http"))
    url_rate = pct(url_ok, len(url_targets))

    # ── 12~14 ───────────────────────────────────────────────────
    product_counts = {code: len(products.get(code) or [])
                      for code, _ in COUNTRY_TITLES}
    signal_rows = []
    for code, label in COUNTRY_TITLES:
        sig = signals.get(code)
        if not sig:
            signal_rows.append("%s: Signal 없음 (조건 A·B 미충족)" % label)
            continue
        ev = sig["evidence"]
        signal_rows.append(
            "%s: %s — 브랜드 %d / 제품 %d / 근거 %d · 조건 %s · %s"
            % (label, sig["name"], ev["brand_count"], ev["product_count"],
               len(ev["source_item_ids"]), ev["condition"], sig["confidence"])
        )
    blocked = [s["name"] for s in sources if s["status"] == "Access Blocked"]
    partial = [s["name"] for s in sources if s["status"] == "Partial Access"]

    # ── Critical C1~C7 ──────────────────────────────────────────
    start, end = C.coverage_window(weekly)
    c1 = (collected["coverage"]["start_kst"] == start.isoformat()
          and collected["coverage"]["end_kst"] == end.isoformat())

    mk = analysis["must_know"]
    c2 = bool(mk) and all((r.get("url") or "").startswith("http") for r in mk)

    c3 = (len(not_checked) == 0) and (len(reflected) >= 3)

    section_heads = sum(
        1 for _, label in COUNTRY_TITLES
        if ("## %s NEW PRODUCT WATCH" % label) in md
    )
    # C4 는 "국가 섹션이 섞이지 않았는가"를 본다. 각 신제품의 국가는 모델 판단이 아니라
    # 수집 Source 의 국가이므로, 섹션 코드와 Source 국가가 일치하는지로 검증한다.
    misplaced = [
        "%s/%s(%s)" % (code, p.get("brand"), p.get("source_country"))
        for code, _ in COUNTRY_TITLES
        for p in (products.get(code) or [])
        if p.get("source_country") and p.get("source_country") != code
    ]
    c4 = section_heads == 3 and not misplaced

    # 같은 제품이 두 나라에 동시에 올라온 경우 — 실패가 아니라 사람이 볼 표시다
    # (글로벌 동시 출시일 수 있다).
    keys_by_country = {
        code: {(p["brand"], p["product"]) for p in (products.get(code) or [])}
        for code, _ in COUNTRY_TITLES
    }
    codes = [c for c, _ in COUNTRY_TITLES]
    cross_listed = 0
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            cross_listed += len(keys_by_country[codes[i]] & keys_by_country[codes[j]])

    c5 = url_rate >= 80.0

    required_notes = sum(
        1 for i in used
        if i in quant_issues and not i.get("tier1_backed")
    ) + sum(1 for r in mk if not r.get("tier1_backed"))
    c6 = md.count(TIER1_NOTE) >= required_notes

    forbidden_hits = []
    for body, where in ((md, "brief"), (html, "email")):
        for pat, label in FORBIDDEN_PATTERNS:
            if re.search(pat, body):
                forbidden_hits.append("%s: %s" % (where, label))
        found = C.ANY_EMAIL_RE.search(body)
        if found:
            forbidden_hits.append("%s: 메일 주소 평문" % where)
    c7 = not forbidden_hits

    numbers_removed = analysis["verification"]["numbers_removed"]
    critical = {
        "C1_coverage_window": c1,
        "C2_must_know_urls": c2,
        "C3_beauty_media": c3,
        "C4_country_split": c4,
        "C5_url_rate_80": c5,
        "C6_tier1_notation": c6,
        "C7_forbidden_content": c7,
    }
    critical_fails = [k for k, v in critical.items() if not v]

    metrics = [
        ("1", "전체 수집 기사 수", str(m_collected)),
        ("2", "중복 제거 후 Issue 수", str(m_after_dedup)),
        ("3", "최종 사용 Issue 수", str(m_used)),
        ("4", "제외된 Noise 기사 수", "%d (규칙 %d + 2-of-5 미달 %d)"
         % (m_noise, collected["stats"]["noise_excluded"],
            analysis["verification"]["excluded_by_rule"])),
        ("5", "Tier 1 직접 확인 수", str(tier1_direct)),
        ("6", "Tier 1 verification rate", "%.1f%% (정량 Issue %d건 기준)"
         % (tier1_rate, len(quant_issues))),
        ("7", "Tier 2 사용 수", str(tier2_used)),
        ("8", "Tier 3 사용 수", str(tier3_used)),
        ("9", "Beauty 전문매체 5개 상태",
         " / ".join("%s: %s" % (r["name"], r["status"]) for r in beauty_rows)),
        ("10", "Beauty Source concentration",
         "1위 %.1f%% · 상위2 %.1f%% → %s"
         % (top1, top2,
            "SOURCE CONCENTRATION WARNING" if concentration_warning else "경고 없음")),
        ("11", "개별 Article URL 확보율", "%.1f%% (%d/%d)"
         % (url_rate, url_ok, len(url_targets))),
        ("12", "신제품 수 KR / US / JP", "%d / %d / %d"
         % (product_counts["KR"], product_counts["US"], product_counts["JP"])),
        ("13", "Trend Signal별 Evidence Count", " · ".join(signal_rows)),
        ("14", "Access Blocked Source", ", ".join(blocked) if blocked else "없음"),
    ]

    usage = analysis.get("usage") or {}
    extra = [
        ("A", "Gemini 호출 수 / 예산", "%s / %s (절대 상한 %s)"
         % (usage.get("calls"), usage.get("budget"), usage.get("hard_cap"))),
        ("B", "Gemini attempt / retry", "%s회 시도 / %s회 재시도 (단계당 최대 %s회, "
         "backoff %s초)"
         % (usage.get("attempts"), usage.get("retries"),
            usage.get("max_attempts_per_stage"), usage.get("backoff_schedule"))),
        ("B2", "마지막 HTTP status / final category", "%s / %s"
         % (usage.get("last_http_status"), usage.get("final_category") or "OK")),
        ("B3", "timeout seconds / backoff history", "%s초 / %s"
         % (usage.get("timeout_seconds"),
            usage.get("backoff_waits") or "없음")),
        ("C", "모델 (primary / fallback / 실사용)", "%s / %s / **%s**"
         % (usage.get("primary_model"), usage.get("fallback_model"),
            usage.get("model_used"))),
        ("C2", "fallback triggered", "%s (primary %s회 / fallback %s회)"
         % ("YES" if usage.get("fallback_triggered") else "NO",
            usage.get("primary_attempts"), usage.get("fallback_attempts"))),
        ("D", "숫자 검증 삭제(미검증 수치)", str(numbers_removed)),
        ("E", "Signal 강등(조건 미달)", str(analysis["verification"]["signals_demoted"])),
        ("F", "규격 위반 교정(Price enum·Observation 혼입)",
         str(analysis["verification"]["spec_violations"])),
        ("G", "Partial Access Source", ", ".join(partial) if partial else "없음"),
        ("H", "2개국 이상 중복 등재 신제품", "%d건%s"
         % (cross_listed,
            " — 글로벌 동시 출시 여부 사람이 확인" if cross_listed else "")),
        ("I", "국가 섹션 불일치 신제품", ", ".join(misplaced) if misplaced else "0건"),
    ]

    email_lines = [
        "Beauty 반영 매체 %d/5 · Not Checked %d" % (len(reflected), len(not_checked)),
        "Article URL 확보율 %.1f%% · Tier 1 직접 확인 %d건" % (url_rate, tier1_direct),
        "신제품 KR %d / US %d / JP %d" % (product_counts["KR"],
                                          product_counts["US"],
                                          product_counts["JP"]),
        "Gemini 호출 %s회 (상한 %s) · 재시도 %s"
        % (usage.get("calls"), usage.get("hard_cap"), usage.get("retries")),
        "Critical QA: %s" % ("ALL PASS" if not critical_fails
                             else "FAIL " + ", ".join(critical_fails)),
    ]

    return {
        "weekly_id": weekly,
        "generated_at_utc": C.stamp_utc(),
        "metrics": metrics,
        "extra": extra,
        "critical": critical,
        "critical_fails": critical_fails,
        "forbidden_hits": forbidden_hits,
        "beauty_rows": beauty_rows,
        "concentration": {"top1_pct": top1, "top2_pct": top2,
                          "warning": concentration_warning},
        "url_rate": url_rate,
        "tier1_direct": tier1_direct,
        "tier1_rate": tier1_rate,
        "product_counts": product_counts,
        "numbers_removed": numbers_removed,
        "signal_rows": signal_rows,
        "access_blocked": blocked,
        "partial_access": partial,
        "used_issues": m_used,
        "email_lines": email_lines,
        "usage": usage,
    }


def render_md_table(qa):
    L = ["| # | 지표 | 값 |", "|---|---|---|"]
    for num, name, value in qa["metrics"]:
        L.append("| %s | %s | %s |" % (num, name, value))
    L.append("")
    L.append("**GA-3 추가 계측**")
    L.append("")
    L.append("| # | 지표 | 값 |")
    L.append("|---|---|---|")
    for num, name, value in qa["extra"]:
        L.append("| %s | %s | %s |" % (num, name, value))
    L.append("")
    L.append("**Critical QA (send_gate.md 3-1)**")
    L.append("")
    L.append("| ID | 결과 |")
    L.append("|---|---|")
    for key, ok in qa["critical"].items():
        L.append("| %s | **%s** |" % (key, "PASS" if ok else "FAIL"))
    L.append("")
    L.append("- Critical FAIL: **%d건**%s"
             % (len(qa["critical_fails"]),
                "" if not qa["critical_fails"]
                else " — " + ", ".join(qa["critical_fails"])))
    if qa["forbidden_hits"]:
        L.append("- 금지 내용 탐지: %s" % ", ".join(qa["forbidden_hits"]))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collected", required=True)
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    collected = C.read_json(args.collected)
    analysis = C.read_json(args.analysis)
    weekly = analysis["weekly_id"]

    md_path = os.path.join(args.out_dir, "%s_gemini.md" % weekly)
    html_path = os.path.join(args.out_dir, "%s_gemini.html" % weekly)
    with open(md_path, "r", encoding="utf-8") as fh:
        md = fh.read()
    with open(html_path, "r", encoding="utf-8") as fh:
        html = fh.read()

    qa = collect_qa(collected, analysis, md, html)

    md = md.replace(QA_PLACEHOLDER, render_md_table(qa))
    html = html.replace(
        QA_EMAIL_PLACEHOLDER,
        "".join("· %s<br>" % C.esc(line) for line in qa["email_lines"]),
    )
    # 이메일 HTML 은 인라인 스타일만 — 외부 자원 참조가 생겼는지 다시 본다 (G2 보조).
    qa["email_external_assets"] = bool(EXTERNAL_ASSET_RE.search(html))

    C.write_text(md_path, md)
    C.write_text(html_path, html)
    C.write_json(os.path.join(args.out_dir, "qa.json"), qa)
    C.write_text(os.path.join(args.out_dir, "qa_summary.md"), render_md_table(qa))

    C.append_summary("### STEP 4 — QA\n\n" + render_md_table(qa))
    print("QA: critical_fails=%d url_rate=%.1f%% beauty_reflected=%d"
          % (len(qa["critical_fails"]), qa["url_rate"],
             sum(1 for r in qa["beauty_rows"] if r["used"] > 0)))
    # QA 자체는 실패로 종료하지 않는다. 발송 차단은 gate.py 가 판정한다.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
