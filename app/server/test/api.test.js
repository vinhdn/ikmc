import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { createApp, initDatabase } from '../index.js';

const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ikmc-api-'));
const dbPath = path.join(tempDir, 'test.sqlite');
let db;
let server;
let baseUrl;

before(async () => {
  db = initDatabase(dbPath);
  server = createApp(db).listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  await new Promise((resolve) => server.close(resolve));
  db.close();
  fs.rmSync(tempDir, { recursive: true, force: true });
});

test('seed imports canonical, published and provenance counts', () => {
  assert.equal(db.prepare('SELECT COUNT(*) count FROM questions').get().count, 436);
  assert.equal(db.prepare("SELECT COUNT(*) count FROM questions WHERE status='published' AND answer_verified=1").get().count, 216);
  assert.equal(db.prepare("SELECT COUNT(*) count FROM questions WHERE status='published' AND TRIM(COALESCE(stem_vi, ''))<>''").get().count, 216);
  assert.equal(db.prepare("SELECT COUNT(*) count FROM questions WHERE status='needs_review'").get().count, 220);
  assert.equal(db.prepare('SELECT COUNT(*) count FROM question_provenance').get().count, 556);
  assert.equal(db.prepare('SELECT COUNT(*) count FROM question_options').get().count, 2180);
});

test('public practice response never leaks correct answer', async () => {
  const response = await fetch(`${baseUrl}/api/v1/practice/questions?limit=5`);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.items.length, 5);
  for (const question of body.items) {
    assert.equal(Object.hasOwn(question, 'correctOption'), false);
    assert.equal(question.options.length, 5);
    assert.ok(question.imageUrl);
    assert.ok(question.stem);
    assert.ok(question.stemVi);
  }
});

test('practice check is scored by server', async () => {
  const question = db.prepare("SELECT id, correct_option FROM questions WHERE status='published' LIMIT 1").get();
  const response = await fetch(`${baseUrl}/api/v1/practice/check`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ questionId: question.id, selectedOption: question.correct_option }),
  });
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.isCorrect, true);
  assert.equal(body.correctOption, question.correct_option);
});

test('random exam has 24 questions, token protection and server scoring', async () => {
  const createResponse = await fetch(`${baseUrl}/api/v1/exams`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}',
  });
  assert.equal(createResponse.status, 201);
  const exam = await createResponse.json();
  assert.equal(exam.questions.length, 24);
  assert.equal(exam.maxScore, 120);
  assert.ok(exam.attemptToken);
  assert.ok(exam.questions.every((question) => !Object.hasOwn(question, 'correctOption')));

  const denied = await fetch(`${baseUrl}/api/v1/attempts/${exam.attemptId}/submit`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}',
  });
  assert.equal(denied.status, 403);

  const answers = Object.fromEntries(exam.questions.map((question) => {
    const answer = db.prepare('SELECT correct_option FROM questions WHERE id=?').get(question.id).correct_option;
    return [question.id, answer];
  }));
  const submit = await fetch(`${baseUrl}/api/v1/attempts/${exam.attemptId}/submit`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-attempt-token': exam.attemptToken },
    body: JSON.stringify({ answers }),
  });
  assert.equal(submit.status, 200);
  const result = await submit.json();
  assert.equal(result.status, 'submitted');
  assert.equal(result.totalScore, 120);
  assert.equal(result.correctCount, 24);
  assert.equal(result.wrongCount, 0);
  assert.equal(result.skippedCount, 0);
  assert.equal(result.review.length, 24);
});

test('official 18-question year remains a faithful source exam', async () => {
  const response = await fetch(`${baseUrl}/api/v1/exams`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ year: 2014 }),
  });
  assert.equal(response.status, 201);
  const exam = await response.json();
  assert.equal(exam.questions.length, 18);
  assert.equal(exam.maxScore, 96);
  assert.deepEqual(exam.questions.map((q) => q.sourceQuestionNumber), Array.from({ length: 18 }, (_, i) => i + 1));
});

test('10 pre-built exam templates are seeded with 24 questions each', () => {
  const templates = db.prepare('SELECT id FROM exam_templates ORDER BY position').all();
  assert.equal(templates.length, 10);
  for (const template of templates) {
    const count = db.prepare('SELECT COUNT(*) count FROM exam_template_questions WHERE template_id=?').get(template.id).count;
    assert.equal(count, 24);
  }
});

test('exam-templates endpoint lists all 10 templates', async () => {
  const response = await fetch(`${baseUrl}/api/v1/exam-templates`);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.items.length, 10);
  assert.equal(body.items[0].title, 'Đề luyện tập số 1');
});

test('starting an exam from a template returns its fixed 24 questions', async () => {
  const [template] = db.prepare('SELECT id FROM exam_templates ORDER BY position').all();
  const response = await fetch(`${baseUrl}/api/v1/exams`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ templateId: template.id }),
  });
  assert.equal(response.status, 201);
  const exam = await response.json();
  assert.equal(exam.questions.length, 24);
  const expectedIds = db.prepare('SELECT question_id FROM exam_template_questions WHERE template_id=? ORDER BY position').all(template.id).map((r) => r.question_id);
  assert.deepEqual(exam.questions.map((q) => q.id), expectedIds);
});

test('register, login, and me/attempts require and honor auth token', async () => {
  const username = `hs_lop2_${Date.now()}`;
  const register = await fetch(`${baseUrl}/api/v1/auth/register`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username, password: 'matkhau123', displayName: 'Bé Na' }),
  });
  assert.equal(register.status, 201);
  const registered = await register.json();
  assert.ok(registered.token);
  assert.equal(registered.user.displayName, 'Bé Na');

  const dupe = await fetch(`${baseUrl}/api/v1/auth/register`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username, password: 'matkhau123' }),
  });
  assert.equal(dupe.status, 409);

  const badLogin = await fetch(`${baseUrl}/api/v1/auth/login`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username, password: 'saimatkhau' }),
  });
  assert.equal(badLogin.status, 401);

  const login = await fetch(`${baseUrl}/api/v1/auth/login`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username, password: 'matkhau123' }),
  });
  assert.equal(login.status, 200);
  const { token } = await login.json();

  const unauthed = await fetch(`${baseUrl}/api/v1/me/attempts`);
  assert.equal(unauthed.status, 401);

  const examCreate = await fetch(`${baseUrl}/api/v1/exams`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
    body: '{}',
  });
  assert.equal(examCreate.status, 201);
  const exam = await examCreate.json();

  const history = await fetch(`${baseUrl}/api/v1/me/attempts`, { headers: { authorization: `Bearer ${token}` } });
  assert.equal(history.status, 200);
  const historyBody = await history.json();
  assert.equal(historyBody.items.length, 1);
  assert.equal(historyBody.items[0].attemptId, exam.attemptId);
  assert.equal(historyBody.items[0].status, 'in_progress');

  const logout = await fetch(`${baseUrl}/api/v1/auth/logout`, { method: 'POST', headers: { authorization: `Bearer ${token}` } });
  assert.equal(logout.status, 204);
  const afterLogout = await fetch(`${baseUrl}/api/v1/me/attempts`, { headers: { authorization: `Bearer ${token}` } });
  assert.equal(afterLogout.status, 401);
});

test('resuming an in-progress attempt after refresh returns saved answers and status', async () => {
  const create = await fetch(`${baseUrl}/api/v1/exams`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}',
  });
  const exam = await create.json();
  const firstQuestion = exam.questions[0];
  const answer = db.prepare('SELECT correct_option FROM questions WHERE id=?').get(firstQuestion.id).correct_option;

  await fetch(`${baseUrl}/api/v1/attempts/${exam.attemptId}/answers`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json', 'x-attempt-token': exam.attemptToken },
    body: JSON.stringify({ answers: { [firstQuestion.id]: answer } }),
  });

  const resumed = await fetch(`${baseUrl}/api/v1/attempts/${exam.attemptId}`, {
    headers: { 'x-attempt-token': exam.attemptToken },
  });
  assert.equal(resumed.status, 200);
  const resumedBody = await resumed.json();
  assert.equal(resumedBody.status, 'in_progress');
  assert.equal(resumedBody.questions[0].selectedOption, answer);

  const wrongToken = await fetch(`${baseUrl}/api/v1/attempts/${exam.attemptId}`, {
    headers: { 'x-attempt-token': 'not-the-token' },
  });
  assert.equal(wrongToken.status, 403);
});

test('a logged-in user can mint a fresh resume token for their own in-progress attempt', async () => {
  const username = `hs_resume_${Date.now()}`;
  const register = await fetch(`${baseUrl}/api/v1/auth/register`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username, password: 'matkhau123' }),
  });
  const { token } = await register.json();

  const create = await fetch(`${baseUrl}/api/v1/exams`, {
    method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` }, body: '{}',
  });
  const exam = await create.json();

  const anotherUser = await fetch(`${baseUrl}/api/v1/auth/register`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username: `${username}_other`, password: 'matkhau123' }),
  });
  const { token: otherToken } = await anotherUser.json();
  const denied = await fetch(`${baseUrl}/api/v1/attempts/${exam.attemptId}/resume-token`, {
    method: 'POST', headers: { authorization: `Bearer ${otherToken}` },
  });
  assert.equal(denied.status, 403);

  const reissue = await fetch(`${baseUrl}/api/v1/attempts/${exam.attemptId}/resume-token`, {
    method: 'POST', headers: { authorization: `Bearer ${token}` },
  });
  assert.equal(reissue.status, 200);
  const { attemptToken: newToken } = await reissue.json();
  assert.notEqual(newToken, exam.attemptToken);

  const oldTokenNowRejected = await fetch(`${baseUrl}/api/v1/attempts/${exam.attemptId}`, {
    headers: { 'x-attempt-token': exam.attemptToken },
  });
  assert.equal(oldTokenNowRejected.status, 403);

  const resumedWithNewToken = await fetch(`${baseUrl}/api/v1/attempts/${exam.attemptId}`, {
    headers: { 'x-attempt-token': newToken },
  });
  assert.equal(resumedWithNewToken.status, 200);
});
