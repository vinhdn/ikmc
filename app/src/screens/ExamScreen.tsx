import { useEffect, useRef, useState } from 'react';
import {
  clearStoredActiveAttempt,
  createExam,
  resumeExam,
  saveExamAnswers,
  storeActiveAttempt,
  submitExam,
  type ExamSession,
  type ServerScoreResult,
} from '../api';
import type { AnswerMap, OptionKey, Question } from '../types';
import QuestionCard from '../components/QuestionCard';
import { formatTime, useCountdown } from '../components/useCountdown';

export interface ResumeRequest {
  attemptId: string;
  attemptToken: string;
}

interface Props {
  templateId?: string;
  resume?: ResumeRequest;
  onComplete: (questions: Question[], answers: AnswerMap, result: ServerScoreResult) => void;
  onQuit: () => void;
}

export default function ExamScreen({ templateId, resume, onComplete, onQuit }: Props) {
  const [session, setSession] = useState<ExamSession | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const started = useRef(false);
  const submitted = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const begin = async () => {
      if (resume) {
        const { session: resumed, answers: resumedAnswers } = await resumeExam(resume.attemptId, resume.attemptToken);
        storeActiveAttempt(resumed);
        setAnswers(resumedAnswers);
        return resumed;
      }
      const created = await createExam(templateId ? { templateId } : undefined);
      storeActiveAttempt(created);
      return created;
    };

    begin()
      .then(setSession)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Không tạo được đề thi.'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!session || submitted.current) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [session]);

  const handleSubmit = async (askConfirmation: boolean) => {
    if (!session || submitting || submitted.current) return;
    if (askConfirmation && !confirm('Bé chắc chắn muốn nộp bài chứ?')) return;
    submitted.current = true;
    setSubmitting(true);
    setError('');
    try {
      const result = await submitExam(session, answers);
      clearStoredActiveAttempt();
      onComplete(session.questions, answers, result);
    } catch (reason) {
      submitted.current = false;
      setError(reason instanceof Error ? reason.message : 'Không nộp được bài thi.');
      setSubmitting(false);
    }
  };

  const remaining = useCountdown(
    session?.durationSeconds ?? 75 * 60,
    Boolean(session) && !submitting,
    () => void handleSubmit(false),
  );

  if (loading) {
    return <div className="card center"><div className="library-status">🦘</div><h2>Đang tạo đề từ ngân hàng câu hỏi…</h2></div>;
  }

  if (error && !session) {
    return (
      <div className="card center">
        <div className="library-status">⚠️</div>
        <h2>Không thể tạo đề thi</h2>
        <p className="practice-subtitle">{error}</p>
        <button type="button" className="btn btn-prev mt" onClick={onQuit}>Về trang chủ</button>
      </div>
    );
  }

  if (!session) return null;
  const current = session.questions[index];
  const answeredCount = Object.values(answers).filter(Boolean).length;
  const isLast = index === session.questions.length - 1;

  const select = (key: OptionKey) => {
    const next = {
      ...answers,
      [current.id]: answers[current.id] === key ? undefined : key,
    };
    setAnswers(next);
    saveExamAnswers(session, next).catch((reason: unknown) => {
      setError(reason instanceof Error ? `Chưa lưu được đáp án: ${reason.message}` : 'Chưa lưu được đáp án.');
    });
  };

  return (
    <>
      <header className="app-header">
        <div className="title-block">
          <span className="badge">IKMC Lớp 1–2 · dữ liệu thật</span>
          <h1>Đề thi thử · 24 câu</h1>
        </div>
        <div className={`timer${remaining <= 60 ? ' warn' : ''}`}>{formatTime(remaining)}</div>
      </header>

      {error && <div className="api-error">⚠️ {error}</div>}
      <QuestionCard
        question={current}
        index={index}
        total={session.questions.length}
        selected={answers[current.id]}
        onSelect={select}
      />

      <div className="actions">
        <button type="button" className="btn btn-prev" disabled={index === 0 || submitting} onClick={() => setIndex((value) => value - 1)}>
          ← Quay lại
        </button>
        <button
          type="button"
          className={`btn ${isLast ? 'btn-submit' : 'btn-next'}`}
          disabled={submitting}
          onClick={() => isLast ? void handleSubmit(true) : setIndex((value) => value + 1)}
        >
          {submitting ? 'Đang chấm…' : isLast ? '✅ Nộp bài' : 'Câu tiếp →'}
        </button>
      </div>

      <div className="card">
        <p className="center exam-save-status">Đã lưu {answeredCount} / {session.questions.length} câu</p>
        <div className="dots">
          {session.questions.map((question, questionIndex) => (
            <button
              key={question.id}
              type="button"
              className={`dot${answers[question.id] ? ' answered' : ''}${questionIndex === index ? ' current' : ''}`}
              onClick={() => setIndex(questionIndex)}
            >
              {questionIndex + 1}
            </button>
          ))}
        </div>
        <div className="center mt">
          <button
            type="button"
            className="link-btn"
            onClick={() => confirm('Thoát bài thi? Đáp án và thời gian đã lưu, bé có thể quay lại làm tiếp bất cứ lúc nào trước khi hết giờ.') && onQuit()}
          >
            Thoát bài thi (có thể quay lại)
          </button>
        </div>
      </div>
    </>
  );
}
