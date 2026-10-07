# -*- coding: utf-8 -*-
"""GA-3 STEP 6 — Gmail SMTP 발송 (테스트 메일 1통).

- gate.json 의 decision 이 정확히 `SEND_TEST` 일 때만 보낸다. 그 밖의 값이면 0통이다.
- CONNECT / TLS / AUTH 블록은 GA-2B·GA-2C 에서 Overall PASS 한 코드를
  **구조·순서·인자까지 그대로** 쓴다. 바꾸면 그 PASS 와의 비교 가능성이 사라진다.
- AUTH 가 PASS 가 아니면 send_message 를 호출하지 않는다 (FAIL CLOSED).
- 수신자 1명, send_message 1회, 재시도 없음.
- Secret·수신 주소 전체를 출력하지 않는다. SMTP 디버그 로그를 켜지 않는다
  (자격증명이 로그로 나간다 — Guard 가 해당 호출의 부재를 정적 검사한다).
"""
import argparse
import os
import smtplib
import socket
import ssl
import sys
from email.message import EmailMessage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

HOST = "smtp.gmail.com"
PORT = 587
TIMEOUT = 30


class SendStop(Exception):
    pass


def plain_text_body(weekly, subject, qa):
    lines = [
        subject,
        "",
        "이 메일은 GA-3 End-to-End 수동 테스트 산출물이다 (정기 발송 아님).",
        "주차: %s" % weekly,
        "",
    ]
    for row in (qa.get("email_lines") if qa else []) or []:
        lines.append("- %s" % row)
    lines.append("")
    lines.append("HTML 본문을 지원하는 메일 클라이언트에서 전체 브리프가 보인다.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    gate_path = os.path.join(args.out_dir, "gate.json")
    if not os.path.exists(gate_path):
        print("gate.json 이 없다 → 발송하지 않는다 (FAIL CLOSED).")
        C.append_summary("### STEP 6 — 발송\n\n- gate.json 없음 → **발송 0통**")
        return 1

    gate = C.read_json(gate_path)
    decision = gate.get("decision")
    weekly = gate.get("weekly_id")
    subject = gate.get("subject") or ("[TEST] WEEKLY INTELLIGENCE — %s" % weekly)

    if decision != "SEND_TEST":
        print("decision=%s → 메일을 보내지 않는다." % decision)
        C.write_json(os.path.join(args.out_dir, "send_result.json"), {
            "weekly_id": weekly, "decision": decision,
            "delivery_state": "NOT_SENT_GATE", "sent": 0,
            "generated_at_utc": C.stamp_utc(),
        })
        C.append_summary(
            "### STEP 6 — 발송\n\n- decision: `%s`\n- **발송 0통.** "
            "Brief·Email·QA 산출물만 남겼다.\n" % decision
        )
        return 0

    qa_path = os.path.join(args.out_dir, "qa.json")
    qa = C.read_json(qa_path) if os.path.exists(qa_path) else {}
    with open(gate["email_path"], "r", encoding="utf-8") as fh:
        html = fh.read()

    user_raw = os.environ.get("GMAIL_USERNAME", "")
    pw_raw = os.environ.get("GMAIL_APP_PASSWORD", "")
    rcpt_raw = os.environ.get("WIB_RECIPIENT", "")
    user = user_raw.strip()
    rcpt = rcpt_raw.strip()
    # 앞뒤 여백 + 내부 공백 모두 제거. 값·길이를 출력하지 않는다.
    pw = "".join(pw_raw.split())

    steps = {"TCP": "FAIL", "TLS": "FAIL", "AUTH": "FAIL", "SEND": "FAIL"}
    delivery_state = "NOT_SENT_PRECHECK_FAILED"
    category = None
    smtp_code = None
    smtp_detail = None
    tls_proto = None
    notes = []
    secrets = (pw, pw_raw, user, user_raw, rcpt, rcpt_raw)

    smtp = None
    try:
        if not user or not pw:
            category = "SECRET_MISSING_GMAIL"
            raise SendStop()
        if not rcpt:
            category = "SECRET_MISSING_RECIPIENT"
            raise SendStop()
        if ("," in rcpt_raw) or (";" in rcpt_raw) or not C.EMAIL_RE.match(rcpt):
            category = "RECIPIENT_FORMAT_INVALID"
            raise SendStop()

        delivery_state = "NOT_SENT_CONNECT_FAILED"

        # ── 아래 CONNECT/TLS/AUTH 블록은 GA-2B·2C PASS 코드 그대로다 ──
        sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
        sock.close()
        steps["TCP"] = "PASS"

        smtp = smtplib.SMTP(HOST, PORT, timeout=TIMEOUT)
        code, _ = smtp.ehlo()
        if code != 250:
            category = "EHLO_UNEXPECTED"
            smtp_code = code
            raise SendStop()

        ctx = ssl.create_default_context()
        if not ctx.check_hostname or ctx.verify_mode != ssl.CERT_REQUIRED:
            category = "TLS_CONTEXT_WEAKENED"
            raise SendStop()
        smtp.starttls(context=ctx)
        steps["TLS"] = "PASS"
        try:
            tls_proto = smtp.sock.version()
        except Exception:
            pass

        code, _ = smtp.ehlo()
        if code != 250:
            category = "EHLO2_UNEXPECTED"
            smtp_code = code
            raise SendStop()

        delivery_state = "NOT_SENT_AUTH_FAILED"
        smtp.login(user, pw)
        steps["AUTH"] = "PASS"
        # ── 재사용 블록 끝 ──

        # FAIL CLOSED — AUTH 가 PASS 가 아니면 발송하지 않는다 (G5).
        if steps["AUTH"] != "PASS":
            category = "SEND_BLOCKED_AUTH_NOT_PASS"
            raise SendStop()

        msg = EmailMessage()
        msg["From"] = user
        msg["To"] = rcpt
        msg["Subject"] = subject
        msg.set_content(plain_text_body(weekly, subject, qa), charset="utf-8")
        msg.add_alternative(html, subtype="html")

        refused = smtp.send_message(msg)
        if refused:
            category = "RECIPIENT_REFUSED"
            delivery_state = "NOT_SENT_RECIPIENT_REFUSED"
            notes.append("거부된 수신자 수: %d" % len(refused))
        else:
            steps["SEND"] = "PASS"
            delivery_state = "MAIL_SENT_1"

    except SendStop:
        pass
    except ssl.SSLCertVerificationError:
        category = "TLS_CERT_VERIFY_FAILED"
    except ssl.SSLError:
        category = "TLS_HANDSHAKE_ERROR"
    except smtplib.SMTPAuthenticationError as e:
        category = "AUTH_REJECTED"
        smtp_code = getattr(e, "smtp_code", None)
        smtp_detail = C.sanitize(getattr(e, "smtp_error", None), secrets)
    except smtplib.SMTPRecipientsRefused:
        category = "RECIPIENTS_REFUSED_ALL"
        delivery_state = "NOT_SENT_RECIPIENT_REFUSED"
    except smtplib.SMTPSenderRefused as e:
        category = "SENDER_REFUSED"
        smtp_code = getattr(e, "smtp_code", None)
    except smtplib.SMTPDataError as e:
        category = "DATA_REJECTED"
        smtp_code = getattr(e, "smtp_code", None)
        smtp_detail = C.sanitize(getattr(e, "smtp_error", None), secrets)
    except smtplib.SMTPNotSupportedError:
        category = "STARTTLS_NOT_SUPPORTED"
    except smtplib.SMTPServerDisconnected:
        category = "SERVER_DISCONNECTED"
    except smtplib.SMTPResponseException as e:
        category = "SMTP_RESPONSE_ERROR"
        smtp_code = getattr(e, "smtp_code", None)
        smtp_detail = C.sanitize(getattr(e, "smtp_error", None), secrets)
    except smtplib.SMTPException as e:
        category = "SMTP_ERROR_" + type(e).__name__
    except OSError as e:
        category = "SOCKET_ERROR_" + type(e).__name__
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                pass

    sent = 1 if delivery_state == "MAIL_SENT_1" else 0
    result = {
        "weekly_id": weekly,
        "decision": decision,
        "steps": steps,
        "delivery_state": delivery_state,
        "sent": sent,
        "subject": subject,
        "from_masked": C.mask_email(user),
        "to_masked": C.mask_email(rcpt),
        "tls": tls_proto,
        "category": category,
        "smtp_code": smtp_code,
        "smtp_detail": smtp_detail,
        "notes": notes,
        "generated_at_utc": C.stamp_utc(),
        "ledger_row": dict(gate["ledger_row_suggestion"],
                           Status="TEST" if sent else "FAILED"),
    }
    C.write_json(os.path.join(args.out_dir, "send_result.json"), result)

    rows = ["| 단계 | 결과 |", "|---|---|"]
    for key in ("TCP", "TLS", "AUTH", "SEND"):
        rows.append("| %s | **%s** |" % (key, steps[key]))
    C.append_summary(
        "### STEP 6 — 발송\n\n" + "\n".join(rows) + "\n\n"
        + "- 발송 통수: **%d**\n- delivery_state: `%s`\n"
          "- 발신/수신: `%s` -> `%s` (마스킹)\n- 제목: `%s`\n"
        % (sent, delivery_state, C.mask_email(user), C.mask_email(rcpt), subject)
        + ("- 오류 category: `%s`\n" % category if category else "")
        + ("- SMTP 응답: `%s` / `%s`\n" % (smtp_code, smtp_detail)
           if smtp_code or smtp_detail else "")
        + "- 수신함 도달은 사용자가 직접 확인한다 (Gmail 수락 ≠ 수신함 도달).\n"
    )
    print("delivery_state=%s sent=%d" % (delivery_state, sent))
    return 0 if sent == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
