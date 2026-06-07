-- =============================================================
--  BIOMETRIC ATTENDANCE SYSTEM - Supabase Database Schema
--  Run this entire file in Supabase SQL Editor
-- =============================================================

-- SCHOOLS
CREATE TABLE schools (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name          TEXT NOT NULL,
    address       TEXT,
    email         TEXT,
    phone         TEXT,
    license_key   TEXT UNIQUE NOT NULL,
    license_tier  TEXT DEFAULT 'basic',
    license_expiry DATE NOT NULL,
    max_scanners  INTEGER DEFAULT 1,
    max_students  INTEGER DEFAULT 200,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- DEPARTMENTS
CREATE TABLE departments (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id   UUID REFERENCES schools(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    code        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- USERS (Admin, Principal, HOD, Lecturer)
CREATE TABLE users (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id) ON DELETE CASCADE,
    department_id UUID REFERENCES departments(id),
    email         TEXT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('super_admin','admin','principal','principal_secretary','hod','hod_secretary','lecturer')),
    teacher_id    TEXT UNIQUE,
    app_password  TEXT,
    pin_hash      TEXT,
    is_active     BOOLEAN DEFAULT true,
    last_login    TIMESTAMP,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- CLASSES (Level + Intake + Course = unique class identity)
CREATE TABLE classes (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id) ON DELETE CASCADE,
    department_id UUID REFERENCES departments(id),
    level         INTEGER NOT NULL CHECK (level IN (4, 5, 6)),
    intake        INTEGER NOT NULL,     -- e.g. 251, 249, 255
    course        TEXT NOT NULL,        -- e.g. Electrical Installation
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW(),
    UNIQUE (department_id, level, intake, course)
);

-- UNITS
CREATE TABLE units (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id) ON DELETE CASCADE,
    department_id UUID REFERENCES departments(id),
    lecturer_id   UUID REFERENCES users(id),
    class_id      UUID REFERENCES classes(id),  -- which class this unit is taught to
    code          TEXT NOT NULL,
    name          TEXT NOT NULL,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- STUDENTS
CREATE TABLE students (
    id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id         UUID REFERENCES schools(id) ON DELETE CASCADE,
    department_id     UUID REFERENCES departments(id),
    class_id          UUID REFERENCES classes(id),
    admission_number  TEXT NOT NULL UNIQUE, -- e.g. EE-DICL/4456081/25
    full_name         TEXT NOT NULL,
    course            TEXT,
    email             TEXT,
    finger_slot       INTEGER,
    is_active         BOOLEAN DEFAULT true,
    created_at        TIMESTAMP DEFAULT NOW()
);

-- SESSIONS
CREATE TABLE sessions (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id) ON DELETE CASCADE,
    session_code  TEXT NOT NULL,
    lecturer_id   UUID REFERENCES users(id),
    unit_id       UUID REFERENCES units(id),
    class_id      UUID REFERENCES classes(id),
    scanner_port  TEXT,
    date          DATE NOT NULL,
    start_time    TIME NOT NULL,
    end_time      TIME,
    total_present INTEGER DEFAULT 0,
    is_active     BOOLEAN DEFAULT true,
    unscheduled   BOOLEAN DEFAULT false,  -- true if not in timetable
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ATTENDANCE
CREATE TABLE attendance (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id) ON DELETE CASCADE,
    session_id    UUID REFERENCES sessions(id),
    student_id    UUID REFERENCES students(id),
    unit_id       UUID REFERENCES units(id),
    class_id      UUID REFERENCES classes(id),
    date          DATE NOT NULL,
    time_in       TIME NOT NULL,
    status        TEXT DEFAULT 'present' CHECK (status IN ('present','late','absent')),
    synced        BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- OFFLINE QUEUE (for when internet is down)
CREATE TABLE offline_queue (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID,
    data          JSONB NOT NULL,
    table_name    TEXT NOT NULL,
    synced        BOOLEAN DEFAULT false,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- LICENSES
CREATE TABLE licenses (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id),
    license_key   TEXT UNIQUE NOT NULL,
    tier          TEXT NOT NULL,
    issued_date   DATE NOT NULL,
    expiry_date   DATE NOT NULL,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ACTIVITY LOG
CREATE TABLE activity_log (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id),
    user_id       UUID REFERENCES users(id),
    action        TEXT NOT NULL,
    details       TEXT,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ROOMS
CREATE TABLE rooms (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    building      TEXT,
    capacity      INTEGER DEFAULT 30,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- SEMESTERS
CREATE TABLE semesters (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    is_active     BOOLEAN DEFAULT false,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- TIMETABLE
CREATE TABLE timetable (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id     UUID REFERENCES schools(id) ON DELETE CASCADE,
    unit_id       UUID REFERENCES units(id),
    lecturer_id   UUID REFERENCES users(id),
    department_id UUID REFERENCES departments(id),
    class_id      UUID REFERENCES classes(id),
    semester_id   UUID REFERENCES semesters(id),
    room_id       UUID REFERENCES rooms(id),
    day_of_week   TEXT NOT NULL CHECK (day_of_week IN
                    ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday')),
    start_time    TIME NOT NULL,
    end_time      TIME NOT NULL,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- LECTURER ATTENDANCE (tracks whether lecturers showed up to their scheduled classes)
CREATE TABLE lecturer_attendance (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    school_id       UUID REFERENCES schools(id),
    timetable_id    UUID REFERENCES timetable(id),
    lecturer_id     UUID REFERENCES users(id),
    unit_id         UUID REFERENCES units(id),
    scheduled_date  DATE NOT NULL,
    status          TEXT DEFAULT 'pending'
                        CHECK (status IN ('pending','present','late','absent')),
    session_id      UUID REFERENCES sessions(id),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ROW LEVEL SECURITY
ALTER TABLE attendance   ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE students     ENABLE ROW LEVEL SECURITY;
ALTER TABLE users        ENABLE ROW LEVEL SECURITY;

-- Attendance is INSERT only by system, SELECT by authenticated users
CREATE POLICY "attendance_select" ON attendance FOR SELECT USING (true);
CREATE POLICY "attendance_insert" ON attendance FOR INSERT WITH CHECK (true);
CREATE POLICY "attendance_no_update" ON attendance FOR UPDATE USING (false);
CREATE POLICY "attendance_no_delete" ON attendance FOR DELETE USING (false);

-- INDEXES
CREATE INDEX idx_attendance_date      ON attendance(date);
CREATE INDEX idx_attendance_student   ON attendance(student_id);
CREATE INDEX idx_attendance_session   ON attendance(session_id);
CREATE INDEX idx_attendance_class     ON attendance(class_id);
CREATE INDEX idx_sessions_date        ON sessions(date);
CREATE INDEX idx_sessions_class       ON sessions(class_id);
CREATE INDEX idx_students_finger      ON students(finger_slot);
CREATE INDEX idx_students_class       ON students(class_id);
CREATE INDEX idx_students_admission   ON students(admission_number);
CREATE INDEX idx_units_lecturer       ON units(lecturer_id);
CREATE INDEX idx_units_class          ON units(class_id);
CREATE INDEX idx_users_teacher_id     ON users(teacher_id);
CREATE INDEX idx_classes_dept         ON classes(department_id);
