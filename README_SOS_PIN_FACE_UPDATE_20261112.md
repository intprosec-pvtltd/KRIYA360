# KRIYA360 SOS, driver PIN and face-photo update — 12 November 2026

## Implemented
- Dashboard: dashboard-wide emergency SOS panel and badge near the upper-right notification area; polls protected `/api/alerts` every 3 seconds, shows driver name, vehicle, phone, time and message.
- SOS map uses the existing **internal** `SOSLocation` dialog. A manager can acknowledge the SOS; when all active SOS events are acknowledged, the repeating alarm stops. Resolved history remains on the Alerts & SOS page.
- Emergency audio is **opt-in**: click **Enable emergency sound** once after dashboard sign-in, because browsers restrict autoplay. Browser audio may be blocked by tab mute, OS settings, power saving, or device policy.
- Backend: a new SOS request creates an individual SOS record rather than deduplicating all incidents from the same driver. The alert API now includes driver phone, vehicle and vehicle registration for authorized managers.
- Driver app: Change security PIN action in the profile using existing `/api/me/change-pin`; the current PIN must match and new PIN must be 6-12 digits. Old PIN stops working on successful change.
- Driver app: Enroll/Update face-photo action opens the front camera with explicit consent, uploads using the existing `/api/face/enroll`, and updates the driver profile. **This stores a photo; it is not biometric verification, face matching, or liveness detection.**
- Dashboard sign-in: the product logo uses background blending to reduce visible rectangular edges while retaining the existing layout.

## Limitations and production gates
- The 3-second poll is near-real-time while the management dashboard tab is open and online; not push delivery when all manager sessions are offline. For a true always-on emergency response system, deploy durable push/WebSocket delivery, paging/escalation, independent on-call monitoring, retries and audit testing.
- An SOS confirms receipt by the server, **not** that a human responded or emergency services were contacted.
- Browser alarms require an explicit sound unlock interaction and open browser tab.
- Current photo enrollment does not perform biometric identity verification. Production requires identity/liveness vendor, privacy/consent controls, retention policy and restricted evidence storage.
- Existing starter API uses a demo-oriented authentication configuration; change default JWT secret, disable demo seeding and deploy TLS, rate limiting, monitoring and robust DB backups before public production.
- Do not copy a demo database or upload directory over your own runtime data. The source archive deliberately excludes runtime database files, secret .env, uploaded user evidence, node_modules and build outputs.

## Update installation
1. Stop backend (`Ctrl+C`) and Vite (`Ctrl+C`).
2. Extract patch ZIP to a folder and run `Install-KRIYA360-SOS-PIN-FACE.ps1` in Windows PowerShell. The script backs up the existing files to `C:\KRIYA360\Backups` and does not modify database, uploads or `.env`.
3. Restart backend: `cd C:\KRIYA360; .\scripts_start_backend.ps1`.
4. In another PowerShell: `cd C:\KRIYA360\dashboard; npm install; npm run build; npm run dev -- --port 5173 --strictPort`.
5. For POCO Android: `cd C:\KRIYA360\driver_app; flutter pub get; flutter analyze; flutter test; flutter build apk --debug --dart-define=API_URL=http://<CURRENT_PC_WIFI_IP>:8000; flutter install --debug -d <YOUR_DEVICE_ID>`.
6. Test manager audio permission and SOS on different manager/dashboard pages, plus PIN and face actions on a spare test driver.

## Verification performed
- Backend: `python -m pytest -q tests/test_api.py` = 10 tests passed.
- Python syntax: `python -m py_compile backend/app/main.py` succeeded.
- React build: not verified in this environment because npm's offline cache lacks `@vitejs/plugin-react`; validate locally.
- Flutter build: not verified in this environment because Flutter SDK is not installed; validate locally.
