import type { Question } from './types';
import P3 from './questions.p3';
import P4 from './questions.p4';
import P5 from './questions.p5';

/** Toàn bộ ngân hàng câu hỏi. */
export const QUESTION_BANK: Question[] = [...P3, ...P4, ...P5];

export { P3, P4, P5 };
