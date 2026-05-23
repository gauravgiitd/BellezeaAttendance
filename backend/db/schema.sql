CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS villas (
  house_id text PRIMARY KEY,
  house_no text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS residents (
  user_id text PRIMARY KEY,
  house_id text NOT NULL REFERENCES villas(house_id),
  passcode text,
  name text NOT NULL,
  user_type text NOT NULL,
  status text NOT NULL,
  mobile_no text,
  email text,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_residents_house_id ON residents(house_id);
CREATE INDEX IF NOT EXISTS idx_residents_passcode ON residents(passcode);

CREATE TABLE IF NOT EXISTS resident_source_syncs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source text NOT NULL,
  row_count integer NOT NULL,
  synced_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS elections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'draft',
  quorum_percent numeric(6,3) NOT NULL DEFAULT 50.000,
  include_defaulters_in_quorum boolean NOT NULL DEFAULT false,
  allow_defaulters_to_vote boolean NOT NULL DEFAULT false,
  voting_opens_at timestamptz,
  voting_closes_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT elections_status_check CHECK (
    status IN ('draft', 'attendance_open', 'discussion', 'voting_open', 'voting_closed', 'results_published', 'archived')
  )
);

CREATE TABLE IF NOT EXISTS election_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  election_id uuid NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
  question_text text NOT NULL,
  image_url text,
  passing_rule text NOT NULL DEFAULT 'simple_majority',
  passing_threshold_percent numeric(6,3),
  display_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT election_questions_passing_rule_check CHECK (
    passing_rule IN ('simple_majority', 'two_thirds', 'custom_threshold')
  )
);

CREATE TABLE IF NOT EXISTS election_choices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  question_id uuid NOT NULL REFERENCES election_questions(id) ON DELETE CASCADE,
  choice_text text NOT NULL,
  image_url text,
  display_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS proxies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  election_id uuid REFERENCES elections(id) ON DELETE CASCADE,
  grantor_house_id text NOT NULL REFERENCES villas(house_id),
  proxy_holder_user_id text NOT NULL REFERENCES residents(user_id),
  status text NOT NULL DEFAULT 'active',
  notes text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT proxies_status_check CHECK (status IN ('active', 'cancelled', 'expired'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_active_proxy_per_grantor_election
  ON proxies(COALESCE(election_id, '00000000-0000-0000-0000-000000000000'::uuid), grantor_house_id)
  WHERE status = 'active';

CREATE TABLE IF NOT EXISTS defaulters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  house_id text NOT NULL REFERENCES villas(house_id),
  reason text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'active',
  effective_at timestamptz NOT NULL DEFAULT now(),
  cleared_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT defaulters_status_check CHECK (status IN ('active', 'cleared'))
);

CREATE TABLE IF NOT EXISTS attendance_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  election_id uuid NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
  resident_user_id text NOT NULL REFERENCES residents(user_id),
  house_id text NOT NULL REFERENCES villas(house_id),
  method text NOT NULL,
  source text NOT NULL DEFAULT 'officer',
  raw_qr_data text,
  attended_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT attendance_records_method_check CHECK (method IN ('qr_scan', 'qr_upload', 'manual'))
);

CREATE INDEX IF NOT EXISTS idx_attendance_records_election ON attendance_records(election_id);
CREATE INDEX IF NOT EXISTS idx_attendance_records_house ON attendance_records(election_id, house_id);

CREATE TABLE IF NOT EXISTS villa_representations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  election_id uuid NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
  house_id text NOT NULL REFERENCES villas(house_id),
  represented_by_user_id text NOT NULL REFERENCES residents(user_id),
  representation_type text NOT NULL DEFAULT 'self',
  source_attendance_record_id uuid REFERENCES attendance_records(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT villa_representations_type_check CHECK (representation_type IN ('self', 'proxy'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_villa_representation_unique
  ON villa_representations(election_id, house_id);

CREATE TABLE IF NOT EXISTS ballots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  election_id uuid NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
  house_id text NOT NULL REFERENCES villas(house_id),
  submitted_by_user_id text NOT NULL REFERENCES residents(user_id),
  submitted_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ballot_unique_per_villa
  ON ballots(election_id, house_id);

CREATE TABLE IF NOT EXISTS ballot_answers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ballot_id uuid NOT NULL REFERENCES ballots(id) ON DELETE CASCADE,
  question_id uuid NOT NULL REFERENCES election_questions(id) ON DELETE CASCADE,
  choice_id uuid NOT NULL REFERENCES election_choices(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ballot_answer_unique_question
  ON ballot_answers(ballot_id, question_id);

CREATE TABLE IF NOT EXISTS audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id text,
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
