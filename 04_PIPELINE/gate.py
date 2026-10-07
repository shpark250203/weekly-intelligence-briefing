# -*- coding: utf-8 -*-
"""GA-3 STEP 5 — 발송 Gate. send_gate.md 의 집행판.

GA-3 의 위치 (중요)
- GA-3 는 **정식 발송을 하지 않는다.** 보내는 것은 `[TEST]` 접두가 붙은 테스트 메일
  1통뿐이며, 이는 send_gate.md §1-2 가 허용하는 LOCAL MODE 수동 테스트 경로다
  (GA-2C 와 같은 성격, 원장 Status=TEST — §4-3 에 따라 중복 판정 대상이 아니다).
- 따라서 **G0(CLOUD_MODE)을 우회하지 않는다.** G0 은 조회해서 기록하고,
  값이 `true` 가 아니면 모드를 LOCAL 로 기록한다. GA-3 는 어느 경우에도 TEST 로만 보낸다.
  정식 발송(`[WEEKLY INTELLIGENCE]` 제목·Status=SENT)은 GA-4 사안이며 이 코드에 없다.
- 발송 승인의 근거는 **사용자가 workflow_dispatch 입력에 직접 넣은 확인 문자열**이다
  (§1-2 "사용자의 명시적 승인"). 저장소 파일·프롬프트는 승인 근거가 아니다.

FAIL CLOSED — 판단이 서지 않으면 보내지 않는다.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

CONFIRM_TOKEN = "SEND-TEST"
REQUIRED_MD_SECTIONS = [
    "# WEEKLY MUST KNOW",
    "# AXIS 1 — GENERAL WEEKLY INTELLIGENCE",
    "# AXIS 2 — BEAUTY INDUSTRY INTELLIGENCE",
    "## KOREA NEW PRODUCT WATCH",
    "## USA NEW PRODUCT WATCH",
    "## JAPAN NEW PRODUCT WATCH",
    "# QA METRICS",
]
EXTERNAL_ASSET_MARKERS = ["<link", "<script", "<img", "@import", "srcset="]


def read_ledger(path):
    rows = []
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekly-id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--repo-root", required=True)
    args = ap.parse_args()

    weekly = args.weekly_id
    md_path = os.path.join(args.out_dir, "%s_gemini.md" % weekly)
    html_path = os.path.join(args.out_dir, "%s_gemini.html" % weekly)
    qa_path = os.path.join(args.out_dir, "qa.json")

    gates, notes = {}, []

    # ── G0 — runtime CLOUD_MODE 직접 조회 (§1-1-1 EVIDENCE RULE) ──
    # 프로세스 환경변수만 근거로 삼는다. 저장소 문자열은 근거가 아니다.
    cloud_raw = os.environ.get("CLOUD_MODE")
    cloud_present = cloud_raw is not None
    mode = "CLOUD" if cloud_raw == "true" else "LOCAL"
    gates["G0_cloud_mode_true"] = (cloud_raw == "true")
    notes.append(
        "G0 근거: 프로세스 환경변수 CLOUD_MODE %s → 모드 %s"
        % ("미설정" if not cloud_present else
           ("정확히 'true'" if cloud_raw == "true" else "값이 'true' 가 아님"), mode)
    )
    notes.append(
        "GA-3 는 모드와 무관하게 [TEST] 메일만 보낸다. 정식 발송 경로는 이 코드에 없다."
    )

    # ── G1 — Weekly Brief 생성 ───────────────────────────────────
    md = ""
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as fh:
            md = fh.read()
    missing = [s for s in REQUIRED_MD_SECTIONS if s not in md]
    gates["G1_brief_built"] = bool(md) and not missing
    if missing:
        notes.append("G1 누락 섹션: %s" % ", ".join(missing))

    # ── G2 — Compact Email 생성 (인라인 스타일만) ────────────────
    html = ""
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as fh:
            html = fh.read()
    external = [m for m in EXTERNAL_ASSET_MARKERS if m in html.lower()]
    gates["G2_email_built"] = bool(html) and not external
    if external:
        notes.append("G2 외부 자원 참조 발견: %s" % ", ".join(external))

    # ── G3 — Critical QA FAIL = 0 ───────────────────────────────
    qa = C.read_json(qa_path) if os.path.exists(qa_path) else None
    if qa is None:
        gates["G3_critical_qa"] = False
        notes.append("G3 판정 불가 — qa.json 없음 (FAIL CLOSED)")
        critical_fails = ["QA_MISSING"]
    else:
        critical_fails = qa.get("critical_fails") or []
        gates["G3_critical_qa"] = not critical_fails
        if critical_fails:
            notes.append("G3 Critical FAIL: %s" % ", ".join(critical_fails))

    # ── G4 — 수신자 환경변수 ────────────────────────────────────
    rcpt_raw = os.environ.get("WIB_RECIPIENT", "")
    rcpt = rcpt_raw.strip()
    single = ("," not in rcpt_raw) and (";" not in rcpt_raw)
    gates["G4_recipient"] = bool(rcpt) and single and bool(C.EMAIL_RE.match(rcpt))
    notes.append("G4 수신자: %s" % (C.mask_email(rcpt) if rcpt else "미설정"))

    # ── G5 — Gmail 인증 ────────────────────────────────────────
    # 인증은 발송 단계에서만 확인할 수 있다. gmail_send.py 가 AUTH 실패 시
    # send_message 를 호출하지 않는 구조(FAIL CLOSED)를 유지한다.
    gates["G5_smtp_auth"] = None
    notes.append("G5: 발송 단계에서 판정 (AUTH 실패 시 발송 호출 자체를 하지 않음)")

    # ── G6 / G7 — 중복 발송 확인 ───────────────────────────────
    ledger_path = os.path.join(args.repo_root, "00_SYSTEM", "send_ledger.csv")
    ledger = read_ledger(ledger_path)
    gmail_query_available = False   # 러너에는 Gmail 조회 경로가 없다 (SMTP 전용)
    gates["G6_duplicate_check_done"] = ledger is not None
    if ledger is None:
        notes.append("G6 실패 — 발송 원장을 읽지 못했다 (FAIL CLOSED)")
    else:
        notes.append(
            "G6: 원장 %d행 확인 완료. Gmail 조회는 러너에서 불가(SMTP 전용)이며, "
            "GA-3 는 Status=TEST 발송이라 §4-3 에 따라 중복 판정 대상이 아니다. "
            "정식 발송의 2중 확인은 GA-4 에서 Gmail 조회 경로를 붙여 충족시킨다."
            % len(ledger)
        )

    force = os.environ.get("FORCE_RESEND", "").strip()
    sent_rows = [r for r in (ledger or [])
                 if r.get("WeeklyID") == weekly and r.get("Status") == "SENT"]
    ga3_test_rows = [r for r in (ledger or [])
                     if r.get("WeeklyID") == weekly
                     and r.get("Status") == "TEST"
                     and "GA-3" in (r.get("Note") or "")]
    if sent_rows:
        gates["G7_no_duplicate"] = False
        notes.append("G7: 같은 주차에 정식 발송(SENT) 기록이 있다 → 발송하지 않는다")
    elif ga3_test_rows and force != weekly:
        gates["G7_no_duplicate"] = False
        notes.append(
            "G7: 같은 주차의 GA-3 TEST 발송 기록이 있다. 다시 보내려면 "
            "FORCE_RESEND=%s 를 명시해야 한다" % weekly
        )
    else:
        gates["G7_no_duplicate"] = True
        if force:
            notes.append("G7: FORCE_RESEND=%s 적용 (G1~G6 은 면제되지 않는다)" % force)

    # ── 사용자 명시적 승인 ──────────────────────────────────────
    confirm = os.environ.get("GA3_CONFIRM_SEND", "")
    gates["GC_user_confirm"] = (confirm == CONFIRM_TOKEN)
    if not gates["GC_user_confirm"]:
        notes.append(
            "확인 입력이 '%s' 와 정확히 일치하지 않는다 → 메일을 보내지 않는다 "
            "(산출물만 남긴다)" % CONFIRM_TOKEN
        )

    # ── 판정 ───────────────────────────────────────────────────
    blocking = ["G1_brief_built", "G2_email_built", "G3_critical_qa",
                "G4_recipient", "G6_duplicate_check_done", "G7_no_duplicate"]
    failed = [g for g in blocking if not gates[g]]
    if failed:
        decision = "BLOCKED_" + failed[0]
    elif not gates["GC_user_confirm"]:
        decision = "SKIPPED_NO_CONFIRM"
    else:
        decision = "SEND_TEST"

    subject = "[TEST] WEEKLY INTELLIGENCE — %s (GA-3 E2E)" % weekly
    result = {
        "weekly_id": weekly,
        "generated_at_utc": C.stamp_utc(),
        "mode": mode,
        "cloud_mode_present": cloud_present,
        "gates": gates,
        "failed_gates": failed,
        "critical_fails": critical_fails,
        "decision": decision,
        "send_class": "TEST",
        "subject": subject,
        "brief_path": md_path,
        "email_path": html_path,
        "gmail_query_available": gmail_query_available,
        "notes": notes,
        "ledger_row_suggestion": {
            "WeeklyID": weekly,
            "Mode": mode,
            "Status": "TEST" if decision == "SEND_TEST" else decision,
            "SentAtKST": C.stamp_kst(),
            "SentAtUTC": C.stamp_utc(),
            "Subject": subject,
            "GmailMessageId": "—",
            "GateResult": ("G1,G2,G3,G4,G6,G7 PASS" if not failed
                           else ",".join(failed) + " FAIL"),
            "Note": "GA-3 End-to-End 수동 테스트. TEST는 중복 판정 대상 아님",
        },
    }
    C.write_json(os.path.join(args.out_dir, "gate.json"), result)

    # workflow 가 다음 단계(발송)를 돌릴지 판단할 수 있게 결정을 출력한다.
    out_file = os.environ.get("GITHUB_OUTPUT")
    if out_file:
        with open(out_file, "a", encoding="utf-8") as fh:
            fh.write("decision=%s\n" % decision)
            fh.write("mode=%s\n" % mode)

    rows = ["| Gate | 결과 |", "|---|---|"]
    for key, val in gates.items():
        rows.append("| %s | **%s** |" % (
            key, "PASS" if val else ("DEFERRED" if val is None else "FAIL")))
    rows.append("| **결정** | **%s** |" % decision)
    C.append_summary(
        "### STEP 5 — 발송 Gate\n\n" + "\n".join(rows) + "\n\n"
        + "\n".join("- %s" % n for n in notes)
    )
    print("gate decision = %s (mode=%s)" % (decision, mode))
    for n in notes:
        print(" - %s" % n)
    # Gate 자체는 0으로 끝낸다. 발송 여부는 gmail_send.py 가 gate.json 을 보고 정한다.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
