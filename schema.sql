-- Online Attendance & Student Performance Management System
-- PostgreSQL schema + BCA demo data
--
-- Demo credentials:
--   Admin   : admin      / admin123
--   Teacher : anjali     / teacher123   (also: ravi / teacher123)
--   Student : vaishnavi  / student123   (all students use student123)

DROP TABLE IF EXISTS marks, attendance, subjects, students, teachers, classes, users CASCADE;

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(10) NOT NULL CHECK (role IN ('admin','teacher','student')),
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(120),
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE classes (
    id       SERIAL PRIMARY KEY,
    name     VARCHAR(100) NOT NULL,
    semester INT NOT NULL,
    room     VARCHAR(50)
);

CREATE TABLE teachers (
    id         SERIAL PRIMARY KEY,
    user_id    INT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    department VARCHAR(100)
);

CREATE TABLE students (
    id       SERIAL PRIMARY KEY,
    user_id  INT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    roll_no  VARCHAR(20) UNIQUE NOT NULL,
    class_id INT REFERENCES classes(id) ON DELETE SET NULL
);

CREATE TABLE subjects (
    id         SERIAL PRIMARY KEY,
    code       VARCHAR(20) UNIQUE NOT NULL,
    name       VARCHAR(100) NOT NULL,
    class_id   INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    teacher_id INT REFERENCES teachers(id) ON DELETE SET NULL
);

CREATE TABLE attendance (
    id         SERIAL PRIMARY KEY,
    date       DATE NOT NULL,
    subject_id INT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    status     VARCHAR(10) NOT NULL CHECK (status IN ('present','absent','late')),
    UNIQUE (date, subject_id, student_id)
);

CREATE TABLE marks (
    id         SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    internal   INT NOT NULL DEFAULT 0 CHECK (internal BETWEEN 0 AND 40),
    external   INT NOT NULL DEFAULT 0 CHECK (external BETWEEN 0 AND 60),
    UNIQUE (student_id, subject_id)
);

-- ---------- Demo data ----------
INSERT INTO users (username, password_hash, role, full_name, email) VALUES
('admin',    'pbkdf2:sha256:600000$bcaDemoSaltadm$00d5293836d7be651c4c04bf20f57d665e69f120ced0efaa07b7bec4e2a08e6a', 'admin',   'System Administrator', 'admin@college.edu'),
('anjali',   'pbkdf2:sha256:600000$bcaDemoSalttea$36c19b9f1d0a08bb0263cb69a12b0e4a604cf7391f77be46980591fe4ae821c4', 'teacher', 'Dr. Anjali Deshmukh', 'anjali.d@college.edu'),
('ravi',     'pbkdf2:sha256:600000$bcaDemoSalttea$36c19b9f1d0a08bb0263cb69a12b0e4a604cf7391f77be46980591fe4ae821c4', 'teacher', 'Prof. Ravi Iyer', 'ravi.iyer@college.edu'),
('aarav',    'pbkdf2:sha256:600000$bcaDemoSaltstu$5eb8fcf9abe3063b13e36a839ce56ed4d55890849ca2c036bbf4a23417566a06', 'student', 'Aarav Patil', 'aarav.patil@student.edu'),
('vaishnavi','pbkdf2:sha256:600000$bcaDemoSaltstu$5eb8fcf9abe3063b13e36a839ce56ed4d55890849ca2c036bbf4a23417566a06', 'student', 'Vaishnavi Sutar', 'vaishnavi.sutar@student.edu'),
('rohan',    'pbkdf2:sha256:600000$bcaDemoSaltstu$5eb8fcf9abe3063b13e36a839ce56ed4d55890849ca2c036bbf4a23417566a06', 'student', 'Rohan Kamble', 'rohan.kamble@student.edu'),
('sneha',    'pbkdf2:sha256:600000$bcaDemoSaltstu$5eb8fcf9abe3063b13e36a839ce56ed4d55890849ca2c036bbf4a23417566a06', 'student', 'Sneha Pawar', 'sneha.pawar@student.edu'),
('nikhil',   'pbkdf2:sha256:600000$bcaDemoSaltstu$5eb8fcf9abe3063b13e36a839ce56ed4d55890849ca2c036bbf4a23417566a06', 'student', 'Nikhil Chavan', 'nikhil.chavan@student.edu'),
('tanvi',    'pbkdf2:sha256:600000$bcaDemoSaltstu$5eb8fcf9abe3063b13e36a839ce56ed4d55890849ca2c036bbf4a23417566a06', 'student', 'Tanvi Salunkhe', 'tanvi.salunkhe@student.edu'),
('sahil',    'pbkdf2:sha256:600000$bcaDemoSaltstu$5eb8fcf9abe3063b13e36a839ce56ed4d55890849ca2c036bbf4a23417566a06', 'student', 'Sahil Mane', 'sahil.mane@student.edu');

INSERT INTO classes (name, semester, room) VALUES
('BCA Semester 3', 3, 'Lab A-201'),
('BCA Semester 5', 5, 'Lab B-104');

INSERT INTO teachers (user_id, department) VALUES
(2, 'Computer Applications'),
(3, 'Computer Applications');

INSERT INTO students (user_id, roll_no, class_id) VALUES
(4, 'BCA3-001', 1), (5, 'BCA3-002', 1), (6, 'BCA3-003', 1), (7, 'BCA3-004', 1),
(8, 'BCA5-001', 2), (9, 'BCA5-002', 2), (10, 'BCA5-003', 2);

INSERT INTO subjects (code, name, class_id, teacher_id) VALUES
('BCA301', 'Data Structures', 1, 1),
('BCA302', 'Object Oriented Programming', 1, 2),
('BCA303', 'Database Management Systems', 1, 1),
('BCA501', 'Web Technologies', 2, 2),
('BCA502', 'Computer Networks', 2, 1);

-- 20 weekday sessions of attendance per subject (deterministic pattern;
-- student 3 (Rohan) is deliberately below 75% to demonstrate defaulter alerts).
INSERT INTO attendance (date, subject_id, student_id, status)
SELECT d::date, sub.id, st.id,
       CASE
         WHEN st.id = 3 AND (EXTRACT(DAY FROM d)::int + sub.id) % 3 = 0 THEN 'absent'
         WHEN st.id = 3 AND (EXTRACT(DAY FROM d)::int) % 5 = 0 THEN 'absent'
         WHEN (EXTRACT(DAY FROM d)::int + st.id * 3 + sub.id) % 11 = 0 THEN 'absent'
         WHEN (EXTRACT(DAY FROM d)::int + st.id + sub.id) % 13 = 0 THEN 'late'
         ELSE 'present'
       END
FROM generate_series(CURRENT_DATE - INTERVAL '27 days', CURRENT_DATE, INTERVAL '1 day') AS d
JOIN subjects sub ON TRUE
JOIN students st ON st.class_id = sub.class_id
WHERE EXTRACT(ISODOW FROM d) < 6;

INSERT INTO marks (student_id, subject_id, internal, external)
SELECT st.id, sub.id,
       LEAST(40, 18 + ((st.id * 7 + sub.id * 5) % 22)),
       LEAST(60, 24 + ((st.id * 11 + sub.id * 3) % 36))
FROM students st JOIN subjects sub ON sub.class_id = st.class_id;
