"""
app.py - University Attendance System
Roles: Admin, Teacher, Student
Run: python app.py → http://localhost:5000
"""

import os
from datetime import datetime, date
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, send_file, jsonify, session)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import database as db
from reports import generate_session_report, generate_monthly_report, generate_student_report

db.init_db()

app = Flask(__name__)
app.secret_key = "uni_attend_secret_2024_xyz"

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED = {"jpg", "jpeg", "png"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED


# ── AUTH HELPERS ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("Access denied.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


def current_user():
    if "user_id" in session:
        return db.get_user_by_id(session["user_id"])
    return None


@app.context_processor
def inject_globals():
    return {
        "now": datetime.now,
        "today": date.today().isoformat(),
        "current_user": current_user(),
        "user_role": session.get("role", ""),
        "user_name": session.get("user_name", ""),
    }


# ── AUTH ROUTES ────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.get_user_by_username(username)

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "danger")
            return render_template("login.html")

        if not user["is_active"]:
            flash("Your account has been deactivated. Contact admin.", "danger")
            return render_template("login.html")

        session["user_id"]   = user["id"]
        session["role"]      = user["role"]
        session["username"]  = user["username"]

        # Set display name
        if user["role"] == "teacher":
            t = db.get_teacher_by_user(user["id"])
            session["user_name"] = t["name"] if t else username
        elif user["role"] == "student":
            s = db.get_student_by_user(user["id"])
            session["user_name"] = s["name"] if s else username
        else:
            session["user_name"] = "Admin"

        db.update_last_login(user["id"])
        flash(f"Welcome back, {session['user_name']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old_pw  = request.form.get("old_password")
        new_pw  = request.form.get("new_password")
        confirm = request.form.get("confirm_password")
        user = db.get_user_by_id(session["user_id"])
        if not check_password_hash(user["password_hash"], old_pw):
            flash("Old password is incorrect.", "danger")
        elif new_pw != confirm:
            flash("New passwords do not match.", "danger")
        elif len(new_pw) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db.change_password(session["user_id"], generate_password_hash(new_pw))
            flash("Password changed successfully!", "success")
            return redirect(url_for("dashboard"))
    return render_template("change_password.html")


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    role = session.get("role")

    if role == "admin":
        stats = db.get_dashboard_stats()
        sessions_today = db.get_sessions(date_str=date.today().isoformat())
        alerts_log = db.get_alerts_log(10)
        return render_template("admin/dashboard.html",
                               stats=stats, sessions_today=sessions_today, alerts_log=alerts_log)

    elif role == "teacher":
        teacher = db.get_teacher_by_user(session["user_id"])
        if not teacher:
            flash("Teacher profile not found. Contact admin.", "warning")
            return redirect(url_for("logout"))
        subjects  = db.get_teacher_subjects(teacher["id"])
        sessions  = db.get_sessions(teacher_id=teacher["id"])[:10]
        return render_template("teacher/dashboard.html",
                               teacher=teacher, subjects=subjects, sessions=sessions)

    elif role == "student":
        student = db.get_student_by_user(session["user_id"])
        if not student:
            flash("Student profile not found. Contact admin.", "warning")
            return redirect(url_for("logout"))
        my_sessions = db.get_student_sessions(student["id"])
        summary     = db.get_student_attendance_summary(student["id"])
        return render_template("student/dashboard.html",
                               student=student, my_sessions=my_sessions[:20], summary=summary)

    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── Manage Students ────────────────────────────────────────────────────────────

@app.route("/admin/students")
@role_required("admin")
def admin_students():
    dept = request.args.get("dept", "")
    sem  = request.args.get("sem",  "")
    students = db.get_all_students(department=dept or None,
                                   semester=int(sem) if sem else None)
    departments = db.get_departments()
    return render_template("admin/students.html",
                           students=students, departments=departments,
                           filter_dept=dept, filter_sem=sem)


@app.route("/admin/students/add", methods=["GET", "POST"])
@role_required("admin")
def admin_add_student():
    departments = db.get_departments()
    if request.method == "POST":
        name     = request.form["name"].strip()
        roll     = request.form["roll_number"].strip()
        dept     = request.form["department"]
        sem      = int(request.form["semester"])
        section  = request.form.get("section", "A")
        email    = request.form.get("email", "").strip()
        phone    = request.form.get("phone", "").strip()
        username = request.form.get("username", roll).strip()
        password = request.form.get("password", roll).strip()

        # Create login account
        uid = db.create_user(username, generate_password_hash(password), "student", email)
        if uid is None:
            flash(f"Username '{username}' already taken.", "danger")
            return render_template("admin/add_student.html", departments=departments)

        sid = db.add_student(name, roll, dept, sem, section, email, phone, user_id=uid)
        if sid is None:
            flash(f"Roll number '{roll}' already exists.", "danger")
            return render_template("admin/add_student.html", departments=departments)

        flash(f"Student '{name}' added. Login: {username} / {password}", "success")
        return redirect(url_for("admin_students"))

    return render_template("admin/add_student.html", departments=departments)


@app.route("/admin/students/<int:sid>/delete", methods=["POST"])
@role_required("admin")
def admin_delete_student(sid):
    s = db.get_student(sid)
    if s:
        db.delete_student(sid)
        flash(f"Student '{s['name']}' deleted.", "info")
    return redirect(url_for("admin_students"))


@app.route("/admin/students/<int:sid>/capture")
@role_required("admin")
def admin_capture_face(sid):
    student = db.get_student(sid)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("admin_students"))
    return render_template("admin/capture_face.html", student=student)


@app.route("/admin/students/<int:sid>/upload_face", methods=["POST"])
@role_required("admin")
def admin_upload_face(sid):
    student = db.get_student(sid)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("admin_students"))

    if "photo" not in request.files:
        flash("No file received.", "danger")
        return redirect(url_for("admin_students"))

    file = request.files["photo"]
    if not allowed_file(file.filename):
        flash("Invalid file type.", "danger")
        return redirect(url_for("admin_students"))

    filename = secure_filename(f"student_{sid}.jpg")
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    try:
        from face_engine import register_face_from_image
        ok, msg = register_face_from_image(sid, path)
        if ok:
            db.update_student_face(sid, path)
            flash(f"Face registered for {student['name']}!", "success")
        else:
            flash(f"Face registration: {msg}", "warning")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for("admin_students"))


# ── Manage Teachers ────────────────────────────────────────────────────────────

@app.route("/admin/teachers")
@role_required("admin")
def admin_teachers():
    teachers = db.get_all_teachers()
    return render_template("admin/teachers.html", teachers=teachers)


@app.route("/admin/teachers/add", methods=["GET", "POST"])
@role_required("admin")
def admin_add_teacher():
    departments = db.get_departments()
    subjects    = db.get_all_subjects()
    if request.method == "POST":
        name      = request.form["name"].strip()
        emp_id    = request.form["employee_id"].strip()
        dept      = request.form["department"]
        email     = request.form.get("email", "").strip()
        phone     = request.form.get("phone", "").strip()
        username  = request.form.get("username", emp_id).strip()
        password  = request.form.get("password", emp_id).strip()

        uid = db.create_user(username, generate_password_hash(password), "teacher", email)
        if uid is None:
            flash(f"Username '{username}' already taken.", "danger")
            return render_template("admin/add_teacher.html",
                                   departments=departments, subjects=subjects)

        tid = db.add_teacher(name, emp_id, dept, email, phone, user_id=uid)
        if tid is None:
            flash(f"Employee ID '{emp_id}' already exists.", "danger")
            return render_template("admin/add_teacher.html",
                                   departments=departments, subjects=subjects)

        # Assign subjects
        for subj_id in request.form.getlist("subject_ids"):
            db.assign_subject_to_teacher(tid, int(subj_id))

        flash(f"Teacher '{name}' added. Login: {username} / {password}", "success")
        return redirect(url_for("admin_teachers"))

    return render_template("admin/add_teacher.html",
                           departments=departments, subjects=subjects)


# ── Manage Subjects ────────────────────────────────────────────────────────────

@app.route("/admin/subjects", methods=["GET", "POST"])
@role_required("admin")
def admin_subjects():
    departments = db.get_departments()
    if request.method == "POST":
        ok = db.add_subject(
            request.form["name"].strip(),
            request.form["code"].strip().upper(),
            request.form["department"],
            int(request.form["semester"]),
            int(request.form.get("credits", 3))
        )
        flash("Subject added!" if ok else "Subject code already exists.", "success" if ok else "danger")
        return redirect(url_for("admin_subjects"))

    subjects = db.get_all_subjects(
        department=request.args.get("dept") or None,
        semester=request.args.get("sem") or None
    )
    return render_template("admin/subjects.html",
                           subjects=subjects, departments=departments)


# ── Alerts ─────────────────────────────────────────────────────────────────────

@app.route("/admin/alerts", methods=["GET", "POST"])
@role_required("admin")
def admin_alerts():
    from database import get_low_attendance_students
    threshold = int(request.args.get("threshold", 75))
    low = get_low_attendance_students(threshold)
    log = db.get_alerts_log(50)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "send_all":
            from alerts import send_low_attendance_alerts
            results = send_low_attendance_alerts(threshold)
            sent = sum(1 for r in results if r["status"] == "sent")
            flash(f"Alerts sent: {sent}/{len(results)}", "success")
        elif action == "test":
            from alerts import send_low_attendance_alerts
            results = send_low_attendance_alerts(threshold, dry_run=True)
            flash(f"Dry run complete. Would send {len(results)} alerts.", "info")
        return redirect(url_for("admin_alerts"))

    return render_template("admin/alerts.html", low_students=low, log=log, threshold=threshold)


# ── Admin Reports ──────────────────────────────────────────────────────────────

@app.route("/admin/reports", methods=["GET"])
@role_required("admin")
def admin_reports():
    departments = db.get_departments()
    subjects    = db.get_all_subjects()
    return render_template("admin/reports.html",
                           departments=departments, subjects=subjects,
                           today=date.today().isoformat())


@app.route("/admin/reports/download")
@role_required("admin")
def admin_report_download():
    dept       = request.args.get("department")
    sem        = request.args.get("semester")
    section    = request.args.get("section", "A")
    subject_id = request.args.get("subject_id") or None
    start      = request.args.get("start") or None
    end        = request.args.get("end") or None
    fmt        = request.args.get("format", "xlsx")
    try:
        path = generate_monthly_report(dept, int(sem), section, subject_id, start, end, fmt)
        if not path:
            flash("No sessions found for selected filters.", "warning")
            return redirect(url_for("admin_reports"))
        return send_file(path, as_attachment=True)
    except Exception as e:
        flash(f"Report error: {e}", "danger")
        return redirect(url_for("admin_reports"))


# ── User management ────────────────────────────────────────────────────────────

@app.route("/admin/users")
@role_required("admin")
def admin_users():
    users = db.get_all_users()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/<int:uid>/toggle", methods=["POST"])
@role_required("admin")
def admin_toggle_user(uid):
    db.toggle_user_active(uid)
    flash("User status updated.", "info")
    return redirect(url_for("admin_users"))


# ══════════════════════════════════════════════════════════════════════════════
# TEACHER ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/teacher/session/start", methods=["GET", "POST"])
@role_required("teacher")
def teacher_start_session():
    teacher  = db.get_teacher_by_user(session["user_id"])
    subjects = db.get_teacher_subjects(teacher["id"])

    if request.method == "POST":
        subject_id = int(request.form["subject_id"])
        section    = request.form.get("section", "A")
        method     = request.form.get("method", "face")
        subj = db.get_subject(subject_id)
        sess_id = db.create_session(subject_id, teacher["id"],
                                    subj["department"], subj["semester"], section, method)
        if method == "face":
            return redirect(url_for("teacher_face_session", sess_id=sess_id))
        else:
            return redirect(url_for("teacher_manual_session", sess_id=sess_id))

    return render_template("teacher/start_session.html",
                           teacher=teacher, subjects=subjects)


@app.route("/teacher/session/<int:sess_id>/face", methods=["GET", "POST"])
@role_required("teacher")
def teacher_face_session(sess_id):
    sess    = db.get_session(sess_id)
    subj    = db.get_subject(sess["subject_id"])
    teacher = db.get_teacher_by_user(session["user_id"])

    if request.method == "POST":
        duration = int(request.form.get("duration", 120))
        try:
            from face_engine import run_attendance_session
            results = run_attendance_session(
                sess_id, subj["name"],
                sess["department"], sess["semester"], sess["section"],
                duration_seconds=duration
            )
            db.close_session(sess_id)
            flash(f"Session complete! {len(results)} students marked present.", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        return redirect(url_for("teacher_session_result", sess_id=sess_id))

    return render_template("teacher/face_session.html",
                           sess=sess, subj=subj, teacher=teacher)


@app.route("/teacher/session/<int:sess_id>/manual", methods=["GET", "POST"])
@role_required("teacher")
def teacher_manual_session(sess_id):
    sess    = db.get_session(sess_id)
    subj    = db.get_subject(sess["subject_id"])
    students = db.get_all_students(department=sess["department"],
                                    semester=sess["semester"],
                                    section=sess["section"])

    if request.method == "POST":
        for sid in request.form.getlist("present_ids"):
            db.mark_present(sess_id, int(sid), method="manual")
        db.close_session(sess_id)
        flash("Manual attendance submitted!", "success")
        return redirect(url_for("teacher_session_result", sess_id=sess_id))

    return render_template("teacher/manual_session.html",
                           sess=sess, subj=subj, students=students)


@app.route("/teacher/session/<int:sess_id>/result")
@role_required("teacher")
def teacher_session_result(sess_id):
    sess    = db.get_session(sess_id)
    subj    = db.get_subject(sess["subject_id"])
    records = db.get_attendance_by_session(sess_id)
    present = sum(1 for r in records if r["status"] == "Present")
    return render_template("teacher/session_result.html",
                           sess=sess, subj=subj, records=records,
                           present=present, total=len(records))


@app.route("/teacher/sessions")
@role_required("teacher")
def teacher_sessions():
    teacher  = db.get_teacher_by_user(session["user_id"])
    sessions = db.get_sessions(teacher_id=teacher["id"])
    return render_template("teacher/sessions.html", sessions=sessions, teacher=teacher)


@app.route("/teacher/reports")
@role_required("teacher")
def teacher_reports():
    teacher  = db.get_teacher_by_user(session["user_id"])
    subjects = db.get_teacher_subjects(teacher["id"])
    return render_template("teacher/reports.html",
                           teacher=teacher, subjects=subjects,
                           today=date.today().isoformat())


@app.route("/teacher/reports/download")
@role_required("teacher")
def teacher_report_download():
    teacher    = db.get_teacher_by_user(session["user_id"])
    sess_id    = request.args.get("session_id")
    subject_id = request.args.get("subject_id")
    fmt        = request.args.get("format", "xlsx")

    try:
        if sess_id:
            path = generate_session_report(int(sess_id), fmt)
        else:
            dept    = request.args.get("department")
            sem     = request.args.get("semester")
            section = request.args.get("section", "A")
            start   = request.args.get("start") or None
            end     = request.args.get("end") or None
            path    = generate_monthly_report(dept, int(sem), section,
                                              int(subject_id) if subject_id else None,
                                              start, end, fmt)
        if not path:
            flash("No data found.", "warning")
            return redirect(url_for("teacher_reports"))
        return send_file(path, as_attachment=True)
    except Exception as e:
        flash(f"Report error: {e}", "danger")
        return redirect(url_for("teacher_reports"))


# ══════════════════════════════════════════════════════════════════════════════
# STUDENT ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/student/register_face")
@role_required("student")
def student_register_face():
    student = db.get_student_by_user(session["user_id"])
    return render_template("student/register_face.html", student=student)


@app.route("/student/upload_face", methods=["POST"])
@role_required("student")
def student_upload_face():
    student = db.get_student_by_user(session["user_id"])
    if "photo" not in request.files:
        flash("No photo received.", "danger")
        return redirect(url_for("student_register_face"))

    file = request.files["photo"]
    if not allowed_file(file.filename):
        flash("Invalid file type.", "danger")
        return redirect(url_for("student_register_face"))

    filename = secure_filename(f"student_{student['id']}.jpg")
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    try:
        from face_engine import register_face_from_image
        ok, msg = register_face_from_image(student["id"], path)
        if ok:
            db.update_student_face(student["id"], path)
            flash("Your face has been registered successfully!", "success")
        else:
            flash(f"Registration issue: {msg}", "warning")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for("dashboard"))


@app.route("/student/my_attendance")
@role_required("student")
def student_my_attendance():
    student  = db.get_student_by_user(session["user_id"])
    sessions = db.get_student_sessions(student["id"])
    summary  = db.get_student_attendance_summary(student["id"])
    return render_template("student/my_attendance.html",
                           student=student, sessions=sessions, summary=summary)


@app.route("/student/report/download")
@role_required("student")
def student_report_download():
    student = db.get_student_by_user(session["user_id"])
    fmt = request.args.get("format", "xlsx")
    try:
        path = generate_student_report(student["id"], fmt)
        return send_file(path, as_attachment=True)
    except Exception as e:
        flash(f"Report error: {e}", "danger")
        return redirect(url_for("student_my_attendance"))


# ── API ────────────────────────────────────────────────────────────────────────

@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify(db.get_dashboard_stats())


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  University Attendance Management System")
    print("  Open: http://localhost:5000")
    print()
    print("  Default Login:")
    print("  Admin    → username: admin    password: admin123")
    print("="*60 + "\n")
    app.run(debug=True, port=5000)
