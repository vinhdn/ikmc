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
  assert.equal(db.prepare('SELECT COUNT(*) count FROM questions').get().count, 412);
  assert.equal(db.prepare("SELECT COUNT(*) count FROM questions WHERE status='published' AND answer_verified=1").get().count, 192);
  assert.equal(db.prepare("SELECT COUNT(*) count FROM questions WHERE status='published' AND TRIM(COALESCE(stem_vi, ''))<>''").get().count, 192);
  assert.equal(db.prepare("SELECT COUNT(*) count FROM questions WHERE status='needs_review'").get().count, 220);
  assert.equal(db.prepare('SELECT COUNT(*) count FROM question_provenance').get().count, 532);
  assert.equal(db.prepare('SELECT COUNT(*) count FROM question_options').get().count, 2060);
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
