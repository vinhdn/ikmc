import { useEffect, useMemo, useState } from 'react';
import {
  EXAM_KIND_LABELS,
  loadExamLibrary,
  type ExamDocument,
  type ExamLibraryIndex,
} from '../examLibrary';

interface Props {
  onHome: () => void;
}

function normalize(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('vi');
}

function excerpt(text: string, query: string): string {
  const clean = text.replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim();
  const at = normalize(clean).indexOf(normalize(query));
  const start = Math.max(0, at < 0 ? 0 : at - 90);
  const value = clean.slice(start, start + 260);
  return `${start > 0 ? '…' : ''}${value}${start + 260 < clean.length ? '…' : ''}`;
}

export default function ExamLibraryScreen({ onHome }: Props) {
  const [library, setLibrary] = useState<ExamLibraryIndex | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<ExamDocument | null>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    loadExamLibrary().then(setLibrary).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : 'Không tải được thư viện đề');
    });
  }, []);

  const matches = useMemo(() => {
    if (!library) return [];
    const needle = normalize(query.trim());
    return library.documents
      .map((document) => {
        const titleMatch = needle !== '' && normalize(document.title).includes(needle);
        const pages = needle === ''
          ? []
          : document.pages.filter((item) => normalize(item.text).includes(needle));
        return { document, pages, titleMatch };
      })
      .filter((item) => query.trim() === '' || item.titleMatch || item.pages.length > 0)
      .sort((a, b) => {
        if (a.document.kind === 'collection') return -1;
        if (b.document.kind === 'collection') return 1;
        if (a.document.kind === 'practice') return -1;
        if (b.document.kind === 'practice') return 1;
        return (b.document.year ?? 0) - (a.document.year ?? 0);
      });
  }, [library, query]);

  const openDocument = (document: ExamDocument, targetPage = 1) => {
    setSelected(document);
    setPage(targetPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (error) {
    return (
      <div className="card center">
        <div className="library-status">⚠️</div>
        <h2>Không tải được thư viện</h2>
        <p className="library-muted">{error}</p>
        <button type="button" className="btn btn-prev mt" onClick={onHome}>Về trang chủ</button>
      </div>
    );
  }

  if (!library) {
    return (
      <div className="card center">
        <div className="library-status">🦘</div>
        <h2>Đang tải thư viện đề…</h2>
      </div>
    );
  }

  if (selected) {
    const currentText = selected.pages[page - 1]?.text ?? '';
    return (
      <>
        <header className="app-header library-header">
          <div className="title-block">
            <span className="badge">{EXAM_KIND_LABELS[selected.kind]}</span>
            <h1>{selected.title}</h1>
          </div>
          <button type="button" className="btn btn-prev" onClick={() => setSelected(null)}>
            ← Danh sách đề
          </button>
        </header>

        <div className="card viewer-toolbar">
          <label htmlFor="exam-page">Trang</label>
          <button
            type="button"
            className="page-arrow"
            disabled={page === 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            aria-label="Trang trước"
          >
            ←
          </button>
          <select
            id="exam-page"
            value={page}
            onChange={(event) => setPage(Number(event.target.value))}
          >
            {selected.pages.map((item) => (
              <option key={item.page} value={item.page}>
                {item.page} / {selected.pageCount}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="page-arrow"
            disabled={page === selected.pageCount}
            onClick={() => setPage((value) => Math.min(selected.pageCount, value + 1))}
            aria-label="Trang tiếp theo"
          >
            →
          </button>
          <span className="viewer-spacer" />
          <a className="btn btn-ghost viewer-link" href={`${selected.pdfUrl}#page=${page}`} target="_blank" rel="noreferrer">
            Mở toàn màn hình
          </a>
          <a className="btn btn-next viewer-link" href={selected.pdfUrl} download>
            Tải PDF
          </a>
        </div>

        <div className="pdf-frame-card">
          <iframe
            key={`${selected.id}-${page}`}
            className="pdf-frame"
            src={`${selected.pdfUrl}#page=${page}&view=FitH`}
            title={`${selected.title}, trang ${page}`}
          />
          <p className="pdf-fallback">
            Nếu trình duyệt không hiển thị PDF,{' '}
            <a href={`${selected.pdfUrl}#page=${page}`} target="_blank" rel="noreferrer">mở tài liệu tại đây</a>.
          </p>
        </div>

        {currentText && (
          <details className="card extracted-text">
            <summary>🔎 Văn bản trích xuất · Trang {page}</summary>
            <pre>{currentText}</pre>
            <small>
              Văn bản dùng để tìm kiếm; hãy đối chiếu bản PDF khi có công thức hoặc hình ảnh.
            </small>
          </details>
        )}
      </>
    );
  }

  return (
    <>
      <header className="app-header library-header">
        <div className="title-block">
          <span className="badge">Thư viện IKMC Lớp 1–2</span>
          <h1>Toàn bộ đề &amp; tài liệu ôn tập</h1>
        </div>
        <button type="button" className="btn btn-prev" onClick={onHome}>🏠 Trang chủ</button>
      </header>

      <div className="card library-summary">
        <div><strong>{library.documentCount}</strong><span>tài liệu PDF</span></div>
        <div><strong>{library.questionCount}</strong><span>lượt câu hỏi</span></div>
        <div><strong>{library.pageCount}</strong><span>trang đã lập chỉ mục</span></div>
      </div>

      <div className="card search-card">
        <label htmlFor="exam-search">Tìm trong toàn bộ đề</label>
        <div className="search-box">
          <span>🔎</span>
          <input
            id="exam-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ví dụ: ladybug, tam giác, đồng hồ, 2020…"
          />
          {query && <button type="button" onClick={() => setQuery('')} aria-label="Xóa tìm kiếm">×</button>}
        </div>
        {query && <p className="search-count">Tìm thấy trong {matches.length} tài liệu</p>}
      </div>

      <div className="exam-grid">
        {matches.map(({ document, pages }) => (
          <article className="exam-doc-card" key={document.id}>
            <button type="button" className="cover-button" onClick={() => openDocument(document)}>
              <img src={document.coverUrl} alt={`Bìa ${document.title}`} loading="lazy" />
            </button>
            <div className="exam-doc-body">
              <span className={`doc-kind ${document.kind}`}>{EXAM_KIND_LABELS[document.kind]}</span>
              <h2>{document.title}</h2>
              <p>{document.language} · {document.questionCount} câu · {document.pageCount} trang</p>
              {query && pages.length > 0 && (
                <button type="button" className="search-hit" onClick={() => openDocument(document, pages[0].page)}>
                  <strong>Trang {pages[0].page}</strong>: {excerpt(pages[0].text, query)}
                  {pages.length > 1 && <em>+ {pages.length - 1} trang phù hợp</em>}
                </button>
              )}
              <div className="doc-actions">
                <button type="button" className="btn btn-next" onClick={() => openDocument(document, pages[0]?.page ?? 1)}>
                  Xem đề
                </button>
                <a href={document.pdfUrl} download className="btn btn-ghost viewer-link">Tải PDF</a>
              </div>
            </div>
          </article>
        ))}
      </div>

      {matches.length === 0 && (
        <div className="card center">
          <div className="library-status">🔍</div>
          <h2>Không tìm thấy nội dung phù hợp</h2>
          <button type="button" className="link-btn mt" onClick={() => setQuery('')}>Xem toàn bộ tài liệu</button>
        </div>
      )}
    </>
  );
}
