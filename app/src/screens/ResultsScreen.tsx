import type { AnswerMap, Question } from '../types';
import { calculateScore } from '../scoring';
import QuestionCard from '../components/QuestionCard';

interface Props {
  questions: Question[];
  answers: AnswerMap;
  onRestart: () => void;
  onHome: () => void;
}

function praise(score: number, max: number): string {
  const pct = score / max;
  if (pct >= 0.85) return 'Xuất sắc! Bé là nhà vô địch Kangaroo tương lai! 🏆';
  if (pct >= 0.65) return 'Giỏi lắm! Bé làm rất tốt! 🌟';
  if (pct >= 0.45) return 'Khá lắm! Luyện thêm chút nữa là tuyệt vời! 💪';
  return 'Cố lên nào! Mỗi lần luyện tập bé sẽ giỏi hơn! 🌱';
}

export default function ResultsScreen({
  questions,
  answers,
  onRestart,
  onHome,
}: Props) {
  const result = calculateScore(questions, answers);

  return (
    <>
      <div className="card result-card">
        <div style={{ fontSize: 52 }}>🎉</div>
        <h2>Hoàn thành bài thi!</h2>
        <div className="score-ring">
          {result.totalScore} / {result.maxScore}
        </div>
        <p style={{ fontWeight: 800, color: 'var(--primary-dark)' }}>
          {praise(result.totalScore, result.maxScore)}
        </p>

        <div className="stats">
          <div className="stat ok">
            <span className="num">{result.correctCount}</span>
            <span className="lbl">Đúng</span>
          </div>
          <div className="stat bad">
            <span className="num">{result.wrongCount}</span>
            <span className="lbl">Sai</span>
          </div>
          <div className="stat skip">
            <span className="num">{result.skippedCount}</span>
            <span className="lbl">Bỏ qua</span>
          </div>
        </div>
        <p style={{ color: 'var(--muted)', fontWeight: 700 }}>
          Điểm xuất phát +{result.baseScore} · Điểm từ bài làm{' '}
          {result.earnedFromAnswers >= 0 ? '+' : ''}
          {result.earnedFromAnswers}
        </p>

        <div className="actions" style={{ justifyContent: 'center', marginTop: 20 }}>
          <button type="button" className="btn btn-prev" onClick={onHome}>
            🏠 Về trang chủ
          </button>
          <button type="button" className="btn btn-submit" onClick={onRestart}>
            🔁 Làm lại
          </button>
        </div>
      </div>

      <h3 className="center" style={{ margin: '8px 0 4px' }}>
        📖 Xem lại &amp; lời giải
      </h3>
      {questions.map((q, i) => (
        <div className="review-item" key={q.id}>
          <QuestionCard
            question={q}
            index={i}
            total={questions.length}
            selected={answers[q.id]}
            onSelect={() => {}}
            reveal
          />
          <p className="answer-line">
            {answers[q.id] ? (
              answers[q.id] === q.correct ? (
                <span className="ok">✅ Bé chọn {answers[q.id]} — Chính xác!</span>
              ) : (
                <span className="bad">
                  ❌ Bé chọn {answers[q.id]} · Đáp án đúng: {q.correct}
                </span>
              )
            ) : (
              <span className="skip">⏭️ Chưa trả lời · Đáp án đúng: {q.correct}</span>
            )}
          </p>
        </div>
      ))}

      <div className="center mt">
        <button type="button" className="link-btn" onClick={onHome}>
          Về trang chủ
        </button>
      </div>
    </>
  );
}
