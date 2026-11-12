# KRIYA360° — Logistics Driver + Management Platform

**Development release:** 11 Nov 2026 (demo source, NOT production certified)

## Contents

- `backend/`: Working Python FastAPI operations backend, SQLAlchemy models, protected APIs, automated tests, SQLite quickstart and PostgreSQL configuration.
- `dashboard/`: React/Vite manager dashboard, branded with supplied `KRIYA-360.png` logo and a real Leaflet/OpenStreetMap fleet map.
- `driver_app/`: Flutter Android driver source code, five-language UI, GPS, SOS, attendance, tasks, camera proof, expenses.
- `scripts/`: Windows PowerShell startup/bootstrap helpers.

## 1. Start backend on Windows PowerShell

```powershell
cd KRIYA360\backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:JWT_SECRET='SET-THIS-TO-A-LONG-RANDOM-SECRET-BEFORE-REAL-USE-123456'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000/docs. The backend uses **SQLite by default** to launch without a DB install. To use PostgreSQL/PostGIS, set `DATABASE_URL` and run the supplied Docker Compose database. PostGIS is initialized by Docker, but the demo ORM stores numeric GPS coordinates; spatial indexing is a planned migration.

## 2. Launch React dashboard (new PowerShell terminal)

```powershell
cd KRIYA360\dashboard
npm install
npm run dev
```

Open http://localhost:5173.

Demo **manager** login: phone `9000000000`, PIN `1234`.

## 3. Prepare and run Flutter driver app (new PowerShell terminal)

Requires Flutter SDK, Android Studio/Android SDK, and Android device/emulator. The archive contains **all handwritten app code** and Android permission manifest. Framework-generated wrapper/build files are intentionally generated on your machine:

```powershell
cd KRIYA360\driver_app
flutter create --project-name kriya360_driver --platforms android .
flutter pub get
flutter run --dart-define=API_URL=http://10.0.2.2:8000
```

If testing on a physical Android device, replace `10.0.2.2` with the **LAN IPv4 of the Windows computer** (example: `http://192.168.1.20:8000`) and make sure phone and computer share a network; allow port 8000 in Windows firewall only for trusted local networks. For release, use an **HTTPS server** and remove `android:usesCleartextTraffic="true"`.

Demo **driver** login: phone `9000000001`, PIN `1234`.

**IMPORTANT:** If `flutter create` replaces the manifest, copy `android/app/src/main/AndroidManifest.xml` from the archive again after creation. The included manifest defines location and foreground service permissions.

## 4. Demo journey (real shared backend data)

1. Log in as manager on web; register additional drivers if desired.
2. Log into the Flutter app as the demo driver; allow device location; Punch In.
3. In management web, navigate to **Assignments > New Assignment**. Enter a destination name, coordinates, deadline and select the driver.
4. Driver refreshes Tasks, taps **Start Delivery** and **Navigate**. Navigation launches installed maps; the backend calculates a route via OSRM demo service (subject to network availability).
5. Manager chooses **Generate OTP** on the assignment. Demo OTP appears ONLY in the manager dashboard. In production, integrate recipient SMS delivery and never expose the OTP to management or logs.
6. Driver taps **Complete Delivery**, enters the OTP and takes a photo. Verification updates the manager dashboard.
7. Driver submits a fuel/toll/parking expense; manager approves it on **Expenses**.
8. Driver taps SOS, explicitly confirms; management sees a critical alert and acknowledges/resolves it.
9. Driver punches out; management can review attendance and performance.

## Implemented in this code

- PIN login with salted PBKDF2 password hashes, bearer token and role checks.
- Manager driver creation, task assignment, current-position route lookup, driver suggestions using a transparent proximity/workload **heuristic** (not trained AI).
- Driver punch in/out, timestamps and vehicle; GPS updates during recorded shifts.
- Driver OSRM map navigation via Google Maps deep link; dashboard OpenStreetMap live map with polling.
- Route deviation detection against OSRM road geometry with fixed 600 m threshold (GPS noise can cause false positives).
- Missed punch-in, overdue delivery and ETA heuristic alerts; alerts update on dashboard requests.
- 10-minute delivery OTP (demo manager display) and mandatory photo; server stores restricted image files.
- Expense submission/approval, performance metrics, SOS driver confirmation with backend acknowledgement.
- English, Hindi, Kannada, Tamil and Telugu interface text (some server errors and dynamic text remain untranslated).
- Optional face-photo enrollment with explicit confirmation; **not face matching/liveness verification**.
- Background GPS through Geolocator Android foreground notification when OS permits; a bounded GPS-only offline retry queue.

## Not completed to production standards — do not misrepresent these

- **Trained AI allocation/prediction:** demo uses deterministic heuristics, not an ML model validated on delivery history.
- **Facial verification/liveness:** only photo enrollment; requires certified/validated biometric matching and anti-spoofing controls.
- **Full offline sync:** only GPS retry queue is implemented; offline task/expense/image conflict reconciliation is not included.
- **Always-on GPS:** Android power management, permission review and OEM restrictions require real-device tests. This is not guaranteed persistent background tracking on all devices.
- **Operational push messaging:** dashboard polls every 8 seconds, and mobile task list polls every 12 seconds. No FCM, WebSocket, APNs or out-of-band SOS dispatch is configured.
- **Route optimization:** OSRM public demo routing is not a commercial SLA, and may return fallback straight-line estimates. Traffic-aware ETA and multi-stop route optimization are not included.
- **Production security:** TLS, driver identity verification, rate limiting, secret rotation, audit events, schema migrations, OTP SMS gateway, biometric retention/erasure, database backup, OTP brute-force throttling, concurrency checks, service hosting and penetration testing are required.
- **Android binary:** Flutter SDK is not installed in this build container, so `flutter analyze`, physical testing and APK compilation have not been verified here.
- **React binary:** The npm registry was unavailable from the build container; `npm install` and Vite compilation have not been verified here.

## Security and privacy

Demo PINs and demo OTPs must never be reused in production. Face-photo consent and verified identity are separate concerns. Location sharing must be visible and shift-scoped. SOS is sent only after a deliberate confirmation and shows success only when the backend acknowledges it. **Never rely on this demo as a guaranteed emergency response system**; include emergency call alternatives.

## Run backend automated tests

```powershell
cd KRIYA360\backend
.\.venv\Scripts\python.exe -m pytest -q
```

The tests cover login, role separation, attendance, GPS, SOS, delivery creation, OTP rejection/acceptance, protected photo retrieval and expense approval.

## Recommended demo presentation

Use one driver account and one manager account side-by-side, show live state transitions in both applications, and end with the SOS alert appearing in the dashboard. Do not claim any user-generated data is actual operating fleet data.
