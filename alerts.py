"""
alerts.py - Email alerts for low attendance students
Configure SMTP settings in config.py or environment variables
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database import get_low_attendance_students, log_alert

# ── Email Config (edit these) ──────────────────────────────────────────────────
SMTP_SERVER   = os.environ.get("SMTP_SERVER",   "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_EMAIL    = os.environ.get("SMTP_EMAIL",    "your_email@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "your_app_password")
SENDER_NAME   = "University Attendance System"
THRESHOLD     = 75  # percentage


def send_email(to_email, subject, html_body):
    """Send a single HTML email. Returns (success, error_message)."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{SENDER_NAME} <{SMTP_EMAIL}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)


def build_student_alert_email(student_name, subject_name, present, total, percentage):
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#2E4057;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;">⚠️ Low Attendance Alert</h2>
        <p style="color:rgba(255,255,255,.7);margin:4px 0 0;">University Attendance Management System</p>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #eee;border-radius:0 0 8px 8px;">
        <p>Dear <strong>{student_name}</strong>,</p>
        <p>This is to inform you that your attendance in <strong>{subject_name}</strong>
           has fallen below the required <strong>75%</strong> threshold.</p>
        <div style="background:#f8d7da;border-radius:8px;padding:16px;margin:16px 0;text-align:center;">
          <div style="font-size:2.5rem;font-weight:700;color:#721c24;">{percentage:.1f}%</div>
          <div style="color:#721c24;">Current Attendance</div>
          <div style="font-size:.85rem;color:#999;margin-top:4px;">
            {present} classes attended out of {total} total classes
          </div>
        </div>
        <p>Please ensure regular attendance to avoid academic consequences.
           A minimum of <strong>75% attendance</strong> is mandatory.</p>
        <div style="background:#fff3cd;border-radius:6px;padding:12px;font-size:.85rem;color:#856404;">
          ⚠️ Students with less than 75% attendance may not be permitted to appear in examinations.
        </div>
        <p style="margin-top:20px;">If you believe this is an error, please contact your department office.</p>
        <p>Regards,<br><strong>Academic Section</strong><br>University Attendance System</p>
      </div>
    </body></html>
    """


def send_low_attendance_alerts(threshold=75, dry_run=False):
    """
    Find all students below threshold and send them email alerts.
    dry_run=True: logs but does not actually send email.
    Returns list of results.
    """
    low_students = get_low_attendance_students(threshold)
    results = []

    for s in low_students:
        if not s.get("email"):
            results.append({
                "student": s["name"],
                "roll": s["roll_number"],
                "subject": s["subject_name"],
                "percentage": s["percentage"],
                "status": "skipped",
                "reason": "No email on file"
            })
            continue

        html = build_student_alert_email(
            s["name"], s["subject_name"],
            s["present_count"], s["total_sessions"], s["percentage"] or 0
        )
        subject_line = f"Low Attendance Warning – {s['subject_name']}"

        if dry_run:
            ok, err = True, None
            log_alert(s["id"], "email", f"DRY RUN: {subject_line}", "dry_run")
        else:
            ok, err = send_email(s["email"], subject_line, html)
            log_alert(s["id"], "email", subject_line, "sent" if ok else f"failed: {err}")

        results.append({
            "student": s["name"],
            "roll": s["roll_number"],
            "subject": s["subject_name"],
            "percentage": s["percentage"],
            "email": s["email"],
            "status": "sent" if ok else "failed",
            "error": err
        })

    return results


def send_custom_alert(student_id, student_name, student_email, custom_message):
    """Send a custom message to a specific student."""
    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#2E4057;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;">📢 Message from University</h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #eee;border-radius:0 0 8px 8px;">
        <p>Dear <strong>{student_name}</strong>,</p>
        <p>{custom_message}</p>
        <p>Regards,<br><strong>University Attendance System</strong></p>
      </div>
    </body></html>
    """
    ok, err = send_email(student_email, "Message from University", html)
    log_alert(student_id, "custom", custom_message, "sent" if ok else f"failed:{err}")
    return ok, err
