"""
database.py - Direct HTTP connection to Supabase
Uses requests library instead of supabase-py for reliability
"""

import sqlite3
import json
import os
import requests
from datetime import datetime
from config import SUPABASE_URL, SUPABASE_KEY, OFFLINE_DB

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

AUTH_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Content-Type": "application/json"
}


class DatabaseManager:
    def __init__(self):
        self.online    = False
        self.token     = None
        self.school_id = None
        self._init_offline_db()
        self._test_connection()

    def _test_connection(self):
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/users?limit=1",
                headers=HEADERS, timeout=10)
            self.online = r.status_code in (200, 206)
        except:
            self.online = False

    def _init_offline_db(self):
        conn = sqlite3.connect(OFFLINE_DB)
        c    = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS offline_attendance (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                data       TEXT NOT NULL,
                synced     INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS cached_students (
                finger_slot INTEGER PRIMARY KEY,
                student_id  TEXT,
                full_name   TEXT,
                course      TEXT
            )
        """)
        conn.commit()
        conn.close()

    def is_online(self):
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/users?limit=1",
                headers=HEADERS, timeout=8)
            self.online = r.status_code in (200, 206)
        except:
            self.online = False
        return self.online

    # ── AUTH ──────────────────────────────────────────
    def login(self, email, password):
        """Login by checking email and password directly in users table."""
        try:
            users = self._get("users", f"email=eq.{email}&is_active=eq.true&limit=1")
            if not users:
                print(f"No user found for email: {email}")
                return None
            user = users[0]
            stored = user.get("app_password","")
            if stored == password:
                self.token = SUPABASE_KEY
                return user
            else:
                print(f"Password mismatch for {email}")
                return None
        except Exception as e:
            print(f"Login error: {e}")
            return None

    def logout(self):
        self.token = None

    def _auth_headers(self):
        """Headers with user token if available."""
        h = dict(HEADERS)
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    # ── GENERIC QUERY ─────────────────────────────────
    def _get(self, table, params=""):
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/{table}?{params}",
                headers=self._auth_headers(), timeout=15)
            if r.status_code in (200, 206):
                return r.json()
            print(f"GET {table} error: {r.status_code} {r.text}")
            return []
        except Exception as e:
            print(f"GET {table} exception: {e}")
            return []

    def _post(self, table, data):
        try:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=self._auth_headers(),
                json=data, timeout=15)
            if r.status_code in (200, 201):
                result = r.json()
                return result[0] if isinstance(result, list) and result else result
            print(f"POST {table} error: {r.status_code} {r.text}")
            return None
        except Exception as e:
            print(f"POST {table} exception: {e}")
            return None

    def _patch(self, table, params, data):
        try:
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/{table}?{params}",
                headers=self._auth_headers(),
                json=data, timeout=15)
            return r.status_code in (200, 204)
        except Exception as e:
            print(f"PATCH {table} exception: {e}")
            return False

    def _delete(self, table, params):
        try:
            r = requests.delete(
                f"{SUPABASE_URL}/rest/v1/{table}?{params}",
                headers=self._auth_headers(), timeout=15)
            return r.status_code in (200, 204)
        except Exception as e:
            print(f"DELETE {table} exception: {e}")
            return False

    def _count(self, table, params=""):
        try:
            h = dict(self._auth_headers())
            h["Prefer"] = "count=exact"
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/{table}?{params}&limit=1",
                headers=h, timeout=15)
            cr = r.headers.get("content-range","0/0")
            return int(cr.split("/")[-1]) if "/" in cr else 0
        except:
            return 0

    # ── CLASSES ───────────────────────────────────────
    def get_classes(self):
        return self._get("classes",
            "is_active=eq.true"
            "&select=*,departments(name)"
            "&order=level,intake") or []

    def add_class(self, level, intake, course, department_id, school_id):
        return self._post("classes", {
            "level":         level,
            "intake":        intake,
            "course":        course,
            "department_id": department_id,
            "school_id":     school_id,
            "is_active":     True
        })

    def delete_class(self, class_id):
        return self._patch("classes", f"id=eq.{class_id}",
                           {"is_active": False})

    # ── STUDENTS ──────────────────────────────────────
    def get_students(self):
        data = self._get("students",
            "is_active=eq.true"
            "&select=*,classes(level,intake,course)"
            "&order=full_name")
        if data:
            self._cache_all_students(data)
        return data or self._get_cached_students()

    def add_student(self, data):
        result = self._post("students", data)
        if result:
            self._cache_student(data)
        return result

    def delete_student(self, student_id):
        return self._patch("students", f"id=eq.{student_id}",
                           {"is_active": False})

    def get_student_by_finger(self, finger_slot):
        data = self._get("students",
                         f"finger_slot=eq.{finger_slot}&is_active=eq.true")
        return data[0] if data else self._get_cached_student_by_finger(finger_slot)

    def _cache_student(self, data):
        try:
            conn = sqlite3.connect(OFFLINE_DB)
            c    = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO cached_students
                (finger_slot, student_id, full_name, course)
                VALUES (?,?,?,?)
            """, (data.get("finger_slot"), data.get("student_id"),
                  data.get("full_name"), data.get("course")))
            conn.commit()
            conn.close()
        except: pass

    def _cache_all_students(self, students):
        for s in students:
            if s.get("finger_slot"):
                self._cache_student(s)

    def _get_cached_students(self):
        try:
            conn = sqlite3.connect(OFFLINE_DB)
            c    = conn.cursor()
            c.execute("SELECT * FROM cached_students")
            rows = c.fetchall()
            conn.close()
            return [{"finger_slot":r[0],"student_id":r[1],
                     "full_name":r[2],"course":r[3]} for r in rows]
        except: return []

    def _get_cached_student_by_finger(self, slot):
        try:
            conn = sqlite3.connect(OFFLINE_DB)
            c    = conn.cursor()
            c.execute("SELECT * FROM cached_students WHERE finger_slot=?", (slot,))
            r = c.fetchone()
            conn.close()
            if r:
                return {"finger_slot":r[0],"student_id":r[1],
                        "full_name":r[2],"course":r[3]}
        except: pass
        return None

    # ── USERS ─────────────────────────────────────────
    def get_all_users(self):
        return self._get("users", "is_active=eq.true&order=full_name") or []

    def get_lecturers(self):
        return self._get("users",
                         "role=eq.lecturer&is_active=eq.true") or []

    def add_user(self, email, password, full_name, role,
                 teacher_id=None, department_id=None, school_id=None):
        """
        Insert a new user directly into the users table.
        Password stored as app_password (plain text), consistent with login().
        No Supabase Auth admin API call needed — the app uses its own auth.
        """
        try:
            # Check if email already exists
            existing = self._get("users", f"email=eq.{email}&limit=1")
            if existing:
                print(f"Add user error: email {email} already exists.")
                return None

            import uuid
            data = {
                "id":            str(uuid.uuid4()),
                "email":         email,
                "app_password":  password,
                "full_name":     full_name,
                "role":          role,
                "teacher_id":    teacher_id,
                "department_id": department_id,
                "school_id":     school_id,
                "is_active":     True
            }
            return self._post("users", data)
        except Exception as e:
            print(f"Add user error: {e}")
            return None

    def deactivate_user(self, user_id):
        return self._patch("users", f"id=eq.{user_id}", {"is_active": False})

    # ── UNITS ─────────────────────────────────────────
    def get_units(self, class_id=None):
        params = "select=*,users(full_name),departments(name),classes(level,intake,course)"
        if class_id:
            params += f"&class_id=eq.{class_id}"
        data = self._get("units", params)
        return data or []

    def add_unit(self, data):
        return self._post("units", data)

    # ── DEPARTMENTS ───────────────────────────────────
    def get_departments(self):
        return self._get("departments") or []

    def add_department(self, name, code, school_id):
        return self._post("departments",
                          {"name": name, "code": code,
                           "school_id": school_id})

    # ── SESSIONS ──────────────────────────────────────
    def start_session(self, data):
        return self._post("sessions", data)

    def end_session(self, session_id, end_time, total_present):
        return self._patch("sessions", f"id=eq.{session_id}",
                           {"end_time": end_time,
                            "total_present": total_present,
                            "is_active": False})

    def get_active_sessions(self):
        return self._get("sessions",
            "is_active=eq.true&select=*,users(full_name),units(code,name)") or []

    # ── ATTENDANCE ────────────────────────────────────
    def log_attendance(self, data):
        if not self.is_online():
            return self._log_offline(data)
        try:
            existing = self._get("attendance",
                f"student_id=eq.{data['student_id']}"
                f"&unit_id=eq.{data['unit_id']}"
                f"&date=eq.{data['date']}")
            if existing:
                return "duplicate"
            result = self._post("attendance", data)
            return "logged" if result else self._log_offline(data)
        except:
            return self._log_offline(data)

    def _log_offline(self, data):
        try:
            conn = sqlite3.connect(OFFLINE_DB)
            c    = conn.cursor()
            c.execute("INSERT INTO offline_attendance (data) VALUES (?)",
                      (json.dumps(data),))
            conn.commit()
            conn.close()
        except: pass
        return "offline"

    def sync_offline_data(self):
        if not self.is_online():
            return 0
        try:
            conn   = sqlite3.connect(OFFLINE_DB)
            c      = conn.cursor()
            c.execute("SELECT id, data FROM offline_attendance WHERE synced=0")
            rows   = c.fetchall()
            synced = 0
            for row_id, data_str in rows:
                try:
                    data = json.loads(data_str)
                    self._post("attendance", data)
                    c.execute(
                        "UPDATE offline_attendance SET synced=1 WHERE id=?",
                        (row_id,))
                    synced += 1
                except: pass
            conn.commit()
            conn.close()
            return synced
        except: return 0

    # ── COUNTS FOR DASHBOARD ──────────────────────────
    def count_students(self):
        return self._count("students", "is_active=eq.true")

    def count_lecturers(self):
        return self._count("users",
                           "role=eq.lecturer&is_active=eq.true")

    def count_active_sessions(self):
        return self._count("sessions", "is_active=eq.true")

    def count_today_attendance(self):
        from datetime import date
        today = date.today().isoformat()
        return self._count("attendance", f"date=eq.{today}")

    def log_activity(self, user_id, action, details=""):
        try:
            self._post("activity_log",
                       {"user_id": user_id,
                        "action":  action,
                        "details": details})
        except: pass