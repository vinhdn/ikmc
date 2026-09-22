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

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      ...(init?.body ? { 'content-type': 'application/json' } : {}),
      ...init?.headers,
    },
  });
  const body = await response.json().catch(() => null) as { error?: { message?: string } } | null;
  if (!response.ok) throw new Error(body?.error?.message ?? `Yêu cầu thất bại (${response.status})`);
  return body as T;
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

export async function createExam(year?: number): Promise<ExamSession> {
  const data = await requestJson<Omit<ExamSession, 'questions'> & { questions: ApiQuestion[] }>(
    '/api/v1/exams',
    { method: 'POST', body: JSON.stringify(year ? { year } : {}) },
  );
  return { ...data, questions: data.questions.map(toQuestion) };
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
