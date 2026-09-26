import type { AuthUser } from '../api';

interface Props {
  user: AuthUser | null;
  activeAttempt: { remainingLabel: string } | null;
  onStartExam: () => void;
  onStartPractice: () => void;
  onOpenLibrary: () => void;
  onOpenHistory: () => void;
  onOpenAuth: () => void;
  onLogout: () => void;
  onResumeActive: () => void;
}

export default function Home({
  user,
  activeAttempt,
  onStartExam,
  onStartPractice,
  onOpenLibrary,
  onOpenHistory,
  onOpenAuth,
  onLogout,
  onResumeActive,
}: Props) {
  return (
    <>
      <header className="app-header">
        <div className="title-block">
          <span className="badge">IKMC Lớp 1–2</span>
          <h1>{user ? `Xin chào, ${user.displayName}!` : 'Khách chưa đăng nhập'}</h1>
        </div>
        {user ? (
          <div className="actions" style={{ marginTop: 0 }}>
            <button type="button" className="btn btn-prev" onClick={onOpenHistory}>📖 Lịch sử</button>
            <button type="button" className="btn btn-ghost" onClick={onLogout}>Đăng xuất</button>
          </div>
        ) : (
          <button type="button" className="btn btn-submit" onClick={onOpenAuth}>👋 Đăng nhập / Tạo tài khoản</button>
        )}
      </header>

      {activeAttempt && (
        <div className="card resume-banner">
          <div>
            <strong>🕐 Bé đang làm dở một bài thi</strong>
            <p>Còn lại {activeAttempt.remainingLabel} trước khi hết giờ.</p>
          </div>
          <button type="button" className="btn btn-submit" onClick={onResumeActive}>Tiếp tục làm bài</button>
        </div>
      )}

      <div className="card hero">
        <div className="mascot">🦘</div>
        <h1>Luyện Thi Toán Kangaroo</h1>
        <p>
          Sân chơi Toán Quốc tế Kangaroo (IKMC) — Level 1 dành cho học sinh{' '}
          <strong>Lớp 2</strong>. Vừa học vừa chơi, rèn tư duy thật vui!
        </p>

        <div className="info-row">
          <span className="chip">✅ 192 câu đã xác minh</span>
          <span className="chip">⏱️ 75 phút</span>
          <span className="chip">🔒 Chấm điểm server</span>
        </div>

        <div className="mode-grid mt">
          <div
            className="mode-card"
            role="button"
            tabIndex={0}
            onClick={onStartExam}
            onKeyDown={(e) => e.key === 'Enter' && onStartExam()}
          >
            <div className="icon">🏁</div>
            <h3>Thi thử</h3>
            <p>10 đề dựng sẵn hoặc tạo đề ngẫu nhiên riêng, 24 câu, bấm giờ và chấm phía server.</p>
          </div>

          <div
            className="mode-card"
            role="button"
            tabIndex={0}
            onClick={onStartPractice}
            onKeyDown={(e) => e.key === 'Enter' && onStartPractice()}
          >
            <div className="icon">📚</div>
            <h3>Luyện tập</h3>
            <p>Luyện câu thật 2014–2022, biết đúng/sai theo khóa đáp án chính thức.</p>
          </div>

          <div
            className="mode-card"
            role="button"
            tabIndex={0}
            onClick={onOpenLibrary}
            onKeyDown={(e) => e.key === 'Enter' && onOpenLibrary()}
          >
            <div className="icon">🗂️</div>
            <h3>Thư viện đề</h3>
            <p>11 tài liệu, 163 trang và 532 lượt câu hỏi từ năm 2009–2022.</p>
          </div>
        </div>
      </div>
    </>
  );
}
