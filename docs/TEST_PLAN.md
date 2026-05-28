# Nambiar Bellezea Elections Test Plan

This checklist covers the main behavior that can regress in the election portal. The automated harness in `scripts/regression_tests.py` covers the core backend rules using synthetic villas and residents in the configured Postgres database.

## Resident Master Data And Directory

- Google Sheet sync is not covered by the automated harness while sheet access is removed.
- When sheet access is available, resident CSV rows with valid `User Id (Do Not Edit)` and `House Id (Do Not Edit)` should sync into Postgres.
- When sheet access is available, rows missing required IDs should be skipped, not partially imported.
- A person can exist against multiple homes because residents are unique on `(user_id, house_id)`.
- Resident directory returns villas with owner-type residents only.
- Tenant/non-owner residents cannot log in, attend, or vote.
- Passcode extraction uses the first QR token and extracts the numeric value.

## Election Setup

- Election officer can create an attendance-only election without questions.
- Election officer cannot start a voting-enabled election without at least one question.
- Questions support more than two choices.
- Question and choice image URLs are stored.
- Passing rule is election-level, not question-level.
- Custom passing threshold requires a custom threshold value.
- Election settings, proxy management, and defaulter management are locked after attendance starts.
- Quorum can still be changed during attendance.
- Quorum is locked once voting starts.
- Questions can be edited during attendance but not after voting starts.
- Election delete removes election data and cascades dependent records.

## Attendance

- Manual attendance by villa marks all owner-type residents of that villa as actual attendees.
- Re-marking the same villa is idempotent and does not create duplicate attendance rows.
- QR attendance works for valid owner passcodes.
- Invalid QR data is rejected.
- Tenant/non-owner passcodes are rejected.
- Attendance cannot be marked in draft or closed elections.
- Attendance can be marked during attendance and voting stages.
- Attendance-only elections can move from attendance to closed without a voting stage.

## Quorum And Defaulters

- Non-defaulter attendee villas count toward quorum.
- Defaulter villas are excluded from eligible villa count when the election is configured to exclude defaulters.
- Defaulter villas can still appear in attendance views, but marked as not counted.
- Defaulter actual attendees are excluded from counted reports when defaulters are excluded.
- Defaulter villas count and appear in reports when the election is configured to include defaulters.
- Defaulters are scoped per election, not globally.

## Proxy Management

- Proxy records are scoped per election.
- Grantor villa must exist.
- Proxy holder must be an owner-type resident.
- Proxy holder villa/name selection must resolve to an owner resident in Resident Master.
- Proxy holder email is stored with the proxy and normalized consistently.
- One active proxy per grantor villa per election is allowed.
- Duplicate active proxy for the same grantor villa in the same election is rejected.
- Proxy management is locked after attendance starts.
- When a proxy holder attends, the grantor villa is represented as proxy.
- Proxy grantor villas marked as defaulters are excluded from counted representation when defaulters are excluded.

## Reports

- Actual Attendee Report for MyGate contains only actual attendees for villas counted through `villa_representations`.
- Actual Attendee Report excludes proxy-only grantor villas.
- Actual Attendee Report excludes defaulter actual attendees when the defaulter villa is not counted.
- Proxy Attendee Report for Google Survey contains only emails for attended proxy holders whose proxy grantor villa is counted.
- Proxy Attendee Report excludes proxies whose proxy holder did not attend.
- Proxy Attendee Report excludes defaulter grantor villas when defaulters are not counted.

## Voter And Voting Flows

- Voting-disabled elections reject ballot submission.
- Voting-enabled elections cannot open voting until quorum is reached.
- Only represented villas can submit ballots.
- Proxy holder can submit separately for proxy grantor villas they represent.
- A villa can submit only one ballot.
- Ballots must answer every question exactly once.
- Results are hidden before voting closes.
- Results appear after voting closes.
- Simple majority, two-thirds, and custom threshold outcomes are calculated at election level.
- Restart voting deletes existing ballots and reopens voting.

## Public Voter Portal / Attendance Board

- Public attendance board does not require MyGate login.
- Public attendance board shows attendance-open elections.
- Closed elections are not shown on the public attendance board.
- When multiple active elections exist, voter portal lets the user select one election and then shows quorum and attending villas for that election.

## Officer Access

- Officer portal requires the configured Google account in deployed environments.
- Local development can disable officer auth with `OFFICER_AUTH_DISABLED=true`.
- Officer-only APIs reject unauthenticated requests when auth is enabled.

## Frontend Smoke Tests

- Officer portal loads on `?portal=officer`.
- Manage Elections shows election setup, question editor, proxy management, and defaulter management.
- Run Election shows attendance, quorum, attending villas, and report download buttons.
- Voter portal loads on `?portal=voter`.
- Voter portal election selector behaves correctly when more than one attendance-open election exists.
- Search boxes filter villas and names in both officer and voter attendance panels.
- Download buttons create CSV files with the expected filenames and headers.
