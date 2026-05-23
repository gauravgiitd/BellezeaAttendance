# Implementation Plan

This plan keeps the working MyGate QR attendance flow and evolves the app into a full election platform. The recommended path is incremental: stabilize attendance first, then add Postgres-backed election state and voting.

## Guiding Principles

- Keep Resident Master in Google Sheets initially.
- Move election state and voting data to Postgres.
- Treat villa-level representation as the central election unit.
- Keep individual attendance records for traceability.
- Never expose voter-level ballot details in public results.
- Keep all officer actions and ballot submissions auditable.
- Prefer strict backend validation over frontend-only rules.

## Phase 0: Current Attendance Hardening

Goal: Make the existing attendance app reliable enough to remain the intake mechanism.

Work:

- Keep MyGate QR scan/upload/manual paste flow.
- Reject non-owner `User Type` at backend.
- Store `User Id (Do Not Edit)` and `House Id (Do Not Edit)` with attendance.
- Populate `Voting Group` with same-house owner rows.
- Show villa representation summary.
- Show attendee list with timestamp.
- Add attendee search.

Status:

- Mostly implemented in the current app.

Remaining:

- Add manual attendance by villa/name for election officer.
- Add election/session selector so attendance is tied to a specific election.
- Add better backend error messages for expired/invalid QR/passcode.

## Phase 1: Postgres Backend Foundation

Goal: Introduce a real backend and database without breaking the current QR workflow.

Recommended stack:

- Render Web Service
- Node.js/Express or Python/FastAPI
- Render Postgres
- Static frontend on Render

Initial backend endpoints:

- `GET /health`
- `POST /api/auth/qr-login`
- `GET /api/residents/sync-status`
- `POST /api/residents/sync-from-google-sheet`
- `GET /api/elections`
- `POST /api/elections`
- `GET /api/elections/:id`

Database tables:

- `villas`
- `residents`
- `resident_source_syncs`
- `audit_events`

Resident sync:

- Read Resident Master Google Sheet.
- Upsert villas by house ID.
- Upsert residents by user ID.
- Preserve raw fields from Google Sheet for debugging.
- Mark residents inactive if source status is inactive.

## Phase 2: Election Officer Election Builder

Goal: Allow election officer to create and configure elections.

Features:

- Create election.
- Edit election title, description, status.
- Set quorum percentage.
- Set defaulter policy.
- Add questions.
- Add choices.
- Upload/attach image URLs for questions and choices.
- Set passing threshold per question.
- Support multiple concurrent elections.

Tables:

- `elections`
- `election_questions`
- `election_choices`

Important validation:

- Draft elections can be edited.
- Voting-open elections cannot change questions/choices.
- Each question must have at least two choices.
- Passing threshold must be valid for the chosen rule.

## Phase 3: Attendance Sessions and Quorum

Goal: Tie attendance to a specific election and compute quorum at villa level.

Features:

- Officer selects active election before taking attendance.
- QR attendance creates an individual attendance record.
- Attendance creates or updates villa representation for the election.
- Manual attendance by villa/name.
- Proxy attendance creates representation for proxy villas.
- Defaulter policy affects quorum denominator and eligibility.

Tables:

- `attendance_records`
- `villa_representations`
- `proxies`
- `defaulters`

Quorum calculation:

- Denominator: eligible villas for election.
- Numerator: represented eligible villas.
- Defaulter handling depends on election policy.
- Representation is villa-level even when multiple people attend for a villa.

## Phase 4: Proxy Management

Goal: Let election officer manage proxy relationships safely.

Features:

- Add proxy grantor and proxy holder.
- Scope proxy to election or meeting.
- Activate/cancel proxy.
- Show proxy holder all represented villas.
- Record proxy action in audit log.

Validation:

- Grantor villa must exist.
- Proxy holder must be owner-type and active.
- Defaulter policy applies to grantor villa.
- Prevent duplicate active proxy for the same grantor/election unless explicitly replaced.

## Phase 5: Voter Portal

Goal: Allow owners/proxy holders to login and submit votes.

Features:

- Login via MyGate QR scan/upload.
- Show active elections.
- Show quorum status.
- Show election questions.
- Disable voting until quorum is met and officer opens voting.
- Show represented villas: own villa plus proxy villas.
- Submit ballot separately for each represented villa.
- After submission, show read-only submitted ballot for that villa.

Tables:

- `ballots`
- `ballot_answers`

Constraints:

- One ballot per election per represented villa.
- One answer per question per ballot.
- Non-owner residents cannot vote.
- No ballot submission after voting close.
- No ballot submission before voting open.

## Phase 6: Results and Archive

Goal: Publish aggregate results and preserve detailed audit records.

Features:

- Officer closes voting.
- Public election results page.
- Attendance count.
- Represented villa count.
- Vote count.
- Per-question counts by choice.
- Pass/fail result per question based on threshold.
- Export archive for election officer.

Archive:

- Ballot records retained in Postgres.
- Audit events retained in Postgres.
- Optional CSV export for officer.
- Public views never expose voter-level details.

## Phase 7: Production Readiness

Goal: Make the system resilient for live election use.

Work:

- Officer authentication.
- Role-based access control.
- Database backups.
- Render environment variables.
- Error monitoring.
- Rate limiting on QR login and vote submission.
- Clear event-day operating checklist.
- Dry-run election mode.
- CSV export for attendance and results.

## Suggested First Implementation Slice

The first meaningful build after this planning doc should be:

1. Add Postgres schema migrations.
2. Add backend service skeleton.
3. Add Resident Master sync from Google Sheets into Postgres.
4. Add election creation and listing.
5. Add attendance session tied to one election.
6. Keep existing static QR UI, but change it to call the new backend instead of Apps Script for election-aware attendance.

This gives us the foundation for quorum, proxies, and voting without rewriting the whole system at once.

## Implementation Progress

The first backend slice has been started in `backend/`.

Included:

- FastAPI backend service.
- Postgres schema for residents, villas, elections, questions, choices, proxies, defaulters, attendance records, villa representations, ballots, ballot answers, and audit events.
- Render Blueprint entries for the backend web service and Postgres database.
- Resident sync endpoints from CSV upload or Google Sheet CSV export URL.
- Election create/list/detail endpoints.
- Question and choice creation endpoints.
- Election status transition endpoint.
- Proxy create/list/cancel endpoints.
- Defaulter create/list/clear endpoints.
- Owner-only QR login endpoint.
- Election-aware QR attendance endpoint.
- Manual attendance endpoint by user ID or house ID plus name.
- Villa representation creation at attendance time.
- Proxy representation expansion at attendance time.
- Villa-level ballot submission endpoint.
- Aggregate results endpoint that hides voter-level ballot details.
- Election-specific attendance dashboard endpoint.
- First officer UI for creating elections, adding two-choice questions, selecting an active election, viewing quorum, and marking QR/manual attendance against Postgres.

Next implementation step:

1. Add officer UI for proxy and defaulter management.
2. Add question image and choice image support.
3. Add voter portal for QR login and represented-villa ballot submission.
4. Add officer results/archive views.
5. Add authentication before live election use.
