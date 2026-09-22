import { useState } from 'react';
import type { ServerScoreResult } from './api';
import type { AnswerMap, Question } from './types';
import Home from './screens/Home';
import ExamScreen from './screens/ExamScreen';
import PracticeScreen from './screens/PracticeScreen';
import ResultsScreen from './screens/ResultsScreen';
import ExamLibraryScreen from './screens/ExamLibraryScreen';

type Screen = 'home' | 'exam' | 'practice' | 'results' | 'library';

export default function App() {
  const [screen, setScreen] = useState<Screen>('home');
  const [examQuestions, setExamQuestions] = useState<Question[]>([]);
  const [examAnswers, setExamAnswers] = useState<AnswerMap>({});
  const [examResult, setExamResult] = useState<ServerScoreResult | null>(null);

  const startExam = () => {
    setExamQuestions([]);
    setExamAnswers({});
    setExamResult(null);
    setScreen('exam');
  };

  const completeExam = (questions: Question[], answers: AnswerMap, result: ServerScoreResult) => {
    setExamQuestions(questions);
    setExamAnswers(answers);
    setExamResult(result);
    setScreen('results');
  };

  return (
    <div className="container">
      {screen === 'home' && (
        <Home
          onStartExam={startExam}
          onStartPractice={() => setScreen('practice')}
          onOpenLibrary={() => setScreen('library')}
        />
      )}

      {screen === 'exam' && <ExamScreen onComplete={completeExam} onQuit={() => setScreen('home')} />}
      {screen === 'practice' && <PracticeScreen onHome={() => setScreen('home')} />}
      {screen === 'library' && <ExamLibraryScreen onHome={() => setScreen('home')} />}

      {screen === 'results' && examResult && (
        <ResultsScreen
          questions={examQuestions}
          answers={examAnswers}
          result={examResult}
          onRestart={startExam}
          onHome={() => setScreen('home')}
        />
      )}
    </div>
  );
}
