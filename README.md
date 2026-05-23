# Online Attendance Web App

This is a tiny web app for online self-attendance.

People open one link, scan their MyGate QR code or upload a screenshot, and the app writes a row to the `Attendance` sheet after matching the passcode in `Resident Master`.

The scanner is a static website in `web/`. Google Apps Script is used only as the Google Sheets backend because Apps Script HTML pages can block camera access in modern browser sandboxing.

## Sheet Structure

Your resident spreadsheet tab is currently configured as `Sheet1`. It should have these headers:

```text
Passcode, Name, Flat, Mobile No, Email, User Type, Status, User Id (Do Not Edit), House Id (Do Not Edit)
```

Your attendance spreadsheet tab is currently configured as `Attendance`. It can be empty. The script will create or extend these headers:

```text
Timestamp, Attendance Date, Source, QR Raw Data, Passcode, Name, Flat, Mobile No, Email, User Type, Status, User Id (Do Not Edit), House Id (Do Not Edit)
```

Your attendance spreadsheet should also have a `Voting Group` tab with these headers:

```text
House No, Resident Type, Resident Name, User Id (Do Not Edit), House Id (Do Not Edit)
```

## Backend Setup

1. Open the Google Sheet where you want to configure the backend. I recommend the `Attendance` Google Sheet.
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
2. Paste the Apps Script web app URL into `apiUrl`.
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

- Looks up the resident using the passcode.
- Appends attendance only when the passcode exists in `Resident Master`.
- Prevents duplicate attendance for the same passcode on the same date.
- After a new attendance row is added, appends all same-house residents whose `User Type` contains `Owner` into `Voting Group`.
- Prevents duplicate `Voting Group` rows by `House Id (Do Not Edit)` + `User Id (Do Not Edit)`.
- Supports camera scanning, QR screenshot upload, and manual paste.

## Quick Test

Before sharing the link widely:

1. Add one known resident row to `Resident Master`.
2. Host the `web/` folder or run it locally.
3. Paste the passcode into the manual field and submit.
4. Confirm a row appears in `Attendance`.
5. Try the same passcode again and confirm it says attendance is already marked.

For local testing:

```bash
python3 -m http.server 8080 --directory web
```

Then open:

```text
http://localhost:8080
```

## Notes

Because this is a public attendance link, anyone with a valid passcode can mark attendance. That is usually fine for a short event window, but avoid sharing the link outside the attendee group.
