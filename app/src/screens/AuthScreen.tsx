import { useState } from 'react';
import { login, register, type AuthSession } from '../api';

interface Props {
  onAuthed: (session: AuthSession) => void;
  onHome: () => void;
}

export default function AuthScreen({ onAuthed, onHome }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const session = mode === 'login'
        ? await login(username, password)
        : await register(username, password, displayName || undefined);
      onAuthed(session);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể xử lý yêu cầu.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card auth-card">
      <h2 className="center">{mode === 'login' ? '👋 Đăng nhập' : '🌟 Tạo tài khoản mới'}</h2>
      <p className="center practice-subtitle">
        Lưu lại lịch sử làm đề và tiếp tục bài đang làm dở trên mọi thiết bị.
      </p>

      {error && <div className="api-error">⚠️ {error}</div>}

      <form className="auth-form" onSubmit={(event) => void submit(event)}>
        <label htmlFor="auth-username">Tên đăng nhập</label>
        <input
          id="auth-username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="vd: be_na_02"
          autoComplete="username"
          required
          minLength={3}
        />

        {mode === 'register' && (
          <>
            <label htmlFor="auth-display">Tên hiển thị (tuỳ chọn)</label>
            <input
              id="auth-display"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="vd: Bé Na"
            />
          </>
        )}

        <label htmlFor="auth-password">Mật khẩu</label>
        <input
          id="auth-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Tối thiểu 6 ký tự"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          required
          minLength={6}
        />

        <button type="submit" className="btn btn-submit mt" disabled={loading}>
          {loading ? 'Đang xử lý…' : mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}
        </button>
      </form>

      <p className="center mt">
        {mode === 'login' ? (
          <button type="button" className="link-btn" onClick={() => setMode('register')}>
            Chưa có tài khoản? Tạo tài khoản mới
          </button>
        ) : (
          <button type="button" className="link-btn" onClick={() => setMode('login')}>
            Đã có tài khoản? Đăng nhập
          </button>
        )}
      </p>

      <div className="center mt">
        <button type="button" className="link-btn" onClick={onHome}>← Về trang chủ</button>
      </div>
    </div>
  );
}
