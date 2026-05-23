# Nambiar Bellezea Election Platform

This document describes the target election platform for Nambiar Bellezea. The current attendance app is the first module: it scans a MyGate QR code, verifies the resident against the Resident Master Google Sheet, and records attendance. The full platform extends that into election creation, quorum tracking, proxy representation, villa-level voting, and result publishing.

## Roles

### Election Officer

The election officer configures and runs elections.

Responsibilities:

- Create one or more elections.
- Add election questions and choices.
- Attach images to questions or choices when needed.
- Set quorum requirements per election, such as `30%`, `50%`, `66.6%`, or a custom value.
- Decide per election whether defaulters count toward quorum and whether defaulters can vote.
- Manage proxies before and during the meeting.
- Manage the defaulter list.
- Take attendance physically by scanning MyGate QR codes.
- Take attendance manually by villa/name when needed.
- Start voting after quorum is reached and discussion is complete.
- Set voting close time.
- Close voting and publish summarized results.
- Preserve detailed vote records for audit/archive without exposing voter-level details publicly.

### Voter

The voter attends, authenticates, and votes for their villa and any proxy villas assigned to them.

Responsibilities:

- Attend physically or virtually.
- Ensure attendance is marked by the election officer.
- Login to the election portal using MyGate QR scan or QR upload.
- View active elections.
- View quorum status and election questions.
- Vote only when quorum is reached and voting is opened by the election officer.
- Submit one vote per represented villa.
- Submit proxy votes separately for each proxy villa.
- View aggregate progress during voting.
- View final aggregate results after voting closes.

## Core Concepts

### Election

An election is a collection of one or more questions. Multiple elections can run concurrently.

Election fields:

- Name/title
- Description
- Status: draft, attendance open, discussion, voting open, voting closed, results published, archived
- Quorum percentage
- Defaulter policy
- Voting open time
- Voting close time
- Result visibility policy

### Question

Each election has one or more questions.

Question fields:

- Question text
- Optional question image
- Passing rule: simple majority, two-thirds majority, or custom threshold
- Choice list

### Choice

Each question has multiple choices, usually two.

Choice fields:

- Choice text
- Optional choice image
- Display order

### Villa-Level Representation

Attendance and voting are tracked at the villa level for quorum and ballot submission.

Rules:

- Multiple owners from the same villa may attend.
- Their individual attendance can be tracked.
- Quorum counts each represented villa only once.
- Voting submission is one submission per villa per election/question.
- Once a villa submits its vote, other owners from that villa can view the submission but cannot modify it.

### Owner-Only Eligibility

Only residents whose `User Type` contains `Owner` are eligible to attend and vote in elections.

Non-owner user types are rejected from attendance and voting.

### Proxy

A proxy allows one eligible owner to represent another villa.

Proxy fields:

- Grantor name
- Grantor villa
- Grantor house ID
- Proxy holder name
- Proxy holder villa
- Proxy holder user ID
- Election scope
- Status: active, cancelled, expired
- Evidence/notes, if required

Proxy behavior:

- When the proxy holder attends, their own villa is represented.
- Any active proxy villas assigned to them also become represented.
- The proxy holder must cast votes separately for each represented villa.
- A proxy vote is recorded against the grantor villa, not the proxy holder villa.

### Defaulter

Defaulters are villas or residents with restricted eligibility depending on election policy.

At election level, the officer chooses:

- Whether defaulters count toward quorum.
- Whether defaulters are allowed to vote.

Defaulter records should support:

- House ID
- Villa
- Reason
- Effective date
- Cleared date
- Status

## Current Attendance Flow

The current implementation supports physical attendance with MyGate QR codes.

Flow:

1. Election officer opens the attendance app.
2. Voter opens MyGate app.
3. Voter taps profile icon.
4. Voter opens QR code next to MyGate ID.
5. Election officer scans QR code.
6. App extracts passcode.
7. Backend looks up resident in Resident Master.
8. Backend verifies `User Type` contains `Owner`.
9. Backend writes attendance row.
10. Backend adds all owner-type residents for the same house ID into the Voting Group tab.

Current data sources:

- Resident Master: Google Sheet
- Attendance: Google Sheet
- Voting Group: Google Sheet

## Target Voting Flow

1. Election officer creates elections.
2. Election officer creates questions and choices.
3. Election officer configures quorum, defaulter policy, and passing rules.
4. Election officer manages proxies and defaulters.
5. Attendance starts.
6. Physical attendees are scanned by election officer.
7. Manual attendees may be added by villa/name.
8. Quorum is calculated at villa level.
9. Once quorum is reached and discussion is complete, election officer opens voting.
10. Voter logs in using MyGate QR scan/upload.
11. Voter sees active elections and represented villas.
12. Voter submits a ballot for their own villa.
13. Voter submits separate ballots for proxy villas, if any.
14. Voting closes at configured time or by officer action.
15. Public results show aggregate counts only.
16. Detailed ballot records remain archived for future audit.

## Result Rules

Each question can have its own passing threshold.

Examples:

- Simple majority: choice passes if it receives more votes than alternatives.
- Two-thirds majority: choice passes only if it reaches at least `66.6%`.
- Custom threshold: officer-defined percentage.

During voting:

- Voters can see how many villas have attended.
- Voters can see how many villas have voted.
- Voters cannot see question-level vote details before voting closes.

After voting closes:

- Voters can see election-level attendance count.
- Voters can see election-level vote count.
- Voters can see final aggregate results per question.
- Voter-level ballot details are not shown publicly.

## Recommended Architecture

Keep Google Sheets as the source for Resident Master for now. Move election state, attendance sessions, proxies, defaulters, ballots, and audit records into Postgres.

Suggested components:

- Frontend: current static web app, expanded into officer and voter views.
- Backend API: Render Web Service.
- Database: Render Postgres.
- Resident source: Google Sheet synced or read through backend.
- QR parsing: browser QR scanner plus backend validation.
- Audit/archive: Postgres immutable ballot and event records.

Why Postgres for the election system:

- Multiple concurrent elections need reliable state.
- Ballots need uniqueness constraints.
- Proxy relationships need clean validation.
- Defaulter policy needs per-election logic.
- Results and audit records should not depend on fragile spreadsheet formulas.
- Officer actions need an auditable event log.

## High-Level Data Model

Core tables:

- `residents`
- `villas`
- `elections`
- `election_questions`
- `election_choices`
- `election_sessions`
- `attendance_records`
- `villa_representations`
- `proxies`
- `defaulters`
- `ballots`
- `ballot_answers`
- `audit_events`

Important constraints:

- One villa representation per election per represented villa.
- One ballot per election per represented villa.
- One answer per question per ballot.
- Only owner-type residents can attend/vote.
- Proxy holder can submit for grantor villa only when active proxy exists.

## Open Decisions

These should be finalized before implementation:

- How election officers authenticate.
- Whether voters can self-mark virtual attendance.
- Whether attendance can be backdated or edited.
- Whether proxy evidence must be uploaded.
- Whether defaulter list is villa-level, resident-level, or both.
- Whether a villa vote can be changed before voting close.
- Whether all owners of a villa can view a submitted vote before voting closes.
- Whether archived ballot details should be exportable as CSV/PDF.
