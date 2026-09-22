import type { ServerScoreResult } from '../api';
import type { AnswerMap, Question } from '../types';
import QuestionCard from '../components/QuestionCard';

interface Props {
  questions: Question[];
  answers: AnswerMap;
  result: ServerScoreResult;
  onRestart: () => void;
  onHome: () => void;
}

function praise(score: number, max: number): string {
  const percentage = score / max;
  if (percentage >= 0.85) return 'Xuất sắc! Bé là nhà vô địch Kangaroo tương lai! 🏆';
  if (percentage >= 0.65) return 'Giỏi lắm! Bé làm rất tốt! 🌟';
  if (percentage >= 0.45) return 'Khá lắm! Luyện thêm chút nữa là tuyệt vời! 💪';
  return 'Cố lên nào! Mỗi lần luyện tập bé sẽ giỏi hơn! 🌱';
}

export default function ResultsScreen({ questions, answers, result, onRestart, onHome }: Props) {
  const reviewById = new Map(result.review.map((item) => [item.questionId, item]));
  const earned = Math.round((result.totalScore - result.baseScore) * 100) / 100;

  return (
    <>
      <div className="card result-card">
        <div className="result-icon">🎉</div>
        <h2>{result.status === 'expired' ? 'Hết giờ — bài đã được chấm!' : 'Hoàn thành bài thi!'}</h2>
        <div className="score-ring">{result.totalScore} / {result.maxScore}</div>
        <p className="result-praise">{praise(result.totalScore, result.maxScore)}</p>
        <p className="server-verified">🔒 Điểm được tính và lưu bởi máy chủ</p>

        <div className="stats">
          <div className="stat ok"><span className="num">{result.correctCount}</span><span className="lbl">Đúng</span></div>
          <div className="stat bad"><span className="num">{result.wrongCount}</span><span className="lbl">Sai</span></div>
          <div className="stat skip"><span className="num">{result.skippedCount}</span><span className="lbl">Bỏ qua</span></div>
        </div>
        <p className="score-detail">
          Điểm xuất phát +{result.baseScore} · Điểm từ bài làm {earned >= 0 ? '+' : ''}{earned}
        </p>

        <div className="actions result-actions">
          <button type="button" className="btn btn-prev" onClick={onHome}>🏠 Về trang chủ</button>
          <button type="button" className="btn btn-submit" onClick={onRestart}>🔁 Đề mới</button>
        </div>
      </div>

      <h3 className="center review-title">📖 Xem lại đáp án chính thức</h3>
      {questions.map((question, index) => {
        const review = reviewById.get(question.id);
        const selected = review?.selectedOption ?? answers[question.id];
        return (
          <div className="review-item" key={question.id}>
            <QuestionCard
              question={question}
              index={index}
              total={questions.length}
              selected={selected ?? undefined}
              onSelect={() => {}}
              reveal
              correctOption={review?.correctOption}
              explanation={review?.explanation}
            />
            <p className="answer-line">
              {!selected ? (
                <span className="skip">⏭️ Chưa trả lời · Đáp án đúng: {review?.correctOption}</span>
              ) : review?.isCorrect ? (
                <span className="ok">✅ Bé chọn {selected} — Chính xác! (+{review.scoreDelta} điểm)</span>
              ) : (
                <span className="bad">❌ Bé chọn {selected} · Đáp án đúng: {review?.correctOption} ({review?.scoreDelta} điểm)</span>
              )}
            </p>
          </div>
        );
      })}

      <div className="center mt"><button type="button" className="link-btn" onClick={onHome}>Về trang chủ</button></div>
    </>
  );
}
