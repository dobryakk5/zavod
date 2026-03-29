'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ApiError, apiFetch } from '@/lib/api';
import type { CoachGoalStep } from '@/lib/api/coaching';

type StepsByGoal = {
  goalId: string;
  goalTitle: string;
  steps: CoachGoalStep[];
};

type PublicStepsResponse = {
  contact_id?: number;
  items?: CoachGoalStep[];
};

type PublicTasksPageClientProps = {
  resolvedClientId?: number;
  useCustomDomainPaths?: boolean;
};

export default function PublicTasksPage({
  resolvedClientId,
  useCustomDomainPaths = false,
}: PublicTasksPageClientProps = {}) {
  const { client_id: rawClientId } = useParams<{ client_id?: string }>();
  const pageClientId = resolvedClientId ?? Number(rawClientId);
  const publicRootPath = useCustomDomainPaths ? '/' : `/c/${pageClientId}`;

  const [steps, setSteps] = useState<CoachGoalStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState<string | null>(null);
  const [showDone, setShowDone] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
      setError('Некорректный идентификатор клиента.');
      setLoading(false);
      return;
    }

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<PublicStepsResponse | CoachGoalStep[]>(`/public/client-page/${pageClientId}/steps/`);
        const items = Array.isArray(data) ? data : data.items ?? [];
        setSteps(items);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setSteps([]);
        } else if (err instanceof ApiError && err.status === 401) {
          setError('Войдите через Telegram, VK или email, чтобы увидеть задания.');
        } else {
          setError('Не удалось загрузить задания.');
        }
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [pageClientId]);

  async function handleToggle(step: CoachGoalStep) {
    if (completing) {
      return;
    }

    setCompleting(step.id);
    try {
      const updated = await apiFetch<CoachGoalStep>(`/public/client-page/${pageClientId}/steps/${step.id}/`, {
        method: 'PATCH',
        body: { done: !step.done },
      });
      setSteps((prev) => prev.map((item) => (item.id === step.id ? { ...item, ...updated } : item)));
    } catch {
      setError('Не удалось обновить статус задания.');
    } finally {
      setCompleting(null);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-8 w-40 rounded-lg bg-[#ece7dd]" />
          <div className="h-20 rounded-lg bg-[#ece7dd]" />
          <div className="h-20 rounded-lg bg-[#ece7dd]" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-6">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
        <Link href={publicRootPath} className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-[#f5f4f0]">
          На главную
        </Link>
      </div>
    );
  }

  const activeSteps = steps.filter((step) => !step.done);
  const doneSteps = steps.filter((step) => step.done);
  const visible = showDone ? steps : activeSteps;

  const byGoal = visible.reduce<StepsByGoal[]>((acc, step) => {
    const goalId = step.goalId ?? 'no-goal';
    const goalTitle = step.goalTitle ?? 'Задания';
    const existing = acc.find((group) => group.goalId === goalId);
    if (existing) {
      existing.steps.push(step);
    } else {
      acc.push({ goalId, goalTitle, steps: [step] });
    }
    return acc;
  }, []);

  byGoal.forEach((group) => {
    group.steps.sort((a, b) => {
      if (a.dueDate && b.dueDate) return new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime();
      if (a.dueDate) return -1;
      if (b.dueDate) return 1;
      return 0;
    });
  });

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-medium text-[#1a1a18]">Задания</h1>
          <p className="text-[12px] text-[#73726c]">
            {activeSteps.length} активных
            {doneSteps.length > 0 ? ` · ${doneSteps.length} выполнено` : ''}
          </p>
        </div>
        {doneSteps.length > 0 ? (
          <button
            type="button"
            onClick={() => setShowDone((current) => !current)}
            className="text-[11px] text-[#73726c] hover:text-[#1a1a18]"
          >
            {showDone ? 'Скрыть выполненные' : 'Показать выполненные'}
          </button>
        ) : null}
      </div>

      {steps.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#e0ddd6] p-8 text-center">
          <p className="text-[14px] font-medium text-[#1a1a18]">Заданий пока нет</p>
          <p className="mt-1 text-[12px] text-[#73726c]">Коуч добавит задания во время сессии</p>
        </div>
      ) : activeSteps.length === 0 && !showDone ? (
        <div className="rounded-xl border border-[#eaf3de] bg-[#eaf3de] p-6 text-center">
          <p className="text-[14px] font-medium text-[#3b6d11]">Все задания выполнены</p>
          <button
            type="button"
            onClick={() => setShowDone(true)}
            className="mt-2 text-[12px] text-[#3b6d11] underline"
          >
            Посмотреть выполненные
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {byGoal.map((group) => (
            <div key={group.goalId}>
              <div className="mb-2 flex items-center gap-2">
                <div className="h-px flex-1 bg-[#e0ddd6]" />
                <span className="text-[11px] font-medium text-[#73726c]">{group.goalTitle}</span>
                <div className="h-px flex-1 bg-[#e0ddd6]" />
              </div>

              <div className="space-y-2">
                {group.steps.map((step) => {
                  const isOverdue = !step.done && step.dueDate && new Date(step.dueDate).getTime() < Date.now();
                  return (
                    <button
                      key={step.id}
                      type="button"
                      onClick={() => void handleToggle(step)}
                      disabled={completing === step.id}
                      className={`flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors disabled:cursor-wait ${
                        step.done ? 'border-[#e0ddd6] bg-white opacity-60' : 'border-[#e0ddd6] bg-white hover:border-[#b4b2a9]'
                      }`}
                    >
                      <div
                        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
                          step.done ? 'border-[#1D9E75] bg-[#1D9E75]' : 'border-[#d3d1c7] hover:border-[#1D9E75]'
                        }`}
                      >
                        {step.done ? (
                          <svg width="9" height="9" viewBox="0 0 10 10" aria-hidden="true">
                            <path d="M2 5l2.5 2.5L8 3" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                          </svg>
                        ) : null}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className={`text-[13px] leading-relaxed ${step.done ? 'text-[#73726c] line-through' : 'text-[#1a1a18]'}`}>
                          {step.text}
                        </p>
                        {step.dueDate ? (
                          <p className={`mt-0.5 text-[11px] ${step.done ? 'text-[#b4b2a9]' : isOverdue ? 'font-medium text-red-500' : 'text-[#73726c]'}`}>
                            {isOverdue ? 'Просрочено · ' : 'До '}
                            {formatDate(step.dueDate)}
                          </p>
                        ) : null}
                      </div>
                      {step.isMilestone && !step.done ? (
                        <div className="shrink-0 rounded-full bg-[rgba(186,117,23,0.12)] px-2 py-0.5 text-[10px] text-[#633806]">
                          ★ milestone
                        </div>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="pt-2 text-center">
        <Link href={publicRootPath} className="text-[11px] text-[#73726c] hover:text-[#1a1a18]">
          ← На главную
        </Link>
      </div>
    </div>
  );
}

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
  }).format(date);
}
