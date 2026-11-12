# KRIYA360 — Customer OTP and grouped expense interface update

## Included
- Backend launcher loads `backend/.env` with Uvicorn `--env-file`, including the reloader subprocess. No SMS credentials are included.
- `Configure-KRIYA360-Twilio.ps1` prompts locally for the SID, sender, and secret token, then writes the Git-ignored `backend/.env` with a timestamped backup of any previous file. Protect and rotate secrets.
- The driver app displays one expandable expense card per delivery, with total amount and individual numbered expenses and their approval status.
- The management dashboard groups expense evidence and review actions by delivery, without changing stored records.
- The company's logo and brand tagline are moved to the bottom of the driver's Profile page.
- Management Users is removed from sidebar navigation; it remains accessible from the top-right manager avatar.

## Important
- A configured Twilio account is not proof that SMS can be delivered. Twilio trial account restrictions, recipient verification, India SMS routing, and account permissions still apply.
- The SMS API deliberately returns an error and does not issue an OTP if configuration is missing or Twilio rejects the message.
- The original demo records with `Approved` and `No evidence` remain unchanged. Grouping does not alter or conceal them; they should be separately audited before real deployment.

## Installation
1. Stop the backend and dashboard.
2. Extract the update ZIP and run `Install-KRIYA360-Delivery-Expense-Update.ps1` from the extracted folder.
3. Run `C:\KRIYA360\Configure-KRIYA360-Twilio.ps1` in PowerShell and enter credentials privately; **rotate the previously exposed token**.
4. Run `C:\KRIYA360\scripts_start_backend.ps1`. Confirm that API `/api/health` responds.
5. In `C:\KRIYA360\dashboard`, run `npm run build` then `npm run dev -- --port 5173 --strictPort`.
6. In `C:\KRIYA360\driver_app`, run `flutter pub get`, `flutter analyze`, `flutter test`, `flutter build apk --debug --dart-define=API_URL=http://YOUR_PC_LAN_IP:8000`, then `flutter install --debug -d YOUR_DEVICE_ID`.
7. Check Expenses for at least two expense items on the same delivery; they should appear inside one expandable delivery card in the app and dashboard.

## Testing SMS
- Use a verified recipient permitted by your Twilio account, with country code (+91... for India).
- The driver requests OTP during an in-progress delivery; the API stores the hashed code only after the SMS provider accepts the submission.
- Do not paste the token, actual OTP, customer phone number, or full Twilio response into a chat or issue.

## Rollback
- The installer saves the replaced files under `C:\KRIYA360\Backups\Expense_SMS_<timestamp>`. Stop services and copy the backed-up files to their original locations if necessary.
