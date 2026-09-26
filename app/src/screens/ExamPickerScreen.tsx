import { useEffect, useState } from 'react';
import { getExamTemplates, type ExamTemplate } from '../api';

interface Props {
  onStart: (templateId?: string) => void;
  onHome: () => void;
}

export default function ExamPickerScreen({ onStart, onHome }: Props) {
  const [templates, setTemplates] = useState<ExamTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getExamTemplates()
      .then(setTemplates)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Không tải được danh sách đề.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <header className="app-header">
        <div className="title-block">
          <span className="badge">Thi thử · 24 câu · 75 phút</span>
          <h1>Chọn đề để bắt đầu</h1>
        </div>
        <button type="button" className="btn btn-prev" onClick={onHome}>🏠 Trang chủ</button>
      </header>

      {error && <div className="api-error">⚠️ {error}</div>}

      <div className="card custom-exam-card">
        <div className="icon">🎲</div>
        <div>
          <h3>Tạo đề ngẫu nhiên riêng</h3>
          <p>Bốc ngẫu nhiên 8 câu mỗi phần A/B/C từ toàn bộ ngân hàng đã kiểm duyệt — mỗi lần một đề khác nhau.</p>
        </div>
        <button type="button" className="btn btn-submit" onClick={() => onStart(undefined)}>Tạo đề mới</button>
      </div>

      {loading ? (
        <div className="card center"><div className="library-status">🦘</div><h2>Đang tải danh sách đề…</h2></div>
      ) : (
        <div className="template-grid">
          {templates.map((template) => (
            <div className="template-card" key={template.id}>
              <span className="template-index">Đề {template.position}</span>
              <h3>{template.title}</h3>
              <p>24 câu · dựng sẵn, giống nhau cho mọi lượt luyện tập</p>
              <button type="button" className="btn btn-next" onClick={() => onStart(template.id)}>Bắt đầu</button>
            </div>
          ))}
        </div>
      )}

      <div className="center mt"><button type="button" className="link-btn" onClick={onHome}>← Về trang chủ</button></div>
    </>
  );
}
