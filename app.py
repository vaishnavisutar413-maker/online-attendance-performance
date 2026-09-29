"""Online Attendance & Student Performance Management System (Flask + PostgreSQL)."""
from datetime import date
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db
from config import Config
from db import execute, query

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

GRADE_BANDS = [(90, "O"), (80, "A+"), (70, "A"), (60, "B+"), (50, "B"), (40, "C"), (0, "F")]


def grade_for(total):
    for minimum, g in GRADE_BANDS:
        if total >= minimum:
            return g
    return "F"


app.jinja_env.globals.update(grade_for=grade_for)


# ---------------- auth helpers ----------------
def login_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if roles and session.get("role") not in roles:
                flash("You do not have access to that page.", "danger")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_teacher_id():
    row = query("SELECT id FROM teachers WHERE user_id=%s", (session["user_id"],), one=True)
    return row["id"] if row else None


def current_student():
    return query(
        """SELECT s.*, u.full_name, u.email, c.name AS class_name
           FROM students s JOIN users u ON u.id=s.user_id
           LEFT JOIN classes c ON c.id=s.class_id WHERE s.user_id=%s""",
        (session["user_id"],), one=True,
    )


def attendance_summary(student_id, subject_id=None):
    sql = """SELECT COUNT(*) AS held,
                    COUNT(*) FILTER (WHERE status <> 'absent') AS attended
             FROM attendance WHERE student_id=%s"""
    params = [student_id]
    if subject_id:
        sql += " AND subject_id=%s"
        params.append(subject_id)
    r = query(sql, params, one=True)
    held, attended = r["held"], r["attended"]
    pct = round(attended * 100.0 / held, 1) if held else 0.0
    return {"held": held, "attended": attended, "percent": pct}


def defaulters(class_id=None, teacher_id=None):
    sql = """SELECT st.id, st.roll_no, u.full_name, c.name AS class_name,
                    COUNT(a.id) AS held,
                    COUNT(a.id) FILTER (WHERE a.status <> 'absent') AS attended
             FROM students st JOIN users u ON u.id=st.user_id
             LEFT JOIN classes c ON c.id=st.class_id
             LEFT JOIN attendance a ON a.student_id=st.id
             LEFT JOIN subjects sub ON sub.id=a.subject_id
             WHERE 1=1"""
    params = []
    if class_id:
        sql += " AND st.class_id=%s"
        params.append(class_id)
    if teacher_id:
        sql += " AND sub.teacher_id=%s"
        params.append(teacher_id)
    sql += " GROUP BY st.id, u.full_name, c.name ORDER BY st.roll_no"
    out = []
    for r in query(sql, params):
        pct = round(r["attended"] * 100.0 / r["held"], 1) if r["held"] else 0.0
        if pct < app.config["ATTENDANCE_THRESHOLD"]:
            out.append({**r, "percent": pct})
    return sorted(out, key=lambda x: x["percent"])


# ---------------- auth routes ----------------
@app.route("/")
def index():
    role = session.get("role")
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "teacher":
        return redirect(url_for("teacher_dashboard"))
    if role == "student":
        return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE username=%s", (username,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], role=user["role"], name=user["full_name"])
            flash(f"Welcome, {user['full_name']}!", "success")
            return redirect(url_for("index"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------- admin ----------------
@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    counts = query(
        """SELECT (SELECT COUNT(*) FROM students) AS students,
                  (SELECT COUNT(*) FROM teachers) AS teachers,
                  (SELECT COUNT(*) FROM classes) AS classes,
                  (SELECT COUNT(*) FROM subjects) AS subjects""",
        one=True,
    )
    overall = query(
        """SELECT COALESCE(ROUND(COUNT(*) FILTER (WHERE status<>'absent')*100.0/NULLIF(COUNT(*),0),1),0) AS pct
           FROM attendance""", one=True)["pct"]
    class_stats = query(
        """SELECT c.id, c.name, c.room,
                  (SELECT COUNT(*) FROM students s WHERE s.class_id=c.id) AS students,
                  COALESCE(ROUND((SELECT COUNT(*) FILTER (WHERE a.status<>'absent')*100.0/NULLIF(COUNT(*),0)
                     FROM attendance a JOIN students s ON s.id=a.student_id WHERE s.class_id=c.id),1),0) AS attendance,
                  COALESCE(ROUND((SELECT AVG(m.internal+m.external) FROM marks m
                     JOIN students s ON s.id=m.student_id WHERE s.class_id=c.id),1),0) AS avg_marks
           FROM classes c ORDER BY c.semester""")
    students = query(
        """SELECT s.id, s.roll_no, u.full_name, u.email, u.username, c.name AS class_name
           FROM students s JOIN users u ON u.id=s.user_id LEFT JOIN classes c ON c.id=s.class_id
           ORDER BY s.roll_no""")
    teachers = query(
        """SELECT t.id, u.full_name, u.email, u.username, t.department
           FROM teachers t JOIN users u ON u.id=t.user_id ORDER BY u.full_name""")
    classes = query("SELECT * FROM classes ORDER BY semester")
    subjects = query(
        """SELECT sub.*, c.name AS class_name, u.full_name AS teacher_name
           FROM subjects sub JOIN classes c ON c.id=sub.class_id
           LEFT JOIN teachers t ON t.id=sub.teacher_id LEFT JOIN users u ON u.id=t.user_id
           ORDER BY sub.code""")
    return render_template(
        "admin/dashboard.html", counts=counts, overall=overall, class_stats=class_stats,
        students=students, teachers=teachers, classes=classes, subjects=subjects,
        defaulters=defaulters()[:8],
    )


def _create_user(username, password, role, full_name, email):
    row = execute(
        """INSERT INTO users (username, password_hash, role, full_name, email)
           VALUES (%s,%s,%s,%s,%s) RETURNING id""",
        (username, generate_password_hash(password), role, full_name, email), returning=True,
    )
    return row["id"]


@app.route("/admin/students/add", methods=["POST"])
@login_required("admin")
def add_student():
    f = request.form
    try:
        uid = _create_user(f["username"], f.get("password") or "student123", "student", f["full_name"], f.get("email"))
        execute("INSERT INTO students (user_id, roll_no, class_id) VALUES (%s,%s,%s)",
                (uid, f["roll_no"], f.get("class_id") or None))
        flash("Student added.", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Could not add student: {e}", "danger")
    return redirect(url_for("admin_dashboard") + "#students")


@app.route("/admin/teachers/add", methods=["POST"])
@login_required("admin")
def add_teacher():
    f = request.form
    try:
        uid = _create_user(f["username"], f.get("password") or "teacher123", "teacher", f["full_name"], f.get("email"))
        execute("INSERT INTO teachers (user_id, department) VALUES (%s,%s)", (uid, f.get("department")))
        flash("Teacher added.", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Could not add teacher: {e}", "danger")
    return redirect(url_for("admin_dashboard") + "#teachers")


@app.route("/admin/classes/add", methods=["POST"])
@login_required("admin")
def add_class():
    f = request.form
    execute("INSERT INTO classes (name, semester, room) VALUES (%s,%s,%s)",
            (f["name"], int(f["semester"]), f.get("room")))
    flash("Class created.", "success")
    return redirect(url_for("admin_dashboard") + "#classes")


@app.route("/admin/subjects/add", methods=["POST"])
@login_required("admin")
def add_subject():
    f = request.form
    try:
        execute("INSERT INTO subjects (code, name, class_id, teacher_id) VALUES (%s,%s,%s,%s)",
                (f["code"], f["name"], f["class_id"], f.get("teacher_id") or None))
        flash("Subject created.", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Could not add subject: {e}", "danger")
    return redirect(url_for("admin_dashboard") + "#classes")


@app.route("/admin/<kind>/<int:item_id>/delete", methods=["POST"])
@login_required("admin")
def delete_item(kind, item_id):
    if kind == "student":
        execute("DELETE FROM users WHERE id=(SELECT user_id FROM students WHERE id=%s)", (item_id,))
    elif kind == "teacher":
        execute("DELETE FROM users WHERE id=(SELECT user_id FROM teachers WHERE id=%s)", (item_id,))
    elif kind == "class":
        execute("DELETE FROM classes WHERE id=%s", (item_id,))
    elif kind == "subject":
        execute("DELETE FROM subjects WHERE id=%s", (item_id,))
    flash(f"{kind.capitalize()} removed.", "info")
    return redirect(url_for("admin_dashboard"))


# ---------------- teacher ----------------
def teacher_subjects():
    if session["role"] == "admin":
        return query("SELECT sub.*, c.name AS class_name FROM subjects sub JOIN classes c ON c.id=sub.class_id ORDER BY code")
    return query(
        """SELECT sub.*, c.name AS class_name FROM subjects sub JOIN classes c ON c.id=sub.class_id
           WHERE sub.teacher_id=%s ORDER BY code""", (current_teacher_id(),))


@app.route("/teacher")
@login_required("teacher")
def teacher_dashboard():
    tid = current_teacher_id()
    subjects = query(
        """SELECT sub.id, sub.code, sub.name, c.name AS class_name,
                  (SELECT COUNT(*) FROM students s WHERE s.class_id=sub.class_id) AS students,
                  (SELECT COUNT(DISTINCT date) FROM attendance a WHERE a.subject_id=sub.id) AS sessions,
                  COALESCE(ROUND((SELECT COUNT(*) FILTER (WHERE status<>'absent')*100.0/NULLIF(COUNT(*),0)
                      FROM attendance a WHERE a.subject_id=sub.id),1),0) AS attendance,
                  COALESCE(ROUND((SELECT AVG(internal+external) FROM marks m WHERE m.subject_id=sub.id),1),0) AS avg_marks
           FROM subjects sub JOIN classes c ON c.id=sub.class_id
           WHERE sub.teacher_id=%s ORDER BY sub.code""", (tid,))
    return render_template("teacher/dashboard.html", subjects=subjects, defaulters=defaulters(teacher_id=tid))


@app.route("/attendance", methods=["GET", "POST"])
@login_required("teacher", "admin")
def attendance():
    subjects = teacher_subjects()
    allowed = {s["id"] for s in subjects}
    subject_id = request.values.get("subject_id", type=int) or (subjects[0]["id"] if subjects else None)
    day = request.values.get("date") or date.today().isoformat()
    if subject_id and subject_id not in allowed:
        flash("You are not assigned to that subject.", "danger")
        return redirect(url_for("attendance"))

    if request.method == "POST" and subject_id:
        roster = query("SELECT s.id FROM students s JOIN subjects sub ON sub.class_id=s.class_id WHERE sub.id=%s", (subject_id,))
        for st in roster:
            status = request.form.get(f"status_{st['id']}", "present")
            if status not in ("present", "absent", "late"):
                status = "present"
            execute(
                """INSERT INTO attendance (date, subject_id, student_id, status) VALUES (%s,%s,%s,%s)
                   ON CONFLICT (date, subject_id, student_id) DO UPDATE SET status=EXCLUDED.status""",
                (day, subject_id, st["id"], status))
        flash(f"Attendance saved for {day}.", "success")
        return redirect(url_for("attendance", subject_id=subject_id, date=day))

    roster = []
    if subject_id:
        roster = query(
            """SELECT s.id, s.roll_no, u.full_name, a.status
               FROM students s JOIN users u ON u.id=s.user_id
               JOIN subjects sub ON sub.class_id=s.class_id AND sub.id=%s
               LEFT JOIN attendance a ON a.student_id=s.id AND a.subject_id=%s AND a.date=%s
               ORDER BY s.roll_no""", (subject_id, subject_id, day))
        for r in roster:
            r.update(attendance_summary(r["id"], subject_id))
    return render_template("attendance.html", subjects=subjects, subject_id=subject_id, day=day,
                           roster=roster, threshold=app.config["ATTENDANCE_THRESHOLD"])


@app.route("/marks", methods=["GET", "POST"])
@login_required("teacher", "admin")
def marks():
    subjects = teacher_subjects()
    allowed = {s["id"] for s in subjects}
    subject_id = request.values.get("subject_id", type=int) or (subjects[0]["id"] if subjects else None)
    if subject_id and subject_id not in allowed:
        flash("You are not assigned to that subject.", "danger")
        return redirect(url_for("marks"))

    if request.method == "POST" and subject_id:
        roster = query("SELECT s.id FROM students s JOIN subjects sub ON sub.class_id=s.class_id WHERE sub.id=%s", (subject_id,))
        for st in roster:
            try:
                internal = max(0, min(40, int(request.form.get(f"internal_{st['id']}", 0))))
                external = max(0, min(60, int(request.form.get(f"external_{st['id']}", 0))))
            except ValueError:
                continue
            execute(
                """INSERT INTO marks (student_id, subject_id, internal, external) VALUES (%s,%s,%s,%s)
                   ON CONFLICT (student_id, subject_id) DO UPDATE
                   SET internal=EXCLUDED.internal, external=EXCLUDED.external""",
                (st["id"], subject_id, internal, external))
        flash("Marks saved.", "success")
        return redirect(url_for("marks", subject_id=subject_id))

    roster = []
    if subject_id:
        roster = query(
            """SELECT s.id, s.roll_no, u.full_name,
                      COALESCE(m.internal,0) AS internal, COALESCE(m.external,0) AS external
               FROM students s JOIN users u ON u.id=s.user_id
               JOIN subjects sub ON sub.class_id=s.class_id AND sub.id=%s
               LEFT JOIN marks m ON m.student_id=s.id AND m.subject_id=%s
               ORDER BY s.roll_no""", (subject_id, subject_id))
    return render_template("marks.html", subjects=subjects, subject_id=subject_id, roster=roster)


@app.route("/reports")
@login_required("teacher", "admin")
def reports():
    subjects = teacher_subjects()
    ids = [s["id"] for s in subjects] or [0]
    subject_perf = query(
        """SELECT sub.code, sub.name,
                  COALESCE(ROUND(AVG(m.internal+m.external),1),0) AS avg_marks,
                  COALESCE(MAX(m.internal+m.external),0) AS top,
                  COUNT(m.id) FILTER (WHERE m.internal+m.external < 40) AS failed
           FROM subjects sub LEFT JOIN marks m ON m.subject_id=sub.id
           WHERE sub.id = ANY(%s) GROUP BY sub.id ORDER BY sub.code""", (ids,))
    grade_rows = query("SELECT internal+external AS total FROM marks WHERE subject_id = ANY(%s)", (ids,))
    grades = {}
    for r in grade_rows:
        g = grade_for(r["total"])
        grades[g] = grades.get(g, 0) + 1
    tid = current_teacher_id() if session["role"] == "teacher" else None
    return render_template("reports.html", subject_perf=subject_perf, grades=grades,
                           defaulters=defaulters(teacher_id=tid),
                           threshold=app.config["ATTENDANCE_THRESHOLD"])


# ---------------- student ----------------
@app.route("/student")
@login_required("student")
def student_dashboard():
    st = current_student()
    if not st:
        flash("Student profile not found.", "danger")
        return redirect(url_for("logout"))
    threshold = app.config["ATTENDANCE_THRESHOLD"]
    rows = query(
        """SELECT sub.id, sub.code, sub.name, COALESCE(m.internal,0) AS internal,
                  COALESCE(m.external,0) AS external
           FROM subjects sub LEFT JOIN marks m ON m.subject_id=sub.id AND m.student_id=%s
           WHERE sub.class_id=%s ORDER BY sub.code""", (st["id"], st["class_id"]))
    for r in rows:
        r.update(attendance_summary(st["id"], r["id"]))
        r["total"] = r["internal"] + r["external"]
        r["grade"] = grade_for(r["total"])
    overall = attendance_summary(st["id"])
    # sessions needed in a row to reach the threshold
    needed = 0
    if overall["held"] and overall["percent"] < threshold:
        a, h = overall["attended"], overall["held"]
        while (a + needed) * 100 < threshold * (h + needed):
            needed += 1
    avg = round(sum(r["total"] for r in rows) / len(rows), 1) if rows else 0
    return render_template("student/dashboard.html", student=st, rows=rows, overall=overall,
                           needed=needed, avg=avg, threshold=threshold)


if __name__ == "__main__":
    app.run(debug=True)
