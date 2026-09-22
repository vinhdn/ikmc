import type { OptionKey, Question } from '../types';
import { TOPIC_EMOJI, TOPIC_LABELS, sectionLabel } from '../types';

interface Props {
  question: Question;
  index: number;
  total: number;
  selected: OptionKey | undefined;
  onSelect: (key: OptionKey) => void;
  /** Chế độ luyện tập: hiển thị đúng/sai + lời giải ngay. */
  reveal?: boolean;
}

export default function QuestionCard({
  question,
  index,
  total,
  selected,
  onSelect,
  reveal = false,
}: Props) {
  return (
    <div className="card">
      <div className="q-topbar">
        <span className="q-index">
          Câu {index + 1} / {total}
        </span>
        <span style={{ display: 'flex', gap: 8 }}>
          <span className="topic-tag">
            {TOPIC_EMOJI[question.topic]} {TOPIC_LABELS[question.topic]}
          </span>
          <span className="points-tag">{sectionLabel(question.points)}</span>
        </span>
      </div>

      {question.visual && <div className="q-visual">{question.visual}</div>}
      <div className="q-text">{question.text}</div>

      <div className="options-grid">
        {question.options.map((opt) => {
          let cls = 'option-btn';
          if (reveal) {
            if (opt.key === question.correct) cls += ' correct';
            else if (opt.key === selected) cls += ' wrong';
          } else if (selected === opt.key) {
            cls += ' selected';
          }
          return (
            <button
              key={opt.key}
              type="button"
              className={cls}
              disabled={reveal}
              onClick={() => onSelect(opt.key)}
            >
              <span className="opt-circle">{opt.key}</span>
              <span>{opt.text}</span>
            </button>
          );
        })}
      </div>

      {reveal && (
        <>
          <div className="explanation-box">
            <h4>💡 Hướng dẫn giải</h4>
            <ol>
              {question.explanation.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </div>
          {question.takeaway && (
            <div className="takeaway">🌟 Mẹo: {question.takeaway}</div>
          )}
        </>
      )}
    </div>
  );
}
