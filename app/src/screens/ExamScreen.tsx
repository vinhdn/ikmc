import { useState } from 'react';
import type { AnswerMap, OptionKey, Question } from '../types';
import QuestionCard from '../components/QuestionCard';
import { formatTime, useCountdown } from '../components/useCountdown';

const EXAM_SECONDS = 75 * 60;

interface Props {
  questions: Question[];
  onSubmit: (answers: AnswerMap) => void;
  onQuit: () => void;
}

export default function ExamScreen({ questions, onSubmit, onQuit }: Props) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<AnswerMap>({});

  const remaining = useCountdown(EXAM_SECONDS, true, () => onSubmit(answers));
  const current = questions[index];
  const answeredCount = Object.values(answers).filter(Boolean).length;

  const select = (key: OptionKey) => {
    setAnswers((prev) => ({
      ...prev,
      // Bấm lại lựa chọn đang chọn = bỏ chọn.
      [current.id]: prev[current.id] === key ? undefined : key,
    }));
  };

  const isLast = index === questions.length - 1;

  const handleNext = () => {
    if (isLast) {
      if (confirm('Bé chắc chắn muốn nộp bài chứ?')) onSubmit(answers);
    } else {
      setIndex((i) => i + 1);
    }
  };

  return (
    <>
      <header className="app-header">
        <div className="title-block">
          <span className="badge">IKMC Level 1 · Lớp 2</span>
          <h1>Đề thi thử</h1>
        </div>
        <div className={`timer${remaining <= 60 ? ' warn' : ''}`}>
          {formatTime(remaining)}
        </div>
      </header>

      <QuestionCard
        question={current}
        index={index}
        total={questions.length}
        selected={answers[current.id]}
        onSelect={select}
      />

      <div className="actions">
        <button
          type="button"
          className="btn btn-prev"
          disabled={index === 0}
          onClick={() => setIndex((i) => i - 1)}
        >
          ← Quay lại
        </button>
        <button
          type="button"
          className={`btn ${isLast ? 'btn-submit' : 'btn-next'}`}
          onClick={handleNext}
        >
          {isLast ? '✅ Nộp bài' : 'Câu tiếp →'}
        </button>
      </div>

      <div className="card">
        <p className="center" style={{ fontWeight: 800, color: 'var(--muted)' }}>
          Đã làm {answeredCount} / {questions.length} câu
        </p>
        <div className="dots">
          {questions.map((q, i) => (
            <button
              key={q.id}
              type="button"
              className={
                'dot' +
                (answers[q.id] ? ' answered' : '') +
                (i === index ? ' current' : '')
              }
              onClick={() => setIndex(i)}
            >
              {i + 1}
            </button>
          ))}
        </div>
        <div className="center mt">
          <button type="button" className="link-btn" onClick={onQuit}>
            Thoát bài thi
          </button>
        </div>
      </div>
    </>
  );
}
