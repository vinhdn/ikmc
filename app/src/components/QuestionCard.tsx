import type { OptionKey, Question } from '../types';
import { TOPIC_EMOJI, TOPIC_LABELS, sectionLabel } from '../types';

interface Props {
  question: Question;
  index: number;
  total: number;
  selected: OptionKey | undefined;
  onSelect: (key: OptionKey) => void;
  reveal?: boolean;
  correctOption?: OptionKey;
  explanation?: string[];
}

export default function QuestionCard({
  question,
  index,
  total,
  selected,
  onSelect,
  reveal = false,
  correctOption,
  explanation,
}: Props) {
  const answer = correctOption ?? question.correct;
  const solution = explanation ?? question.explanation;

  return (
    <div className="card">
      <div className="q-topbar">
        <span className="q-index">
          Câu {index + 1} / {total}
          {question.year && question.sourceQuestionNumber
            ? ` · Đề ${question.year}, câu ${question.sourceQuestionNumber}`
            : ''}
        </span>
        <span className="q-tags">
          {question.origin === 'ai' && <span className="ai-chip">AI generate</span>}
          <span className="topic-tag">
            {TOPIC_EMOJI[question.topic]} {TOPIC_LABELS[question.topic]}
          </span>
          <span className="points-tag">{sectionLabel(question.points)}</span>
        </span>
      </div>

      {question.visual && <div className="q-visual">{question.visual}</div>}
      {question.imageUrl ? (
        <>
          <img className="question-scan" src={question.imageUrl} alt={question.textVi ?? question.text} />
          <div className="bilingual-question">
            {question.textVi && (
              <section className="language-block vi">
                <span className="language-label">🇻🇳 Tiếng Việt</span>
                <p>{question.textVi}</p>
              </section>
            )}
            {question.textEn && (
              <details className="language-block en">
                <summary>🇬🇧 English · Nguyên văn</summary>
                <p>{question.textEn}</p>
              </details>
            )}
          </div>
        </>
      ) : (
        <div className="bilingual-question">
          {question.textVi && (
            <section className="language-block vi">
              <span className="language-label">🇻🇳 Tiếng Việt</span>
              <p>{question.textVi}</p>
            </section>
          )}
          <section className="language-block en">
            <span className="language-label">🇬🇧 English</span>
            <p>{question.textEn ?? question.text}</p>
          </section>
        </div>
      )}

      {/* Official scans already show option content inside the image, so only the letter is shown.
          AI-generated questions draw the figure only; their option text must stay visible. */}
      <div className={`options-grid scan-answer-grid${question.origin === 'ai' ? ' show-option-text' : ''}`}>
        {question.options.map((option) => {
          let className = 'option-btn';
          if (reveal) {
            if (option.key === answer) className += ' correct';
            else if (option.key === selected) className += ' wrong';
          } else if (selected === option.key) {
            className += ' selected';
          }
          return (
            <button
              key={option.key}
              type="button"
              className={className}
              disabled={reveal}
              onClick={() => onSelect(option.key)}
            >
              <span className="opt-circle">{option.key}</span>
              <span>{option.text}</span>
              {option.imageUrl && <img src={option.imageUrl} alt={`Phương án ${option.key}`} />}
            </button>
          );
        })}
      </div>

      {reveal && answer && (
        <>
          <div className="explanation-box">
            <h4>{question.origin === 'ai' ? `✅ Đáp án đúng: ${answer}` : `✅ Đáp án đã xác minh: ${answer}`}</h4>
            {solution.length > 0 ? (
              <>
              {question.origin === 'ai' && <p className="solution-label">Hướng dẫn giải:</p>}
              <ol>
                {solution.map((step, index) => <li key={index}>{step}</li>)}
              </ol>
              </>
            ) : (
              <p>Đáp án được đối chiếu từ khóa đáp án chính thức của kỳ thi.</p>
            )}
          </div>
          {question.takeaway && <div className="takeaway">🌟 Mẹo: {question.takeaway}</div>}
        </>
      )}
    </div>
  );
}
