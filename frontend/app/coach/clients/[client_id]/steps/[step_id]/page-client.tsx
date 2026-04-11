'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError } from '@/lib/api';
import {
  coachingApi,
  type CoachGoalStep,
  type CoachGoalTreeNode,
  type CoachStepHistoryEntry,
  type CoachingClient,
} from '@/lib/api/coaching';

const PANEL_CLASS = 'rounded-[10px] border border-[#e0ddd6] bg-white';

type CoachClientStepPageProps = {
  clientId: number;
  stepId: string;
};

type LoadedStepState = {
  client: CoachingClient | null;
  goal: CoachGoalTreeNode | null;
  step: CoachGoalStep | null;
  history: CoachStepHistoryEntry[];
};

export default function CoachClientStepPage({ clientId, stepId }: CoachClientStepPageProps) {
  const router = useRouter();
  const [state, setState] = useState<LoadedStepState>({
    client: null,
    goal: null,
    step: null,
    history: [],
  });
  const [titleDraft, setTitleDraft] = useState('');
  const [dueDateDraft, setDueDateDraft] = useState('');
  const [isMilestoneDraft, setIsMilestoneDraft] = useState(false);
  const [milestoneNoteDraft, setMilestoneNoteDraft] = useState('');
  const [commentDraft, setCommentDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [commentSaving, setCommentSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const syncDrafts = useCallback((step: CoachGoalStep | null) => {
    setTitleDraft(step?.text ?? '');
    setDueDateDraft(step?.dueDate ?? '');
    setIsMilestoneDraft(Boolean(step?.isMilestone));
    setMilestoneNoteDraft(step?.milestoneNote ?? '');
  }, []);

  const loadStep = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [clientResult, goalsResult, historyResult] = await Promise.allSettled([
        coachingApi.getCoachClient(clientId),
        coachingApi.getCoachClientGoals(clientId),
        coachingApi.getCoachStepHistory(stepId),
      ]);

      if (clientResult.status === 'rejected') {
        throw clientResult.reason;
      }
      if (goalsResult.status === 'rejected') {
        throw goalsResult.reason;
      }

      const client = clientResult.value;
      const goals = goalsResult.value;
      const history = historyResult.status === 'fulfilled' ? historyResult.value : [];

      let matchedGoal: CoachGoalTreeNode | null = null;
      let matchedStep: CoachGoalStep | null = null;
      for (const goal of goals) {
        const step = goal.steps.find((item) => String(item.id) === String(stepId));
        if (!step) continue;
        matchedGoal = goal;
        matchedStep = step;
        break;
      }

      if (!matchedGoal || !matchedStep) {
        setState({ client, goal: null, step: null, history });
        setError('Шаг не найден.');
        return;
      }

      setState({
        client,
        goal: matchedGoal,
        step: matchedStep,
        history,
      });
      syncDrafts(matchedStep);

      if (historyResult.status === 'rejected') {
        setActionMessage('Историю шага загрузить не удалось.');
      }
    } catch (err) {
      const status = err instanceof ApiError ? err.status : null;
      setError(status === 404 ? 'Шаг не найден.' : 'Не удалось загрузить шаг.');
    } finally {
      setLoading(false);
    }
  }, [clientId, stepId, syncDrafts]);

  useEffect(() => {
    void loadStep();
  }, [loadStep]);

  useEffect(() => {
    if (!actionMessage) return undefined;
    const timeoutId = window.setTimeout(() => setActionMessage(null), 2800);
    return () => window.clearTimeout(timeoutId);
  }, [actionMessage]);

  const step = state.step;
  const goal = state.goal;
  const client = state.client;
  const orderedHistory = useMemo(() => [...state.history].reverse(), [state.history]);

  const stepChanged = useMemo(() => {
    if (!step) return false;
    return (
      titleDraft.trim() !== step.text
      || dueDateDraft !== (step.dueDate ?? '')
      || isMilestoneDraft !== Boolean(step.isMilestone)
      || milestoneNoteDraft !== (step.milestoneNote ?? '')
    );
  }, [dueDateDraft, isMilestoneDraft, milestoneNoteDraft, step, titleDraft]);

  const replaceStepFromResponse = useCallback((steps: CoachGoalStep[]) => {
    if (!goal) return;
    const nextStep = steps.find((item) => String(item.id) === String(stepId)) ?? null;
    setState((current) => ({
      ...current,
      goal: current.goal ? { ...current.goal, steps } : current.goal,
      step: nextStep,
    }));
    if (nextStep) {
      syncDrafts(nextStep);
    }
  }, [goal, stepId, syncDrafts]);

  const refreshHistory = useCallback(async () => {
    const history = await coachingApi.getCoachStepHistory(stepId);
    setState((current) => ({ ...current, history }));
  }, [stepId]);

  const handleSave = async () => {
    if (!goal || !step || saving) return;
    const nextTitle = titleDraft.trim();
    if (!nextTitle) {
      setActionMessage('Введите название шага.');
      return;
    }

    setSaving(true);
    try {
      const response = await coachingApi.updateCoachGoalStep(goal.id, step.id, {
        text: nextTitle,
        dueDate: dueDateDraft || '',
        isMilestone: isMilestoneDraft,
        milestoneNote: milestoneNoteDraft,
      });
      replaceStepFromResponse(response.steps);
      await refreshHistory();
      setActionMessage('Шаг обновлён.');
    } catch {
      setActionMessage('Не удалось сохранить шаг.');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleDone = async () => {
    if (!goal || !step || saving) return;
    setSaving(true);
    try {
      const response = await coachingApi.updateCoachGoalStep(goal.id, step.id, { done: !step.done });
      replaceStepFromResponse(response.steps);
      await refreshHistory();
      setActionMessage(step.done ? 'Шаг возвращён в работу.' : 'Шаг отмечен выполненным.');
    } catch {
      setActionMessage('Не удалось обновить статус шага.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!goal || !step || deleting) return;
    setDeleting(true);
    try {
      await coachingApi.deleteCoachGoalStep(goal.id, step.id);
      router.push(`/coach/clients/${clientId}?tab=session`);
    } catch {
      setActionMessage('Не удалось удалить шаг.');
      setDeleting(false);
    }
  };

  const handleAddComment = async () => {
    const note = commentDraft.trim();
    if (!step || !note || commentSaving) return;

    setCommentSaving(true);
    try {
      const entry = await coachingApi.addCoachStepComment(step.id, note);
      setState((current) => ({ ...current, history: [...current.history, entry] }));
      setCommentDraft('');
      setActionMessage('Комментарий добавлен.');
    } catch {
      setActionMessage('Не удалось добавить комментарий.');
    } finally {
      setCommentSaving(false);
    }
  };

  if (loading) {
    return <div className="min-h-screen bg-[#f5f4f0] p-5 text-[#73726c]">Загрузка шага...</div>;
  }

  if (!step || !goal) {
    return (
      <div className="min-h-screen bg-[#f5f4f0] p-5">
        <div className="mx-auto max-w-[960px] space-y-4">
          <Link href={`/coach/clients/${clientId}?tab=session`} className="text-[13px] text-[#185fa5] hover:underline">
            Вернуться к сессии
          </Link>
          <div className={`${PANEL_CLASS} p-5 text-[14px] text-[#7a3b3b]`}>
            {error || 'Шаг не найден.'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f5f4f0] p-3 text-[#1a1a18] sm:p-5">
      <div className="mx-auto max-w-[1100px] space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <Link href={`/coach/clients/${clientId}?tab=session`} className="text-[13px] text-[#185fa5] hover:underline">
              Вернуться к сессии
            </Link>
            <div className="text-[11px] uppercase tracking-[0.08em] text-[#8b887f]">Редактирование шага</div>
            <div className="text-[24px] font-medium leading-tight">{client?.name || 'Клиент'}</div>
            <div className="text-[13px] text-[#73726c]">{goal.title}</div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void handleToggleDone()}
              disabled={saving}
              className={`rounded-[8px] px-4 py-3 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                step.done
                  ? 'border border-[#d7d2c7] bg-white text-[#5c564e]'
                  : 'bg-[#1D9E75] text-[#E1F5EE]'
              }`}
            >
              {step.done ? 'Вернуть в работу' : 'Отметить выполненным'}
            </button>
            <button
              type="button"
              onClick={() => void handleDelete()}
              disabled={deleting}
              className="rounded-[8px] border border-red-200 bg-white px-3 py-2 text-[12px] text-red-700 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {deleting ? 'Удаление...' : 'Удалить шаг'}
            </button>
          </div>
        </div>

        {error ? (
          <div className="rounded-[8px] border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800">{error}</div>
        ) : null}
        {actionMessage ? (
          <div className="rounded-[8px] border border-[#d7d2c7] bg-white px-3 py-2 text-[12px] text-[#4f4b45]">{actionMessage}</div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
          <div className={`${PANEL_CLASS} p-4 sm:p-5`}>
            <div className="mb-4 text-[16px] font-medium">Параметры шага</div>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-[#5c564e]">Название шага</label>
                <input
                  value={titleDraft}
                  onChange={(event) => setTitleDraft(event.target.value)}
                  className="w-full rounded-[8px] border border-[#d7d2c7] bg-white px-3 py-3 text-[14px] outline-none focus:border-[#185fa5]"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label className="text-[13px] font-medium text-[#5c564e]">Срок</label>
                  <input
                    type="date"
                    value={dueDateDraft}
                    onChange={(event) => setDueDateDraft(event.target.value)}
                    className="w-full rounded-[8px] border border-[#d7d2c7] bg-white px-3 py-3 text-[14px] outline-none focus:border-[#185fa5]"
                    style={{ fontSize: '16px', minHeight: '44px' }}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[13px] font-medium text-[#5c564e]">Статус</label>
                  <div className="rounded-[8px] border border-[#e0ddd6] bg-[#f8f6f1] px-3 py-2 text-[14px] text-[#4f4b45]">
                    {step.done ? 'Выполнен' : 'В работе'}
                  </div>
                </div>
              </div>

              <label className="flex items-center gap-3 rounded-[8px] border border-[#e0ddd6] bg-[#f8f6f1] px-3 py-3 text-[14px] text-[#4f4b45]">
                <input
                  type="checkbox"
                  checked={isMilestoneDraft}
                  onChange={(event) => setIsMilestoneDraft(event.target.checked)}
                  className="h-5 w-5 rounded border-[#c8c3b7]"
                />
                Отмечать этот шаг как веху
              </label>

              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-[#5c564e]">Комментарий к вехе</label>
                <textarea
                  value={milestoneNoteDraft}
                  onChange={(event) => setMilestoneNoteDraft(event.target.value)}
                  rows={4}
                  placeholder="Необязательно"
                  className="w-full rounded-[8px] border border-[#d7d2c7] bg-white px-3 py-3 text-[14px] outline-none focus:border-[#185fa5]"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => void handleSave()}
                  disabled={saving || !stepChanged || !titleDraft.trim()}
                  className="rounded-[8px] bg-[#185fa5] px-4 py-3 text-[13px] text-white transition-colors hover:bg-[#154f89] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving ? 'Сохраняем...' : 'Сохранить'}
                </button>
                <button
                  type="button"
                  onClick={() => syncDrafts(step)}
                  disabled={saving || !stepChanged}
                  className="rounded-[8px] border border-[#d7d2c7] bg-white px-4 py-3 text-[13px] text-[#5c564e] transition-colors hover:bg-[#f8f6f1] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Сбросить
                </button>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className={`${PANEL_CLASS} p-4 sm:p-5`}>
              <div className="mb-3 text-[16px] font-medium">Комментарий</div>
              <div className="space-y-3">
                <textarea
                  value={commentDraft}
                  onChange={(event) => setCommentDraft(event.target.value)}
                  rows={4}
                  placeholder="Добавьте комментарий к задаче"
                  className="w-full rounded-[8px] border border-[#d7d2c7] bg-white px-3 py-3 text-[14px] outline-none focus:border-[#185fa5]"
                />
                <button
                  type="button"
                  onClick={() => void handleAddComment()}
                  disabled={commentSaving || !commentDraft.trim()}
                  className="rounded-[8px] bg-[#1D9E75] px-4 py-3 text-[13px] text-[#E1F5EE] transition-colors hover:bg-[#16805f] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {commentSaving ? 'Добавляем...' : 'Добавить комментарий'}
                </button>
              </div>
            </div>

            <div className={`${PANEL_CLASS} p-4 sm:p-5`}>
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="text-[16px] font-medium">История задачи</div>
                <div className="text-[12px] text-[#8b887f]">{state.history.length}</div>
              </div>

              {orderedHistory.length === 0 ? (
                <div className="text-[13px] text-[#8b887f]">История пока пуста.</div>
              ) : (
                <div className="space-y-3">
                  {orderedHistory.map((entry) => {
                    const isComment = entry.created_by !== 0;
                    return (
                      <div key={entry.id} className="rounded-[8px] border border-[#ece8df] bg-[#faf9f6] px-3 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-[12px] font-medium text-[#1a1a18]">
                              {isComment ? 'Комментарий' : entry.note}
                            </div>
                            <div className="mt-0.5 text-[12px] text-[#8b887f]">
                              {formatHistoryMeta(entry)}
                            </div>
                          </div>
                          {entry.status ? (
                            <div className="rounded-full border border-[#d7d2c7] bg-white px-2 py-1 text-[11px] text-[#5c564e]">
                              {formatTaskStatus(entry.status)}
                            </div>
                          ) : null}
                        </div>
                        {isComment ? (
                          <div className="mt-2 whitespace-pre-wrap text-[14px] leading-[1.5] text-[#4f4b45]">
                            {entry.note}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatHistoryMeta(entry: CoachStepHistoryEntry): string {
  const author = entry.created_by_username?.trim()
    || (entry.created_by < 0 ? 'Клиент' : entry.created_by > 0 ? 'Коуч' : 'Система');
  return `${author} · ${formatDateTime(entry.created_at)}`;
}

function formatTaskStatus(status: string): string {
  switch (status) {
    case 'done':
      return 'Выполнено';
    case 'checked':
      return 'Проверено';
    case 'in_progress':
      return 'В работе';
    case 'open':
      return 'Открыто';
    default:
      return status;
  }
}

function formatDateTime(value: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value));
  } catch {
    return value;
  }
}
