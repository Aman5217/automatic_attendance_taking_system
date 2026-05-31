"""
face_engine.py - Face registration and recognition
Primary: DeepFace (97-99% accuracy)
Fallback: OpenCV LBPH (if DeepFace not installed)
"""

import os
import cv2
import numpy as np
import shutil
from datetime import datetime

STUDENT_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "student_images")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "data", "lbph_model.yml")
CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

os.makedirs(STUDENT_IMAGES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

face_cascade = cv2.CascadeClassifier(CASCADE_PATH)

# Check if DeepFace available
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
    print("[INFO] DeepFace loaded — high accuracy mode")
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("[INFO] DeepFace not found — using LBPH fallback")


# ── LBPH recognizer (fallback) ─────────────────────────────────────────────────
lbph = cv2.face.LBPHFaceRecognizer_create()


def detect_faces_cv(gray):
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
    return faces if len(faces) > 0 else []


def preprocess_face(gray, x, y, w, h):
    roi = gray[y:y+h, x:x+w]
    return cv2.resize(roi, (200, 200))


# ── REGISTRATION ───────────────────────────────────────────────────────────────

def register_face_from_image(student_id, image_path):
    """
    Register student face from uploaded/captured image.
    Saves augmented copies and trains LBPH model.
    Returns (success, message)
    """
    img = cv2.imread(image_path)
    if img is None:
        return False, "Cannot read image file."

    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = detect_faces_cv(gray)

    if len(faces) == 0:
        # Try without detection (use full image)
        gray_resized = cv2.resize(gray, (200, 200))
        faces_data = [gray_resized]
    else:
        x, y, w, h = faces[0]
        roi = preprocess_face(gray, x, y, w, h)
        # Augmentations for better model robustness
        faces_data = [
            roi,
            cv2.flip(roi, 1),
            cv2.equalizeHist(roi),
            cv2.GaussianBlur(roi, (3, 3), 0),
            cv2.convertScaleAbs(roi, alpha=1.15, beta=15),
            cv2.convertScaleAbs(roi, alpha=0.85, beta=-15),
            cv2.convertScaleAbs(roi, alpha=1.3, beta=0),
            cv2.convertScaleAbs(roi, alpha=0.7, beta=0),
        ]

    # Save images
    save_dir = os.path.join(STUDENT_IMAGES_DIR, str(student_id))
    os.makedirs(save_dir, exist_ok=True)
    idx = 0
    for face_img in faces_data:
        for _ in range(5):  # 5 copies of each augmentation = 40 total
            cv2.imwrite(os.path.join(save_dir, f"{idx:03d}.jpg"), face_img)
            idx += 1

    # Also save original image for DeepFace
    orig_path = os.path.join(save_dir, "original.jpg")
    shutil.copy(image_path, orig_path)

    # Train LBPH model
    train_lbph()
    return True, f"Face registered successfully with {idx} training images."


def train_lbph():
    """Train LBPH model from all student images."""
    from database import get_all_students
    students = get_all_students()

    faces_data, labels = [], []
    for s in students:
        img_dir = os.path.join(STUDENT_IMAGES_DIR, str(s["id"]))
        if not os.path.isdir(img_dir):
            continue
        for fname in os.listdir(img_dir):
            if fname == "original.jpg":
                continue
            path = os.path.join(img_dir, fname)
            img  = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                faces_data.append(cv2.resize(img, (200, 200)))
                labels.append(s["id"])

    if faces_data:
        lbph.train(faces_data, np.array(labels))
        lbph.save(MODEL_PATH)
        return True
    return False


def load_lbph():
    if os.path.exists(MODEL_PATH):
        lbph.read(MODEL_PATH)
        return True
    return False


# ── RECOGNITION ────────────────────────────────────────────────────────────────

def recognize_face_deepface(frame_bgr, student_id):
    """Use DeepFace to verify if frame matches student's registered face."""
    orig_path = os.path.join(STUDENT_IMAGES_DIR, str(student_id), "original.jpg")
    if not os.path.exists(orig_path):
        return False, 999

    try:
        result = DeepFace.verify(
            frame_bgr, orig_path,
            model_name="VGG-Face",
            enforce_detection=False,
            silent=True
        )
        return result["verified"], result["distance"]
    except Exception as e:
        return False, 999


def run_attendance_session(session_id, subject_name, department, semester, section,
                           duration_seconds=120, confidence_threshold=75):
    """
    Opens webcam, recognises students, marks attendance.
    Uses DeepFace if available, else LBPH.
    Returns list of marked student dicts.
    """
    from database import get_all_students, mark_present

    students = get_all_students(department=department, semester=semester, section=section)
    registered = [s for s in students if s["face_registered"]]

    if not registered:
        print("[WARN] No students with registered faces.")
        return []

    # Load LBPH model
    if not DEEPFACE_AVAILABLE:
        if not load_lbph():
            if not train_lbph():
                print("[ERROR] No LBPH model available.")
                return []
            lbph.read(MODEL_PATH)

    id_map = {s["id"]: s for s in registered}

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Webcam not accessible.")
        return []

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    marked = set()
    results = []
    import time
    start = time.time()
    frame_n = 0

    print(f"\n[SESSION] {subject_name} | {department} Sem-{semester} Sec-{section}")
    print(f"[INFO] {len(registered)} students registered | Duration: {duration_seconds}s | Press Q to stop\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_n += 1
        elapsed   = time.time() - start
        remaining = max(0, duration_seconds - int(elapsed))

        if frame_n % 3 == 0:
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detect_faces_cv(gray)

            for (x, y, w, h) in faces:
                matched_id   = None
                matched_name = "Unknown"
                color        = (0, 60, 220)
                conf_text    = ""

                if DEEPFACE_AVAILABLE:
                    # Try DeepFace against each registered student
                    face_crop = frame[y:y+h, x:x+w]
                    best_dist = 999
                    for sid, s in id_map.items():
                        if sid in marked:
                            continue
                        verified, dist = recognize_face_deepface(face_crop, sid)
                        if verified and dist < best_dist:
                            best_dist  = dist
                            matched_id = sid
                    if matched_id:
                        matched_name = id_map[matched_id]["name"]
                        color        = (0, 220, 80)
                        conf_text    = f" ({best_dist:.2f})"
                else:
                    # LBPH fallback
                    roi = preprocess_face(gray, x, y, w, h)
                    try:
                        sid, conf = lbph.predict(roi)
                        if conf < confidence_threshold and sid in id_map and sid not in marked:
                            matched_id   = sid
                            matched_name = id_map[sid]["name"]
                            color        = (0, 220, 80)
                            conf_text    = f" ({int(conf)})"
                    except:
                        pass

                if matched_id and matched_id not in marked:
                    was_new = mark_present(session_id, matched_id, method='face')
                    if was_new:
                        results.append({
                            "student_id": matched_id,
                            "name": id_map[matched_id]["name"],
                            "roll_number": id_map[matched_id]["roll_number"],
                            "time": datetime.now().strftime("%H:%M:%S")
                        })
                        marked.add(matched_id)
                        print(f"[OK] {id_map[matched_id]['name']} ({id_map[matched_id]['roll_number']}){conf_text}")

                # Draw
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                cv2.rectangle(frame, (x, y+h-28), (x+w, y+h), color, cv2.FILLED)
                label = f"{matched_name}{conf_text}"
                cv2.putText(frame, label, (x+4, y+h-8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1)

        # HUD
        cv2.rectangle(frame, (0, 0), (640, 48), (20, 20, 20), cv2.FILLED)
        cv2.putText(frame, f"{subject_name} | {department} Sem{semester}-{section}",
                    (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1)
        cv2.putText(frame, f"Marked: {len(marked)}/{len(registered)}  |  Time left: {remaining}s  |  Q=stop",
                    (8, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (80, 220, 80), 1)
        mode_text = "DeepFace" if DEEPFACE_AVAILABLE else "LBPH"
        cv2.putText(frame, f"Mode: {mode_text}", (540, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 200, 255), 1)

        cv2.imshow("Attendance Session – Press Q to Stop", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        if elapsed >= duration_seconds:
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n[DONE] Session ended. {len(results)} marked.")
    return results
