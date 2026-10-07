-- Câu hỏi/đề do AI sinh ("AI generate"): tách khỏi ngân hàng đề chính thức.
ALTER TABLE questions ADD COLUMN origin TEXT NOT NULL DEFAULT 'official';
ALTER TABLE exam_templates ADD COLUMN tag TEXT;

CREATE INDEX IF NOT EXISTS idx_questions_origin_pool
  ON questions(origin, status, answer_verified, points);

INSERT OR IGNORE INTO schema_migrations(version) VALUES (3);
