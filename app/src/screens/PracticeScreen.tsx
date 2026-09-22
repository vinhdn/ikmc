import { useEffect, useState } from 'react';
import { checkPracticeAnswer, getBankMeta, getPracticeQuestions, type BankMeta, type PracticeCheckResult } from '../api';
import type { OptionKey, Question, Topic } from '../types';
import { TOPIC_EMOJI, TOPIC_LABELS } from '../types';
import QuestionCard from '../components/QuestionCard';

interface Props {
  onHome: () => void;
}

const TOPICS: Topic[] = ['arithmetic', 'spatial', 'measurement', 'logic'];

export default function PracticeScreen({ onHome }: Props) {
  const [meta, setMeta] = useState<BankMeta | null>(null);
  const [topic, setTopic] = useState<Topic | 'all' | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [index, setIndex] = useState(0);
  const [choice, setChoice] = useState<OptionKey>();
  const [checkResult, setCheckResult] = useState<PracticeCheckResult | null>(null);
  const [correctSoFar, setCorrectSoFar] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getBankMeta().then(setMeta).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : 'Không tải được thống kê ngân hàng câu hỏi.');
    });
  }, []);

  const chooseTopic = async (value: Topic | 'all') => {
    setTopic(value);
    setLoading(true);
    setError('');
    setIndex(0);
    setChoice(undefined);
    setCheckResult(null);
    setCorrectSoFar(0);
    try {
      setQuestions(await getPracticeQuestions(value, 20));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không tải được câu hỏi.');
      setQuestions([]);
    } finally {
      setLoading(false);
    }
  };

  const resetTopic = () => {
    setTopic(null);
    setQuestions([]);
    setIndex(0);
    setChoice(undefined);
    setCheckResult(null);
    setCorrectSoFar(0);
    setError('');
  };

  if (topic === null) {
    const counts = Object.fromEntries(meta?.topics.map((item) => [item.topic, item.count]) ?? []);
    return (
      <div className="card">
        <h2 className="center">📚 Chọn chủ đề luyện tập</h2>
        <p className="center practice-subtitle">
          Câu hỏi thật từ đề 2014–2022; đáp án được chấm trực tiếp trên máy chủ.
        </p>
        {error && <div className="api-error">⚠️ {error}</div>}
        <div className="topic-grid">
          {TOPICS.map((item) => (
            <button key={item} className="topic-card" type="button" onClick={() => void chooseTopic(item)}>
              <span className="ic">{TOPIC_EMOJI[item]}</span>
              {TOPIC_LABELS[item]}
              <small>{counts[item] ?? '…'} câu đã kiểm duyệt</small>
            </button>
          ))}
          <button className="topic-card topic-all" type="button" onClick={() => void chooseTopic('all')}>
            <span className="ic">🎲</span>
            Trộn tất cả chủ đề
            <small>{meta?.published_questions ?? '…'} câu · lấy ngẫu nhiên 20 câu</small>
          </button>
        </div>
        <div className="center mt">
          <button type="button" className="link-btn" onClick={onHome}>← Về trang chủ</button>
        </div>
      </div>
    );
  }

  if (loading) {
    return <div className="card center"><div className="library-status">🦘</div><h2>Đang lấy câu hỏi từ ngân hàng…</h2></div>;
  }

  if (error || questions.length === 0) {
    return (
      <div className="card center">
        <div className="library-status">⚠️</div>
        <h2>Không thể bắt đầu luyện tập</h2>
        <p className="practice-subtitle">{error || 'Chủ đề này chưa có câu hỏi đã kiểm duyệt.'}</p>
        <button type="button" className="btn btn-prev mt" onClick={resetTopic}>Chọn lại chủ đề</button>
      </div>
    );
  }

  if (index >= questions.length) {
    return (
      <div className="card result-card">
        <div className="result-icon">🌟</div>
        <h2>Hoàn thành phần luyện tập!</h2>
        <div className="score-ring">{correctSoFar} / {questions.length}</div>
        <p className="result-praise">Kết quả đã được chấm từ đáp án chính thức trên server.</p>
        <div className="actions result-actions">
          <button type="button" className="btn btn-prev" onClick={resetTopic}>📚 Chủ đề khác</button>
          <button type="button" className="btn btn-submit" onClick={onHome}>🏠 Trang chủ</button>
        </div>
      </div>
    );
  }

  const current = questions[index];

  const check = async (key: OptionKey) => {
    if (checkResult || loading) return;
    setChoice(key);
    setLoading(true);
    setError('');
    try {
      const result = await checkPracticeAnswer(current.id, key);
      setCheckResult(result);
      if (result.isCorrect) setCorrectSoFar((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không chấm được câu trả lời.');
      setChoice(undefined);
    } finally {
      setLoading(false);
    }
  };

  const next = () => {
    setIndex((value) => value + 1);
    setChoice(undefined);
    setCheckResult(null);
    setError('');
  };

  return (
    <>
      <header className="app-header">
        <div className="title-block">
          <span className="badge">Luyện tập · dữ liệu thật</span>
          <h1>{topic === 'all' ? 'Tất cả chủ đề' : TOPIC_LABELS[topic]}</h1>
        </div>
        <div className="timer practice-score">⭐ {correctSoFar}</div>
      </header>

      {error && <div className="api-error">⚠️ {error}</div>}
      <QuestionCard
        question={current}
        index={index}
        total={questions.length}
        selected={choice}
        onSelect={(key) => void check(key)}
        reveal={Boolean(checkResult)}
        correctOption={checkResult?.correctOption}
        explanation={checkResult?.explanation}
      />

      <div className="actions">
        <button type="button" className="btn btn-prev" onClick={onHome}>🏠 Trang chủ</button>
        <button type="button" className="btn btn-next" disabled={!checkResult || loading} onClick={next}>
          {index === questions.length - 1 ? 'Xem kết quả →' : 'Câu tiếp →'}
        </button>
      </div>
    </>
  );
}
