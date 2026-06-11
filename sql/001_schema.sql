CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type text NOT NULL CHECK (type IN ('rss', 'website', 'api', 'manual')),
  name text NOT NULL,
  url text NOT NULL UNIQUE,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NOT NULL REFERENCES sources(id),
  external_id text,
  url text NOT NULL,
  title text NOT NULL,
  author text,
  published_at timestamptz,
  raw_content text NOT NULL DEFAULT '',
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  content_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id),
  UNIQUE (source_id, url)
);

CREATE TABLE IF NOT EXISTS dedupe_groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  representative_item_id uuid,
  reason text NOT NULL CHECK (reason IN ('canonical_url', 'content_hash', 'simhash', 'semantic')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_item_id uuid NOT NULL UNIQUE REFERENCES raw_items(id),
  canonical_url text NOT NULL,
  title text NOT NULL,
  content text NOT NULL DEFAULT '',
  summary text,
  language text,
  normalized_hash text NOT NULL,
  dedupe_group_id uuid REFERENCES dedupe_groups(id),
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'analyzing', 'ready', 'pushed', 'archived', 'ignored')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (canonical_url)
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'dedupe_groups_representative_item_fk'
  ) THEN
    ALTER TABLE dedupe_groups
      ADD CONSTRAINT dedupe_groups_representative_item_fk
      FOREIGN KEY (representative_item_id) REFERENCES items(id)
      DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS analysis_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id uuid NOT NULL REFERENCES items(id),
  model_name text NOT NULL,
  summary text NOT NULL,
  topics jsonb NOT NULL DEFAULT '[]'::jsonb,
  tags jsonb NOT NULL DEFAULT '[]'::jsonb,
  importance_score numeric(4, 3) NOT NULL,
  novelty_score numeric(4, 3) NOT NULL,
  recommended_action text NOT NULL,
  reason text NOT NULL,
  raw_output jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type text NOT NULL CHECK (type IN ('ingest', 'normalize', 'dedupe', 'analyze', 'push', 'push_digest', 'export_obsidian')),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
  run_after timestamptz NOT NULL DEFAULT now(),
  attempts integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 3,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS jobs_pending_idx ON jobs (status, run_after, created_at);

CREATE TABLE IF NOT EXISTS push_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id uuid NOT NULL REFERENCES items(id),
  channel text NOT NULL DEFAULT 'feishu',
  recipient text,
  message_id text,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
  sent_at timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id uuid NOT NULL REFERENCES items(id),
  push_event_id uuid REFERENCES push_events(id),
  user_id text,
  action text NOT NULL CHECK (action IN ('useful', 'not_useful', 'read_later', 'save_obsidian', 'wrong_tag')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id uuid NOT NULL UNIQUE REFERENCES items(id),
  path text NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'written', 'failed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO jobs (type, payload)
VALUES ('ingest', '{}'::jsonb)
ON CONFLICT DO NOTHING;
