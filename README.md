# University Attendance Management System

A complete, production-ready attendance system for universities with role-based login, face recognition, email alerts, and Excel/CSV reports.

---

## Features

| Feature | Details |
|---|---|
| **Role-based login** | Admin, Teacher, Student — separate dashboards |
| **Student self-registration** | Live webcam capture in browser |
| **Face recognition** | OpenCV LBPH (works offline, no dlib) |
| **DeepFace support** | Auto-detects if installed for 97-99% accuracy |
| **Manual attendance** | Checkbox-based fallback |
| **Email alerts** | Low attendance warnings via Gmail SMTP |
| **Excel reports** | Color-coded P/A matrix with % |
| **CSV export** | For any software import |
| **60-100 students** | Optimized for classroom size |
| **SQLite database** | Zero-config, file-based |

---

## Project Structure

```
uni_attendance/
├── app.py              ← Main Flask application
├── database.py         ← All database operations
├── face_engine.py      ← Face recognition (LBPH + DeepFace)
├── alerts.py           ← Email alert system
├── reports.py          ← Excel/CSV report generation
├── setup_demo.py       ← Load demo data (run once)
├── requirements.txt    ← Python packages
├── data/               ← SQLite database
├── student_images/     ← Registered face images
├── uploads/            ← Uploaded photos
├── reports/            ← Generated report files
└── templates/
    ├── login.html
    ├── base.html
    ├── change_password.html
    ├── admin/
    │   ├── dashboard.html
    │   ├── students.html
    │   ├── add_student.html
    │   ├── teachers.html
    │   ├── add_teacher.html
    │   ├── subjects.html
    │   ├── users.html
    │   ├── alerts.html
    │   ├── reports.html
    │   └── capture_face.html
    ├── teacher/
    │   ├── dashboard.html
    │   ├── start_session.html
    │   ├── face_session.html
    │   ├── manual_session.html
    │   ├── session_result.html
    │   ├── sessions.html
    │   └── reports.html
    └── student/
        ├── dashboard.html
        ├── register_face.html
        └── my_attendance.html
```

---

## Installation

```bash
# Step 1: Install packages
pip install opencv-contrib-python numpy pandas flask werkzeug openpyxl pillow

# Step 2 (optional): Install DeepFace for higher accuracy
pip install deepface tf-keras

# Step 3: Setup demo data (run ONCE)
python setup_demo.py

# Step 4: Start the system
python app.py
# → Open http://localhost:5000
```

---

## Login Accounts

| Role | Username | Password |
|---|---|---|
| Admin | admin | admin123 |
| Teacher | T001 | T001 |
| Student | CSB23068 | CSB23068 |

*(Student username = roll number)*

---

## How to Use

### Admin
1. Login → Add departments, subjects
2. Add teachers → assign subjects
3. Add students → they get login credentials
4. Send low attendance alerts
5. Download full reports

### Teacher
1. Login → Click "Take Attendance"
2. Select subject + section + method
3. Face Recognition: webcam window opens → students face camera
4. Manual: check boxes for present students
5. Download session or monthly reports

### Student
1. Login → Click "Register Face"
2. Allow camera → Click Capture (30 photos taken)
3. Click Save → face registered
4. View attendance and download personal report

---

## Email Alert Setup

Edit `alerts.py`:
```python
SMTP_EMAIL    = "your_gmail@gmail.com"
SMTP_PASSWORD = "your_app_password"  # Gmail App Password
```

To get Gmail App Password:
1. Google Account → Security → 2-Step Verification → App Passwords
2. Generate password for "Mail"
3. Paste it in alerts.py

---

## Database Tables

```
users          → login accounts (all roles)
students       → student profiles
teachers       → teacher profiles
subjects       → course subjects
teacher_subjects → which teacher teaches which subject
attendance_sessions → each class session
attendance     → individual student records per session
alerts_log     → history of sent alerts
departments    → department list
```

---

## Accuracy

| Method | Accuracy | Install |
|---|---|---|
| LBPH (default) | 70-80% | Easy |
| DeepFace VGG-Face | 97-99% | pip install deepface |
