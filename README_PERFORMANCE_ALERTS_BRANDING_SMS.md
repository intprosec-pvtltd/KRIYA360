# KRIYA360 — Performance, Alerts, Attendance & Branding Update

- Performance: per-driver bar comparisons, fleet/delivery donut, per-driver selection, CSV for all or one driver, browser Print/Save PDF. Export reflects currently loaded backend figures.
- Attendance: preserved punch-in/out thumbnails and expanded evidence; removed only redundant all-GPS overview map.
- Alerts: response-oriented cards, status/severity filters, summary counts and existing acknowledge/resolve actions.
- Mobile: latest supplied KRIYA360 app icon, branded loading screen, sign-in company logo moved to footer, branded profile footer retained.
- Web: favicon uses latest supplied KRIYA360 emblem.
- Backend: existing OTP endpoint unchanged. Startup passes absolute .env path to Uvicorn and reports whether it exists.

## SMS troubleshooting
1. Run `cd C:\KRIYA360; .\Check-KRIYA360-Twilio.ps1`. Never paste credentials into chat.
2. If missing, run `.\Configure-KRIYA360-Twilio.ps1` in PowerShell and enter your **rotated** token privately.
3. Stop the old FastAPI server (`Ctrl+C`) and restart with `.\scripts_start_backend.ps1`; check for `.env detected`.
4. If the app still displays **Customer SMS is not configured**, check that the POCO API_URL points to the correct PC and that the request reaches this restarted backend instance.
5. If the error changes to **SMS provider could not accept the message**, inspect sanitized Twilio Messaging Logs for trial restrictions, verified recipient, international permissions, and India DLT routing. Twilio accepting a message does not guarantee delivery.

Only install on a development system. The `.env` file contains plaintext credentials; restrict access and rotate previously exposed secrets.
