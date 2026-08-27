# Recommended Intelligent Agent Workflows (CGMH)

This document outlines the standard multi-step intelligent workflows for AI coding agents orchestrating Chang Gung Memorial Hospital (CGMH) operations.

---

## Workflow 1: The Safe & Smart Outpatient Booking Cycle
Before executing a booking, a smart agent always verifies availability and checks for existing registrations to prevent duplications or booking locked sessions.

### Step-by-Step Cycle:
```
  [Start]
     │
     ▼
1. Fetch Doctor Schedule ────► (Check if the doctor's slot has "停診" or is "額滿")
     │
     ▼
2. Check Duplicates ─────────► (Call query_cgmh_registration.py. If duplicate exists, [Stop])
     │
     ▼
3. Execute Booking ──────────► (Call book_cgmh_appointment.py using solved Tesseract OCR)
     │
     ▼
4. Verify & Log ─────────────► (Call query_cgmh_registration.py to fetch "看診序號" & "預估看診時間")
     │
     ▼
  [End]
```

### Script Execution Example:
```bash
# 1. (Analytic Step) Parse register.cgmh.org.tw/Department_WEEK/V/V1200A
# 2. Check duplicate registrations in Tucheng Hospital (V)
python3 templates/query_cgmh_registration.py A123456789 700101 V

# 3. If query returns empty (no duplicate), proceed with booking:
python3 templates/book_cgmh_appointment.py A123456789 700101 V1200A 20260722 1985 2 V

# 4. Instantly verify and extract sequence number:
python3 templates/query_cgmh_registration.py A123456789 700101 V
```

---

## Workflow 2: Smart Consultation Progress Tracking & Notification
Patients often want to know when they should set off for the hospital. A smart agent can run a cron-like tracking routine.

### Step-by-Step Cycle:
1. **Query Sequence Number**: Query the patient's registered sequence number (e.g. Number `24`).
2. **Check Current Progress**: Fetch `https://register.cgmh.org.tw/Progress/V`, select Gastroenterology (胃腸科), and retrieve the currently called number (e.g. Number `18`).
3. **Calculate Buffer**: Compare `24 - 18 = 6` numbers remaining.
4. **Trigger Alert**:
   - If distance is `> 10`: "距離看診還有 10 號以上，可稍候出發。"
   - If distance is `between 5 and 10`: "即將到診（差 6 號），建議準備出發！"
   - If distance is `< 5`: "即將呼叫您的號碼，請立即前往診間！"

---

## Workflow 3: Safe Interactive Cancellation
Before cancelling, a smart agent confirms the target date, department, and doctor to avoid accidental cancellation.

### Script Execution Example:
```bash
# 1. Fetch current list of appointments to confirm target details
python3 templates/query_cgmh_registration.py A123456789 700101 V

# 2. Present details to the user and prompt: "Are you sure you want to cancel Dr. Lin's appointment on 2026-07-22?"
# 3. Upon receiving user confirmation, execute cancellation:
python3 templates/cancel_cgmh_registration.py A123456789 700101 2026-07-22 張三醫師 V

# 4. Verify cancellation outcome
python3 templates/query_cgmh_registration.py A123456789 700101 V
```
