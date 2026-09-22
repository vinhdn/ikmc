export type ExamKind = 'official' | 'practice' | 'collection';
export type ExtractionMethod = 'embedded' | 'ocr' | 'ocr-hires';

export interface ExamPage {
  page: number;
  text: string;
  method: ExtractionMethod;
}

export interface ExamDocument {
  id: string;
  title: string;
  year: number | null;
  questionCount: number;
  pageCount: number;
  language: string;
  kind: ExamKind;
  pdfUrl: string;
  coverUrl: string;
  pages: ExamPage[];
}

export interface ExamLibraryIndex {
  generatedAt: string;
  documentCount: number;
  questionCount: number;
  pageCount: number;
  documents: ExamDocument[];
}

let cache: Promise<ExamLibraryIndex> | undefined;

/** Tải một lần và lưu cache chỉ mục văn bản/OCR của toàn bộ tài liệu. */
export function loadExamLibrary(): Promise<ExamLibraryIndex> {
  if (!cache) {
    cache = fetch('/exams/index.json').then(async (response) => {
      if (!response.ok) throw new Error(`Không tải được thư viện đề (${response.status})`);
      return (await response.json()) as ExamLibraryIndex;
    });
  }
  return cache;
}

export const EXAM_KIND_LABELS: Record<ExamKind, string> = {
  official: 'Đề theo năm',
  practice: 'Tài liệu ôn tập',
  collection: 'Bộ đề tổng hợp',
};
