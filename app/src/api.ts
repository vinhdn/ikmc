import type { AnswerMap, OptionKey, Question, Topic } from './types';

interface ApiOption {
  key: OptionKey;
  text: string | null;
  image_url: string | null;
}

interface ApiQuestion {
  id: string;
  year: number;
  sourceQuestionNumber: number;
  sourcePage: number;
  sourceTitle: string;
  sourcePdfUrl: string;
  section: 'A' | 'B' | 'C';
  points: 3 | 4 | 5;
  topic: Topic;
  stem: string;
  stemVi: string | null;
  imageUrl: string | null;
  origin?: 'official' | 'ai';
  options: ApiOption[];
}

export interface ExamSession {
  attemptId: string;
  attemptToken: string;
  expiresAt: string;
  durationSeconds: number;
  baseScore: number;
  maxScore: number;
  questions: Question[];
}

export interface ReviewAnswer {
  questionId: string;
  selectedOption: OptionKey | null;
  correctOption: OptionKey;
  isCorrect: boolean | null;
  scoreDelta: number;
  explanation: string[];
}

export interface ServerScoreResult {
  attemptId: string;
  status: 'submitted' | 'expired';
  totalScore: number;
  maxScore: number;
  baseScore: number;
  correctCount: number;
  wrongCount: number;
  skippedCount: number;
  review: ReviewAnswer[];
}

export interface PracticeCheckResult {
  questionId: string;
  selectedOption: OptionKey;
  correctOption: OptionKey;
  isCorrect: boolean;
  explanation: string[];
}

export interface BankMeta {
  canonical_questions: number;
  published_questions: number;
  needs_review: number;
  provenanceRecords: number;
  topics: Array<{ topic: Topic; count: number }>;
  years: Array<{ year: number; count: number }>;
}

export interface AuthUser {
  id: string;
  username: string;
  displayName: string;
}

export interface AuthSession {
  token: string;
  expiresAt: string;
  user: AuthUser;
}

export interface ExamTemplate {
  id: string;
  title: string;
  position: number;
  tag: string | null;
}

export interface AttemptHistoryItem {
  attemptId: string;
  mode: 'exam' | 'practice';
  status: 'in_progress' | 'submitted' | 'expired';
  totalScore: number | null;
  baseScore: number;
  correctCount: number | null;
  wrongCount: number | null;
  skippedCount: number | null;
  startedAt: string;
  expiresAt: string | null;
  submittedAt: string | null;
  templateTitle: string | null;
  templateTag: string | null;
  questionCount: number;
  maxScore: number | null;
}

const AUTH_TOKEN_KEY = 'ikmc:auth-token';
const AUTH_USER_KEY = 'ikmc:auth-user';
const ACTIVE_ATTEMPT_KEY = 'ikmc:active-attempt';

export function getStoredAuth(): { token: string; user: AuthUser } | null {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  const rawUser = localStorage.getItem(AUTH_USER_KEY);
  if (!token || !rawUser) return null;
  try {
    return { token, user: JSON.parse(rawUser) as AuthUser };
  } catch {
    return null;
  }
}

export function storeAuth(session: AuthSession): void {
  localStorage.setItem(AUTH_TOKEN_KEY, session.token);
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(session.user));
}

export function clearStoredAuth(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
}

export interface StoredActiveAttempt {
  attemptId: string;
  attemptToken: string;
  expiresAt: string;
}

export function getStoredActiveAttempt(): StoredActiveAttempt | null {
  const raw = localStorage.getItem(ACTIVE_ATTEMPT_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredActiveAttempt;
    if (Date.now() > Date.parse(parsed.expiresAt)) {
      localStorage.removeItem(ACTIVE_ATTEMPT_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function storeActiveAttempt(session: ExamSession): void {
  const value: StoredActiveAttempt = {
    attemptId: session.attemptId,
    attemptToken: session.attemptToken,
    expiresAt: session.expiresAt,
  };
  localStorage.setItem(ACTIVE_ATTEMPT_KEY, JSON.stringify(value));
}

export function clearStoredActiveAttempt(): void {
  localStorage.removeItem(ACTIVE_ATTEMPT_KEY);
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const auth = getStoredAuth();
  const response = await fetch(url, {
    ...init,
    headers: {
      ...(init?.body ? { 'content-type': 'application/json' } : {}),
      ...(auth ? { authorization: `Bearer ${auth.token}` } : {}),
      ...init?.headers,
    },
  });
  const body = await response.json().catch(() => null) as { error?: { message?: string } } | null;
  if (!response.ok) throw new Error(body?.error?.message ?? `Yêu cầu thất bại (${response.status})`);
  return body as T;
}

export async function register(username: string, password: string, displayName?: string): Promise<AuthSession> {
  return requestJson<AuthSession>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, displayName }),
  });
}

export async function login(username: string, password: string): Promise<AuthSession> {
  return requestJson<AuthSession>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  await requestJson('/api/v1/auth/logout', { method: 'POST' });
}

export async function getExamTemplates(): Promise<ExamTemplate[]> {
  const data = await requestJson<{ items: ExamTemplate[] }>('/api/v1/exam-templates');
  return data.items;
}

export async function getMyAttempts(): Promise<AttemptHistoryItem[]> {
  const data = await requestJson<{ items: AttemptHistoryItem[] }>('/api/v1/me/attempts');
  return data.items;
}

export async function getResumeToken(attemptId: string): Promise<{ attemptId: string; attemptToken: string; expiresAt: string }> {
  return requestJson(`/api/v1/attempts/${attemptId}/resume-token`, { method: 'POST' });
}

function toQuestion(item: ApiQuestion): Question {
  return {
    id: item.id,
    year: item.year,
    sourceQuestionNumber: item.sourceQuestionNumber,
    sourcePage: item.sourcePage,
    sourceTitle: item.sourceTitle,
    sourcePdfUrl: item.sourcePdfUrl,
    section: item.section,
    topic: item.topic,
    points: item.points,
    text: item.stemVi || item.stem,
    textEn: item.stem,
    textVi: item.stemVi ?? undefined,
    imageUrl: item.imageUrl ?? undefined,
    origin: item.origin ?? 'official',
    options: item.options.map((option) => ({
      key: option.key,
      text: option.text || `Phương án ${option.key}`,
      imageUrl: option.image_url ?? undefined,
    })),
    explanation: [],
  };
}

export async function getBankMeta(): Promise<BankMeta> {
  return requestJson<BankMeta>('/api/v1/meta');
}

export async function getPracticeQuestions(topic: Topic | 'all', limit = 20): Promise<Question[]> {
  const data = await requestJson<{ items: ApiQuestion[] }>(
    `/api/v1/practice/questions?topic=${encodeURIComponent(topic)}&limit=${limit}`,
  );
  return data.items.map(toQuestion);
}

export async function checkPracticeAnswer(
  questionId: string,
  selectedOption: OptionKey,
): Promise<PracticeCheckResult> {
  return requestJson<PracticeCheckResult>('/api/v1/practice/check', {
    method: 'POST',
    body: JSON.stringify({ questionId, selectedOption }),
  });
}

export async function createExam(options?: { year?: number; templateId?: string }): Promise<ExamSession> {
  const data = await requestJson<Omit<ExamSession, 'questions'> & { questions: ApiQuestion[] }>(
    '/api/v1/exams',
    { method: 'POST', body: JSON.stringify(options ?? {}) },
  );
  return { ...data, questions: data.questions.map(toQuestion) };
}

interface ApiQuestionWithAnswer extends ApiQuestion {
  selectedOption: OptionKey | null;
}

export interface ResumedExam {
  session: ExamSession;
  answers: AnswerMap;
}

export async function resumeExam(attemptId: string, token: string): Promise<ResumedExam> {
  const data = await requestJson<
    { attemptId: string; status: string; expiresAt: string; questions: ApiQuestionWithAnswer[] } | { status: string }
  >(`/api/v1/attempts/${attemptId}`, { headers: { 'x-attempt-token': token } });
  if (data.status !== 'in_progress' || !('questions' in data)) {
    throw new Error('Lượt làm bài này đã kết thúc.');
  }
  const questions = data.questions.map(toQuestion);
  const answers: AnswerMap = {};
  data.questions.forEach((question, i) => {
    if (question.selectedOption) answers[questions[i].id] = question.selectedOption;
  });
  const durationSeconds = Math.max(0, Math.round((Date.parse(data.expiresAt) - Date.now()) / 1000));
  const session: ExamSession = {
    attemptId: data.attemptId,
    attemptToken: token,
    expiresAt: data.expiresAt,
    durationSeconds,
    baseScore: 24,
    maxScore: 24 + questions.reduce((sum, question) => sum + question.points, 0),
    questions,
  };
  return { session, answers };
}

export async function saveExamAnswers(session: ExamSession, answers: AnswerMap): Promise<void> {
  const compact = Object.fromEntries(Object.entries(answers).filter((entry): entry is [string, OptionKey] => Boolean(entry[1])));
  await requestJson(`/api/v1/attempts/${session.attemptId}/answers`, {
    method: 'PUT',
    headers: { 'x-attempt-token': session.attemptToken },
    body: JSON.stringify({ answers: compact }),
  });
}

export async function submitExam(session: ExamSession, answers: AnswerMap): Promise<ServerScoreResult> {
  const compact = Object.fromEntries(Object.entries(answers).filter((entry): entry is [string, OptionKey] => Boolean(entry[1])));
  return requestJson<ServerScoreResult>(`/api/v1/attempts/${session.attemptId}/submit`, {
    method: 'POST',
    headers: { 'x-attempt-token': session.attemptToken },
    body: JSON.stringify({ answers: compact }),
  });
}
