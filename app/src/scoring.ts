import type { AnswerMap, Points, Question, ScoreResult } from './types';

export const BASE_SCORE = 24;
export const SECTION_SIZE = 8; // 8 câu mỗi phần
export const MAX_SCORE = BASE_SCORE + SECTION_SIZE * (3 + 4 + 5); // 24 + 96 = 120

/** Fisher–Yates shuffle (không đột biến mảng gốc). */
export function shuffle<T>(arr: readonly T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/**
 * Tạo đề chuẩn IKMC: 8 câu 3đ + 8 câu 4đ + 8 câu 5đ = 24 câu.
 * Nếu không đủ câu cho một phần, lấy tối đa có thể (giữ thứ tự A→B→C).
 */
export function generateExam(pool: readonly Question[]): Question[] {
  const pick = (pts: Points) =>
    shuffle(pool.filter((q) => q.points === pts)).slice(0, SECTION_SIZE);
  return [...pick(3), ...pick(4), ...pick(5)];
}

/**
 * Chấm điểm theo quy tắc Kangaroo:
 * - Điểm xuất phát: +24
 * - Đúng: +điểm câu (3/4/5)
 * - Sai: -1/4 điểm câu (-0.75 / -1.0 / -1.25)
 * - Bỏ trống: 0
 * - Không dưới 0.
 */
export function calculateScore(
  questions: readonly Question[],
  answers: AnswerMap,
): ScoreResult {
  let earned = 0;
  let correctCount = 0;
  let wrongCount = 0;
  let skippedCount = 0;

  for (const q of questions) {
    const selected = answers[q.id];
    if (!selected) {
      skippedCount++;
    } else if (selected === q.correct) {
      correctCount++;
      earned += q.points;
    } else {
      wrongCount++;
      earned -= q.points * 0.25;
    }
  }

  const total = Math.max(0, BASE_SCORE + earned);
  const maxScore =
    BASE_SCORE + questions.reduce((sum, q) => sum + q.points, 0);

  return {
    totalScore: roundHalf(total),
    maxScore,
    baseScore: BASE_SCORE,
    correctCount,
    wrongCount,
    skippedCount,
    earnedFromAnswers: roundHalf(earned),
  };
}

/** Làm tròn tới 0.25 để hiển thị gọn (điểm phạt là bội của 0.25). */
function roundHalf(n: number): number {
  return Math.round(n * 100) / 100;
}
