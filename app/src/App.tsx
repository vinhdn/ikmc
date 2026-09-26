import { useEffect, useState } from 'react';
import {
  clearStoredAuth,
  getStoredActiveAttempt,
  getStoredAuth,
  logout as apiLogout,
  storeAuth,
  type AuthSession,
  type AuthUser,
  type ServerScoreResult,
} from './api';
import type { AnswerMap, Question } from './types';
import { formatTime } from './components/useCountdown';
import Home from './screens/Home';
import ExamScreen, { type ResumeRequest } from './screens/ExamScreen';
import ExamPickerScreen from './screens/ExamPickerScreen';
import PracticeScreen from './screens/PracticeScreen';
import ResultsScreen from './screens/ResultsScreen';
import ExamLibraryScreen from './screens/ExamLibraryScreen';
import AuthScreen from './screens/AuthScreen';
import HistoryScreen from './screens/HistoryScreen';

type Screen = 'home' | 'picker' | 'exam' | 'practice' | 'results' | 'library' | 'auth' | 'history';

export default function App() {
  const [screen, setScreen] = useState<Screen>('home');
  const [user, setUser] = useState<AuthUser | null>(() => getStoredAuth()?.user ?? null);
  const [examTemplateId, setExamTemplateId] = useState<string | undefined>(undefined);
  const [examResume, setExamResume] = useState<ResumeRequest | undefined>(undefined);
  const [examQuestions, setExamQuestions] = useState<Question[]>([]);
  const [examAnswers, setExamAnswers] = useState<AnswerMap>({});
  const [examResult, setExamResult] = useState<ServerScoreResult | null>(null);
  const [activeAttemptLabel, setActiveAttemptLabel] = useState<string | null>(null);

  useEffect(() => {
    if (screen !== 'home') return;
    const refresh = () => {
      const cached = getStoredActiveAttempt();
      if (!cached) {
        setActiveAttemptLabel(null);
        return;
      }
      const remainingSeconds = Math.max(0, Math.round((Date.parse(cached.expiresAt) - Date.now()) / 1000));
      setActiveAttemptLabel(remainingSeconds > 0 ? formatTime(remainingSeconds) : null);
    };
    refresh();
    const id = setInterval(refresh, 15_000);
    return () => clearInterval(id);
  }, [screen]);

  const startExam = (templateId?: string) => {
    setExamTemplateId(templateId);
    setExamResume(undefined);
    setExamQuestions([]);
    setExamAnswers({});
    setExamResult(null);
    setScreen('exam');
  };

  const resumeActiveAttempt = () => {
    const cached = getStoredActiveAttempt();
    if (!cached) return;
    setExamTemplateId(undefined);
    setExamResume({ attemptId: cached.attemptId, attemptToken: cached.attemptToken });
    setExamQuestions([]);
    setExamAnswers({});
    setExamResult(null);
    setScreen('exam');
  };

  const resumeFromHistory = (request: ResumeRequest) => {
    setExamTemplateId(undefined);
    setExamResume(request);
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

  const handleAuthed = (session: AuthSession) => {
    storeAuth(session);
    setUser(session.user);
    setScreen('home');
  };

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch {
      // token có thể đã hết hạn; vẫn xoá phiên cục bộ.
    }
    clearStoredAuth();
    setUser(null);
    setScreen('home');
  };

  return (
    <div className="container">
      {screen === 'home' && (
        <Home
          user={user}
          activeAttempt={activeAttemptLabel ? { remainingLabel: activeAttemptLabel } : null}
          onStartExam={() => setScreen('picker')}
          onStartPractice={() => setScreen('practice')}
          onOpenLibrary={() => setScreen('library')}
          onOpenHistory={() => setScreen('history')}
          onOpenAuth={() => setScreen('auth')}
          onLogout={() => void handleLogout()}
          onResumeActive={resumeActiveAttempt}
        />
      )}

      {screen === 'picker' && <ExamPickerScreen onStart={startExam} onHome={() => setScreen('home')} />}

      {screen === 'auth' && <AuthScreen onAuthed={handleAuthed} onHome={() => setScreen('home')} />}

      {screen === 'history' && <HistoryScreen onHome={() => setScreen('home')} onResume={resumeFromHistory} />}

      {screen === 'exam' && (
        <ExamScreen
          templateId={examTemplateId}
          resume={examResume}
          onComplete={completeExam}
          onQuit={() => setScreen('home')}
        />
      )}

      {screen === 'practice' && <PracticeScreen onHome={() => setScreen('home')} />}
      {screen === 'library' && <ExamLibraryScreen onHome={() => setScreen('home')} />}

      {screen === 'results' && examResult && (
        <ResultsScreen
          questions={examQuestions}
          answers={examAnswers}
          result={examResult}
          onRestart={() => setScreen('picker')}
          onHome={() => setScreen('home')}
        />
      )}
    </div>
  );
}
