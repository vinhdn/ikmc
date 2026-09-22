import { useState } from 'react';
import type { AnswerMap, Question } from './types';
import { QUESTION_BANK } from './questions';
import { generateExam } from './scoring';
import Home from './screens/Home';
import ExamScreen from './screens/ExamScreen';
import PracticeScreen from './screens/PracticeScreen';
import ResultsScreen from './screens/ResultsScreen';

type Screen = 'home' | 'exam' | 'practice' | 'results';

export default function App() {
  const [screen, setScreen] = useState<Screen>('home');
  const [examQuestions, setExamQuestions] = useState<Question[]>([]);
  const [examAnswers, setExamAnswers] = useState<AnswerMap>({});

  const startExam = () => {
    setExamQuestions(generateExam(QUESTION_BANK));
    setExamAnswers({});
    setScreen('exam');
  };

  const submitExam = (answers: AnswerMap) => {
    setExamAnswers(answers);
    setScreen('results');
  };

  return (
    <div className="container">
      {screen === 'home' && (
        <Home onStartExam={startExam} onStartPractice={() => setScreen('practice')} />
      )}

      {screen === 'exam' && (
        <ExamScreen
          questions={examQuestions}
          onSubmit={submitExam}
          onQuit={() => setScreen('home')}
        />
      )}

      {screen === 'practice' && <PracticeScreen onHome={() => setScreen('home')} />}

      {screen === 'results' && (
        <ResultsScreen
          questions={examQuestions}
          answers={examAnswers}
          onRestart={startExam}
          onHome={() => setScreen('home')}
        />
      )}
    </div>
  );
}
