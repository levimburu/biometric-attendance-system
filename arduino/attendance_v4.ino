/*
=============================================================
  BIOMETRIC ATTENDANCE SYSTEM v5 — Arduino Uno
  Based on supervisor's working code + Supabase bridge

  FLOW:
    1. Boot screen
    2. PIN entry (any 4 keys to unlock)
    3. Scan fingerprint
    4. Bridge logs attendance to Supabase
    5. OLED shows student name + admission number

  LIBRARIES:
    - U8g2 by oliver
    - Adafruit Fingerprint Sensor Library
    - Keypad by Mark Stanley

  WIRING:
    OLED:   SDA->A4, SCL->A5, VCC->5V, GND->GND
    R305:   TX->2,  RX->3,   VCC->5V, GND->GND
    Keypad Rows: 5,7,9,4   Cols: 6,8,10
    Buzzer: Pin 11
=============================================================
*/

#include <Arduino.h>
#include <Adafruit_Fingerprint.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <SoftwareSerial.h>
#include <Keypad.h>

// ── BUZZER ────────────────────────────────────────────────
#define PIEZO_BUZZER 11

// ── KEYPAD ────────────────────────────────────────────────
const byte ROWS = 4;
const byte COLS = 3;
char hexaKeys[ROWS][COLS] = {
  {'1','2','3'},
  {'4','5','6'},
  {'7','8','9'},
  {'*','0','#'}
};
byte rowPins[ROWS] = {5, 7, 9, 4};
byte colPins[COLS]  = {6, 8, 10};
Keypad customKeypad = Keypad(makeKeymap(hexaKeys),
                              rowPins, colPins, ROWS, COLS);

// ── PIN SECURITY ──────────────────────────────────────────
int  pinPressCount  = 0;
bool systemUnlocked = false;

// ── OLED ──────────────────────────────────────────────────
U8G2_SSD1306_128X64_NONAME_1_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);

// ── FINGERPRINT ───────────────────────────────────────────
SoftwareSerial mySerial(2, 3);
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&mySerial);

// ── SERIAL READ ───────────────────────────────────────────
bool rdLine(char* buf, uint8_t mx, uint16_t tms) {
  unsigned long t = millis();
  uint8_t i = 0; buf[0] = 0;
  while (millis()-t < tms) {
    if (Serial.available()) {
      char c = Serial.read();
      if (c=='\n'||c=='\r') { buf[i]=0; return i>0; }
      if (i < mx-1) buf[i++] = c;
    }
  }
  buf[i]=0; return i>0;
}

// ── BUZZER HELPERS ────────────────────────────────────────
void triggerBeep(int freq, int dur) {
  tone(PIEZO_BUZZER, freq, dur);
}

// ── DISPLAY FUNCTIONS ─────────────────────────────────────
void displayLockScreen(int count) {
  u8g2.firstPage();
  do {
    u8g2.setFont(u8g2_font_helvB08_tr);
    u8g2.drawStr(0, 12, "SYSTEM LOCKED");
    u8g2.drawHLine(0, 16, 128);
    u8g2.setFont(u8g2_font_helvR08_tr);
    u8g2.drawStr(0, 35, "Press any 4 keys");
    u8g2.drawStr(0, 48, "to unlock:");
    char masked[9] = "";
    for (int i = 0; i < count; i++) {
      masked[i*2]   = '*';
      masked[i*2+1] = ' ';
    }
    masked[count*2] = 0;
    u8g2.setFont(u8g2_font_helvB12_tr);
    u8g2.drawStr(40, 62, masked);
  } while (u8g2.nextPage());
}

void displayStandby() {
  u8g2.firstPage();
  do {
    u8g2.setFont(u8g2_font_helvB08_tr);
    u8g2.drawStr(0, 12, "ATTENDANCE SYSTEM");
    u8g2.drawHLine(0, 16, 128);
    u8g2.setFont(u8g2_font_helvR10_tr);
    u8g2.drawStr(12, 45, "Scan Finger...");
    u8g2.setFont(u8g2_font_helvR08_tr);
    u8g2.drawStr(0, 62, "* = End Session");
  } while (u8g2.nextPage());
}

void displayAttendance(const char* name, const char* admNum) {
  u8g2.firstPage();
  do {
    u8g2.setFont(u8g2_font_helvB08_tr);
    u8g2.drawStr(0, 12, "LOGGED IN SUCCESS!");
    u8g2.drawHLine(0, 16, 128);
    u8g2.setFont(u8g2_font_helvR08_tr);
    u8g2.drawStr(0, 30, "Present!");
    u8g2.setFont(u8g2_font_helvB10_tr);
    u8g2.drawStr(0, 46, name);
    u8g2.setFont(u8g2_font_helvR08_tr);
    u8g2.drawStr(0, 60, admNum);
  } while (u8g2.nextPage());
}

void displayDuplicate() {
  u8g2.firstPage();
  do {
    u8g2.setFont(u8g2_font_helvB08_tr);
    u8g2.drawStr(0, 12, "ALREADY MARKED");
    u8g2.drawHLine(0, 16, 128);
    u8g2.setFont(u8g2_font_helvR08_tr);
    u8g2.drawStr(0, 34, "Already marked");
    u8g2.drawStr(0, 48, "for today.");
  } while (u8g2.nextPage());
}

void displayUnknown() {
  u8g2.firstPage();
  do {
    u8g2.setFont(u8g2_font_helvB08_tr);
    u8g2.drawStr(0, 12, "ACCESS DENIED");
    u8g2.drawHLine(0, 16, 128);
    u8g2.setFont(u8g2_font_helvR08_tr);
    u8g2.drawStr(0, 34, "Not recognized.");
    u8g2.drawStr(0, 48, "Not enrolled.");
    u8g2.drawStr(0, 60, "Contact admin.");
  } while (u8g2.nextPage());
}

void displayMsg(const char* h, const char* l1,
                const char* l2, const char* l3) {
  u8g2.firstPage();
  do {
    u8g2.setFont(u8g2_font_helvB08_tr);
    u8g2.drawStr(0, 12, h);
    u8g2.drawHLine(0, 16, 128);
    u8g2.setFont(u8g2_font_helvR08_tr);
    if (l1&&l1[0]) u8g2.drawStr(0, 30, l1);
    if (l2&&l2[0]) u8g2.drawStr(0, 44, l2);
    if (l3&&l3[0]) u8g2.drawStr(0, 58, l3);
  } while (u8g2.nextPage());
}

// ── FINGERPRINT ───────────────────────────────────────────
int getFingerprintID() {
  uint8_t p = finger.getImage();
  if (p != FINGERPRINT_OK) return -1;
  p = finger.image2Tz();
  if (p != FINGERPRINT_OK) return -1;
  p = finger.fingerFastSearch();
  if (p != FINGERPRINT_OK) return -1;
  return finger.fingerID;
}

void doEnroll(uint8_t slot) {
  char b[17]; snprintf(b,17,"Slot: %d",slot);
  displayMsg("ENROLLING","Place finger...",b,"");
  triggerBeep(2200,50);

  uint8_t p=-1; unsigned long t=millis();
  while (p!=FINGERPRINT_OK&&millis()-t<15000) {
    p=finger.getImage(); delay(50);
  }
  if (p!=FINGERPRINT_OK||finger.image2Tz(1)!=FINGERPRINT_OK) {
    displayMsg("FAILED","Timeout.","Try again.","");
    Serial.println(F("ENR_FAIL")); delay(2000); return;
  }

  displayMsg("ENROLLING","Remove finger...","","");
  delay(2000);
  while (finger.getImage()!=FINGERPRINT_NOFINGER);

  displayMsg("ENROLLING","Place same","finger again...","");
  p=-1; t=millis();
  while (p!=FINGERPRINT_OK&&millis()-t<15000) {
    p=finger.getImage(); delay(50);
  }
  if (p!=FINGERPRINT_OK||finger.image2Tz(2)!=FINGERPRINT_OK) {
    displayMsg("FAILED","Timeout.","Try again.","");
    Serial.println(F("ENR_FAIL")); delay(2000); return;
  }

  bool ok = (finger.createModel()==FINGERPRINT_OK)&&
            (finger.storeModel(slot)==FINGERPRINT_OK);
  snprintf(b,17,"Slot: %d",slot);
  if (ok) {
    displayMsg("ENROLLED!","Success!",b,"");
    triggerBeep(2000,120);delay(140);triggerBeep(2500,200);
    Serial.print(F("ENR_OK:")); Serial.println(slot);
  } else {
    displayMsg("FAILED","Store error.","Try again.","");
    triggerBeep(800,400);
    Serial.println(F("ENR_FAIL"));
  }
  delay(2000);
}

// ── SETUP ─────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  pinMode(PIEZO_BUZZER, OUTPUT);

  // OLED — exactly as supervisor's working code
  u8g2.setI2CAddress(0x3C * 2);
  u8g2.begin();
  u8g2.setContrast(255);

  // Fingerprint
  finger.begin(57600);
  if (!finger.verifyPassword()) {
    finger.begin(9600);
    if (!finger.verifyPassword()) {
      displayMsg("SENSOR ERROR","Sensor not found!",
                 "Check wiring.","");
      while(1) delay(1);
    }
  }

  // Boot screen
  displayMsg("ATTENDANCE SYS","Biometric v5.0",
             "System Ready!","");
  triggerBeep(2000,100); delay(140); triggerBeep(2500,200);
  delay(1500);
}

// ── MAIN LOOP ─────────────────────────────────────────────
void loop() {
  char key = customKeypad.getKey();

  // ── Handle serial commands from bridge ──────────────
  if (Serial.available()) {
    char cmd[64]; rdLine(cmd, 64, 100);

    if (!strncmp(cmd,"NAME:",5)) {
      // Format: NAME:{name}|{admission_number}
      char name[20]="", adm[24]="";
      char* pipe = strchr(cmd+5,'|');
      if (pipe) {
        uint8_t nl = pipe-(cmd+5);
        if (nl>19) nl=19;
        strncpy(name,cmd+5,nl); name[nl]=0;
        strncpy(adm,pipe+1,23); adm[23]=0;
      } else {
        strncpy(name,cmd+5,19); name[19]=0;
      }
      displayAttendance(name, adm);
      triggerBeep(2000,120); delay(140); triggerBeep(2500,200);
      delay(3000);

    } else if (!strcmp(cmd,"DUPLICATE")) {
      displayDuplicate();
      triggerBeep(1500,80); delay(100); triggerBeep(1500,80);
      delay(2000);

    } else if (!strcmp(cmd,"UNKNOWN")) {
      displayUnknown();
      triggerBeep(800,400);
      delay(2000);

    } else if (!strcmp(cmd,"FORCE_END")) {
      displayMsg("SESSION ENDED","Time limit.",
                 "Auto-closed.","Thank you.");
      triggerBeep(2000,500);
      delay(3000);
      systemUnlocked = false;
      pinPressCount  = 0;

    } else if (!strncmp(cmd,"ENROLL:",7)) {
      uint8_t slot = atoi(cmd+7);
      if (slot>=1&&slot<=127) doEnroll(slot);
      else Serial.println(F("ENR_FAIL"));

    } else if (!strcmp(cmd,"E")) {
      doEnroll(finger.getTemplateCount()+1);

    } else if (!strncmp(cmd,"D:",2)) {
      finger.deleteModel(atoi(cmd+2));
      Serial.print(F("DELETED:")); Serial.println(atoi(cmd+2));

    } else if (!strcmp(cmd,"WIPE_ALL")) {
      finger.emptyDatabase();
      displayMsg("WIPED","All prints","deleted.","");
      triggerBeep(2000,500);
      Serial.println(F("WIPED"));
      delay(2000);
    }
  }

  // ── STATE: LOCKED ────────────────────────────────────
  if (!systemUnlocked) {
    displayLockScreen(pinPressCount);
    if (key) {
      pinPressCount++;
      triggerBeep(2200, 50);
      if (pinPressCount >= 4) {
        systemUnlocked = true;
        pinPressCount  = 0;
        triggerBeep(2000,100); delay(120); triggerBeep(2500,200);
      }
    }
  }

  // ── STATE: ACTIVE SCANNING ───────────────────────────
  else {
    displayStandby();
    int id = getFingerprintID();
    if (id > 0) {
      Serial.print(F("ATT:")); Serial.println(id);
      // Wait for bridge response
      char resp[64];
      if (rdLine(resp, 64, 5000)) {
        if (!strncmp(resp,"NAME:",5)) {
          char name[20]="", adm[24]="";
          char* pipe = strchr(resp+5,'|');
          if (pipe) {
            uint8_t nl = pipe-(resp+5);
            if (nl>19) nl=19;
            strncpy(name,resp+5,nl); name[nl]=0;
            strncpy(adm,pipe+1,23); adm[23]=0;
          } else {
            strncpy(name,resp+5,19); name[19]=0;
          }
          displayAttendance(name, adm);
          triggerBeep(2000,120); delay(140); triggerBeep(2500,200);
          delay(3000);
        } else if (!strcmp(resp,"DUPLICATE")) {
          displayDuplicate();
          triggerBeep(1500,80); delay(100); triggerBeep(1500,80);
          delay(2000);
        } else if (!strcmp(resp,"UNKNOWN")) {
          displayUnknown();
          triggerBeep(800,400);
          delay(2000);
        }
      }
    }
    // * key ends session
    if (key == '*') {
      Serial.println(F("SESSION_END"));
      displayMsg("SESSION ENDED","Session closed.",
                 "Thank you.","");
      triggerBeep(2000,500);
      delay(2000);
      systemUnlocked = false;
      pinPressCount  = 0;
    }
  }

  delay(20);
}
