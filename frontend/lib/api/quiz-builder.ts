import { apiFetch } from '../api';

export type QuizBuilderQuestionType = 'single' | 'multiple' | 'rating' | 'text' | 'date' | 'slider';
export type QuizBuilderScreenKind = 'intro' | 'question' | 'lead' | 'result';
export type QuizResultOperator = 'includes' | 'not_includes' | 'gte' | 'lte' | 'equals';

export type QuizBuilderOption = {
  id?: number | string;
  label: string;
  emoji: string;
  nextScreenId?: number | string | null;
  nextSpecial?: '__lead' | '__end' | null;
};

export type QuizBuilderResultCondition = {
  id?: number | string;
  screenId: number | string;
  operator: QuizResultOperator;
  value: string[];
};

export type QuizBuilderResultRule = {
  id?: number | string;
  position?: number;
  conditions: QuizBuilderResultCondition[];
};

export type QuizBuilderScreen = {
  id?: number | string;
  kind: QuizBuilderScreenKind;
  title: string;
  subtitle: string;
  questionType?: QuizBuilderQuestionType | null;
  options?: QuizBuilderOption[];
  placeholder?: string | null;
  minVal?: number | null;
  maxVal?: number | null;
  maxRating?: number | null;
  required?: boolean;
  isDefaultResult?: boolean;
  rules?: QuizBuilderResultRule[];
};

export type QuizBuilderPayload = {
  id: number;
  title: string;
  accentColor: string;
  isPublished: boolean;
  screens: QuizBuilderScreen[];
};

export type PublicQuizAnswerPayload = {
  screenId: number;
  valueText?: string | null;
  valueNumber?: number | null;
  valueOptions?: number[] | null;
};

export type PublicQuizSubmitPayload = {
  name?: string;
  phone?: string;
  email?: string;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  answers: PublicQuizAnswerPayload[];
};

export type PublicQuizSubmitResponse = {
  ok: boolean;
  quiz_id: number;
  contact_id: number;
  answers_stored: number;
  facts_added: number;
};

export const quizBuilderApi = {
  getCurrent: async (): Promise<QuizBuilderPayload> => {
    return apiFetch<QuizBuilderPayload>('/quiz-builder/current/');
  },

  saveCurrent: async (payload: Omit<QuizBuilderPayload, 'id'>): Promise<QuizBuilderPayload> => {
    return apiFetch<QuizBuilderPayload>('/quiz-builder/current/', {
      method: 'PUT',
      body: payload,
    });
  },

  getPublic: async (quizId: number | string): Promise<QuizBuilderPayload> => {
    return apiFetch<QuizBuilderPayload>(`/public/quiz/${quizId}/`);
  },

  submitPublic: async (
    quizId: number | string,
    payload: PublicQuizSubmitPayload
  ): Promise<PublicQuizSubmitResponse> => {
    return apiFetch<PublicQuizSubmitResponse>(`/public/quiz/${quizId}/submit/`, {
      method: 'POST',
      body: payload,
    });
  },
};
