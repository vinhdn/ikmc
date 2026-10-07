import { useEffect, useState } from 'react';
import { getMyAttempts, getResumeToken, type AttemptHistoryItem } from '../api';
import type { ResumeRequest } from './ExamScreen';

interface Props {
  onHome: () => void;
  onResume: (request: ResumeRequest) => void;
}

const STATUS_LABELS: Record<AttemptHistoryItem['status'], string> = {
  in_progress: '🕐 Đang làm dở',
  submitted: '✅ Đã nộp bài',
  expired: '⏰ Hết giờ',
};

function formatDate(value: string): string {
  // SQLite CURRENT_TIMESTAMP trả về UTC dạng "YYYY-MM-DD HH:MM:SS" (không có "Z"),
  // nếu không bổ sung sẽ bị Date hiểu nhầm thành giờ địa phương.
  const iso = /Z|[+-]\d\d:\d\d$/.test(value) ? value : `${value.replace(' ', 'T')}Z`;
  return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
}

export default function HistoryScreen({ onHome, onResume }: Props) {
  const [items, setItems] = useState<AttemptHistoryItem[] | null>(null);
  const [error, setError] = useState('');
  const [resumingId, setResumingId] = useState<string | null>(null);

  useEffect(() => {
    getMyAttempts()
      .then(setItems)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Không tải được lịch sử.'));
  }, []);

  const resume = async (attemptId: string) => {
    setResumingId(attemptId);
    setError('');
    try {
      const { attemptToken } = await getResumeToken(attemptId);
      onResume({ attemptId, attemptToken });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tiếp tục lượt làm bài này.');
      setResumingId(null);
    }
  };

  return (
    <>
      <header className="app-header">
        <div className="title-block">
          <span className="badge">Lịch sử luyện tập</span>
          <h1>Quá trình làm đề của bé</h1>
        </div>
        <button type="button" className="btn btn-prev" onClick={onHome}>🏠 Trang chủ</button>
      </header>

      {error && <div className="api-error">⚠️ {error}</div>}

      {items === null && !error && (
        <div className="card center"><div className="library-status">🦘</div><h2>Đang tải lịch sử…</h2></div>
      )}

      {items !== null && items.length === 0 && (
        <div className="card center">
          <div className="library-status">📭</div>
          <h2>Bé chưa làm đề nào</h2>
          <p className="practice-subtitle">Hãy bắt đầu một đề thi thử để lịch sử xuất hiện ở đây.</p>
        </div>
      )}

      {items !== null && items.length > 0 && (
        <div className="history-list">
          {items.map((item) => (
            <div className="card history-item" key={item.attemptId}>
              <div className="history-top">
                <span className={`history-status ${item.status}`}>{STATUS_LABELS[item.status]}</span>
                <span className="history-date">{formatDate(item.startedAt)}</span>
              </div>
              <h3>
                {item.templateTitle ?? 'Đề ngẫu nhiên'}{' '}
                {item.templateTag === 'ai_generated' && <span className="ai-chip">AI generate</span>}
              </h3>
              {item.status === 'in_progress' ? (
                <>
                  <p>{item.questionCount} câu · đang chờ hoàn thành</p>
                  <button
                    type="button"
                    className="btn btn-submit"
                    disabled={resumingId === item.attemptId}
                    onClick={() => void resume(item.attemptId)}
                  >
                    {resumingId === item.attemptId ? 'Đang mở lại…' : '▶️ Tiếp tục làm bài'}
                  </button>
                </>
              ) : (
                <p className="history-score">
                  Điểm: <strong>{item.totalScore} / {item.maxScore}</strong>
                  {' · '}Đúng {item.correctCount} · Sai {item.wrongCount} · Bỏ qua {item.skippedCount}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="center mt"><button type="button" className="link-btn" onClick={onHome}>← Về trang chủ</button></div>
    </>
  );
}
