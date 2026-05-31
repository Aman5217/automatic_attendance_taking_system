"""
database.py - Complete database layer for University Attendance System
Tables: users, students, teachers, subjects, timetable, attendance, alerts_log
"""

import sqlite3
import os
import json
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "university.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Users (login accounts)
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','teacher','student')),
        email TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        last_login TEXT
    )""")

    # Departments
    c.execute("""CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        code TEXT UNIQUE NOT NULL
    )""")

    # Students
    c.execute("""CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        name TEXT NOT NULL,
        roll_number TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL,
        semester INTEGER NOT NULL,
        section TEXT DEFAULT 'A',
        email TEXT,
        phone TEXT,
        face_registered INTEGER DEFAULT 0,
        face_image_path TEXT,
        registered_at TEXT DEFAULT (datetime('now'))
    )""")

    # Teachers
    c.execute("""CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        name TEXT NOT NULL,
        employee_id TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL,
        email TEXT,
        phone TEXT
    )""")

    # Subjects
    c.execute("""CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL,
        semester INTEGER NOT NULL,
        credits INTEGER DEFAULT 3
    )""")

    # Teacher-Subject mapping
    c.execute("""CREATE TABLE IF NOT EXISTS teacher_subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER REFERENCES teachers(id),
        subject_id INTEGER REFERENCES subjects(id),
        section TEXT DEFAULT 'A',
        UNIQUE(teacher_id, subject_id, section)
    )""")

    # Attendance sessions
    c.execute("""CREATE TABLE IF NOT EXISTS attendance_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER REFERENCES subjects(id),
        teacher_id INTEGER REFERENCES teachers(id),
        date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        department TEXT,
        semester INTEGER,
        section TEXT DEFAULT 'A',
        method TEXT DEFAULT 'face',
        total_students INTEGER DEFAULT 0,
        present_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'open'
    )""")

    # Attendance records
    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER REFERENCES attendance_sessions(id),
        student_id INTEGER REFERENCES students(id),
        status TEXT DEFAULT 'Present',
        marked_at TEXT DEFAULT (datetime('now')),
        method TEXT DEFAULT 'face',
        UNIQUE(session_id, student_id)
    )""")

    # Email/alert log
    c.execute("""CREATE TABLE IF NOT EXISTS alerts_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER REFERENCES students(id),
        alert_type TEXT,
        message TEXT,
        sent_at TEXT DEFAULT (datetime('now')),
        status TEXT DEFAULT 'sent'
    )""")

    conn.commit()

    # Create default admin if not exists
    from werkzeug.security import generate_password_hash
    admin_exists = conn.execute("SELECT id FROM users WHERE role='admin'").fetchone()
    if not admin_exists:
        conn.execute("""INSERT INTO users (username, password_hash, role, email)
            VALUES (?, ?, 'admin', 'admin@university.edu')""",
            ('admin', generate_password_hash('admin123')))
        conn.commit()
        print("[OK] Default admin created: username=admin, password=admin123")

    # Default departments
    depts = [('Computer Science', 'CSE'), ('Electronics', 'ECE'),
             ('Mechanical', 'ME'), ('Civil', 'CE'), ('Physics', 'PHY')]
    for name, code in depts:
        try:
            conn.execute("INSERT INTO departments (name, code) VALUES (?, ?)", (name, code))
        except:
            pass

    conn.commit()
    conn.close()


# ── USER AUTH ──────────────────────────────────────────────────────────────────

def get_user_by_username(username):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_last_login(uid):
    conn = get_conn()
    conn.execute("UPDATE users SET last_login=? WHERE id=?", (datetime.now().isoformat(), uid))
    conn.commit()
    conn.close()

def create_user(username, password_hash, role, email=None):
    from werkzeug.security import generate_password_hash
    conn = get_conn()
    try:
        conn.execute("INSERT INTO users (username, password_hash, role, email) VALUES (?,?,?,?)",
                     (username, password_hash, role, email))
        conn.commit()
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return uid
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY role, username").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def toggle_user_active(uid):
    conn = get_conn()
    conn.execute("UPDATE users SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?", (uid,))
    conn.commit()
    conn.close()

def change_password(uid, new_hash):
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, uid))
    conn.commit()
    conn.close()


# ── STUDENTS ───────────────────────────────────────────────────────────────────

def add_student(name, roll_number, department, semester, section, email, phone, user_id=None):
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO students
            (user_id, name, roll_number, department, semester, section, email, phone)
            VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, name, roll_number, department, semester, section, email, phone))
        conn.commit()
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return sid
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_all_students(department=None, semester=None, section=None):
    conn = get_conn()
    q = "SELECT * FROM students WHERE 1=1"
    params = []
    if department:
        q += " AND department=?"; params.append(department)
    if semester:
        q += " AND semester=?"; params.append(semester)
    if section:
        q += " AND section=?"; params.append(section)
    q += " ORDER BY department, semester, roll_number"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_student(sid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_student_by_user(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM students WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_student_by_roll(roll):
    conn = get_conn()
    row = conn.execute("SELECT * FROM students WHERE roll_number=?", (roll,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_student_face(sid, image_path):
    conn = get_conn()
    conn.execute("UPDATE students SET face_registered=1, face_image_path=? WHERE id=?",
                 (image_path, sid))
    conn.commit()
    conn.close()

def delete_student(sid):
    conn = get_conn()
    conn.execute("DELETE FROM attendance WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM students WHERE id=?", (sid,))
    conn.commit()
    conn.close()

def get_student_attendance_summary(sid):
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.name as subject_name, s.code,
               COUNT(a.id) as present,
               (SELECT COUNT(*) FROM attendance_sessions ss
                WHERE ss.subject_id=s.id
                AND ss.department=(SELECT department FROM students WHERE id=?)
                AND ss.semester=(SELECT semester FROM students WHERE id=?)) as total
        FROM subjects s
        LEFT JOIN attendance_sessions sess ON sess.subject_id=s.id
        LEFT JOIN attendance a ON a.session_id=sess.id AND a.student_id=?
        GROUP BY s.id
    """, (sid, sid, sid)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── TEACHERS ───────────────────────────────────────────────────────────────────

def add_teacher(name, employee_id, department, email, phone, user_id=None):
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO teachers (user_id, name, employee_id, department, email, phone)
            VALUES (?,?,?,?,?,?)""", (user_id, name, employee_id, department, email, phone))
        conn.commit()
        tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return tid
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_all_teachers():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM teachers ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_teacher(tid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_teacher_by_user(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM teachers WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── SUBJECTS ───────────────────────────────────────────────────────────────────

def add_subject(name, code, department, semester, credits=3):
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO subjects (name, code, department, semester, credits)
            VALUES (?,?,?,?,?)""", (name, code, department, semester, credits))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_all_subjects(department=None, semester=None):
    conn = get_conn()
    q = "SELECT * FROM subjects WHERE 1=1"
    params = []
    if department:
        q += " AND department=?"; params.append(department)
    if semester:
        q += " AND semester=?"; params.append(int(semester))
    rows = conn.execute(q + " ORDER BY department, semester, name", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_subject(sid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM subjects WHERE id=?", (sid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def assign_subject_to_teacher(teacher_id, subject_id, section='A'):
    conn = get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO teacher_subjects (teacher_id, subject_id, section) VALUES (?,?,?)",
                     (teacher_id, subject_id, section))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def get_teacher_subjects(teacher_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.*, ts.section FROM subjects s
        JOIN teacher_subjects ts ON ts.subject_id=s.id
        WHERE ts.teacher_id=?
    """, (teacher_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── ATTENDANCE ─────────────────────────────────────────────────────────────────

def create_session(subject_id, teacher_id, department, semester, section, method='face'):
    conn = get_conn()
    today = date.today().isoformat()
    now   = datetime.now().strftime("%H:%M:%S")
    total = conn.execute(
        "SELECT COUNT(*) as c FROM students WHERE department=? AND semester=? AND section=?",
        (department, semester, section)).fetchone()["c"]
    conn.execute("""INSERT INTO attendance_sessions
        (subject_id, teacher_id, date, start_time, department, semester, section, method, total_students)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (subject_id, teacher_id, today, now, department, semester, section, method, total))
    conn.commit()
    sess_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return sess_id

def close_session(session_id):
    conn = get_conn()
    now = datetime.now().strftime("%H:%M:%S")
    present = conn.execute(
        "SELECT COUNT(*) as c FROM attendance WHERE session_id=?", (session_id,)).fetchone()["c"]
    conn.execute("""UPDATE attendance_sessions
        SET end_time=?, present_count=?, status='closed' WHERE id=?""",
        (now, present, session_id))
    conn.commit()
    conn.close()

def mark_present(session_id, student_id, method='face'):
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO attendance (session_id, student_id, method)
            VALUES (?,?,?)""", (session_id, student_id, method))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_session(session_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM attendance_sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_session_attendance(session_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT a.*, s.name, s.roll_number, s.department, s.semester, s.section
        FROM attendance a JOIN students s ON a.student_id=s.id
        WHERE a.session_id=?
        ORDER BY s.roll_number
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_sessions(teacher_id=None, date_str=None):
    conn = get_conn()
    q = """SELECT sess.*, sub.name as subject_name, sub.code,
           t.name as teacher_name
           FROM attendance_sessions sess
           JOIN subjects sub ON sess.subject_id=sub.id
           JOIN teachers t ON sess.teacher_id=t.id
           WHERE 1=1"""
    params = []
    if teacher_id:
        q += " AND sess.teacher_id=?"; params.append(teacher_id)
    if date_str:
        q += " AND sess.date=?"; params.append(date_str)
    q += " ORDER BY sess.date DESC, sess.start_time DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_attendance_by_session(session_id):
    conn = get_conn()
    # All students for that session's dept/sem/section
    sess = conn.execute("SELECT * FROM attendance_sessions WHERE id=?", (session_id,)).fetchone()
    if not sess:
        conn.close()
        return []
    all_students = conn.execute(
        "SELECT * FROM students WHERE department=? AND semester=? AND section=? ORDER BY roll_number",
        (sess["department"], sess["semester"], sess["section"])).fetchall()
    present_ids = {r["student_id"] for r in
                   conn.execute("SELECT student_id FROM attendance WHERE session_id=?", (session_id,)).fetchall()}
    conn.close()
    result = []
    for s in all_students:
        result.append({**dict(s),
                       "status": "Present" if s["id"] in present_ids else "Absent"})
    return result

def get_student_sessions(student_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT sess.*, sub.name as subject_name, sub.code,
               CASE WHEN a.id IS NOT NULL THEN 'Present' ELSE 'Absent' END as status
        FROM attendance_sessions sess
        JOIN subjects sub ON sess.subject_id=sub.id
        LEFT JOIN attendance a ON a.session_id=sess.id AND a.student_id=?
        JOIN students st ON st.department=sess.department AND st.semester=sess.semester
        WHERE st.id=?
        ORDER BY sess.date DESC
    """, (student_id, student_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_low_attendance_students(threshold=75):
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.id, s.name, s.roll_number, s.email, s.phone, s.department, s.semester,
               sub.name as subject_name, sub.code,
               COUNT(a.id) as present_count,
               COUNT(sess.id) as total_sessions,
               ROUND(CAST(COUNT(a.id) AS FLOAT)/NULLIF(COUNT(sess.id),0)*100, 1) as percentage
        FROM students s
        JOIN attendance_sessions sess ON sess.department=s.department AND sess.semester=s.semester
        JOIN subjects sub ON sess.subject_id=sub.id
        LEFT JOIN attendance a ON a.session_id=sess.id AND a.student_id=s.id
        GROUP BY s.id, sub.id
        HAVING percentage < ? OR total_sessions=0
        ORDER BY percentage ASC
    """, (threshold,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── REPORTS DATA ───────────────────────────────────────────────────────────────

def get_report_data(department, semester, section, subject_id=None, start_date=None, end_date=None):
    conn = get_conn()
    students = conn.execute(
        "SELECT * FROM students WHERE department=? AND semester=? AND section=? ORDER BY roll_number",
        (department, semester, section)).fetchall()

    q = "SELECT * FROM attendance_sessions WHERE department=? AND semester=? AND section=?"
    params = [department, semester, section]
    if subject_id:
        q += " AND subject_id=?"; params.append(subject_id)
    if start_date:
        q += " AND date>=?"; params.append(start_date)
    if end_date:
        q += " AND date<=?"; params.append(end_date)
    sessions = conn.execute(q + " ORDER BY date", params).fetchall()

    data = {}
    for s in students:
        data[s["id"]] = {"student": dict(s), "records": {}}
    for sess in sessions:
        present_ids = {r["student_id"] for r in
                       conn.execute("SELECT student_id FROM attendance WHERE session_id=?",
                                    (sess["id"],)).fetchall()}
        for sid in data:
            data[sid]["records"][sess["id"]] = "P" if sid in present_ids else "A"
    conn.close()
    return data, [dict(s) for s in sessions]


# ── DEPARTMENTS ────────────────────────────────────────────────────────────────

def get_departments():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM departments ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── ALERTS LOG ─────────────────────────────────────────────────────────────────

def log_alert(student_id, alert_type, message, status='sent'):
    conn = get_conn()
    conn.execute("INSERT INTO alerts_log (student_id, alert_type, message, status) VALUES (?,?,?,?)",
                 (student_id, alert_type, message, status))
    conn.commit()
    conn.close()

def get_alerts_log(limit=100):
    conn = get_conn()
    rows = conn.execute("""
        SELECT al.*, s.name, s.roll_number FROM alerts_log al
        JOIN students s ON al.student_id=s.id
        ORDER BY al.sent_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── DASHBOARD STATS ────────────────────────────────────────────────────────────

def get_dashboard_stats():
    conn = get_conn()
    today = date.today().isoformat()
    stats = {
        "total_students": conn.execute("SELECT COUNT(*) FROM students").fetchone()[0],
        "total_teachers": conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0],
        "total_subjects": conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0],
        "face_registered": conn.execute("SELECT COUNT(*) FROM students WHERE face_registered=1").fetchone()[0],
        "today_sessions": conn.execute("SELECT COUNT(*) FROM attendance_sessions WHERE date=?", (today,)).fetchone()[0],
        "today_present": conn.execute("""
            SELECT COUNT(DISTINCT student_id) FROM attendance a
            JOIN attendance_sessions s ON a.session_id=s.id WHERE s.date=?""", (today,)).fetchone()[0],
        "total_sessions": conn.execute("SELECT COUNT(*) FROM attendance_sessions").fetchone()[0],
    }
    conn.close()
    return stats
