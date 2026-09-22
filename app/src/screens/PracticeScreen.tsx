import { useMemo, useState } from 'react';
import type { OptionKey, Question, Topic } from '../types';
import { TOPIC_EMOJI, TOPIC_LABELS } from '../types';
import { QUESTION_BANK } from '../questions';
import { shuffle } from '../scoring';
import QuestionCard from '../components/QuestionCard';

interface Props {
  onHome: () => void;
}

const TOPICS: Topic[] = ['arithmetic', 'spatial', 'measurement', 'logic'];

export default function PracticeScreen({ onHome }: Props) {
  const [topic, setTopic] = useState<Topic | 'all' | null>(null);
  const [index, setIndex] = useState(0);
  const [choice, setChoice] = useState<OptionKey | undefined>(undefined);
  const [revealed, setRevealed] = useState(false);
  const [correctSoFar, setCorrectSoFar] = useState(0);

  const questions: Question[] = useMemo(() => {
    if (topic === null) return [];
    const pool =
      topic === 'all'
        ? QUESTION_BANK
        : QUESTION_BANK.filter((q) => q.topic === topic);
    return shuffle(pool);
  }, [topic]);

  // ----- Topic picker -----
  if (topic === null) {
    const counts = TOPICS.map((t) => ({
      t,
      n: QUESTION_BANK.filter((q) => q.topic === t).length,
    }));
    return (
      <div className="card">
        <h2 className="center">📚 Chọn chủ đề luyện tập</h2>
        <p className="center" style={{ color: 'var(--muted)', fontWeight: 700, marginTop: 6 }}>
          Làm câu nào biết ngay đúng/sai kèm lời giải chi tiết.
        </p>
        <div className="topic-grid">
          {counts.map(({ t, n }) => (
            <div
              key={t}
              className="topic-card"
              role="button"
              tabIndex={0}
              onClick={() => setTopic(t)}
              onKeyDown={(e) => e.key === 'Enter' && setTopic(t)}
            >
              <span className="ic">{TOPIC_EMOJI[t]}</span>
              {TOPIC_LABELS[t]}
              <small>{n} câu</small>
            </div>
          ))}
          <div
            className="topic-card"
            role="button"
            tabIndex={0}
            onClick={() => setTopic('all')}
            onKeyDown={(e) => e.key === 'Enter' && setTopic('all')}
            style={{ gridColumn: '1 / -1' }}
          >
            <span className="ic">🎲</span>
            Tất cả chủ đề
            <small>{QUESTION_BANK.length} câu · trộn ngẫu nhiên</small>
          </div>
        </div>
        <div className="center mt">
          <button type="button" className="link-btn" onClick={onHome}>
            ← Về trang chủ
          </button>
        </div>
      </div>
    );
  }

  const current = questions[index];
  const done = index >= questions.length;

  // ----- Finished all -----
  if (done || !current) {
    return (
      <div className="card result-card">
        <div style={{ fontSize: 48 }}>🌟</div>
        <h2>Hoàn thành phần luyện tập!</h2>
        <div className="score-ring">
          {correctSoFar} / {questions.length}
        </div>
        <p style={{ fontWeight: 800, color: 'var(--primary-dark)' }}>
          Bé đã trả lời đúng {correctSoFar} câu. Giỏi lắm!
        </p>
        <div className="actions" style={{ justifyContent: 'center', marginTop: 18 }}>
          <button
            type="button"
            className="btn btn-prev"
            onClick={() => {
              setTopic(null);
              setIndex(0);
              setChoice(undefined);
              setRevealed(false);
              setCorrectSoFar(0);
            }}
          >
            📚 Chủ đề khác
          </button>
          <button type="button" className="btn btn-submit" onClick={onHome}>
            🏠 Trang chủ
          </button>
        </div>
      </div>
    );
  }

  const check = (key: OptionKey) => {
    if (revealed) return;
    setChoice(key);
    setRevealed(true);
    if (key === current.correct) setCorrectSoFar((c) => c + 1);
  };

  const next = () => {
    setIndex((i) => i + 1);
    setChoice(undefined);
    setRevealed(false);
  };

  return (
    <>
      <header className="app-header">
        <div className="title-block">
          <span className="badge">Luyện tập</span>
          <h1>
            {topic === 'all' ? 'Tất cả chủ đề' : TOPIC_LABELS[topic as Topic]}
          </h1>
        </div>
        <div className="timer" style={{ background: 'var(--secondary-soft)', color: '#2e7d32' }}>
          ⭐ {correctSoFar}
        </div>
      </header>

      <QuestionCard
        question={current}
        index={index}
        total={questions.length}
        selected={choice}
        onSelect={check}
        reveal={revealed}
      />

      <div className="actions">
        <button type="button" className="btn btn-prev" onClick={onHome}>
          🏠 Trang chủ
        </button>
        <button
          type="button"
          className="btn btn-next"
          disabled={!revealed}
          onClick={next}
        >
          {index === questions.length - 1 ? 'Xem kết quả →' : 'Câu tiếp →'}
        </button>
      </div>
    </>
  );
}
