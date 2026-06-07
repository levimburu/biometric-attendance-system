"""
Biometric Attendance System v5 - Fixed dark tables
"""
import customtkinter as ctk
from tkinter import messagebox
import threading
import time
import serial
import serial.tools.list_ports
from datetime import datetime, date
from config import APP_NAME, APP_VERSION, COMPANY_NAME, BAUD_RATE
from database import DatabaseManager

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

TEAL   = "#0D9488"
NAVY   = "#0D1B2A"
DARK   = "#112233"
DARKER = "#0A1628"
AMBER  = "#F59E0B"
RED    = "#EF4444"
GREEN  = "#22C55E"
GRAY   = "#64748B"
WHITE  = "#F8FAFC"
BLUE   = "#3B82F6"
PURPLE = "#8B5CF6"
ROW1   = "#0f1a2e"
ROW2   = "#112233"

ROLE_COLORS = {
    "super_admin":         TEAL,
    "admin":               TEAL,
    "principal":           PURPLE,
    "principal_secretary": BLUE,
    "hod":                 AMBER,
    "hod_secretary":       AMBER,
    "lecturer":            GREEN,
}


# ══════════════════════════════════════════════════════
# CUSTOM DARK TABLE (replaces ttk.Treeview)
# ══════════════════════════════════════════════════════
class DarkTable(ctk.CTkFrame):
    """A fully dark-themed scrollable table using CTk widgets."""

    def __init__(self, parent, columns, **kwargs):
        super().__init__(parent, fg_color=NAVY, **kwargs)
        self.columns  = columns
        self.rows     = []
        self._sel_row = None
        self._sel_iid = None
        self._iid_map = {}

        # Header
        hdr = ctk.CTkFrame(self, fg_color=TEAL, corner_radius=0)
        hdr.pack(fill="x")
        for col, w, label in columns:
            ctk.CTkLabel(hdr, text=label, width=w,
                         font=ctk.CTkFont("Helvetica",10,weight="bold"),
                         text_color=WHITE, anchor="w"
                         ).pack(side="left", padx=6, pady=6)

        # Scrollable body
        self.body = ctk.CTkScrollableFrame(self, fg_color=DARKER,
                                            corner_radius=0)
        self.body.pack(fill="both", expand=True)

    def insert(self, values, iid=None):
        idx = len(self.rows)
        bg  = ROW1 if idx % 2 == 0 else ROW2

        row_frame = ctk.CTkFrame(self.body, fg_color=bg,
                                  corner_radius=0, height=30)
        row_frame.pack(fill="x", pady=(0,1))
        row_frame.pack_propagate(False)

        for i, (col, w, label) in enumerate(self.columns):
            val = values[i] if i < len(values) else ""
            # Color status cells
            color = WHITE
            if str(val) in ("Active","YES","Present","Yes","● Active"):
                color = GREEN
            elif str(val) in ("Inactive","NO","Absent","No","■ Ended"):
                color = RED
            elif str(val) in ("Late","⚠️ Watch"):
                color = AMBER
            elif str(val).startswith("✅"):
                color = GREEN
            elif str(val).startswith("❌"):
                color = RED

            lbl = ctk.CTkLabel(row_frame, text=str(val), width=w,
                                font=ctk.CTkFont("Helvetica",10),
                                text_color=color, anchor="w")
            lbl.pack(side="left", padx=6)
            lbl.bind("<Button-1>", lambda e, rf=row_frame, i=iid: self._select(rf, i))

        row_frame.bind("<Button-1>", lambda e, rf=row_frame, i=iid: self._select(rf, i))

        key = iid or str(idx)
        self._iid_map[key] = {"frame": row_frame, "values": values}
        self.rows.append(key)
        return key

    def _select(self, frame, iid):
        # Deselect previous
        if self._sel_row:
            idx = self.rows.index(self._sel_iid) if self._sel_iid in self.rows else 0
            self._sel_row.configure(fg_color=ROW1 if idx%2==0 else ROW2)
        self._sel_row = frame
        self._sel_iid = iid
        frame.configure(fg_color=TEAL)

    def focus(self):
        return self._sel_iid

    def item(self, iid, key):
        if iid and iid in self._iid_map:
            return self._iid_map[iid].get(key, ())
        return ()

    def get_children(self):
        return list(self.rows)

    def delete(self, iid):
        if iid in self._iid_map:
            self._iid_map[iid]["frame"].destroy()
            del self._iid_map[iid]
            if iid in self.rows:
                self.rows.remove(iid)

    def clear(self):
        for key in list(self._iid_map.keys()):
            self._iid_map[key]["frame"].destroy()
        self._iid_map.clear()
        self.rows.clear()
        self._sel_row = None
        self._sel_iid = None


# ══════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════
class LoginWindow:
    def __init__(self, on_login):
        self.on_login = on_login
        self.db = DatabaseManager()
        self.root = ctk.CTk()
        self.root.title(f"{APP_NAME} — Login")
        self.root.geometry("460x560")
        self.root.resizable(False, False)
        self.root.configure(fg_color=NAVY)
        self._center()
        self._build()
        self.root.mainloop()

    def _center(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth()  - 460) // 2
        y = (self.root.winfo_screenheight() - 560) // 2
        self.root.geometry(f"460x560+{x}+{y}")

    def _build(self):
        hdr = ctk.CTkFrame(self.root, fg_color=TEAL, corner_radius=0, height=130)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=COMPANY_NAME,
                     font=ctk.CTkFont("Helvetica",12), text_color="white").pack(pady=(22,2))
        ctk.CTkLabel(hdr, text="Biometric Attendance",
                     font=ctk.CTkFont("Helvetica",20,weight="bold"),
                     text_color="white").pack()
        ctk.CTkLabel(hdr, text="Management System",
                     font=ctk.CTkFont("Helvetica",20,weight="bold"),
                     text_color="white").pack()
        ctk.CTkLabel(hdr, text=f"v{APP_VERSION}",
                     font=ctk.CTkFont("Helvetica",10),
                     text_color="#CCFBF1").pack(pady=(2,0))

        form = ctk.CTkFrame(self.root, fg_color=NAVY)
        form.pack(fill="both", expand=True, padx=35, pady=25)

        ctk.CTkLabel(form, text="Sign In to Your Account",
                     font=ctk.CTkFont("Helvetica",16,weight="bold"),
                     text_color=WHITE).pack(anchor="w", pady=(0,4))
        ctk.CTkLabel(form,
                     text="Contact your administrator if you need access.",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=GRAY).pack(anchor="w", pady=(0,18))

        ctk.CTkLabel(form, text="Email Address",
                     font=ctk.CTkFont("Helvetica",12),
                     text_color=WHITE).pack(anchor="w")
        self.email = ctk.CTkEntry(form, height=42,
                                   placeholder_text="your@email.com",
                                   fg_color=DARK, border_color=TEAL,
                                   font=ctk.CTkFont("Helvetica",12))
        self.email.pack(fill="x", pady=(4,14))

        ctk.CTkLabel(form, text="Password",
                     font=ctk.CTkFont("Helvetica",12),
                     text_color=WHITE).pack(anchor="w")
        self.pwd = ctk.CTkEntry(form, height=42,
                                 placeholder_text="••••••••", show="•",
                                 fg_color=DARK, border_color=TEAL,
                                 font=ctk.CTkFont("Helvetica",12))
        self.pwd.pack(fill="x", pady=(4,5))

        ctk.CTkLabel(form,
                     text="Forgot password? Contact your administrator.",
                     font=ctk.CTkFont("Helvetica",10),
                     text_color=GRAY).pack(anchor="e", pady=(0,16))

        self.err = ctk.CTkLabel(form, text="",
                                 font=ctk.CTkFont("Helvetica",11),
                                 text_color=RED)
        self.err.pack()

        self.btn = ctk.CTkButton(form, text="SIGN IN", height=44,
                                  fg_color=TEAL, hover_color="#0F766E",
                                  font=ctk.CTkFont("Helvetica",13,weight="bold"),
                                  command=self._login)
        self.btn.pack(fill="x", pady=(5,0))
        self.pwd.bind("<Return>", lambda e: self._login())

        ctk.CTkLabel(self.root,
                     text=f"{COMPANY_NAME}  •  {APP_NAME}  •  v{APP_VERSION}",
                     font=ctk.CTkFont("Helvetica",9),
                     text_color=GRAY).pack(pady=8)

    def _login(self):
        email = self.email.get().strip()
        pwd   = self.pwd.get().strip()
        if not email or not pwd:
            self.err.configure(text="Please enter email and password.")
            return
        self.btn.configure(text="Signing in...", state="disabled")
        self.err.configure(text="")

        def attempt():
            try:
                user = self.db.login(email, pwd)
                if user:
                    self.root.after(0, lambda: self._success(user))
                else:
                    self.root.after(0, lambda: self.err.configure(
                        text="Invalid email or password. Try again."))
                    self.root.after(0, lambda: self.btn.configure(
                        text="SIGN IN", state="normal"))
            except Exception as e:
                print(f"Login error: {e}")
                self.root.after(0, lambda: self.err.configure(
                    text="Connection error. Check internet."))
                self.root.after(0, lambda: self.btn.configure(
                    text="SIGN IN", state="normal"))
        threading.Thread(target=attempt, daemon=True).start()

    def _success(self, user_data):
        self.root.destroy()
        self.on_login(user_data, self.db)


# ══════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════
class MainApp:
    def __init__(self, user, db):
        self.user = user
        self.db   = db
        self.role = user.get("role","lecturer")

        self.root = ctk.CTk()
        self.root.title(f"{APP_NAME} — {user.get('full_name','')}")
        self.root.geometry("1280x750")
        self.root.configure(fg_color=NAVY)
        self._center()
        self._build_ui()
        self._show("dashboard")
        self._start_sync()
        self.root.mainloop()

    def _center(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth()  - 1280) // 2
        y = (self.root.winfo_screenheight() - 750)  // 2
        self.root.geometry(f"1280x750+{x}+{y}")

    def _build_ui(self):
        self.sidebar = ctk.CTkFrame(self.root, width=235,
                                     fg_color=DARKER, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        lf = ctk.CTkFrame(self.sidebar, fg_color=TEAL,
                           corner_radius=0, height=75)
        lf.pack(fill="x"); lf.pack_propagate(False)
        ctk.CTkLabel(lf, text=COMPANY_NAME,
                     font=ctk.CTkFont("Helvetica",10),
                     text_color="white").pack(pady=(12,0))
        ctk.CTkLabel(lf, text="Attendance System",
                     font=ctk.CTkFont("Helvetica",13,weight="bold"),
                     text_color="white").pack()

        uf = ctk.CTkFrame(self.sidebar, fg_color=DARK, corner_radius=8)
        uf.pack(fill="x", padx=12, pady=10)
        ctk.CTkLabel(uf, text=self.user.get("full_name",""),
                     font=ctk.CTkFont("Helvetica",12,weight="bold"),
                     text_color=WHITE).pack(pady=(10,2))
        ctk.CTkLabel(uf,
                     text=self.role.upper().replace("_"," "),
                     font=ctk.CTkFont("Helvetica",10),
                     text_color=ROLE_COLORS.get(self.role, TEAL)
                     ).pack(pady=(0,10))

        ctk.CTkLabel(self.sidebar, text="NAVIGATION",
                     font=ctk.CTkFont("Helvetica",9),
                     text_color=GRAY).pack(anchor="w", padx=15, pady=(4,4))

        self.nav_btns = {}
        for label, icon, page in self._nav_items():
            btn = ctk.CTkButton(self.sidebar,
                                text=f"  {icon}  {label}",
                                anchor="w", height=40,
                                fg_color="transparent",
                                hover_color=DARK,
                                text_color=WHITE,
                                font=ctk.CTkFont("Helvetica",12),
                                command=lambda p=page: self._show(p))
            btn.pack(fill="x", padx=8, pady=2)
            self.nav_btns[page] = btn

        self.online_lbl = ctk.CTkLabel(self.sidebar,
                                        text="● Checking...",
                                        font=ctk.CTkFont("Helvetica",10),
                                        text_color=AMBER)
        self.online_lbl.pack(side="bottom", pady=10)

        ctk.CTkButton(self.sidebar, text="Sign Out",
                      fg_color=RED, hover_color="#B91C1C", height=36,
                      font=ctk.CTkFont("Helvetica",11),
                      command=self._signout).pack(
                          side="bottom", fill="x", padx=12, pady=(0,5))

        self.content = ctk.CTkFrame(self.root, fg_color=NAVY, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

    def _nav_items(self):
        base = [("Dashboard","🏠","dashboard"),
                ("Attendance","📋","attendance")]
        if self.role in ["super_admin","admin","principal","principal_secretary","hod","hod_secretary"]:
            base += [("Timetable","📅","timetable"),
                     ("Lec. Report","📊","lec_report")]
        if self.role in ["super_admin","admin"]:
            base += [
                ("Students","👥","students"),
                ("Lecturers","👨‍🏫","lecturers"),
                ("Departments","🏫","departments"),
                ("Classes","🎓","classes"),
                ("Units","📚","units"),
                ("Rooms","🚪","rooms"),
                ("Semesters","📆","semesters"),
                ("Enroll Finger","👆","enroll"),
                ("User Accounts","🔐","users"),
                ("Settings","⚙️","settings"),
            ]
        elif self.role in ["hod","hod_secretary"]:
            base += [("Students","👥","students"),
                     ("Units","📚","units")]
        elif self.role == "lecturer":
            base += [("My Classes","📚","my_classes")]
        return base

    def _clear(self):
        for w in self.content.winfo_children(): w.destroy()

    def _header(self, title, subtitle=""):
        h = ctk.CTkFrame(self.content, fg_color=DARK,
                          corner_radius=0, height=68)
        h.pack(fill="x"); h.pack_propagate(False)
        ctk.CTkLabel(h, text=title,
                     font=ctk.CTkFont("Helvetica",20,weight="bold"),
                     text_color=WHITE).pack(anchor="w", padx=25, pady=(14,2))
        if subtitle:
            ctk.CTkLabel(h, text=subtitle,
                         font=ctk.CTkFont("Helvetica",11),
                         text_color=GRAY).pack(anchor="w", padx=25)

    def _show(self, page):
        for p, btn in self.nav_btns.items():
            btn.configure(fg_color=TEAL if p==page else "transparent")
        self._clear()
        {
            "dashboard":  self._dashboard,
            "students":   self._students,
            "lecturers":  self._lecturers,
            "departments":self._departments,
            "classes":    self._classes,
            "units":      self._units,
            "rooms":      self._rooms,
            "semesters":  self._semesters,
            "timetable":  self._timetable,
            "lec_report": self._lec_report,
            "attendance": self._attendance,
            "my_classes": self._my_classes,
            "enroll":     self._enroll,
            "users":      self._user_accounts,
            "settings":   self._settings,
        }.get(page, lambda: None)()

    # ── DASHBOARD ────────────────────────────────────
    def _dashboard(self):
        self._header("Dashboard", f"Welcome back, {self.user.get('full_name','')}")
        body = ctk.CTkScrollableFrame(self.content, fg_color=NAVY)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        # Stats row
        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x", pady=(0,20))

        def make_stat(val, label, color):
            c = ctk.CTkFrame(stats, fg_color=DARK, corner_radius=12)
            c.pack(side="left", fill="both", expand=True, padx=5)
            ctk.CTkLabel(c, text=str(val),
                         font=ctk.CTkFont("Helvetica",32,weight="bold"),
                         text_color=color).pack(pady=(18,2))
            ctk.CTkLabel(c, text=label,
                         font=ctk.CTkFont("Helvetica",11),
                         text_color=GRAY).pack(pady=(0,18))

        try:
            stu = self.db.count_students()
            make_stat(stu, "Total Students", TEAL)
            lec = self.db.count_lecturers()
            make_stat(lec, "Lecturers", AMBER)
            ses = self.db.count_active_sessions()
            make_stat(ses, "Active Sessions", GREEN)
            att = self.db.count_today_attendance()
            make_stat(att, "Present Today", BLUE)
        except Exception as e:
            print(f"Stats error: {e}")
            make_stat("—", "Total Students", TEAL)
            make_stat("—", "Lecturers", AMBER)
            make_stat("—", "Active Sessions", GREEN)
            make_stat("—", "Present Today", BLUE)

        sf = ctk.CTkFrame(body, fg_color=DARK, corner_radius=12)
        sf.pack(fill="x", pady=(0,15))
        ctk.CTkLabel(sf, text="System Status",
                     font=ctk.CTkFont("Helvetica",14,weight="bold"),
                     text_color=WHITE).pack(anchor="w", padx=20, pady=(15,5))

        online = self.db.is_online()
        status = "● Online — Connected to Supabase" if online else "● Offline — Using local storage"
        color  = GREEN if online else AMBER
        ctk.CTkLabel(sf, text=status,
                     font=ctk.CTkFont("Helvetica",12),
                     text_color=color).pack(anchor="w",padx=20,pady=(0,15))

        af = ctk.CTkFrame(body, fg_color=DARK, corner_radius=12)
        af.pack(fill="x")
        ctk.CTkLabel(af, text="Quick Actions",
                     font=ctk.CTkFont("Helvetica",14,weight="bold"),
                     text_color=WHITE).pack(anchor="w", padx=20, pady=(15,10))
        bf = ctk.CTkFrame(af, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=(0,15))
        for lbl, color, page in [
            ("+ Add Student",  TEAL,   "students"),
            ("+ Add Lecturer", AMBER,  "lecturers"),
            ("Timetable",      BLUE,   "timetable"),
            ("Lec. Report",    PURPLE, "lec_report"),
            ("Attendance",     GRAY,   "attendance"),
        ]:
            ctk.CTkButton(bf, text=lbl, fg_color=color,
                          hover_color=DARK, height=38,
                          font=ctk.CTkFont("Helvetica",11,weight="bold"),
                          command=lambda p=page: self._show(p)
                          ).pack(side="left", padx=(0,8))

    # ── TABLE PAGE HELPER ────────────────────────────
    def _table_page(self, title, subtitle, cols,
                    add_cmd=None, edit_cmd=None,
                    delete_cmd=None, add_label="+ Add"):
        self._header(title, subtitle)

        tb = ctk.CTkFrame(self.content, fg_color=DARK,
                          corner_radius=0, height=50)
        tb.pack(fill="x"); tb.pack_propagate(False)

        if add_cmd:
            ctk.CTkButton(tb, text=add_label,
                          fg_color=TEAL, hover_color="#0F766E",
                          height=34,
                          font=ctk.CTkFont("Helvetica",11,weight="bold"),
                          command=add_cmd).pack(side="left",padx=12,pady=8)
        if edit_cmd:
            ctk.CTkButton(tb, text="✎ Edit",
                          fg_color=DARK, hover_color=NAVY,
                          height=34,
                          font=ctk.CTkFont("Helvetica",11),
                          command=edit_cmd).pack(side="left",padx=(0,8),pady=8)
        if delete_cmd:
            ctk.CTkButton(tb, text="🗑 Delete",
                          fg_color="#7F1D1D", hover_color="#991B1B",
                          height=34,
                          font=ctk.CTkFont("Helvetica",11),
                          command=delete_cmd).pack(side="left",pady=8)

        table = DarkTable(self.content, cols)
        table.pack(fill="both", expand=True, padx=12, pady=12)
        return table

    # ── STUDENTS ─────────────────────────────────────
    def _students(self):
        cols = [("slot",70,"Slot"),("adm",160,"Admission No."),
                ("name",200,"Full Name"),("class",180,"Class"),
                ("status",80,"Status")]
        self.stu_table = self._table_page(
            "Students","Manage enrolled students", cols,
            add_cmd=lambda: self._student_form(),
            delete_cmd=self._delete_student,
            add_label="+ Add Student")
        self._load_students()

    def _load_students(self):
        self.stu_table.clear()
        def fetch():
            data = self.db.get_students()
            self.root.after(0, lambda: [
                self.stu_table.insert(values=(
                    s.get("finger_slot","—"),
                    s.get("admission_number",""),
                    s.get("full_name",""),
                    self._class_label(s.get("classes")),
                    "Active" if s.get("is_active") else "Inactive"
                ), iid=s.get("id")) for s in data
            ])
        threading.Thread(target=fetch, daemon=True).start()

    def _class_label(self, cls):
        if not cls: return "—"
        return f"L{cls.get('level','?')} / {cls.get('intake','?')} / {cls.get('course','?')[:15]}"

    def _student_form(self, student=None):
        win = ctk.CTkToplevel(self.root)
        win.title("Add Student")
        win.geometry("500x580")
        win.configure(fg_color=NAVY)
        win.grab_set()

        ctk.CTkLabel(win, text="Add New Student",
                     font=ctk.CTkFont("Helvetica",18,weight="bold"),
                     text_color=WHITE).pack(pady=(25,5),padx=30,anchor="w")

        fields = {}
        for label, key, ph in [
            ("Admission Number","admission_number","e.g. EE-DICL/4456081/25"),
            ("Full Name","full_name","e.g. John Kamau"),
            ("Email","email","e.g. john@college.ac.ke"),
            ("Finger Slot","finger_slot","Leave blank — assigned during enrollment"),
        ]:
            ctk.CTkLabel(win, text=label,
                         font=ctk.CTkFont("Helvetica",11),
                         text_color=WHITE).pack(anchor="w",padx=30,pady=(8,2))
            e = ctk.CTkEntry(win, height=38, placeholder_text=ph,
                             fg_color=DARK, border_color=TEAL,
                             font=ctk.CTkFont("Helvetica",11))
            if student and student.get(key):
                e.insert(0, str(student[key]))
            e.pack(fill="x", padx=30)
            fields[key] = e

        # Class dropdown
        ctk.CTkLabel(win, text="Class",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(10,2))
        class_var = ctk.StringVar(value="Select class...")
        try:
            classes   = self.db.get_classes()
        except:
            classes = []
        class_names = [
            f"L{c.get('level')} / {c.get('intake')} / {c.get('course')}"
            for c in classes]
        class_map   = {
            f"L{c.get('level')} / {c.get('intake')} / {c.get('course')}": c.get("id")
            for c in classes}
        ctk.CTkOptionMenu(win, variable=class_var,
                          values=class_names or ["No classes — add classes first"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        err = ctk.CTkLabel(win, text="",
                           font=ctk.CTkFont("Helvetica",11),
                           text_color=RED)
        err.pack(pady=5)

        def save():
            data = {k: v.get().strip() for k,v in fields.items()}
            if not data["admission_number"] or not data["full_name"]:
                err.configure(text="Admission number and full name required.")
                return
            try:
                data["finger_slot"] = int(data["finger_slot"]) \
                    if data["finger_slot"] else None
            except:
                err.configure(text="Finger slot must be a number.")
                return
            data["class_id"]  = class_map.get(class_var.get())
            data["school_id"] = self.user.get("school_id")
            result = self.db.add_student(data)
            if result:
                win.destroy()
                self._load_students()
            else:
                err.configure(text="Failed to save. Check connection.")

        ctk.CTkButton(win, text="SAVE STUDENT", height=42,
                      fg_color=TEAL, hover_color="#0F766E",
                      font=ctk.CTkFont("Helvetica",12,weight="bold"),
                      command=save).pack(fill="x",padx=30,pady=(5,5))
        ctk.CTkButton(win, text="Cancel", height=36,
                      fg_color=DARK, command=win.destroy
                      ).pack(fill="x",padx=30)

    def _delete_student(self):
        iid = self.stu_table.focus()
        if not iid:
            messagebox.showinfo("Select","Select a student first.")
            return
        vals = self.stu_table.item(iid,"values")
        name = vals[2] if vals else "?"
        if messagebox.askyesno("Confirm", f"Deactivate {name}?"):
            self.db.delete_student(iid)
            self._load_students()

    # ── LECTURERS ────────────────────────────────────
    def _lecturers(self):
        cols = [("tid",100,"Teacher ID"),("name",200,"Full Name"),
                ("email",210,"Email"),("role",140,"Role")]
        self.lec_table = self._table_page(
            "Lecturers & Staff","Manage staff accounts", cols,
            add_cmd=self._add_lecturer_form,
            delete_cmd=self._delete_lecturer,
            add_label="+ Add Staff")
        self._load_lecturers()

    def _load_lecturers(self):
        self.lec_table.clear()
        def fetch():
            data = self.db.get_all_users()
            self.root.after(0, lambda: [
                self.lec_table.insert(values=(
                    u.get("teacher_id","—"), u.get("full_name",""),
                    u.get("email",""),
                    u.get("role","").upper().replace("_"," ")
                ), iid=u.get("id"))
                for u in data if u.get("role") != "super_admin"
            ])
        threading.Thread(target=fetch, daemon=True).start()

    def _add_lecturer_form(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Add Staff Account")
        win.geometry("500x540")
        win.configure(fg_color=NAVY)
        win.grab_set()

        ctk.CTkLabel(win, text="Add New Staff Account",
                     font=ctk.CTkFont("Helvetica",18,weight="bold"),
                     text_color=WHITE).pack(pady=(25,4),padx=30,anchor="w")
        ctk.CTkLabel(win,
                     text="Only admins can create accounts — no self-registration.",
                     font=ctk.CTkFont("Helvetica",10),
                     text_color=TEAL).pack(padx=30,anchor="w",pady=(0,16))

        fields = {}
        for label, key, ph, show in [
            ("Full Name","full_name","e.g. Dr. Otieno",""),
            ("Email","email","e.g. otieno@college.ac.ke",""),
            ("Password","password","Temporary password","•"),
            ("Teacher ID","teacher_id","e.g. TCH001",""),
        ]:
            ctk.CTkLabel(win, text=label,
                         font=ctk.CTkFont("Helvetica",11),
                         text_color=WHITE).pack(anchor="w",padx=30,pady=(8,2))
            e = ctk.CTkEntry(win, height=38, placeholder_text=ph,
                             show=show, fg_color=DARK, border_color=TEAL,
                             font=ctk.CTkFont("Helvetica",11))
            e.pack(fill="x", padx=30)
            fields[key] = e

        ctk.CTkLabel(win, text="Role",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(10,2))
        role_var = ctk.StringVar(value="lecturer")
        ctk.CTkOptionMenu(win, variable=role_var,
                          values=["lecturer","hod","hod_secretary",
                                  "principal","principal_secretary",
                                  "admin","dept_admin"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        err = ctk.CTkLabel(win, text="",
                           font=ctk.CTkFont("Helvetica",11),
                           text_color=RED)
        err.pack(pady=5)

        def save():
            data = {k: v.get().strip() for k,v in fields.items()}
            if not data["full_name"] or not data["email"] or not data["password"]:
                err.configure(text="Full name, email and password required.")
                return
            result = self.db.add_user(
                email=data["email"], password=data["password"],
                full_name=data["full_name"], role=role_var.get(),
                teacher_id=data.get("teacher_id") or None,
                school_id=self.user.get("school_id"))
            if result:
                win.destroy()
                self._load_lecturers()
            else:
                err.configure(text="Failed. Email may already exist.")

        ctk.CTkButton(win, text="CREATE ACCOUNT", height=42,
                      fg_color=AMBER, hover_color="#D97706",
                      font=ctk.CTkFont("Helvetica",12,weight="bold"),
                      command=save).pack(fill="x",padx=30,pady=(5,5))
        ctk.CTkButton(win, text="Cancel", height=36,
                      fg_color=DARK, command=win.destroy
                      ).pack(fill="x",padx=30)

    def _delete_lecturer(self):
        iid = self.lec_table.focus()
        if not iid:
            messagebox.showinfo("Select","Select a staff member first.")
            return
        vals = self.lec_table.item(iid,"values")
        name = vals[1] if vals else "?"
        if messagebox.askyesno("Confirm", f"Deactivate account for {name}?"):
            self.db.deactivate_user(iid)
            self._load_lecturers()

    # ── DEPARTMENTS ──────────────────────────────────
    def _departments(self):
        cols = [("code",120,"Code"),("name",300,"Department Name"),
                ("created",160,"Created")]
        self.dept_table = self._table_page(
            "Departments","Manage college departments", cols,
            add_cmd=self._add_dept_form,
            delete_cmd=self._delete_dept,
            add_label="+ Add Department")
        self._load_depts()

    def _load_depts(self):
        self.dept_table.clear()
        def fetch():
            data = self.db.get_departments()
            self.root.after(0, lambda: [
                self.dept_table.insert(values=(
                    d.get("code",""), d.get("name",""),
                    d.get("created_at","")[:10]
                ), iid=d.get("id")) for d in data
            ])
        threading.Thread(target=fetch, daemon=True).start()

    def _add_dept_form(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Add Department")
        win.geometry("440x280")
        win.configure(fg_color=NAVY)
        win.grab_set()

        ctk.CTkLabel(win, text="Add Department",
                     font=ctk.CTkFont("Helvetica",18,weight="bold"),
                     text_color=WHITE).pack(pady=(25,20),padx=30,anchor="w")

        fields = {}
        for label, key, ph in [
            ("Department Name","name","e.g. Engineering"),
            ("Department Code","code","e.g. ENG"),
        ]:
            ctk.CTkLabel(win, text=label,
                         font=ctk.CTkFont("Helvetica",11),
                         text_color=WHITE).pack(anchor="w",padx=30,pady=(8,2))
            e = ctk.CTkEntry(win, height=38, placeholder_text=ph,
                             fg_color=DARK, border_color=TEAL,
                             font=ctk.CTkFont("Helvetica",11))
            e.pack(fill="x", padx=30)
            fields[key] = e

        err = ctk.CTkLabel(win, text="",
                           font=ctk.CTkFont("Helvetica",11),
                           text_color=RED)
        err.pack(pady=5)

        def save():
            name = fields["name"].get().strip()
            code = fields["code"].get().strip()
            if not name or not code:
                err.configure(text="Both fields required.")
                return
            result = self.db.add_department(name, code, self.user.get("school_id"))
            if result:
                win.destroy()
                self._load_depts()
            else:
                err.configure(text="Failed. Check connection.")

        ctk.CTkButton(win, text="SAVE DEPARTMENT", height=42,
                      fg_color=TEAL, hover_color="#0F766E",
                      font=ctk.CTkFont("Helvetica",12,weight="bold"),
                      command=save).pack(fill="x",padx=30,pady=(5,5))
        ctk.CTkButton(win, text="Cancel", height=36,
                      fg_color=DARK, command=win.destroy
                      ).pack(fill="x",padx=30)

    def _delete_dept(self):
        iid = self.dept_table.focus()
        if not iid:
            messagebox.showinfo("Select","Select a department first.")
            return
        vals = self.dept_table.item(iid,"values")
        name = vals[1] if vals else "?"
        if messagebox.askyesno("Confirm", f"Delete department '{name}'?"):
            try:
                self.db._delete("departments", f"id=eq.{iid}")
                self._load_depts()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ── UNITS ────────────────────────────────────────
    def _units(self):
        cols = [("code",100,"Code"),("name",200,"Unit Name"),
                ("class",160,"Class"),("lecturer",180,"Lecturer"),
                ("dept",130,"Department")]
        self.unit_table = self._table_page(
            "Units","Manage teaching units", cols,
            add_cmd=self._add_unit_form,
            delete_cmd=self._delete_unit,
            add_label="+ Add Unit")
        self._load_units()

    def _load_units(self):
        self.unit_table.clear()
        def fetch():
            data = self.db.get_units()
            self.root.after(0, lambda: [
                self.unit_table.insert(values=(
                    u.get("code",""), u.get("name",""),
                    self._class_label(u.get("classes")),
                    u.get("users",{}).get("full_name","—") if u.get("users") else "—",
                    u.get("departments",{}).get("name","—") if u.get("departments") else "—"
                ), iid=u.get("id")) for u in data
            ])
        threading.Thread(target=fetch, daemon=True).start()

    def _add_unit_form(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Add Unit")
        win.geometry("480x520")
        win.configure(fg_color=NAVY)
        win.grab_set()

        ctk.CTkLabel(win, text="Add Teaching Unit",
                     font=ctk.CTkFont("Helvetica",18,weight="bold"),
                     text_color=WHITE).pack(pady=(25,15),padx=30,anchor="w")

        fields = {}
        for label, key, ph in [
            ("Unit Code","code","e.g. EEE301"),
            ("Unit Name","name","e.g. Power Systems"),
        ]:
            ctk.CTkLabel(win, text=label,
                         font=ctk.CTkFont("Helvetica",11),
                         text_color=WHITE).pack(anchor="w",padx=30,pady=(8,2))
            e = ctk.CTkEntry(win, height=38, placeholder_text=ph,
                             fg_color=DARK, border_color=TEAL,
                             font=ctk.CTkFont("Helvetica",11))
            e.pack(fill="x", padx=30)
            fields[key] = e

        ctk.CTkLabel(win, text="Assign Lecturer",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(10,2))
        lec_var = ctk.StringVar(value="Select lecturer...")
        lecturers = self.db.get_lecturers()
        lec_names = [f"{l.get('teacher_id','?')} — {l.get('full_name','')}" for l in lecturers]
        lec_map   = {f"{l.get('teacher_id','?')} — {l.get('full_name','')}": l.get("id") for l in lecturers}
        ctk.CTkOptionMenu(win, variable=lec_var,
                          values=lec_names or ["No lecturers found"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        ctk.CTkLabel(win, text="Assign to Class",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(10,2))
        class_var = ctk.StringVar(value="Select class...")
        try:
            classes = self.db.get_classes()
        except:
            classes = []
        class_names = [
            f"L{c.get('level')} / {c.get('intake')} / {c.get('course')}"
            for c in classes]
        class_map = {
            f"L{c.get('level')} / {c.get('intake')} / {c.get('course')}": c.get("id")
            for c in classes}
        ctk.CTkOptionMenu(win, variable=class_var,
                          values=class_names or ["No classes — add classes first"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        ctk.CTkLabel(win, text="Department",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(10,2))
        dept_var  = ctk.StringVar(value="Select department...")
        depts     = self.db.get_departments()
        dept_names= [f"{d.get('code')} — {d.get('name')}" for d in depts]
        dept_map  = {f"{d.get('code')} — {d.get('name')}": d.get("id") for d in depts}
        ctk.CTkOptionMenu(win, variable=dept_var,
                          values=dept_names or ["No departments found"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        err = ctk.CTkLabel(win, text="",
                           font=ctk.CTkFont("Helvetica",11),
                           text_color=RED)
        err.pack(pady=5)

        def save():
            code = fields["code"].get().strip()
            name = fields["name"].get().strip()
            if not code or not name:
                err.configure(text="Code and name required.")
                return
            if not class_map.get(class_var.get()):
                err.configure(text="Please select a class.")
                return
            result = self.db.add_unit({
                "code":          code,
                "name":          name,
                "school_id":     self.user.get("school_id"),
                "lecturer_id":   lec_map.get(lec_var.get()),
                "class_id":      class_map.get(class_var.get()),
                "department_id": dept_map.get(dept_var.get()),
                "is_active":     True
            })
            if result:
                win.destroy()
                self._load_units()
            else:
                err.configure(text="Failed. Check connection.")

        ctk.CTkButton(win, text="SAVE UNIT", height=42,
                      fg_color=TEAL, hover_color="#0F766E",
                      font=ctk.CTkFont("Helvetica",12,weight="bold"),
                      command=save).pack(fill="x",padx=30,pady=(5,5))
        ctk.CTkButton(win, text="Cancel", height=36,
                      fg_color=DARK, command=win.destroy
                      ).pack(fill="x",padx=30)

    def _delete_unit(self):
        iid = self.unit_table.focus()
        if not iid:
            messagebox.showinfo("Select","Select a unit first.")
            return
        vals = self.unit_table.item(iid,"values")
        name = vals[1] if vals else "?"
        if messagebox.askyesno("Confirm", f"Delete unit '{name}'?"):
            try:
                self.db._delete("units", f"id=eq.{iid}")
                self._load_units()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ── CLASSES ──────────────────────────────────────
    def _classes(self):
        cols = [("level",80,"Level"),("intake",100,"Intake"),
                ("course",240,"Course"),("dept",180,"Department")]
        self.class_table = self._table_page(
            "Classes","Manage student classes by level and intake", cols,
            add_cmd=self._add_class_form,
            delete_cmd=self._delete_class,
            add_label="+ Add Class")
        self._load_classes()

    def _load_classes(self):
        self.class_table.clear()
        def fetch():
            try:
                data = self.db.get_classes()
                self.root.after(0, lambda: [
                    self.class_table.insert(values=(
                        f"Level {c.get('level','')}",
                        c.get("intake",""),
                        c.get("course",""),
                        c.get("departments",{}).get("name","—") if c.get("departments") else "—"
                    ), iid=c.get("id")) for c in (data or [])
                ])
            except: pass
        threading.Thread(target=fetch, daemon=True).start()

    def _add_class_form(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Add Class")
        win.geometry("460x400")
        win.configure(fg_color=NAVY)
        win.grab_set()

        ctk.CTkLabel(win, text="Add Class",
                     font=ctk.CTkFont("Helvetica",18,weight="bold"),
                     text_color=WHITE).pack(pady=(25,5),padx=30,anchor="w")
        ctk.CTkLabel(win,
                     text="A class is uniquely identified by Level + Intake + Course.",
                     font=ctk.CTkFont("Helvetica",10),
                     text_color=TEAL).pack(padx=30,anchor="w",pady=(0,12))

        fields = {}
        for label, key, ph in [
            ("Intake Number","intake","e.g. 251"),
            ("Course Name","course","e.g. Electrical Installation"),
        ]:
            ctk.CTkLabel(win, text=label,
                         font=ctk.CTkFont("Helvetica",11),
                         text_color=WHITE).pack(anchor="w",padx=30,pady=(8,2))
            e = ctk.CTkEntry(win, height=38, placeholder_text=ph,
                             fg_color=DARK, border_color=TEAL,
                             font=ctk.CTkFont("Helvetica",11))
            e.pack(fill="x", padx=30)
            fields[key] = e

        ctk.CTkLabel(win, text="Level",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(8,2))
        level_var = ctk.StringVar(value="4")
        ctk.CTkOptionMenu(win, variable=level_var,
                          values=["4","5","6"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        ctk.CTkLabel(win, text="Department",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(8,2))
        dept_var  = ctk.StringVar(value="Select department...")
        depts     = self.db.get_departments()
        dept_names= [f"{d.get('code')} — {d.get('name')}" for d in depts]
        dept_map  = {f"{d.get('code')} — {d.get('name')}": d.get("id") for d in depts}
        ctk.CTkOptionMenu(win, variable=dept_var,
                          values=dept_names or ["No departments found"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        err = ctk.CTkLabel(win, text="",
                           font=ctk.CTkFont("Helvetica",11),
                           text_color=RED)
        err.pack(pady=5)

        def save():
            intake = fields["intake"].get().strip()
            course = fields["course"].get().strip()
            if not intake or not course:
                err.configure(text="Intake and course required.")
                return
            try:
                intake_int = int(intake)
            except:
                err.configure(text="Intake must be a number e.g. 251.")
                return
            result = self.db.add_class(
                level=int(level_var.get()),
                intake=intake_int,
                course=course,
                department_id=dept_map.get(dept_var.get()),
                school_id=self.user.get("school_id")
            )
            if result:
                win.destroy()
                self._load_classes()
            else:
                err.configure(text="Failed. Class may already exist.")

        ctk.CTkButton(win, text="SAVE CLASS", height=42,
                      fg_color=TEAL, hover_color="#0F766E",
                      font=ctk.CTkFont("Helvetica",12,weight="bold"),
                      command=save).pack(fill="x",padx=30,pady=(5,5))
        ctk.CTkButton(win, text="Cancel", height=36,
                      fg_color=DARK, command=win.destroy
                      ).pack(fill="x",padx=30)

    def _delete_class(self):
        iid = self.class_table.focus()
        if not iid:
            messagebox.showinfo("Select","Select a class first.")
            return
        vals = self.class_table.item(iid,"values")
        name = f"{vals[0]} / {vals[1]} / {vals[2]}" if vals else "?"
        if messagebox.askyesno("Confirm", f"Deactivate class '{name}'?\n"
                               "This will also hide all students and units in this class."):
            self.db.delete_class(iid)
            self._load_classes()

    # ── ROOMS ────────────────────────────────────────
    def _rooms(self):
        cols = [("name",200,"Room Name"),("building",180,"Building"),
                ("cap",100,"Capacity"),("status",90,"Status")]
        self.room_table = self._table_page(
            "Rooms","Manage classrooms and labs", cols,
            add_cmd=self._add_room_form,
            delete_cmd=self._delete_room,
            add_label="+ Add Room")
        self._load_rooms()

    def _load_rooms(self):
        self.room_table.clear()
        def fetch():
            try:
                data = self.db._get("rooms", "is_active=eq.true")
                self.root.after(0, lambda: [
                    self.room_table.insert(values=(
                        r.get("name",""), r.get("building","—"),
                        r.get("capacity",30),
                        "Active" if r.get("is_active") else "Inactive"
                    ), iid=r.get("id")) for r in (data or [])
                ])
            except: pass
        threading.Thread(target=fetch, daemon=True).start()

    def _add_room_form(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Add Room")
        win.geometry("440x300")
        win.configure(fg_color=NAVY)
        win.grab_set()

        ctk.CTkLabel(win, text="Add Room / Lab",
                     font=ctk.CTkFont("Helvetica",18,weight="bold"),
                     text_color=WHITE).pack(pady=(25,20),padx=30,anchor="w")

        fields = {}
        for label, key, ph in [
            ("Room Name","name","e.g. Lab 3 / Room 101"),
            ("Building","building","e.g. Block A"),
            ("Capacity","capacity","e.g. 40"),
        ]:
            ctk.CTkLabel(win, text=label,
                         font=ctk.CTkFont("Helvetica",11),
                         text_color=WHITE).pack(anchor="w",padx=30,pady=(8,2))
            e = ctk.CTkEntry(win, height=38, placeholder_text=ph,
                             fg_color=DARK, border_color=TEAL,
                             font=ctk.CTkFont("Helvetica",11))
            e.pack(fill="x", padx=30)
            fields[key] = e

        err = ctk.CTkLabel(win, text="",
                           font=ctk.CTkFont("Helvetica",11),
                           text_color=RED)
        err.pack(pady=5)

        def save():
            name = fields["name"].get().strip()
            if not name:
                err.configure(text="Room name required.")
                return
            try:
                cap = int(fields["capacity"].get().strip() or 30)
            except:
                cap = 30
            try:
                self.db._post("rooms", {
                    "name": name,
                    "building": fields["building"].get().strip() or None,
                    "capacity": cap,
                    "school_id": self.user.get("school_id"),
                    "is_active": True
                }
                )
                win.destroy()
                self._load_rooms()
            except Exception as e:
                err.configure(text=f"Failed: {e}")

        ctk.CTkButton(win, text="SAVE ROOM", height=42,
                      fg_color=TEAL, hover_color="#0F766E",
                      font=ctk.CTkFont("Helvetica",12,weight="bold"),
                      command=save).pack(fill="x",padx=30,pady=(5,5))
        ctk.CTkButton(win, text="Cancel", height=36,
                      fg_color=DARK, command=win.destroy
                      ).pack(fill="x",padx=30)

    def _delete_room(self):
        iid = self.room_table.focus()
        if not iid:
            messagebox.showinfo("Select","Select a room first.")
            return
        vals = self.room_table.item(iid,"values")
        name = vals[0] if vals else "?"
        if messagebox.askyesno("Confirm", f"Delete room '{name}'?"):
            try:
                self.db._delete("rooms", f"id=eq.{iid}")
                self._load_rooms()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ── SEMESTERS ────────────────────────────────────
    def _semesters(self):
        cols = [("name",220,"Semester Name"),("start",130,"Start Date"),
                ("end",130,"End Date"),("active",80,"Active")]
        self.sem_table = self._table_page(
            "Semesters","Manage academic semesters", cols,
            add_cmd=self._add_semester_form,
            delete_cmd=self._delete_semester,
            add_label="+ Add Semester")
        self._load_semesters()

    def _load_semesters(self):
        self.sem_table.clear()
        def fetch():
            try:
                data = self.db._get("semesters", "order=start_date.desc")
                self.root.after(0, lambda: [
                    self.sem_table.insert(values=(
                        s.get("name",""), s.get("start_date",""),
                        s.get("end_date",""),
                        "Yes" if s.get("is_active") else "No"
                    ), iid=s.get("id")) for s in (data or [])
                ])
            except: pass
        threading.Thread(target=fetch, daemon=True).start()

    def _add_semester_form(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Add Semester")
        win.geometry("440x320")
        win.configure(fg_color=NAVY)
        win.grab_set()

        ctk.CTkLabel(win, text="Add Semester",
                     font=ctk.CTkFont("Helvetica",18,weight="bold"),
                     text_color=WHITE).pack(pady=(25,20),padx=30,anchor="w")

        fields = {}
        for label, key, ph in [
            ("Semester Name","name","e.g. Semester 1 — 2026"),
            ("Start Date","start_date","e.g. 2026-01-13"),
            ("End Date","end_date","e.g. 2026-05-30"),
        ]:
            ctk.CTkLabel(win, text=label,
                         font=ctk.CTkFont("Helvetica",11),
                         text_color=WHITE).pack(anchor="w",padx=30,pady=(8,2))
            e = ctk.CTkEntry(win, height=38, placeholder_text=ph,
                             fg_color=DARK, border_color=TEAL,
                             font=ctk.CTkFont("Helvetica",11))
            e.pack(fill="x", padx=30)
            fields[key] = e

        active_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(win, text="Set as active semester",
                        variable=active_var,
                        text_color=WHITE).pack(anchor="w",padx=30,pady=(10,0))

        err = ctk.CTkLabel(win, text="",
                           font=ctk.CTkFont("Helvetica",11),
                           text_color=RED)
        err.pack(pady=5)

        def save():
            data = {k: v.get().strip() for k,v in fields.items()}
            if not all(data.values()):
                err.configure(text="All fields required.")
                return
            try:
                if active_var.get():
                    self.db._patch("semesters", "is_active=eq.true", {"is_active": False})
                self.db._post("semesters", {
                    **data,
                    "is_active": active_var.get(),
                    "school_id": self.user.get("school_id")
                }
                )
                win.destroy()
                self._load_semesters()
            except Exception as e:
                err.configure(text=f"Failed: {e}")

        ctk.CTkButton(win, text="SAVE SEMESTER", height=42,
                      fg_color=TEAL, hover_color="#0F766E",
                      font=ctk.CTkFont("Helvetica",12,weight="bold"),
                      command=save).pack(fill="x",padx=30,pady=(5,5))
        ctk.CTkButton(win, text="Cancel", height=36,
                      fg_color=DARK, command=win.destroy
                      ).pack(fill="x",padx=30)

    def _delete_semester(self):
        iid = self.sem_table.focus()
        if not iid:
            messagebox.showinfo("Select","Select a semester first.")
            return
        vals = self.sem_table.item(iid,"values")
        name = vals[0] if vals else "?"
        if messagebox.askyesno("Confirm", f"Delete semester '{name}'?"):
            try:
                self.db._delete("semesters", f"id=eq.{iid}")
                self._load_semesters()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ── TIMETABLE ────────────────────────────────────
    def _timetable(self):
        cols = [("day",110,"Day"),("start",80,"Start"),("end",80,"End"),
                ("unit",110,"Unit"),("lecturer",190,"Lecturer"),
                ("dept",160,"Department")]
        self.tt_table = self._table_page(
            "Timetable","Semester-based class schedule", cols,
            add_cmd=self._add_timetable_form,
            delete_cmd=self._delete_timetable,
            add_label="+ Add Class")
        self._load_timetable()

    def _load_timetable(self):
        self.tt_table.clear()
        def fetch():
            try:
                data = self.db._get("timetable", "is_active=eq.true&select=*,users(full_name),units(code,name),departments(name)")
                day_order = {"Monday":1,"Tuesday":2,"Wednesday":3,
                             "Thursday":4,"Friday":5,"Saturday":6}
                rows = sorted(data.data or [],
                              key=lambda x: (day_order.get(x.get("day_of_week",""),7),
                                             x.get("start_time","")))
                self.root.after(0, lambda: [
                    self.tt_table.insert(values=(
                        t.get("day_of_week",""),
                        str(t.get("start_time",""))[:5],
                        str(t.get("end_time",""))[:5],
                        t.get("units",{}).get("code","") if t.get("units") else "",
                        t.get("users",{}).get("full_name","") if t.get("users") else "",
                        t.get("departments",{}).get("name","") if t.get("departments") else "",
                    ), iid=t.get("id")) for t in rows
                ])
            except: pass
        threading.Thread(target=fetch, daemon=True).start()

    def _add_timetable_form(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Add Timetable Entry")
        win.geometry("500x480")
        win.configure(fg_color=NAVY)
        win.grab_set()

        ctk.CTkLabel(win, text="Add Class to Timetable",
                     font=ctk.CTkFont("Helvetica",18,weight="bold"),
                     text_color=WHITE).pack(pady=(25,15),padx=30,anchor="w")

        ctk.CTkLabel(win, text="Day of Week",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(0,2))
        day_var = ctk.StringVar(value="Monday")
        ctk.CTkOptionMenu(win, variable=day_var,
                          values=["Monday","Tuesday","Wednesday",
                                  "Thursday","Friday","Saturday"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        tf = ctk.CTkFrame(win, fg_color="transparent")
        tf.pack(fill="x",padx=30,pady=(10,0))
        ctk.CTkLabel(tf, text="Start Time",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(side="left",padx=(0,5))
        start_e = ctk.CTkEntry(tf, height=36, width=100,
                                placeholder_text="08:00",
                                fg_color=DARK, border_color=TEAL,
                                font=ctk.CTkFont("Helvetica",11))
        start_e.pack(side="left",padx=(0,20))
        ctk.CTkLabel(tf, text="End Time",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(side="left",padx=(0,5))
        end_e = ctk.CTkEntry(tf, height=36, width=100,
                              placeholder_text="10:00",
                              fg_color=DARK, border_color=TEAL,
                              font=ctk.CTkFont("Helvetica",11))
        end_e.pack(side="left")

        ctk.CTkLabel(win, text="Unit",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(10,2))
        unit_var = ctk.StringVar(value="Select unit...")
        units = self.db.get_units()
        unit_names = [f"{u.get('code')} — {u.get('name')}" for u in units]
        unit_map   = {f"{u.get('code')} — {u.get('name')}": u for u in units}
        ctk.CTkOptionMenu(win, variable=unit_var,
                          values=unit_names or ["No units"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        ctk.CTkLabel(win, text="Semester",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(anchor="w",padx=30,pady=(10,2))
        sem_var = ctk.StringVar(value="Select semester...")
        try:
            sems = self.db._get("semesters") or []
        except:
            sems = []
        sem_names = [s.get("name","") for s in sems]
        sem_map   = {s.get("name",""): s.get("id") for s in sems}
        ctk.CTkOptionMenu(win, variable=sem_var,
                          values=sem_names or ["No semesters"],
                          fg_color=DARK, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(fill="x",padx=30)

        err = ctk.CTkLabel(win, text="",
                           font=ctk.CTkFont("Helvetica",11),
                           text_color=RED)
        err.pack(pady=5)

        def save():
            unit_sel = unit_map.get(unit_var.get())
            if not unit_sel:
                err.configure(text="Select a unit."); return
            if not start_e.get().strip() or not end_e.get().strip():
                err.configure(text="Enter start and end times."); return
            try:
                self.db._post("timetable", {
                    "day_of_week":   day_var.get(),
                    "start_time":    start_e.get().strip(),
                    "end_time":      end_e.get().strip(),
                    "unit_id":       unit_sel.get("id"),
                    "lecturer_id":   unit_sel.get("lecturer_id"),
                    "department_id": unit_sel.get("department_id"),
                    "semester_id":   sem_map.get(sem_var.get()),
                    "school_id":     self.user.get("school_id"),
                    "is_active":     True
                }
                )
                win.destroy()
                self._load_timetable()
            except Exception as e:
                err.configure(text=f"Failed: {e}")

        ctk.CTkButton(win, text="ADD TO TIMETABLE", height=42,
                      fg_color=BLUE, hover_color="#2563EB",
                      font=ctk.CTkFont("Helvetica",12,weight="bold"),
                      command=save).pack(fill="x",padx=30,pady=(5,5))
        ctk.CTkButton(win, text="Cancel", height=36,
                      fg_color=DARK, command=win.destroy
                      ).pack(fill="x",padx=30)

    def _delete_timetable(self):
        iid = self.tt_table.focus()
        if not iid:
            messagebox.showinfo("Select","Select a timetable entry first.")
            return
        vals = self.tt_table.item(iid,"values")
        if messagebox.askyesno("Confirm",
            f"Remove {vals[0]} {vals[1]}-{vals[2]} ({vals[3]}) from timetable?"):
            try:
                self.db._patch("timetable", f"id=eq.{iid}", {"is_active": False})
                self._load_timetable()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ── LECTURER REPORT ──────────────────────────────
    def _lec_report(self):
        self._header("Lecturer Attendance Report",
                     "Track which lecturers have been attending their scheduled classes")

        fb = ctk.CTkFrame(self.content, fg_color=DARK,
                          corner_radius=0, height=55)
        fb.pack(fill="x"); fb.pack_propagate(False)

        ctk.CTkLabel(fb, text="Period:",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=WHITE).pack(side="left",padx=(15,5),pady=15)
        self.rpt_start = ctk.CTkEntry(fb, height=34, width=120,
                                       placeholder_text="2026-01-01",
                                       fg_color=NAVY, border_color=TEAL,
                                       font=ctk.CTkFont("Helvetica",11))
        self.rpt_start.pack(side="left",padx=(0,8),pady=10)
        ctk.CTkLabel(fb, text="to",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=GRAY).pack(side="left",padx=(0,8))
        self.rpt_end = ctk.CTkEntry(fb, height=34, width=120,
                                     placeholder_text="2026-05-30",
                                     fg_color=NAVY, border_color=TEAL,
                                     font=ctk.CTkFont("Helvetica",11))
        self.rpt_end.pack(side="left",padx=(0,12),pady=10)
        ctk.CTkButton(fb, text="Generate",
                      fg_color=PURPLE, hover_color="#7C3AED",
                      height=34,
                      font=ctk.CTkFont("Helvetica",11,weight="bold"),
                      command=self._generate_lec_report
                      ).pack(side="left",pady=10)
        ctk.CTkButton(fb, text="Mark Absences",
                      fg_color=RED, hover_color="#B91C1C",
                      height=34,
                      font=ctk.CTkFont("Helvetica",11),
                      command=self._mark_absences
                      ).pack(side="left",padx=8,pady=10)

        self.rpt_summary = ctk.CTkFrame(self.content, fg_color="transparent", height=85)
        self.rpt_summary.pack(fill="x",padx=12,pady=(8,0))
        self.rpt_summary.pack_propagate(False)

        cols = [("lecturer",180,"Lecturer"),("dept",140,"Department"),
                ("unit",90,"Unit"),("scheduled",90,"Scheduled"),
                ("present",80,"Present"),("late",70,"Late"),
                ("absent",70,"Absent"),("rate",80,"Rate"),
                ("status",90,"Status")]
        self.rpt_table = DarkTable(self.content, cols)
        self.rpt_table.pack(fill="both", expand=True, padx=12, pady=8)

        now = datetime.now()
        self.rpt_start.insert(0, f"{now.year}-{now.month:02d}-01")
        self.rpt_end.insert(0, now.strftime("%Y-%m-%d"))
        self._generate_lec_report()

    def _generate_lec_report(self):
        self.rpt_table.clear()
        start = self.rpt_start.get().strip()
        end   = self.rpt_end.get().strip()

        def fetch():
            try:
                tt = self.db._get("timetable", "is_active=eq.true&select=*,users(full_name),units(code,name),departments(name)")
                la = self.db._get("lecturer_attendance", f"scheduled_date=gte.{start}&scheduled_date=lte.{end}")

                summary = {}
                for rec in (la or []):
                    key = f"{rec['lecturer_id']}_{rec['unit_id']}"
                    if key not in summary:
                        summary[key] = {"present":0,"late":0,"absent":0,"total":0,
                                        "lecturer_id":rec["lecturer_id"],
                                        "unit_id":rec["unit_id"]}
                    summary[key]["total"] += 1
                    s = rec.get("status","pending")
                    if s in ("present","late","absent"):
                        summary[key][s] += 1

                rows = []
                for key, data in summary.items():
                    tt_entry = next((t for t in (tt or [])
                        if t.get("lecturer_id")==data["lecturer_id"] and
                           t.get("unit_id")==data["unit_id"]), None)
                    if not tt_entry: continue
                    total   = data["total"]
                    present = data["present"]
                    late    = data["late"]
                    absent  = data["absent"]
                    covered = present + late
                    rate    = round((covered/total)*100) if total > 0 else 0
                    status  = "✅ Good" if rate>=80 else "⚠️ Watch" if rate>=60 else "❌ At Risk"
                    rows.append((
                        tt_entry.get("users",{}).get("full_name","") if tt_entry.get("users") else "",
                        tt_entry.get("departments",{}).get("name","") if tt_entry.get("departments") else "",
                        tt_entry.get("units",{}).get("code","") if tt_entry.get("units") else "",
                        total, present, late, absent, f"{rate}%", status
                    ))

                rows.sort(key=lambda x: x[0])
                self.root.after(0, lambda: [self.rpt_table.insert(values=r) for r in rows])

                total_lecs = len(set(r[0] for r in rows))
                good = sum(1 for r in rows if "✅" in r[8])
                risk = sum(1 for r in rows if "❌" in r[8])

                def add_cards():
                    for w in self.rpt_summary.winfo_children(): w.destroy()
                    for val, label, color in [
                        (total_lecs,"Tracked",TEAL),
                        (good,"Good",GREEN),
                        (risk,"At Risk",RED),
                        (f"{start[:7]}","Period",GRAY),
                    ]:
                        c = ctk.CTkFrame(self.rpt_summary, fg_color=DARK, corner_radius=8)
                        c.pack(side="left", fill="both", expand=True, padx=4)
                        ctk.CTkLabel(c, text=str(val),
                                     font=ctk.CTkFont("Helvetica",22,weight="bold"),
                                     text_color=color).pack(pady=(8,0))
                        ctk.CTkLabel(c, text=label,
                                     font=ctk.CTkFont("Helvetica",9),
                                     text_color=GRAY).pack(pady=(0,8))

                self.root.after(0, add_cards)
            except Exception as e:
                print(f"Report error: {e}")

        threading.Thread(target=fetch, daemon=True).start()

    def _mark_absences(self):
        if not messagebox.askyesno("Confirm",
            "Mark all pending past classes as ABSENT?"):
            return
        def run():
            try:
                self.db._patch("lecturer_attendance", f"status=eq.pending&scheduled_date=lt.{date.today().isoformat()}", {"status":"absent"})
                self.root.after(0, lambda: messagebox.showinfo("Done","Done!"))
                self.root.after(0, self._generate_lec_report)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error",str(e)))
        threading.Thread(target=run, daemon=True).start()

    # ── ATTENDANCE ───────────────────────────────────
    def _attendance(self):
        self._header("Attendance Records","View all student attendance — read only")

        fb = ctk.CTkFrame(self.content, fg_color=DARK,
                          corner_radius=0, height=50)
        fb.pack(fill="x"); fb.pack_propagate(False)
        self.att_date = ctk.CTkEntry(fb, height=34, width=140,
                                      fg_color=NAVY, border_color=TEAL,
                                      font=ctk.CTkFont("Helvetica",11))
        self.att_date.insert(0, date.today().isoformat())
        self.att_date.pack(side="left",padx=12,pady=8)
        ctk.CTkButton(fb, text="Load",
                      fg_color=TEAL, hover_color="#0F766E",
                      height=34, font=ctk.CTkFont("Helvetica",11),
                      command=self._load_attendance
                      ).pack(side="left",pady=8)

        cols = [("sid",95,"Student ID"),("name",160,"Name"),
                ("unit",85,"Unit"),("lecturer",150,"Lecturer"),
                ("date",95,"Date"),("time",70,"Time"),("status",80,"Status")]
        self.att_table = DarkTable(self.content, cols)
        self.att_table.pack(fill="both", expand=True, padx=12, pady=12)
        self._load_attendance()

    def _load_attendance(self):
        self.att_table.clear()
        d = self.att_date.get().strip()
        def fetch():
            try:
                data = self.db._get("attendance", f"date=eq.{d}&order=time_in.desc&select=*,students(student_id,full_name),units(code,name),sessions(*,users(full_name))")
                self.root.after(0, lambda: [
                    self.att_table.insert(values=(
                        r.get("students",{}).get("student_id","") if r.get("students") else "",
                        r.get("students",{}).get("full_name","") if r.get("students") else "",
                        r.get("units",{}).get("code","") if r.get("units") else "",
                        r.get("sessions",{}).get("users",{}).get("full_name","") if r.get("sessions") and r.get("sessions",{}).get("users") else "",
                        r.get("date",""),
                        str(r.get("time_in",""))[:5],
                        r.get("status","").upper()
                    )) for r in (data or [])
                ])
            except: pass
        threading.Thread(target=fetch, daemon=True).start()

    # ── MY CLASSES ───────────────────────────────────
    def _my_classes(self):
        self._header("My Classes","Your assigned units and schedule")
        body = ctk.CTkScrollableFrame(self.content, fg_color=NAVY)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        def fetch():
            try:
                uid = self.user.get("id")
                tt = self.db._get("timetable", f"lecturer_id=eq.{uid}&is_active=eq.true&select=*,units(code,name)")
                self.root.after(0, lambda: [
                    self._class_card(body,t) for t in (tt or [])
                ])
            except: pass
        threading.Thread(target=fetch, daemon=True).start()

    def _class_card(self, parent, t):
        card = ctk.CTkFrame(parent, fg_color=DARK, corner_radius=12)
        card.pack(fill="x", pady=6)
        unit = t.get("units",{}) if t.get("units") else {}
        ctk.CTkLabel(card,
                     text=f"{unit.get('code','')} — {unit.get('name','')}",
                     font=ctk.CTkFont("Helvetica",14,weight="bold"),
                     text_color=TEAL).pack(anchor="w",padx=15,pady=(12,2))
        ctk.CTkLabel(card,
                     text=f"{t.get('day_of_week','')}  {str(t.get('start_time',''))[:5]} — {str(t.get('end_time',''))[:5]}",
                     font=ctk.CTkFont("Helvetica",12),
                     text_color=WHITE).pack(anchor="w",padx=15,pady=(0,12))

    # ── ENROLL ───────────────────────────────────────
    def _enroll(self):
        self._header("Fingerprint Enrollment",
                     "Enroll student fingerprints — slot auto-assigned")
        body = ctk.CTkFrame(self.content, fg_color=NAVY)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        # Port selector
        pf = ctk.CTkFrame(body, fg_color=DARK, corner_radius=12)
        pf.pack(fill="x", pady=(0,15))
        ctk.CTkLabel(pf, text="Scanner Connection",
                     font=ctk.CTkFont("Helvetica",14,weight="bold"),
                     text_color=WHITE).pack(anchor="w",padx=20,pady=(15,5))
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_var = ctk.StringVar(value=ports[0] if ports else "No scanner")
        ctk.CTkOptionMenu(pf, variable=self.port_var,
                          values=ports or ["No scanner detected"],
                          fg_color=NAVY, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11)
                          ).pack(anchor="w",padx=20,pady=(0,15))

        # Student selector
        sf = ctk.CTkFrame(body, fg_color=DARK, corner_radius=12)
        sf.pack(fill="x", pady=(0,15))
        ctk.CTkLabel(sf, text="Select Student to Enroll",
                     font=ctk.CTkFont("Helvetica",14,weight="bold"),
                     text_color=WHITE).pack(anchor="w",padx=20,pady=(15,5))

        students = self.db.get_students()
        # Only show students without a finger slot assigned
        unrolled = [s for s in students if not s.get("finger_slot")]
        enrolled  = [s for s in students if s.get("finger_slot")]

        if unrolled:
            stu_names = [f"{s.get('student_id')} — {s.get('full_name')}" for s in unrolled]
            stu_map   = {f"{s.get('student_id')} — {s.get('full_name')}": s for s in unrolled}
        else:
            stu_names = ["All students enrolled!"]
            stu_map   = {}

        self.enroll_stu_var = ctk.StringVar(value=stu_names[0] if stu_names else "No students")
        ctk.CTkOptionMenu(sf, variable=self.enroll_stu_var,
                          values=stu_names,
                          fg_color=NAVY, button_color=TEAL,
                          font=ctk.CTkFont("Helvetica",11),
                          width=500
                          ).pack(anchor="w",padx=20,pady=(0,5))

        # Show next available slot
        used_slots = [s.get("finger_slot") for s in enrolled if s.get("finger_slot")]
        next_slot  = 1
        while next_slot in used_slots:
            next_slot += 1

        ctk.CTkLabel(sf,
                     text=f"Next available finger slot: {next_slot}  (slots 1-64)",
                     font=ctk.CTkFont("Helvetica",11),
                     text_color=TEAL).pack(anchor="w",padx=20,pady=(0,15))

        # Enrollment area
        ef = ctk.CTkFrame(body, fg_color=DARK, corner_radius=12)
        ef.pack(fill="x")
        ctk.CTkLabel(ef, text="Enrollment Process",
                     font=ctk.CTkFont("Helvetica",14,weight="bold"),
                     text_color=WHITE).pack(anchor="w",padx=20,pady=(15,5))

        self.enroll_status = ctk.CTkLabel(ef,
                                           text="Select a student then click Start Enrollment.",
                                           font=ctk.CTkFont("Helvetica",12),
                                           text_color=GRAY)
        self.enroll_status.pack(padx=20,pady=10)

        self.enroll_prog = ctk.CTkProgressBar(ef, fg_color=NAVY, progress_color=TEAL)
        self.enroll_prog.pack(fill="x",padx=20,pady=(0,10))
        self.enroll_prog.set(0)

        ctk.CTkButton(ef, text="▶  START ENROLLMENT",
                      height=44, fg_color=TEAL, hover_color="#0F766E",
                      font=ctk.CTkFont("Helvetica",13,weight="bold"),
                      command=lambda: self._start_enroll(
                          stu_map, used_slots, next_slot)
                      ).pack(fill="x",padx=20,pady=(0,15))

    def _start_enroll(self, stu_map, used_slots, next_slot):
        selected = self.enroll_stu_var.get()
        student  = stu_map.get(selected)

        if not student:
            self.enroll_status.configure(
                text="Select a valid student first.", text_color=RED)
            return

        # Find next available slot
        slot = next_slot

        self.enroll_status.configure(
            text=f"Connecting to scanner... (Slot {slot})", text_color=AMBER)
        self.enroll_prog.set(0.1)

        def run():
            try:
                ser = serial.Serial(self.port_var.get(), BAUD_RATE, timeout=30)
                time.sleep(2)

                # Send slot number to Arduino
                cmd = f"ENROLL:{slot}\n"
                ser.write(cmd.encode())

                self.root.after(0, lambda: self.enroll_status.configure(
                    text=f"Step 1: Place finger on sensor... (Slot {slot})",
                    text_color=AMBER))
                self.root.after(0, lambda: self.enroll_prog.set(0.3))

                # Wait for Arduino response
                response = ""
                timeout  = 30
                start    = time.time()
                while time.time() - start < timeout:
                    if ser.in_waiting:
                        line = ser.readline().decode("utf-8", errors="ignore").strip()
                        if line.startswith("ENR_OK:") or line == "ENR_FAIL":
                            response = line
                            break
                    self.root.after(0, lambda: self.enroll_prog.set(
                        min(0.9, self.enroll_prog.get() + 0.02)))
                    time.sleep(0.5)

                ser.close()

                if response.startswith("ENR_OK:"):
                    actual_slot = int(response.split(":")[1])
                    # Save slot to database
                    self.db._patch("students",
                                   f"id=eq.{student['id']}",
                                   {"finger_slot": actual_slot})
                    self.root.after(0, lambda: self.enroll_status.configure(
                        text=f"✓ {student['full_name']} enrolled at slot {actual_slot}!",
                        text_color=GREEN))
                    self.root.after(0, lambda: self.enroll_prog.set(1.0))
                    # Refresh enrollment page
                    self.root.after(2000, lambda: self._show("enroll"))
                else:
                    self.root.after(0, lambda: self.enroll_status.configure(
                        text="Enrollment failed. Please try again.",
                        text_color=RED))
                    self.root.after(0, lambda: self.enroll_prog.set(0))

            except Exception as e:
                self.root.after(0, lambda: self.enroll_status.configure(
                    text=f"Error: {e}", text_color=RED))

        threading.Thread(target=run, daemon=True).start()

    # ── USER ACCOUNTS ────────────────────────────────
    def _user_accounts(self):
        cols = [("name",200,"Full Name"),("email",230,"Email"),
                ("role",160,"Role"),("active",80,"Active")]
        self.usr_table = self._table_page(
            "User Accounts","Manage system access — no self-registration", cols,
            add_cmd=self._add_lecturer_form,
            delete_cmd=self._deactivate_user,
            add_label="+ Create Account")
        self._load_users()

    def _load_users(self):
        self.usr_table.clear()
        def fetch():
            data = self.db.get_all_users()
            self.root.after(0, lambda: [
                self.usr_table.insert(values=(
                    u.get("full_name",""), u.get("email",""),
                    u.get("role","").upper().replace("_"," "),
                    "Yes" if u.get("is_active") else "No"
                ), iid=u.get("id")) for u in data
            ])
        threading.Thread(target=fetch, daemon=True).start()

    def _deactivate_user(self):
        iid = self.usr_table.focus()
        if not iid:
            messagebox.showinfo("Select","Select a user first.")
            return
        vals = self.usr_table.item(iid,"values")
        name = vals[0] if vals else "?"
        if messagebox.askyesno("Confirm", f"Deactivate account for {name}?"):
            self.db.deactivate_user(iid)
            self._load_users()

    # ── SETTINGS ─────────────────────────────────────
    def _settings(self):
        self._header("Settings","System configuration")
        body = ctk.CTkScrollableFrame(self.content, fg_color=NAVY)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        for section, items in [
            ("Application Info",[
                ("App Name",APP_NAME),("Version",APP_VERSION),
                ("Company",COMPANY_NAME),("Database","Supabase (PostgreSQL)"),
                ("Your Role",self.role.upper().replace("_"," ")),
            ]),
            ("Access Levels",[
                ("super_admin","Full access to everything"),
                ("admin","Full access — school IT person"),
                ("principal","View all departments and reports"),
                ("principal_secretary","View and manage for principal"),
                ("hod","View their department only"),
                ("hod_secretary","View and manage for HOD"),
                ("lecturer","View their own classes only"),
            ]),
        ]:
            card = ctk.CTkFrame(body, fg_color=DARK, corner_radius=12)
            card.pack(fill="x", pady=(0,15))
            ctk.CTkLabel(card, text=section,
                         font=ctk.CTkFont("Helvetica",14,weight="bold"),
                         text_color=WHITE).pack(anchor="w",padx=20,pady=(15,8))
            for k,v in items:
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x",padx=20,pady=2)
                ctk.CTkLabel(row, text=f"{k}:",
                             font=ctk.CTkFont("Helvetica",11),
                             text_color=GRAY, width=160).pack(side="left")
                ctk.CTkLabel(row, text=v,
                             font=ctk.CTkFont("Helvetica",11),
                             text_color=WHITE).pack(side="left")
            ctk.CTkLabel(card, text="", height=10).pack()

    # ── SIGNOUT & SYNC ───────────────────────────────
    def _signout(self):
        if messagebox.askyesno("Sign Out","Are you sure?"):
            self.db.logout()
            self.root.destroy()
            start_app()

    def _start_sync(self):
        def loop():
            while True:
                time.sleep(30)
                try:
                    online = self.db.is_online()
                    color  = GREEN if online else AMBER
                    status = "● Online" if online else "● Offline"
                    self.root.after(0,lambda s=status,c=color: self.online_lbl.configure(
                        text=s,text_color=c))
                    if online:
                        synced = self.db.sync_offline_data()
                        if synced > 0:
                            self.root.after(0,lambda n=synced: messagebox.showinfo(
                                "Sync",f"Synced {n} offline record(s)."))
                except: pass
        threading.Thread(target=loop,daemon=True).start()


def start_app():
    def on_login(user_data, db):
        MainApp(user_data, db)
    LoginWindow(on_login)


if __name__ == "__main__":
    start_app()