CREATE TABLE IF NOT EXISTS publications (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  client_label TEXT NOT NULL DEFAULT '',
  model_json TEXT NOT NULL,
  access_salt TEXT NOT NULL,
  access_hash TEXT NOT NULL,
  access_iterations INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  published_at TEXT
);

CREATE TABLE IF NOT EXISTS publication_files (
  id TEXT PRIMARY KEY,
  publication_id TEXT NOT NULL,
  name TEXT NOT NULL,
  extension TEXT NOT NULL DEFAULT '',
  size_bytes INTEGER NOT NULL DEFAULT 0,
  object_key TEXT NOT NULL UNIQUE,
  content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  sort_order INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portal_events (
  id TEXT PRIMARY KEY,
  publication_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  file_id TEXT,
  file_name TEXT,
  visitor_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_publication_files_publication ON publication_files(publication_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_portal_events_publication ON portal_events(publication_id, occurred_at);
