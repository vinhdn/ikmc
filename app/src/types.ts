// Domain types for the IKMC Level 1 (Lớp 2) exam-prep app.

export type Topic =
  | 'arithmetic' // Số học & Quy luật trực quan
  | 'spatial' // Hình học & Không gian
  | 'measurement' // Đo lường, Thời gian & Cân đĩa
  | 'logic'; // Tư duy logic & Tổ hợp

export type Points = 3 | 4 | 5;

export type OptionKey = 'A' | 'B' | 'C' | 'D' | 'E';

export interface Option {
  key: OptionKey;
  text: string;
  imageUrl?: string;
}

export interface Question {
  id: string;
  topic: Topic;
  points: Points;
  /** Văn bản ưu tiên để hỗ trợ fallback. */
  text: string;
  /** Hai bản ngôn ngữ độc lập từ database. */
  textEn?: string;
  textVi?: string;
  /** Emoji/biểu tượng minh hoạ cho câu tự biên soạn cũ. */
  visual?: string;
  /** Crop nguyên bản của câu hỏi trong đề, gồm cả hình và phương án. */
  imageUrl?: string;
  year?: number;
  sourceQuestionNumber?: number;
  sourcePage?: number;
  sourceTitle?: string;
  sourcePdfUrl?: string;
  section?: 'A' | 'B' | 'C';
  options: Option[];
  /** Chỉ có ở dữ liệu local cũ; API không trả trường này trước khi chấm. */
  correct?: OptionKey;
  explanation: string[];
  takeaway?: string;
}

/** Câu trả lời của người dùng: id câu hỏi -> lựa chọn (hoặc undefined nếu bỏ trống). */
export type AnswerMap = Record<string, OptionKey | undefined>;

export interface ScoreResult {
  totalScore: number;
  maxScore: number;
  baseScore: number;
  correctCount: number;
  wrongCount: number;
  skippedCount: number;
  /** Điểm đã cộng thêm (không tính điểm xuất phát). */
  earnedFromAnswers: number;
}

export const TOPIC_LABELS: Record<Topic, string> = {
  arithmetic: 'Số học & Quy luật',
  spatial: 'Hình học & Không gian',
  measurement: 'Đo lường & Thời gian',
  logic: 'Tư duy logic & Tổ hợp',
};

export const TOPIC_EMOJI: Record<Topic, string> = {
  arithmetic: '🔢',
  spatial: '🧩',
  measurement: '⏰',
  logic: '🧠',
};

export function sectionLabel(points: Points): string {
  switch (points) {
    case 3:
      return 'Phần A · 3 điểm';
    case 4:
      return 'Phần B · 4 điểm';
    case 5:
      return 'Phần C · 5 điểm';
  }
}
