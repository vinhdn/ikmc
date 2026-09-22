interface Props {
  onStartExam: () => void;
  onStartPractice: () => void;
}

export default function Home({ onStartExam, onStartPractice }: Props) {
  return (
    <div className="card hero">
      <div className="mascot">🦘</div>
      <h1>Luyện Thi Toán Kangaroo</h1>
      <p>
        Sân chơi Toán Quốc tế Kangaroo (IKMC) — Level 1 dành cho học sinh{' '}
        <strong>Lớp 2</strong>. Vừa học vừa chơi, rèn tư duy thật vui!
      </p>

      <div className="info-row">
        <span className="chip">📝 24 câu hỏi</span>
        <span className="chip">⏱️ 75 phút</span>
        <span className="chip">🎯 Tối đa 120 điểm</span>
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
          <p>Làm đủ 24 câu, bấm giờ 75 phút, chấm điểm chuẩn Kangaroo.</p>
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
          <p>Làm từng câu, biết ngay đúng/sai và xem lời giải chi tiết.</p>
        </div>
      </div>
    </div>
  );
}
