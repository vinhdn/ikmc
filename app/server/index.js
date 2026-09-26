import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import Database from 'better-sqlite3';
import express from 'express';
import { rateLimit } from 'express-rate-limit';
import helmet from 'helmet';
import { z } from 'zod';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OPTION_KEYS = ['A', 'B', 'C', 'D', 'E'];
const EXAM_SECONDS = 75 * 60;
const BASE_SCORE = 24;
const TEMPLATE_COUNT = 10;
const SESSION_DAYS = 30;

const answerMapSchema = z.record(z.string().min(1).max(100), z.enum(OPTION_KEYS));
const examSchema = z.object({
  year: z.number().int().min(2000).max(2100).optional(),
  templateId: z.string().min(1).max(100).optional(),
}).strict().refine((value) => !(value.year && value.templateId), {
  message: 'Chỉ được chọn một trong hai: năm đề hoặc đề dựng sẵn.',
});
const practiceCheckSchema = z.object({
  questionId: z.string().min(1).max(100),
  selectedOption: z.enum(OPTION_KEYS),
}).strict();
const usernameSchema = z.string().trim().toLowerCase().min(3).max(40).regex(/^[a-z0-9_.]+$/);
const passwordSchema = z.string().min(6).max(200);
const registerSchema = z.object({
  username: usernameSchema,
  password: passwordSchema,
  displayName: z.string().trim().min(1).max(80).optional(),
}).strict();
const loginSchema = z.object({
  username: usernameSchema,
  password: passwordSchema,
}).strict();

function parseJson(value, fallback = []) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function tokenHash(token) {
  return crypto.createHash('sha256').update(token).digest('hex');
}

function apiError(status, code, message) {
  const error = new Error(message);
  error.status = status;
  error.code = code;
  return error;
}

function hashPassword(password) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(password, salt, 64).toString('hex');
  return { hash, salt };
}

function verifyPassword(password, salt, expectedHash) {
  const candidate = crypto.scryptSync(password, salt, 64);
  const expected = Buffer.from(expectedHash, 'hex');
  return candidate.length === expected.length && crypto.timingSafeEqual(candidate, expected);
}

function publicUser(row) {
  return { id: row.id, username: row.username, displayName: row.display_name };
}

function createSession(db, userId) {
  const token = crypto.randomBytes(32).toString('base64url');
  const expiresAt = new Date(Date.now() + SESSION_DAYS * 24 * 60 * 60 * 1000).toISOString();
  db.prepare('INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)').run(tokenHash(token), userId, expiresAt);
  return { token, expiresAt };
}

function currentUser(db, request) {
  const header = request.get('authorization') ?? '';
  const match = /^Bearer\s+(.+)$/i.exec(header);
  if (!match) return null;
  const session = db.prepare('SELECT * FROM sessions WHERE token_hash=?').get(tokenHash(match[1]));
  if (!session || Date.parse(session.expires_at) < Date.now()) return null;
  const user = db.prepare('SELECT * FROM users WHERE id=?').get(session.user_id);
  return user ?? null;
}

function requireUser(db, request) {
  const user = currentUser(db, request);
  if (!user) throw apiError(401, 'AUTH_REQUIRED', 'Vui lòng đăng nhập.');
  return user;
}

function mulberry32(seed) {
  let state = seed >>> 0;
  return () => {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seededShuffle(items, seed) {
  const random = mulberry32(seed);
  const result = [...items];
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

function seedExamTemplates(db) {
  const existing = db.prepare('SELECT COUNT(*) AS count FROM exam_templates').get().count;
  if (existing >= TEMPLATE_COUNT) return;
  const pools = [3, 4, 5].map((points) => db.prepare(`
    SELECT id FROM questions WHERE status='published' AND answer_verified=1 AND points=?
    ORDER BY id
  `).all(points).map((row) => row.id));
  if (pools.some((pool) => pool.length < 8)) return;

  const insertTemplate = db.prepare(`
    INSERT INTO exam_templates(id, slug, title, position) VALUES (?, ?, ?, ?)
    ON CONFLICT(id) DO NOTHING
  `);
  const insertQuestion = db.prepare(`
    INSERT INTO exam_template_questions(template_id, question_id, position) VALUES (?, ?, ?)
    ON CONFLICT(template_id, position) DO NOTHING
  `);

  db.transaction(() => {
    for (let index = 0; index < TEMPLATE_COUNT; index += 1) {
      const templateId = `tpl-${String(index + 1).padStart(2, '0')}`;
      insertTemplate.run(templateId, `de-${index + 1}`, `Đề luyện tập số ${index + 1}`, index + 1);
      const sections = pools.map((pool) => {
        const shuffled = seededShuffle(pool, 1000 + index * 7 + pool.length);
        const start = (index * 8) % shuffled.length;
        const wrapped = [...shuffled.slice(start), ...shuffled.slice(0, start)];
        return wrapped.slice(0, 8);
      });
      const ordered = sections.flat();
      ordered.forEach((questionId, position) => insertQuestion.run(templateId, questionId, position + 1));
    }
  })();
}

export function initDatabase(dbPath, { seed = true } = {}) {
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  const db = new Database(dbPath);
  db.pragma('foreign_keys = ON');
  db.pragma('journal_mode = WAL');
  db.pragma('synchronous = NORMAL');
  db.pragma('busy_timeout = 5000');

  const migrationsDir = path.join(__dirname, 'migrations');
  const files = fs.readdirSync(migrationsDir).filter((name) => name.endsWith('.sql')).sort();
  let applied = new Set();
  try {
    applied = new Set(db.prepare('SELECT version FROM schema_migrations').all().map((row) => row.version));
  } catch {
    // schema_migrations chưa tồn tại ở lần khởi tạo đầu tiên; migration 001 sẽ tạo bảng này.
  }
  for (const file of files) {
    const version = Number.parseInt(file, 10);
    if (applied.has(version)) continue;
    db.exec(fs.readFileSync(path.join(migrationsDir, file), 'utf8'));
  }
  if (seed) seedDatabase(db);
  return db;
}

export function seedDatabase(db) {
  const payload = JSON.parse(fs.readFileSync(path.join(__dirname, 'data/questions.seed.json'), 'utf8'));
  const sourceStmt = db.prepare(`
    INSERT INTO exam_sources
      (id, slug, title, year, language, kind, source_pdf_url, page_count, question_count, review_status)
    VALUES
      (@id, @slug, @title, @year, @language, @kind, @source_pdf_url, @page_count, @question_count, @review_status)
    ON CONFLICT(id) DO UPDATE SET
      slug=excluded.slug, title=excluded.title, year=excluded.year, language=excluded.language,
      kind=excluded.kind, source_pdf_url=excluded.source_pdf_url, page_count=excluded.page_count,
      question_count=excluded.question_count, review_status=excluded.review_status,
      updated_at=CURRENT_TIMESTAMP
  `);
  const questionStmt = db.prepare(`
    INSERT INTO questions
      (id, canonical_hash, source_id, source_question_number, source_page, year, section, points,
       topic, stem, stem_vi, image_url, correct_option, explanation_json, status,
       answer_verified, answer_source)
    VALUES
      (@id, @canonical_hash, @source_id, @source_question_number, @source_page, @year, @section,
       @points, @topic, @stem, @stem_vi, @image_url, @correct_option, @explanation_json,
       @status, @answer_verified, @answer_source)
    ON CONFLICT(id) DO UPDATE SET
      canonical_hash=excluded.canonical_hash, source_id=excluded.source_id,
      source_question_number=excluded.source_question_number, source_page=excluded.source_page,
      year=excluded.year, section=excluded.section, points=excluded.points, topic=excluded.topic,
      stem=excluded.stem, stem_vi=excluded.stem_vi, image_url=excluded.image_url,
      correct_option=excluded.correct_option, explanation_json=excluded.explanation_json,
      status=excluded.status, answer_verified=excluded.answer_verified,
      answer_source=excluded.answer_source, updated_at=CURRENT_TIMESTAMP
  `);
  const optionStmt = db.prepare(`
    INSERT INTO question_options (question_id, option_key, option_text, image_url, sort_order)
    VALUES (@question_id, @key, @text, @image_url, @sort_order)
    ON CONFLICT(question_id, option_key) DO UPDATE SET
      option_text=excluded.option_text, image_url=excluded.image_url, sort_order=excluded.sort_order
  `);
  const provenanceStmt = db.prepare(`
    INSERT INTO question_provenance
      (question_id, source_id, source_question_number, source_page, raw_text)
    VALUES
      (@question_id, @source_id, @source_question_number, @source_page, @raw_text)
    ON CONFLICT(question_id, source_id, source_question_number) DO UPDATE SET
      source_page=excluded.source_page, raw_text=excluded.raw_text
  `);

  db.transaction(() => {
    for (const source of payload.sources) sourceStmt.run(source);
    for (const question of payload.questions) {
      questionStmt.run({
        ...question,
        explanation_json: JSON.stringify(question.explanation ?? []),
        answer_verified: question.answer_verified ? 1 : 0,
      });
      for (const option of question.options) optionStmt.run({ ...option, question_id: question.id });
    }
    for (const row of payload.provenance) provenanceStmt.run(row);
  })();
  seedExamTemplates(db);
  return payload.summary;
}

function publicQuestion(db, id) {
  const row = db.prepare(`
    SELECT q.id, q.year, q.source_question_number, q.source_page, q.section, q.points, q.topic,
           q.stem, q.stem_vi, q.image_url, s.title AS source_title,
           s.source_pdf_url
    FROM questions q JOIN exam_sources s ON s.id=q.source_id
    WHERE q.id=? AND q.status='published' AND q.answer_verified=1
  `).get(id);
  if (!row) return null;
  const options = db.prepare(`
    SELECT option_key AS key, option_text AS text, image_url
    FROM question_options WHERE question_id=? ORDER BY sort_order
  `).all(id);
  return {
    id: row.id,
    year: row.year,
    sourceQuestionNumber: row.source_question_number,
    sourcePage: row.source_page,
    sourceTitle: row.source_title,
    sourcePdfUrl: row.source_pdf_url,
    section: row.section,
    points: row.points,
    topic: row.topic,
    stem: row.stem,
    stemVi: row.stem_vi,
    imageUrl: row.image_url,
    options,
  };
}

function requireAttempt(db, request) {
  const attempt = db.prepare('SELECT * FROM attempts WHERE id=?').get(request.params.id);
  if (!attempt) throw apiError(404, 'ATTEMPT_NOT_FOUND', 'Không tìm thấy lượt làm bài.');
  const token = request.get('x-attempt-token') ?? '';
  const provided = Buffer.from(tokenHash(token), 'hex');
  const expected = Buffer.from(attempt.client_token_hash ?? '', 'hex');
  if (provided.length !== expected.length || !crypto.timingSafeEqual(provided, expected)) {
    throw apiError(403, 'INVALID_ATTEMPT_TOKEN', 'Token lượt làm bài không hợp lệ.');
  }
  return attempt;
}

function saveAnswers(db, attempt, answers, replace = false) {
  if (attempt.status !== 'in_progress') {
    throw apiError(409, 'ATTEMPT_CLOSED', 'Lượt làm bài đã kết thúc.');
  }
  if (attempt.expires_at && Date.now() > Date.parse(attempt.expires_at)) {
    throw apiError(409, 'ATTEMPT_EXPIRED', 'Lượt làm bài đã hết thời gian.');
  }
  const update = db.prepare(`
    UPDATE attempt_questions
    SET selected_option=?, answered_at=CURRENT_TIMESTAMP
    WHERE attempt_id=? AND question_id=?
  `);
  db.transaction(() => {
    if (replace) {
      db.prepare('UPDATE attempt_questions SET selected_option=NULL, answered_at=NULL WHERE attempt_id=?').run(attempt.id);
    }
    for (const [questionId, option] of Object.entries(answers)) {
      const result = update.run(option, attempt.id, questionId);
      if (result.changes !== 1) throw apiError(400, 'QUESTION_NOT_IN_ATTEMPT', `Câu ${questionId} không thuộc lượt thi.`);
    }
  })();
}

function attemptResult(db, attemptId) {
  const attempt = db.prepare('SELECT * FROM attempts WHERE id=?').get(attemptId);
  const rows = db.prepare(`
    SELECT aq.position, aq.selected_option, aq.is_correct, aq.score_delta,
           q.id, q.correct_option, q.points, q.explanation_json
    FROM attempt_questions aq JOIN questions q ON q.id=aq.question_id
    WHERE aq.attempt_id=? ORDER BY aq.position
  `).all(attemptId);
  return {
    attemptId,
    status: attempt.status,
    totalScore: attempt.total_score,
    maxScore: BASE_SCORE + rows.reduce((sum, row) => sum + row.points, 0),
    baseScore: attempt.base_score,
    correctCount: attempt.correct_count,
    wrongCount: attempt.wrong_count,
    skippedCount: attempt.skipped_count,
    review: rows.map((row) => ({
      questionId: row.id,
      selectedOption: row.selected_option,
      correctOption: row.correct_option,
      isCorrect: row.is_correct === null ? null : Boolean(row.is_correct),
      scoreDelta: row.score_delta,
      explanation: parseJson(row.explanation_json),
    })),
  };
}

export function createApp(db) {
  const app = express();
  app.set('trust proxy', 1);
  app.disable('x-powered-by');
  app.use(helmet({ contentSecurityPolicy: false }));
  app.use(express.json({ limit: '64kb' }));
  app.use('/api', rateLimit({ windowMs: 60_000, limit: 300, standardHeaders: 'draft-8', legacyHeaders: false }));

  app.get('/healthz', (_request, response) => {
    const row = db.prepare("SELECT COUNT(*) AS count FROM questions WHERE status='published' AND answer_verified=1").get();
    response.json({ status: 'ok', database: 'ok', publishedQuestions: row.count });
  });

  app.get('/api/v1/meta', (_request, response) => {
    const counts = db.prepare(`
      SELECT COUNT(*) AS canonical_questions,
             SUM(CASE WHEN status='published' AND answer_verified=1 THEN 1 ELSE 0 END) AS published_questions,
             SUM(CASE WHEN status='needs_review' THEN 1 ELSE 0 END) AS needs_review
      FROM questions
    `).get();
    const topics = db.prepare(`
      SELECT topic, COUNT(*) AS count FROM questions
      WHERE status='published' AND answer_verified=1 GROUP BY topic ORDER BY topic
    `).all();
    const years = db.prepare(`
      SELECT year, COUNT(*) AS count FROM questions
      WHERE status='published' AND answer_verified=1 GROUP BY year ORDER BY year DESC
    `).all();
    const provenance = db.prepare('SELECT COUNT(*) AS count FROM question_provenance').get().count;
    response.json({ ...counts, provenanceRecords: provenance, topics, years });
  });

  app.get('/api/v1/sources', (_request, response) => {
    const items = db.prepare(`
      SELECT s.id, s.title, s.year, s.language, s.kind, s.source_pdf_url AS sourcePdfUrl,
             s.review_status AS reviewStatus, COUNT(q.id) AS publishedQuestions
      FROM exam_sources s LEFT JOIN questions q
        ON q.source_id=s.id AND q.status='published' AND q.answer_verified=1
      GROUP BY s.id ORDER BY s.year DESC, s.title
    `).all();
    response.json({ items });
  });

  app.get('/api/v1/practice/questions', (request, response) => {
    const topic = typeof request.query.topic === 'string' ? request.query.topic : 'all';
    const year = request.query.year ? Number(request.query.year) : null;
    const limit = Math.min(50, Math.max(1, Number(request.query.limit) || 20));
    if (topic !== 'all' && !['arithmetic', 'spatial', 'measurement', 'logic'].includes(topic)) {
      throw apiError(400, 'INVALID_TOPIC', 'Chủ đề không hợp lệ.');
    }
    if (year !== null && (!Number.isInteger(year) || year < 2000 || year > 2100)) {
      throw apiError(400, 'INVALID_YEAR', 'Năm đề không hợp lệ.');
    }
    const conditions = ["status='published'", 'answer_verified=1'];
    const params = [];
    if (topic !== 'all') { conditions.push('topic=?'); params.push(topic); }
    if (year !== null) { conditions.push('year=?'); params.push(year); }
    params.push(limit);
    const ids = db.prepare(`SELECT id FROM questions WHERE ${conditions.join(' AND ')} ORDER BY RANDOM() LIMIT ?`).all(...params);
    response.json({ items: ids.map(({ id }) => publicQuestion(db, id)) });
  });

  app.post('/api/v1/practice/check', rateLimit({ windowMs: 60_000, limit: 90 }), (request, response) => {
    const input = practiceCheckSchema.parse(request.body);
    const row = db.prepare(`
      SELECT correct_option, explanation_json FROM questions
      WHERE id=? AND status='published' AND answer_verified=1
    `).get(input.questionId);
    if (!row) throw apiError(404, 'QUESTION_NOT_FOUND', 'Không tìm thấy câu hỏi đã xuất bản.');
    const isCorrect = input.selectedOption === row.correct_option;
    db.prepare('INSERT INTO practice_events(question_id, selected_option, is_correct) VALUES (?, ?, ?)')
      .run(input.questionId, input.selectedOption, isCorrect ? 1 : 0);
    response.json({
      questionId: input.questionId,
      selectedOption: input.selectedOption,
      correctOption: row.correct_option,
      isCorrect,
      explanation: parseJson(row.explanation_json),
    });
  });

  app.get('/api/v1/exam-templates', (_request, response) => {
    const items = db.prepare('SELECT id, title, position FROM exam_templates ORDER BY position').all();
    response.json({ items });
  });

  app.post('/api/v1/auth/register', rateLimit({ windowMs: 60_000, limit: 10 }), (request, response) => {
    const input = registerSchema.parse(request.body ?? {});
    const existing = db.prepare('SELECT id FROM users WHERE username=?').get(input.username);
    if (existing) throw apiError(409, 'USERNAME_TAKEN', 'Tên đăng nhập đã được sử dụng.');
    const { hash, salt } = hashPassword(input.password);
    const userId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO users(id, username, display_name, password_hash, password_salt)
      VALUES (?, ?, ?, ?, ?)
    `).run(userId, input.username, input.displayName || input.username, hash, salt);
    const session = createSession(db, userId);
    response.status(201).json({ token: session.token, expiresAt: session.expiresAt, user: publicUser({ id: userId, username: input.username, display_name: input.displayName || input.username }) });
  });

  app.post('/api/v1/auth/login', rateLimit({ windowMs: 60_000, limit: 20 }), (request, response) => {
    const input = loginSchema.parse(request.body ?? {});
    const user = db.prepare('SELECT * FROM users WHERE username=?').get(input.username);
    if (!user || !verifyPassword(input.password, user.password_salt, user.password_hash)) {
      throw apiError(401, 'INVALID_CREDENTIALS', 'Tên đăng nhập hoặc mật khẩu không đúng.');
    }
    const session = createSession(db, user.id);
    response.json({ token: session.token, expiresAt: session.expiresAt, user: publicUser(user) });
  });

  app.post('/api/v1/auth/logout', (request, response) => {
    const header = request.get('authorization') ?? '';
    const match = /^Bearer\s+(.+)$/i.exec(header);
    if (match) db.prepare('DELETE FROM sessions WHERE token_hash=?').run(tokenHash(match[1]));
    response.status(204).end();
  });

  app.get('/api/v1/auth/me', (request, response) => {
    const user = requireUser(db, request);
    response.json({ user: publicUser(user) });
  });

  app.get('/api/v1/me/attempts', (request, response) => {
    const user = requireUser(db, request);
    const rows = db.prepare(`
      SELECT a.id AS attemptId, a.mode, a.status, a.total_score AS totalScore, a.base_score AS baseScore,
             a.correct_count AS correctCount, a.wrong_count AS wrongCount, a.skipped_count AS skippedCount,
             a.started_at AS startedAt, a.expires_at AS expiresAt, a.submitted_at AS submittedAt,
             t.title AS templateTitle,
             (SELECT COUNT(*) FROM attempt_questions aq WHERE aq.attempt_id = a.id) AS questionCount,
             (SELECT SUM(q.points) FROM attempt_questions aq JOIN questions q ON q.id = aq.question_id WHERE aq.attempt_id = a.id) AS pointsSum
      FROM attempts a LEFT JOIN exam_templates t ON t.id = a.exam_template_id
      WHERE a.user_id = ? AND a.mode = 'exam'
      ORDER BY a.started_at DESC
      LIMIT 100
    `).all(user.id);
    response.json({
      items: rows.map((row) => ({
        ...row,
        maxScore: row.pointsSum ? BASE_SCORE + row.pointsSum : null,
        pointsSum: undefined,
      })),
    });
  });

  app.post('/api/v1/exams', rateLimit({ windowMs: 60_000, limit: 20 }), (request, response) => {
    const input = examSchema.parse(request.body ?? {});
    const user = currentUser(db, request);
    let ids;
    let templateId = null;
    if (input.templateId) {
      const template = db.prepare('SELECT id FROM exam_templates WHERE id=?').get(input.templateId);
      if (!template) throw apiError(404, 'TEMPLATE_NOT_FOUND', 'Không tìm thấy đề dựng sẵn.');
      templateId = template.id;
      ids = db.prepare(`
        SELECT question_id AS id FROM exam_template_questions WHERE template_id=? ORDER BY position
      `).all(templateId);
    } else if (input.year) {
      ids = db.prepare(`
        SELECT id FROM questions WHERE status='published' AND answer_verified=1 AND year=?
        ORDER BY source_question_number
      `).all(input.year);
      if (ids.length === 0) throw apiError(404, 'YEAR_NOT_FOUND', 'Không có đề đã kiểm duyệt cho năm này.');
    } else {
      ids = [3, 4, 5].flatMap((points) => db.prepare(`
        SELECT id FROM questions WHERE status='published' AND answer_verified=1 AND points=?
        ORDER BY RANDOM() LIMIT 8
      `).all(points));
      if (ids.length !== 24) throw apiError(503, 'QUESTION_POOL_INCOMPLETE', 'Ngân hàng câu hỏi chưa đủ để tạo đề 24 câu.');
    }
    const attemptId = crypto.randomUUID();
    const token = crypto.randomBytes(32).toString('base64url');
    const expiresAt = new Date(Date.now() + EXAM_SECONDS * 1000).toISOString();
    db.transaction(() => {
      db.prepare(`
        INSERT INTO attempts(id, mode, status, base_score, expires_at, client_token_hash, user_id, exam_template_id)
        VALUES (?, 'exam', 'in_progress', ?, ?, ?, ?, ?)
      `).run(attemptId, BASE_SCORE, expiresAt, tokenHash(token), user?.id ?? null, templateId);
      const insert = db.prepare('INSERT INTO attempt_questions(attempt_id, question_id, position) VALUES (?, ?, ?)');
      ids.forEach(({ id }, index) => insert.run(attemptId, id, index + 1));
    })();
    const questions = ids.map(({ id }) => publicQuestion(db, id));
    response.status(201).json({
      attemptId,
      attemptToken: token,
      expiresAt,
      durationSeconds: EXAM_SECONDS,
      baseScore: BASE_SCORE,
      maxScore: BASE_SCORE + questions.reduce((sum, question) => sum + question.points, 0),
      questions,
    });
  });

  app.get('/api/v1/attempts/:id', (request, response) => {
    const attempt = requireAttempt(db, request);
    const rows = db.prepare(`
      SELECT question_id AS id, position, selected_option AS selectedOption
      FROM attempt_questions WHERE attempt_id=? ORDER BY position
    `).all(attempt.id);
    if (attempt.status !== 'in_progress') return response.json(attemptResult(db, attempt.id));
    response.json({
      attemptId: attempt.id,
      status: attempt.status,
      expiresAt: attempt.expires_at,
      questions: rows.map((row) => ({ ...publicQuestion(db, row.id), selectedOption: row.selectedOption })),
    });
  });

  app.put('/api/v1/attempts/:id/answers', rateLimit({ windowMs: 60_000, limit: 120 }), (request, response) => {
    const attempt = requireAttempt(db, request);
    const answers = answerMapSchema.parse(request.body?.answers ?? {});
    saveAnswers(db, attempt, answers, true);
    response.json({ saved: Object.keys(answers).length });
  });

  app.post('/api/v1/attempts/:id/resume-token', rateLimit({ windowMs: 60_000, limit: 20 }), (request, response) => {
    const user = requireUser(db, request);
    const attempt = db.prepare('SELECT * FROM attempts WHERE id=?').get(request.params.id);
    if (!attempt) throw apiError(404, 'ATTEMPT_NOT_FOUND', 'Không tìm thấy lượt làm bài.');
    if (attempt.user_id !== user.id) throw apiError(403, 'FORBIDDEN', 'Bạn không có quyền với lượt làm bài này.');
    if (attempt.status !== 'in_progress') throw apiError(409, 'ATTEMPT_CLOSED', 'Lượt làm bài đã kết thúc.');
    if (attempt.expires_at && Date.now() > Date.parse(attempt.expires_at)) {
      throw apiError(409, 'ATTEMPT_EXPIRED', 'Lượt làm bài đã hết thời gian.');
    }
    const token = crypto.randomBytes(32).toString('base64url');
    db.prepare('UPDATE attempts SET client_token_hash=? WHERE id=?').run(tokenHash(token), attempt.id);
    response.json({ attemptId: attempt.id, attemptToken: token, expiresAt: attempt.expires_at });
  });

  app.post('/api/v1/attempts/:id/submit', rateLimit({ windowMs: 60_000, limit: 20 }), (request, response) => {
    const attempt = requireAttempt(db, request);
    if (attempt.status !== 'in_progress') return response.json(attemptResult(db, attempt.id));
    const expired = attempt.expires_at && Date.now() > Date.parse(attempt.expires_at);
    if (!expired) {
      const answers = answerMapSchema.parse(request.body?.answers ?? {});
      saveAnswers(db, attempt, answers, true);
    }
    const rows = db.prepare(`
      SELECT aq.question_id, aq.selected_option, q.correct_option, q.points
      FROM attempt_questions aq JOIN questions q ON q.id=aq.question_id
      WHERE aq.attempt_id=? ORDER BY aq.position
    `).all(attempt.id);
    let score = BASE_SCORE;
    let correct = 0;
    let wrong = 0;
    let skipped = 0;
    const update = db.prepare(`
      UPDATE attempt_questions SET is_correct=?, score_delta=? WHERE attempt_id=? AND question_id=?
    `);
    db.transaction(() => {
      for (const row of rows) {
        let isCorrect = null;
        let delta = 0;
        if (!row.selected_option) {
          skipped += 1;
        } else if (row.selected_option === row.correct_option) {
          correct += 1;
          isCorrect = 1;
          delta = row.points;
        } else {
          wrong += 1;
          isCorrect = 0;
          delta = -(row.points * 0.25);
        }
        score += delta;
        update.run(isCorrect, delta, attempt.id, row.question_id);
      }
      db.prepare(`
        UPDATE attempts SET status=?, total_score=?, correct_count=?, wrong_count=?, skipped_count=?, submitted_at=CURRENT_TIMESTAMP
        WHERE id=?
      `).run(expired ? 'expired' : 'submitted', Math.max(0, score), correct, wrong, skipped, attempt.id);
    })();
    response.json(attemptResult(db, attempt.id));
  });

  app.use((request, _response, next) => next(apiError(404, 'NOT_FOUND', `Không tìm thấy ${request.method} ${request.path}`)));
  app.use((error, _request, response, _next) => {
    if (error instanceof z.ZodError) {
      return response.status(400).json({ error: { code: 'VALIDATION_ERROR', message: 'Dữ liệu không hợp lệ.', details: error.issues } });
    }
    const status = Number(error.status) || 500;
    if (status >= 500) console.error(error);
    response.status(status).json({ error: { code: error.code ?? 'INTERNAL_ERROR', message: status >= 500 ? 'Lỗi máy chủ.' : error.message } });
  });
  return app;
}

export function startServer() {
  const dbPath = process.env.DB_PATH ?? path.join(__dirname, 'data/ikmc.sqlite');
  const port = Number(process.env.PORT ?? 3000);
  const db = initDatabase(dbPath);
  const app = createApp(db);
  const server = app.listen(port, '0.0.0.0', () => console.log(`IKMC API listening on :${port}; database=${dbPath}`));
  const shutdown = () => server.close(() => { db.close(); process.exit(0); });
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
  return { app, db, server };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) startServer();
