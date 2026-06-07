# Biometric Attendance System

A full-stack biometric attendance system built for The Kitale National Polytechnic. Uses fingerprint scanning to verify student and staff identity in real time, logging attendance to a cloud database accessible from anywhere.

Showcased at **Madaraka Day 2026** — Kenya national innovation showcase.

---

## System Overview

```
Arduino Device          Python Bridge          Supabase Cloud
──────────────         ──────────────         ──────────────
Fingerprint scan   →   Identify student   →   Log attendance
OLED display       ←   Send name + adm#   ←   Fetch records
PIN lock screen        Session management     Real-time sync
```

---

## Features

- Biometric fingerprint verification using R305/AS608 sensor
- Real-time attendance logging to Supabase PostgreSQL
- Full admin desktop app (Python + CustomTkinter)
- Web dashboard for remote attendance viewing
- PIN lock security with failed attempt lockout
- Offline fallback with local SQLite storage
- Role-based access (super admin, admin, HOD, lecturer)
- Timetable validation and auto session management
- Student and staff enrollment from admin app

---

## Hardware

| Component | Purpose |
|---|---|
| Arduino Uno | Microcontroller |
| R305 Fingerprint Sensor | Biometric scanning |
| SSD1306 OLED 128x64 | Display |
| 3x4 Matrix Keypad | Input |
| Active Buzzer | Audio feedback |

---

## Software Stack

| Layer | Technology |
|---|---|
| Microcontroller | Arduino C++ |
| Bridge | Python 3 + PySerial |
| Admin App | Python + CustomTkinter |
| Database | Supabase (PostgreSQL) |
| Web Dashboard | HTML + JavaScript |
| Local Fallback | SQLite |

---

## Project Structure

```
biometric-attendance-system/
├── arduino/
│   └── attendance_v4.ino       # Arduino sketch
├── admin_app/
│   ├── main.py                 # Desktop admin app
│   ├── database.py             # Supabase HTTP client
│   ├── bridge.py               # Hardware-to-cloud bridge
│   └── config.py               # Configuration (see setup)
├── web_dashboard/
│   └── index.html              # Browser-based dashboard
├── database/
│   └── schema.sql              # Full database schema
├── docs/
│   └── project_summary.html   # Project one-pager
├── requirements.txt
└── README.md
```

---

## Setup Guide

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/biometric-attendance-system.git
cd biometric-attendance-system
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up Supabase

- Create a free account at [supabase.com](https://supabase.com)
- Create a new project
- Go to SQL Editor and run the full contents of `database/schema.sql`
- Copy your Project URL and anon key

### 4. Configure credentials

Copy `admin_app/config.py` and fill in your Supabase details:

```python
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-key-here"
```

### 5. Run the admin app

```bash
cd admin_app
python main.py
```

### 6. Upload Arduino sketch

- Open `arduino/attendance_v4.ino` in Arduino IDE
- Install required libraries (U8g2, Adafruit Fingerprint Sensor, Keypad)
- Select board: Arduino Uno
- Upload

### 7. Run the bridge

```bash
cd admin_app
python bridge.py
```

---

## Wiring

| Component | Arduino Pin |
|---|---|
| OLED SDA | A4 |
| OLED SCL | A5 |
| R305 TX | Pin 2 |
| R305 RX | Pin 3 |
| Keypad Row 1-4 | Pins 5,7,9,4 |
| Keypad Col 1-3 | Pins 6,8,10 |
| Buzzer | Pin 11 |

---

## Authors

- **Levi Mburu** — Student, Electrical & Electronics Engineering
- **Mary Kalimi** — Student, Electrical & Electronics Engineering
- **Kevin Wakhisi** — Supervisor

**Institution:** The Kitale National Polytechnic
**Department:** Electrical & Electronics Engineering
**Year:** 2026

---

## License

This project is open source and available under the [MIT License](LICENSE).
