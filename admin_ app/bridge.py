"""
=============================================================
  BIOMETRIC ATTENDANCE SYSTEM v5 - Bridge Script
  Connects Arduino to Supabase database

  Protocol:
  - GET_LEVELS:{teacher_id}         → LEVELS:{name}:{level},{level},...
  - GET_CLASSES:{teacher_id},{level} → CLASSES:{id}|{intake},...
  - GET_UNITS:{teacher_id},{class_id} → UNITS:{id}|{code}|{name},...
  - SESSION_START:{teacher_id},{unit_id},{class_id}
  - SESSION_END:{unit_id}
  - ATT:{finger_slot}               → NAME:{name} / DUPLICATE / UNKNOWN
  - ENR:{slot}                      → (admin app handles enrollment)

  Uses direct HTTP requests (no supabase-py)
=============================================================
"""

import serial
import serial.tools.list_ports
import threading
import time
import json
import sqlite3
import uuid
import requests
from datetime import datetime
from config import SUPABASE_URL, SUPABASE_KEY, BAUD_RATE, OFFLINE_DB, \
                   LATE_THRESHOLD_MINS

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation"
}


def _get(table, params=""):
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?{params}",
            headers=HEADERS, timeout=15)
        if r.status_code in (200, 206):
            data = r.json()
            return data if isinstance(data, list) else [data]
        print(f"[BRIDGE] GET {table} error: {r.status_code} {r.text}")
        return []
    except Exception as e:
        print(f"[BRIDGE] GET {table} exception: {e}")
        return []


def _post(table, data):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=HEADERS, json=data, timeout=15)
        if r.status_code in (200, 201):
            result = r.json()
            return result[0] if isinstance(result, list) and result else result
        print(f"[BRIDGE] POST {table} error: {r.status_code} {r.text}")
        return None
    except Exception as e:
        print(f"[BRIDGE] POST {table} exception: {e}")
        return None


def _patch(table, params, data):
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/{table}?{params}",
            headers=HEADERS, json=data, timeout=15)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"[BRIDGE] PATCH {table} exception: {e}")
        return False


class Bridge:
    def __init__(self, port):
        self.port         = port
        self.serial       = None
        self.running      = False
        self.session      = None
        self.serial_lock  = threading.Lock()  # Prevents serial collision
        self._connect()

    def _connect(self):
        try:
            self.serial  = serial.Serial(self.port, BAUD_RATE, timeout=1)
            self.running = True
            # Listener thread
            threading.Thread(target=self._listen, daemon=True).start()
            # Auto-end checker thread
            threading.Thread(target=self._auto_end_loop, daemon=True).start()
            print(f"[BRIDGE] Connected on {self.port}")
        except Exception as e:
            print(f"[BRIDGE] Error connecting to {self.port}: {e}")

    def _listen(self):
        while self.running:
            try:
                if self.serial and self.serial.in_waiting > 0:
                    line = self.serial.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        print(f"[{self.port}] {line}")
                        self._handle(line)
                time.sleep(0.05)
            except Exception as e:
                print(f"[BRIDGE] Read error: {e}")
                time.sleep(2)

    def _serial_write(self, data):
        """Thread-safe serial write using lock."""
        with self.serial_lock:
            try:
                if self.serial and self.serial.is_open:
                    self._serial_write(data)
            except Exception as e:
                print(f"[BRIDGE] Serial write error: {e}")

    def _handle(self, line):
        # TEACHER_LOGIN:{teacher_id}
        # Bridge looks up lecturer, finds their current timetable slot,
        # auto-starts session, responds SESSION_OK:{unit_code} or ID_NOT_FOUND
        if line.startswith("TEACHER_LOGIN:"):
            teacher_id = line[14:].strip()
            self._teacher_login(teacher_id)

        # SESSION_END — Arduino ending session manually
        elif line.startswith("SESSION_END"):
            self._end_session()

        # ATT:{finger_slot}
        elif line.startswith("ATT:"):
            try:
                finger_slot = int(line[4:])
                self._log_attendance(finger_slot)
            except Exception as e:
                print(f"[BRIDGE] ATT parse error: {e}")

        # ENR:{slot} — finger enrolled, admin app handles the DB update
        elif line.startswith("ENR:"):
            try:
                slot = int(line[4:])
                print(f"[BRIDGE] Finger enrolled at slot {slot}. "
                      f"Assign to a student in the admin app.")
            except:
                pass

    def _teacher_login(self, teacher_id):
        """
        Handles TEACHER_LOGIN from Arduino.
        1. Looks up lecturer by teacher_id
        2. Finds their current timetable slot
        3. Auto-starts session
        4. Responds SESSION_OK:{unit_code} or ID_NOT_FOUND
        """
        try:
            # Get lecturer
            lecturers = _get("users",
                f"teacher_id=eq.{teacher_id}&is_active=eq.true&limit=1")
            if not lecturers:
                self._serial_write(b"ID_NOT_FOUND\n")
                print(f"[BRIDGE] Teacher not found: {teacher_id}")
                return

            lecturer = lecturers[0]
            now      = datetime.now()
            day_name = now.strftime("%A")
            hour_min = now.strftime("%H:%M")

            # Find current timetable slot
            timetable = _get("timetable",
                f"lecturer_id=eq.{lecturer['id']}"
                f"&day_of_week=eq.{day_name}"
                f"&is_active=eq.true")

            # Find slot that matches current time
            current_slot = None
            for tt in (timetable or []):
                start = tt.get("start_time","00:00")[:5]
                end   = tt.get("end_time","23:59")[:5]
                if start <= hour_min <= end:
                    current_slot = tt
                    break

            # If no current slot, use first slot of the day as fallback
            if not current_slot and timetable:
                current_slot = timetable[0]

            if not current_slot:
                # No timetable — start unscheduled session
                # Get lecturer's first unit
                units = _get("units",
                    f"lecturer_id=eq.{lecturer['id']}"
                    f"&is_active=eq.true&limit=1")
                if not units:
                    self._serial_write(b"ID_NOT_FOUND\n")
                    print(f"[BRIDGE] No units for {lecturer['full_name']}")
                    return
                unit     = units[0]
                class_id = unit.get("class_id")
            else:
                # Get unit and class from timetable slot
                units = _get("units",
                    f"id=eq.{current_slot['unit_id']}&limit=1")
                if not units:
                    self._serial_write(b"ID_NOT_FOUND\n")
                    return
                unit     = units[0]
                class_id = current_slot.get("class_id") or unit.get("class_id")

            # Create session
            session_code = str(uuid.uuid4())[:8].upper()
            date         = now.strftime("%Y-%m-%d")
            time_str     = now.strftime("%H:%M:%S")
            is_scheduled = current_slot is not None

            result = _post("sessions", {
                "session_code": session_code,
                "lecturer_id":  lecturer["id"],
                "unit_id":      unit["id"],
                "class_id":     class_id,
                "scanner_port": self.port,
                "date":         date,
                "start_time":   time_str,
                "is_active":    True,
                "unscheduled":  not is_scheduled
            })

            if result:
                self.session = {
                    "id":            result.get("id"),
                    "code":          session_code,
                    "lecturer_id":   lecturer["id"],
                    "lecturer_name": lecturer["full_name"],
                    "unit_id":       unit["id"],
                    "unit_code":     unit["code"],
                    "unit_name":     unit.get("name",""),
                    "class_id":      class_id,
                    "start_time":    now,
                    "total_present": 0,
                    "unscheduled":   not is_scheduled
                }
                # Respond to Arduino with unit code
                response = f"SESSION_OK:{unit['code']}\n"
                self._serial_write(response.encode())
                status = "SCHEDULED" if is_scheduled else "UNSCHEDULED"
                print(f"[BRIDGE] Session started: {session_code} | "
                      f"{lecturer['full_name']} | {unit['code']} | {status}")
            else:
                self._serial_write(b"ID_NOT_FOUND\n")

        except Exception as e:
            print(f"[BRIDGE] Teacher login error: {e}")
            self._serial_write(b"ID_NOT_FOUND\n")
        """
        Returns the distinct levels (4, 5, 6) this lecturer teaches.
        Looks up units assigned to this lecturer and extracts unique levels
        from their linked classes.

        Format sent: LEVELS:{name}:{level},{level},...
        e.g.         LEVELS:Dr. Otieno:4,5,6
        Or:          LEVELS:NOT_FOUND: if teacher not found
        """
        try:
            # Get lecturer
            lecturers = _get("users",
                f"teacher_id=eq.{teacher_id}&is_active=eq.true&limit=1")
            if not lecturers:
                self._serial_write(b"LEVELS:NOT_FOUND:\n")
                print(f"[BRIDGE] Teacher ID not found: {teacher_id}")
                return

            lecturer = lecturers[0]
            name     = lecturer.get("full_name", "Unknown")
            lec_id   = lecturer.get("id")

            # Get all active units for this lecturer with their class info
            units = _get("units",
                f"lecturer_id=eq.{lec_id}"
                f"&is_active=eq.true"
                f"&select=class_id,classes(level)")

            # Extract unique levels
            seen_levels = set()
            for u in (units or []):
                cls = u.get("classes")
                if cls and cls.get("level"):
                    seen_levels.add(str(cls["level"]))

            if not seen_levels:
                self._serial_write(b"LEVELS:NOT_FOUND:\n")
                print(f"[BRIDGE] No classes found for {name}")
                return

            levels_str = ",".join(sorted(seen_levels))
            response = f"LEVELS:{name}:{levels_str}\n"
            self._serial_write(response.encode())
            print(f"[BRIDGE] Sent levels for {name}: {levels_str}")

        except Exception as e:
            print(f"[BRIDGE] GET_LEVELS error: {e}")
            self._serial_write(b"LEVELS:NOT_FOUND:\n")

    def _send_classes_for_level(self, teacher_id, level):
        """
        Returns intake numbers only — no UUIDs sent to Arduino.
        Bridge keeps UUID mapping internally in self.class_map.

        Format sent: CLASSES:{intake},{intake},...
        e.g.         CLASSES:251,249
        Or:          CLASSES:NONE if none found
        """
        try:
            lecturers = _get("users",
                f"teacher_id=eq.{teacher_id}&is_active=eq.true&limit=1")
            if not lecturers:
                self._serial_write(b"CLASSES:NONE\n")
                return
            lec_id = lecturers[0].get("id")

            units = _get("units",
                f"lecturer_id=eq.{lec_id}"
                f"&is_active=eq.true"
                f"&select=class_id,classes(id,level,intake)"
                f"&classes.level=eq.{level}")

            seen_ids = set()
            # Store UUID map on bridge for later resolution
            self.class_map = {}  # intake -> class_id
            intakes = []
            for u in (units or []):
                cls = u.get("classes")
                if not cls:
                    continue
                if str(cls.get("level", "")) != str(level):
                    continue
                cid = cls.get("id")
                intake = str(cls.get("intake", "?"))
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    self.class_map[intake] = cid
                    intakes.append(intake)

            if not intakes:
                self._serial_write(b"CLASSES:NONE\n")
                return

            response = "CLASSES:" + ",".join(intakes) + "\n"
            self._serial_write(response.encode())
            print(f"[BRIDGE] Sent {len(intakes)} class(es) for level {level}")

        except Exception as e:
            print(f"[BRIDGE] GET_CLASSES error: {e}")
            self._serial_write(b"CLASSES:NONE\n")

    def _send_units(self, teacher_id, level, intake):
        """
        Fetch units by teacher_id + level + intake (no UUID needed from Arduino).
        Bridge resolves class UUID using self.class_map.
        Sends only unit codes — no UUIDs to Arduino.
        Stores unit_map internally for session start.

        Format sent: UNITS:{code},{code},...
        Or: UNITS:NONE if none found
        """
        try:
            lecturers = _get("users",
                f"teacher_id=eq.{teacher_id}&is_active=eq.true&limit=1")
            if not lecturers:
                self._serial_write(b"UNITS:NONE\n")
                return
            lec_id = lecturers[0].get("id")

            # Resolve class UUID from intake
            class_id = getattr(self, 'class_map', {}).get(intake)
            if not class_id:
                # Fallback: look up from database
                classes = _get("classes",
                    f"intake=eq.{intake}&level=eq.{level}&is_active=eq.true&limit=1")
                if classes:
                    class_id = classes[0].get("id")

            if not class_id:
                self._serial_write(b"UNITS:NONE\n")
                print(f"[BRIDGE] Class not found: level={level} intake={intake}")
                return

            units = _get("units",
                f"lecturer_id=eq.{lec_id}"
                f"&class_id=eq.{class_id}"
                f"&is_active=eq.true")

            if not units:
                self._serial_write(b"UNITS:NONE\n")
                return

            # Store unit map for session start
            self.unit_map = {u['code']: u for u in units}

            codes = ",".join(u['code'] for u in units)
            response = f"UNITS:{codes}\n"
            self._serial_write(response.encode())
            print(f"[BRIDGE] Sent {len(units)} unit(s)")

        except Exception as e:
            print(f"[BRIDGE] GET_UNITS error: {e}")
            self._serial_write(b"UNITS:NONE\n")

    def _start_session(self, teacher_id, level, intake, unit_code):
        """
        Start a session. Resolves UUIDs from labels internally.
        Arduino sends: teacher_id, level, intake, unit_code
        """
        try:
            # Get lecturer
            lecturers = _get("users",
                f"teacher_id=eq.{teacher_id}&is_active=eq.true&limit=1")
            if not lecturers:
                print(f"[BRIDGE] Session start: lecturer not found ({teacher_id})")
                return
            lecturer = lecturers[0]

            # Resolve class UUID
            class_id = getattr(self, 'class_map', {}).get(intake)
            if not class_id:
                classes = _get("classes",
                    f"intake=eq.{intake}&level=eq.{level}"
                    f"&is_active=eq.true&limit=1")
                if classes:
                    class_id = classes[0].get("id")
            if not class_id:
                print(f"[BRIDGE] Session start: class not found (L{level}/{intake})")
                return

            # Resolve unit UUID
            unit = getattr(self, 'unit_map', {}).get(unit_code)
            if not unit:
                units = _get("units",
                    f"code=eq.{unit_code}"
                    f"&lecturer_id=eq.{lecturer['id']}"
                    f"&class_id=eq.{class_id}&limit=1")
                if units:
                    unit = units[0]
            if not unit:
                print(f"[BRIDGE] Session start: unit not found ({unit_code})")
                return

            now      = datetime.now()
            date     = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M:%S")

            # Timetable validation
            day_name = now.strftime("%A")
            hour_min = now.strftime("%H:%M")
            timetable = _get("timetable",
                f"unit_id=eq.{unit['id']}"
                f"&lecturer_id=eq.{lecturer['id']}"
                f"&class_id=eq.{class_id}"
                f"&day_of_week=eq.{day_name}"
                f"&is_active=eq.true")

            is_scheduled = False
            if timetable:
                for tt in timetable:
                    start = tt.get("start_time", "00:00")[:5]
                    end   = tt.get("end_time", "23:59")[:5]
                    if start <= hour_min <= end:
                        is_scheduled = True
                        break

            if not is_scheduled:
                warn_msg = f"TIMETABLE_WARN:{unit['code']}\n"
                self._serial_write(warn_msg.encode())
                print(f"[BRIDGE] Timetable warning sent for {unit['code']}")
                time.sleep(8)

            session_code = str(uuid.uuid4())[:8].upper()
            result = _post("sessions", {
                "session_code": session_code,
                "lecturer_id":  lecturer["id"],
                "unit_id":      unit["id"],
                "class_id":     class_id,
                "scanner_port": self.port,
                "date":         date,
                "start_time":   time_str,
                "is_active":    True,
                "unscheduled":  not is_scheduled
            })

            if result:
                self.session = {
                    "id":            result.get("id"),
                    "code":          session_code,
                    "lecturer_id":   lecturer["id"],
                    "lecturer_name": lecturer["full_name"],
                    "unit_id":       unit["id"],
                    "unit_code":     unit["code"],
                    "unit_name":     unit.get("name", ""),
                    "class_id":      class_id,
                    "start_time":    now,
                    "total_present": 0
                }
                status = "SCHEDULED" if is_scheduled else "UNSCHEDULED"
                print(f"[BRIDGE] Session started: {session_code} | "
                      f"{lecturer['full_name']} | {unit['code']} | {status}")

        except Exception as e:
            print(f"[BRIDGE] Session start error: {e}")

    def _end_session(self):
        if not self.session:
            return
        try:
            end_time = datetime.now().strftime("%H:%M:%S")
            _patch("sessions", f"id=eq.{self.session['id']}", {
                "end_time":      end_time,
                "total_present": self.session["total_present"],
                "is_active":     False
            })
            print(f"[BRIDGE] Session ended: {self.session['code']} | "
                  f"Total present: {self.session['total_present']}")
            self.session = None
        except Exception as e:
            print(f"[BRIDGE] Session end error: {e}")

    def _log_attendance(self, finger_slot):
        # Step 1: Ensure we have a session
        if not self.session:
            sessions = _get("sessions", "is_active=eq.true&limit=1")
            if sessions:
                s = sessions[0]
                self.session = {
                    "id":            s.get("id"),
                    "code":          s.get("session_code","DEMO"),
                    "lecturer_id":   s.get("lecturer_id"),
                    "lecturer_name": "",
                    "unit_id":       s.get("unit_id"),
                    "unit_code":     "DEMO",
                    "class_id":      s.get("class_id"),
                    "start_time":    datetime.now(),
                    "total_present": s.get("total_present", 0)
                }
                print(f"[BRIDGE] Resumed session: {self.session['code']}")
            else:
                now = datetime.now()
                result = _post("sessions", {
                    "session_code":  "DEMO01",
                    "date":          now.strftime("%Y-%m-%d"),
                    "start_time":    now.strftime("%H:%M:%S"),
                    "is_active":     True,
                    "unscheduled":   True,
                    "total_present": 0
                })
                if result:
                    self.session = {
                        "id":            result.get("id"),
                        "code":          "DEMO01",
                        "lecturer_id":   None,
                        "lecturer_name": "",
                        "unit_id":       None,
                        "unit_code":     "DEMO",
                        "class_id":      None,
                        "start_time":    now,
                        "total_present": 0
                    }
                    print("[BRIDGE] Auto-created demo session")
                else:
                    print("[BRIDGE] Could not create session.")
                    return

        # Step 2: Look up student
        students = _get("students",
            f"finger_slot=eq.{finger_slot}&is_active=eq.true&limit=1")
        if not students:
            self._serial_write(b"UNKNOWN\n")
            print(f"[BRIDGE] Unknown finger slot: {finger_slot}")
            return

        student = students[0]
        now     = datetime.now()
        date    = now.strftime("%Y-%m-%d")
        time_in = now.strftime("%H:%M:%S")
        print(f"[BRIDGE] Student found: {student['full_name']}")

        # Step 3: Check duplicate
        if self.session.get("unit_id"):
            dup = _get("attendance",
                f"student_id=eq.{student['id']}"
                f"&unit_id=eq.{self.session['unit_id']}"
                f"&date=eq.{date}")
            if dup:
                self._serial_write(b"DUPLICATE\n")
                print(f"[BRIDGE] {student['full_name']} already marked.")
                return

        # Step 4: Determine status
        mins   = (now - self.session["start_time"]).seconds // 60
        status = "late" if mins > LATE_THRESHOLD_MINS else "present"
        print(f"[BRIDGE] Status: {status}")

        # Step 5: Log attendance
        try:
            att = {
                "student_id": student["id"],
                "date":       date,
                "time_in":    time_in,
                "status":     status,
                "synced":     True
            }
            if self.session.get("id"):       att["session_id"] = self.session["id"]
            if self.session.get("unit_id"):  att["unit_id"]    = self.session["unit_id"]
            if self.session.get("class_id"): att["class_id"]   = self.session["class_id"]
            print(f"[BRIDGE] Posting attendance...")
            result = _post("attendance", att)
            print(f"[BRIDGE] Attendance posted: {result is not None}")
        except Exception as e:
            print(f"[BRIDGE] Attendance post error: {e}")

        # Step 6: Update session count
        try:
            self.session["total_present"] += 1
            if self.session.get("id"):
                _patch("sessions", f"id=eq.{self.session['id']}", {
                    "total_present": self.session["total_present"]
                })
        except Exception as e:
            print(f"[BRIDGE] Session update error: {e}")

        # Step 7: Send name to Arduino
        name = student["full_name"]
        adm  = student.get("admission_number", "")
        print(f"[BRIDGE] Sending name: {name}|{adm}")
        self._serial_write(f"NAME:{name}|{adm}\n".encode())
        print(f"[BRIDGE] LOGGED: {name} | {status.upper()} | {time_in}")

    def _save_offline(self, finger_slot):
        try:
            conn = sqlite3.connect(OFFLINE_DB)
            c    = conn.cursor()
            c.execute(
                "INSERT INTO offline_attendance (data) VALUES (?)",
                (json.dumps({
                    "finger_slot": finger_slot,
                    "session_id":  self.session["id"] if self.session else None,
                    "unit_id":     self.session["unit_id"] if self.session else None,
                    "class_id":    self.session["class_id"] if self.session else None,
                    "date":        datetime.now().strftime("%Y-%m-%d"),
                    "time_in":     datetime.now().strftime("%H:%M:%S"),
                    "status":      "present"
                }),)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[BRIDGE] Offline save error: {e}")

    def _auto_end_loop(self):
        """
        Background thread — checks every 60 seconds if the active session
        should be automatically ended.

        Logic:
        - Scheduled session: ends at timetable end_time
        - Unscheduled session: ends 2 hours after start_time
        """
        while self.running:
            time.sleep(60)
            try:
                if not self.session:
                    continue

                now        = datetime.now()
                session_id = self.session.get("id")
                unit_id    = self.session.get("unit_id")
                class_id   = self.session.get("class_id")
                lec_id     = self.session.get("lecturer_id")
                start_time = self.session.get("start_time")

                should_end  = False
                reason      = ""

                # Get session record from Supabase to check unscheduled flag
                records = _get("sessions", f"id=eq.{session_id}&limit=1")
                if not records:
                    continue
                record = records[0]

                if record.get("unscheduled", False):
                    # Unscheduled — end 2 hours after start
                    elapsed_mins = (now - start_time).seconds // 60
                    if elapsed_mins >= 120:
                        should_end = True
                        reason = "2-hour limit reached (unscheduled session)"
                else:
                    # Scheduled — find timetable end_time
                    day_name = now.strftime("%A")
                    timetable = _get("timetable",
                        f"unit_id=eq.{unit_id}"
                        f"&lecturer_id=eq.{lec_id}"
                        f"&class_id=eq.{class_id}"
                        f"&day_of_week=eq.{day_name}"
                        f"&is_active=eq.true")

                    if timetable:
                        for tt in timetable:
                            end_str = tt.get("end_time", "")[:5]  # "HH:MM"
                            if end_str:
                                end_h, end_m = map(int, end_str.split(":"))
                                scheduled_end = now.replace(
                                    hour=end_h, minute=end_m, second=0)
                                if now >= scheduled_end:
                                    should_end = True
                                    reason = f"Scheduled end time reached ({end_str})"
                                    break
                    else:
                        # Timetable entry missing — fall back to 2-hour limit
                        elapsed_mins = (now - start_time).seconds // 60
                        if elapsed_mins >= 120:
                            should_end = True
                            reason = "2-hour limit reached (no timetable entry)"

                if should_end:
                    print(f"[BRIDGE] Auto-ending session {self.session['code']} — {reason}")
                    # End in database first
                    self._end_session()
                    # Then notify Arduino
                    self._serial_write(b"FORCE_END\n")

            except Exception as e:
                print(f"[BRIDGE] Auto-end check error: {e}")

    def stop(self):
        self.running = False
        self._end_session()
        if self.serial and self.serial.is_open:
            self.serial.close()


def auto_detect_and_run():
    print("[BRIDGE] Detecting Arduino ports...")
    bridges = {}
    while True:
        ports = [
            p.device for p in serial.tools.list_ports.comports()
            if any(x in (p.description or "").lower()
                   for x in ["arduino", "ch340", "cp210", "ftdi", "usb serial"])
        ]
        for port in ports:
            if port not in bridges:
                print(f"[BRIDGE] New scanner detected: {port}")
                bridges[port] = Bridge(port)
        for port in list(bridges.keys()):
            if port not in ports:
                print(f"[BRIDGE] Scanner disconnected: {port}")
                bridges[port].stop()
                del bridges[port]
        time.sleep(5)


if __name__ == "__main__":
    print("=" * 55)
    print("  BIOMETRIC ATTENDANCE SYSTEM - Bridge v5")
    print("  Connecting hardware to Supabase database")
    print("=" * 55)
    try:
        auto_detect_and_run()
    except KeyboardInterrupt:
        print("\n[BRIDGE] Stopped.")
