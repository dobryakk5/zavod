'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { ApiError } from '@/lib/api';
import {
  quizBuilderApi,
  type QuizBuilderPayload,
  type QuizBuilderScreen,
  type PublicQuizSubmitResponse,
} from '@/lib/api/quiz-builder';

type QuestionAnswer = {
  text?: string;
  number?: number;
  options?: number[];
};

function isAnswerFilled(answer: QuestionAnswer | undefined, screen: QuizBuilderScreen): boolean {
  if (!answer) return false;
  const questionType = screen.questionType;
  if (questionType === 'single' || questionType === 'multiple') {
    return Array.isArray(answer.options) && answer.options.length > 0;
  }
  if (questionType === 'rating' || questionType === 'slider') {
    return typeof answer.number === 'number' && Number.isFinite(answer.number);
  }
  return Boolean((answer.text || '').trim());
}

export default function QuizPublicClient() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const quizId = Number(params.id);

  const [quiz, setQuiz] = useState<QuizBuilderPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [started, setStarted] = useState(false);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [leadSubmitted, setLeadSubmitted] = useState<PublicQuizSubmitResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [answers, setAnswers] = useState<Record<number, QuestionAnswer>>({});
  const [leadName, setLeadName] = useState('');
  const [leadPhone, setLeadPhone] = useState('');
  const [leadEmail, setLeadEmail] = useState('');

  const loadQuiz = useCallback(async () => {
    if (!Number.isFinite(quizId) || quizId <= 0) {
      setError('Некорректный id квиза.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await quizBuilderApi.getPublic(quizId);
      setQuiz(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError('Квиз не найден или еще не опубликован.');
      } else {
        setError('Не удалось загрузить квиз.');
      }
    } finally {
      setLoading(false);
    }
  }, [quizId]);

  useEffect(() => {
    void loadQuiz();
  }, [loadQuiz]);

  const introScreen = useMemo(
    () => quiz?.screens.find((screen) => screen.kind === 'intro') || null,
    [quiz]
  );

  const questionScreens = useMemo(
    () => (quiz?.screens || []).filter((screen) => screen.kind === 'question'),
    [quiz]
  );

  const leadScreen = useMemo(
    () => quiz?.screens.find((screen) => screen.kind === 'lead') || null,
    [quiz]
  );

  const resultScreen = useMemo(
    () => quiz?.screens.find((screen) => screen.kind === 'result') || null,
    [quiz]
  );

  const currentQuestion = questionScreens[questionIndex] || null;
  const currentQuestionId = Number(currentQuestion?.id || 0);
  const currentAnswer = currentQuestionId ? answers[currentQuestionId] : undefined;
  const currentRequired = Boolean(currentQuestion?.required);
  const canGoNextQuestion = !currentQuestion || !currentRequired || isAnswerFilled(currentAnswer, currentQuestion);

  const accentColor = quiz?.accentColor || '#5b5ef4';

  const updateAnswer = (screenId: number, patch: Partial<QuestionAnswer>) => {
    setAnswers((prev) => ({
      ...prev,
      [screenId]: {
        ...prev[screenId],
        ...patch,
      },
    }));
  };

  const toggleOption = (screenId: number, optionId: number, multiple: boolean) => {
    setAnswers((prev) => {
      const prevOptions = Array.isArray(prev[screenId]?.options) ? prev[screenId]?.options : [];
      let nextOptions: number[];

      if (!multiple) {
        nextOptions = [optionId];
      } else if (prevOptions.includes(optionId)) {
        nextOptions = prevOptions.filter((id) => id !== optionId);
      } else {
        nextOptions = [...prevOptions, optionId];
      }

      return {
        ...prev,
        [screenId]: {
          ...prev[screenId],
          options: nextOptions,
        },
      };
    });
  };

  const handleSubmitLead = async () => {
    if (!quiz) return;

    const name = leadName.trim();
    const phone = leadPhone.trim();
    const email = leadEmail.trim();
    if (!name && !phone && !email) {
      toast.error('Укажите хотя бы имя, телефон или email.');
      return;
    }

    const serializedAnswers = questionScreens
      .map((screen) => {
        const screenId = Number(screen.id);
        if (!Number.isFinite(screenId) || screenId <= 0) {
          return null;
        }

        const answer = answers[screenId];
        if (!isAnswerFilled(answer, screen)) {
          return null;
        }

        const questionType = screen.questionType;
        if (questionType === 'single' || questionType === 'multiple') {
          return {
            screenId,
            valueOptions: answer?.options || [],
          };
        }
        if (questionType === 'rating' || questionType === 'slider') {
          return {
            screenId,
            valueNumber: answer?.number ?? null,
          };
        }
        return {
          screenId,
          valueText: answer?.text || '',
        };
      })
      .filter((item): item is NonNullable<typeof item> => item !== null);

    setSubmitting(true);
    try {
      const response = await quizBuilderApi.submitPublic(quiz.id, {
        name: name || undefined,
        phone: phone || undefined,
        email: email || undefined,
        utm_source: searchParams.get('utm_source'),
        utm_medium: searchParams.get('utm_medium'),
        utm_campaign: searchParams.get('utm_campaign'),
        answers: serializedAnswers,
      });
      setLeadSubmitted(response);
      toast.success('Спасибо! Ответы отправлены.');
    } catch {
      toast.error('Не удалось отправить квиз. Попробуйте еще раз.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="mx-auto max-w-2xl p-8 text-center text-sm text-muted-foreground">Загрузка квиза...</div>;
  }

  if (error || !quiz) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <Card>
          <CardHeader>
            <CardTitle>Квиз недоступен</CardTitle>
            <CardDescription>{error || 'Попробуйте открыть ссылку позже.'}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const totalSteps = questionScreens.length + (leadScreen ? 1 : 0);
  const currentStep = Math.min(totalSteps, questionIndex + 1);

  return (
    <div className="min-h-screen bg-slate-50 py-8 px-4">
      <div className="mx-auto w-full max-w-2xl">
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <div className="mb-3 h-1.5 w-full rounded-full bg-slate-100">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: totalSteps > 0 ? `${Math.round((currentStep / totalSteps) * 100)}%` : '0%',
                  backgroundColor: accentColor,
                }}
              />
            </div>
            <CardTitle>{quiz.title}</CardTitle>
            {totalSteps > 0 ? (
              <CardDescription>
                Шаг {currentStep} из {totalSteps}
              </CardDescription>
            ) : null}
          </CardHeader>

          <CardContent className="space-y-5">
            {!started && introScreen ? (
              <div className="space-y-4">
                <h2 className="text-xl font-semibold">{introScreen.title || quiz.title}</h2>
                {introScreen.subtitle ? <p className="text-muted-foreground">{introScreen.subtitle}</p> : null}
                <Button onClick={() => setStarted(true)} style={{ backgroundColor: accentColor }}>
                  Начать
                </Button>
              </div>
            ) : leadSubmitted ? (
              <div className="space-y-4">
                <h2 className="text-xl font-semibold">{resultScreen?.title || 'Спасибо за ответы!'}</h2>
                <p className="text-muted-foreground">
                  {resultScreen?.subtitle || 'Мы получили ваши ответы и скоро свяжемся с вами.'}
                </p>
              </div>
            ) : currentQuestion ? (
              <div className="space-y-4">
                <h2 className="text-xl font-semibold">{currentQuestion.title}</h2>
                {currentQuestion.subtitle ? <p className="text-muted-foreground">{currentQuestion.subtitle}</p> : null}

                {(currentQuestion.questionType === 'single' || currentQuestion.questionType === 'multiple') && (
                  <div className="grid gap-2">
                    {(currentQuestion.options || []).map((option) => {
                      const optionId = Number(option.id);
                      const selected = Boolean(
                        Number.isFinite(optionId) &&
                          optionId > 0 &&
                          Array.isArray(currentAnswer?.options) &&
                          currentAnswer?.options?.includes(optionId)
                      );

                      return (
                        <button
                          key={String(option.id)}
                          type="button"
                          className={`rounded-lg border px-4 py-3 text-left transition ${
                            selected ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white hover:bg-slate-100'
                          }`}
                          onClick={() => {
                            if (!Number.isFinite(optionId) || optionId <= 0) return;
                            toggleOption(currentQuestionId, optionId, currentQuestion.questionType === 'multiple');
                          }}
                        >
                          <span className="mr-2">{option.emoji || '•'}</span>
                          {option.label || 'Вариант'}
                        </button>
                      );
                    })}
                  </div>
                )}

                {currentQuestion.questionType === 'text' && (
                  <Input
                    value={currentAnswer?.text || ''}
                    onChange={(event) => updateAnswer(currentQuestionId, { text: event.target.value })}
                    placeholder={currentQuestion.placeholder || 'Введите ответ'}
                  />
                )}

                {currentQuestion.questionType === 'date' && (
                  <Input
                    type="date"
                    value={currentAnswer?.text || ''}
                    onChange={(event) => updateAnswer(currentQuestionId, { text: event.target.value })}
                  />
                )}

                {currentQuestion.questionType === 'rating' && (
                  <div className="flex flex-wrap gap-2">
                    {Array.from({ length: currentQuestion.maxRating || 5 }).map((_, idx) => {
                      const value = idx + 1;
                      const selected = currentAnswer?.number === value;
                      return (
                        <button
                          key={value}
                          type="button"
                          className={`h-10 w-10 rounded-full border text-sm font-semibold ${
                            selected ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 bg-white hover:bg-slate-100'
                          }`}
                          onClick={() => updateAnswer(currentQuestionId, { number: value })}
                        >
                          {value}
                        </button>
                      );
                    })}
                  </div>
                )}

                {currentQuestion.questionType === 'slider' && (
                  <div className="space-y-2">
                    <Input
                      type="range"
                      min={currentQuestion.minVal ?? 0}
                      max={currentQuestion.maxVal ?? 100}
                      value={currentAnswer?.number ?? currentQuestion.minVal ?? 0}
                      onChange={(event) => updateAnswer(currentQuestionId, { number: Number(event.target.value) })}
                    />
                    <div className="text-sm text-muted-foreground">
                      Значение: {currentAnswer?.number ?? currentQuestion.minVal ?? 0}
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={questionIndex === 0}
                    onClick={() => setQuestionIndex((prev) => Math.max(0, prev - 1))}
                  >
                    Назад
                  </Button>
                  <Button
                    type="button"
                    style={{ backgroundColor: accentColor }}
                    disabled={!canGoNextQuestion}
                    onClick={() => {
                      if (questionIndex < questionScreens.length - 1) {
                        setQuestionIndex((prev) => prev + 1);
                        return;
                      }
                      if (leadScreen) {
                        setQuestionIndex((prev) => prev + 1);
                      } else {
                        void handleSubmitLead();
                      }
                    }}
                  >
                    {questionIndex < questionScreens.length - 1 ? 'Далее' : leadScreen ? 'Контакты' : 'Отправить'}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <h2 className="text-xl font-semibold">{leadScreen?.title || 'Оставьте контакты'}</h2>
                {leadScreen?.subtitle ? <p className="text-muted-foreground">{leadScreen.subtitle}</p> : null}

                <div className="space-y-2">
                  <Label htmlFor="lead-name">Имя</Label>
                  <Input id="lead-name" value={leadName} onChange={(event) => setLeadName(event.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lead-phone">Телефон</Label>
                  <Input id="lead-phone" value={leadPhone} onChange={(event) => setLeadPhone(event.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lead-email">Email</Label>
                  <Input id="lead-email" type="email" value={leadEmail} onChange={(event) => setLeadEmail(event.target.value)} />
                </div>

                <div className="flex items-center justify-between pt-2">
                  {questionScreens.length > 0 ? (
                    <Button type="button" variant="outline" onClick={() => setQuestionIndex((prev) => Math.max(0, prev - 1))}>
                      Назад
                    </Button>
                  ) : (
                    <span />
                  )}
                  <Button type="button" style={{ backgroundColor: accentColor }} disabled={submitting} onClick={() => void handleSubmitLead()}>
                    {submitting ? 'Отправка...' : 'Получить результат'}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
