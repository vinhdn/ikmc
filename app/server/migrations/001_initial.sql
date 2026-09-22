PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exam_sources (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  year INTEGER,
  language TEXT NOT NULL CHECK (language IN ('en', 'vi', 'bilingual')),
  kind TEXT NOT NULL CHECK (kind IN ('official', 'collection', 'practice')),
  source_pdf_url TEXT NOT NULL,
  page_count INTEGER NOT NULL CHECK (page_count > 0),
  question_count INTEGER NOT NULL CHECK (question_count >= 0),
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'reviewed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
  id TEXT PRIMARY KEY,
  canonical_hash TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES exam_sources(id) ON DELETE RESTRICT,
  source_question_number INTEGER NOT NULL,
  source_page INTEGER NOT NULL,
  year INTEGER,
  section TEXT NOT NULL CHECK (section IN ('A', 'B', 'C')),
  points INTEGER NOT NULL CHECK (points IN (3, 4, 5)),
  topic TEXT NOT NULL CHECK (topic IN ('arithmetic', 'spatial', 'measurement', 'logic')),
  stem TEXT NOT NULL,
  stem_vi TEXT,
  image_url TEXT,
  correct_option TEXT CHECK (correct_option IN ('A', 'B', 'C', 'D', 'E')),
  explanation_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'needs_review' CHECK (status IN ('needs_review', 'published', 'archived')),
  answer_verified INTEGER NOT NULL DEFAULT 0 CHECK (answer_verified IN (0, 1)),
  answer_source TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (source_id, source_question_number)
);

CREATE INDEX IF NOT EXISTS idx_questions_publish_pool
  ON questions(status, answer_verified, points, topic);
CREATE INDEX IF NOT EXISTS idx_questions_source
  ON questions(source_id, source_question_number);
CREATE INDEX IF NOT EXISTS idx_questions_hash ON questions(canonical_hash);

CREATE TABLE IF NOT EXISTS question_options (
  question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  option_key TEXT NOT NULL CHECK (option_key IN ('A', 'B', 'C', 'D', 'E')),
  option_text TEXT,
  image_url TEXT,
  sort_order INTEGER NOT NULL CHECK (sort_order BETWEEN 1 AND 5),
  PRIMARY KEY (question_id, option_key),
  UNIQUE (question_id, sort_order)
);

-- Một câu có thể xuất hiện trong nhiều tài liệu; bảng này giữ đầy đủ provenance
-- mà không nhân bản câu canonical trong pool thi.
CREATE TABLE IF NOT EXISTS question_provenance (
  question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES exam_sources(id) ON DELETE CASCADE,
  source_question_number INTEGER,
  source_page INTEGER,
  raw_text TEXT,
  PRIMARY KEY (question_id, source_id, source_question_number)
);

CREATE TABLE IF NOT EXISTS attempts (
  id TEXT PRIMARY KEY,
  mode TEXT NOT NULL CHECK (mode IN ('exam', 'practice')),
  status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'submitted', 'expired')),
  base_score REAL NOT NULL DEFAULT 24,
  total_score REAL,
  correct_count INTEGER,
  wrong_count INTEGER,
  skipped_count INTEGER,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT,
  submitted_at TEXT,
  client_token_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_attempts_status ON attempts(status, started_at);

CREATE TABLE IF NOT EXISTS attempt_questions (
  attempt_id TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
  position INTEGER NOT NULL,
  selected_option TEXT CHECK (selected_option IN ('A', 'B', 'C', 'D', 'E')),
  is_correct INTEGER CHECK (is_correct IN (0, 1)),
  score_delta REAL,
  answered_at TEXT,
  PRIMARY KEY (attempt_id, question_id),
  UNIQUE (attempt_id, position)
);

CREATE TABLE IF NOT EXISTS practice_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
  selected_option TEXT NOT NULL CHECK (selected_option IN ('A', 'B', 'C', 'D', 'E')),
  is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);
