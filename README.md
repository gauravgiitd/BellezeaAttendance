# Nambiar Bellezea Elections

This is the web app and backend for Nambiar Bellezea election attendance and voting.

For the broader election-management product plan, see:

- [Election Platform README](docs/ELECTION_PLATFORM_README.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Regression Test Plan](docs/TEST_PLAN.md)

The public site is intended to live at `https://bellezea-elections.onrender.com/`.

The new Postgres-backed election API lives in `backend/`. The static web app now includes the first election officer console for election setup, question creation, quorum tracking, and election-aware attendance.

Election officers can create elections, add questions, select an active election, scan MyGate QR codes, and track villa-level quorum. Resident Master is synced from Google Sheets into Postgres, while election state and attendance records are stored in Postgres.

The scanner is a static website in `web/`. The election backend is a FastAPI service in `backend/`.

## Resident Master Structure

Your resident spreadsheet tab is currently configured as `Sheet1`. It should have these headers:

```text
Passcode, Name, Flat, Mobile No, Email, User Type, Status, User Id (Do Not Edit), House Id (Do Not Edit)
```

This sheet is synced into Postgres through the backend.

## Legacy Sheet Structure

These sheets are used only by the original Apps Script attendance backend:

Your attendance spreadsheet tab is currently configured as `Attendance`. It can be empty. The script will create or extend these headers:

```text
Timestamp, Attendance Date, Source, QR Raw Data, Passcode, Name, Flat, Mobile No, Email, User Type, Status, User Id (Do Not Edit), House Id (Do Not Edit)
```

Your attendance spreadsheet should also have a `Voting Group` tab with these headers:

```text
House No, Resident Type, Resident Name, User Id (Do Not Edit), House Id (Do Not Edit)
```

## Legacy Apps Script Setup

The original Apps Script attendance backend remains in `apps-script/` for reference and fallback.

1. Open the Google Sheet where you want to configure the legacy backend. I recommend the `Attendance` Google Sheet.
2. Go to **Extensions -> Apps Script**.
3. Create this file in Apps Script:
   - `Code.gs` from `apps-script/Code.gs`
4. In `CONFIG`, paste the two spreadsheet IDs:
   - `RESIDENT_SPREADSHEET_ID`: the spreadsheet file containing the `Resident Master` tab
   - `ATTENDANCE_SPREADSHEET_ID`: the spreadsheet file containing the `Attendance` tab
5. If both tabs are in the same spreadsheet where the script is bound, leave both IDs blank.
6. Deploy with **Deploy -> New deployment -> Web app**.
7. Set:
   - **Execute as:** Me
   - **Who has access:** Anyone
8. Copy the web app URL.

## Frontend Setup

1. Open `web/config.js`.
2. Confirm `apiUrl` points to the deployed election API.
3. Host the `web/` folder on any HTTPS static host:
   - Netlify
   - Vercel
   - GitHub Pages
4. Share the hosted static website URL with online attendees.

Camera scanning requires HTTPS. Local testing works at `http://localhost`.

## Behavior

- Extracts the passcode from the first token of the QR text, matching your AppSheet formula:

```appsheet
NUMBER(
  INDEX(
    SPLIT([QR Raw Data], " "),
    1
  )
)
```

- Looks up the resident using the passcode in Postgres after Resident Master sync.
- Allows only residents whose `User Type` contains `Owner`.
- Records attendance against the selected election.
- Updates villa-level quorum representation.
- Supports camera scanning, QR screenshot upload, and manual paste.

## Quick Test

Before sharing the link widely:

1. Sync Resident Master into Postgres.
2. Create a test election.
3. Add one question with two choices.
4. Paste a known owner passcode into the attendance manual field.
5. Confirm quorum and attendee list update for the selected election.

For local testing:

```bash
cp .env.local.example .env.local
./scripts/start_local_api.sh
./scripts/start_local_web.sh
```

Set `RESIDENT_MASTER_CSV_URL` in `.env.local` to the same Google Sheet CSV export URL used on Render. Keep it in quotes because the URL contains `&`:

```bash
RESIDENT_MASTER_CSV_URL="https://docs.google.com/spreadsheets/d/.../export?format=csv&gid=..."
```

`scripts/start_local_api.sh` loads `.env.local` automatically. Then use **Sync Resident Master** in the officer console the same way as on Render.

Then open:

```text
http://localhost:8080
```

## Regression Tests

Run the backend regression harness before pushing changes:

```bash
.venv/bin/python scripts/regression_tests.py
```

The harness uses `DATABASE_URL` when it is set. If it is not set, it defaults to a local `bellezea_elections` Postgres database for the current macOS user. It creates synthetic villas, residents, and elections prefixed with `Regression Harness:` and cleans them up at the end.

On Render, the paid API service runs the same harness as a `preDeployCommand` after installing dependencies and before starting the new API version. If the harness fails, Render fails the deployment. This keeps local runs manual while gating every Render deploy.

## Notes

Because this is a public attendance link, anyone with a valid passcode can mark attendance. That is usually fine for a short event window, but avoid sharing the link outside the attendee group.
