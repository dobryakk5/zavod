'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { ApiError, apiFetch } from '@/lib/api';
import {
  coachingApi,
  type CoachGoalStep,
  type CoachGoalTreeNode,
  type CoachMilestone,
  type CoachingCompetency,
} from '@/lib/api/coaching';

type PortalData = {
  clientName: string;
  intention: string;
  goals: CoachGoalTreeNode[];
  competencies: CoachingCompetency[];
  milestones: CoachMilestone[];
};

type PublicCoachingPortalPageProps = {
  resolvedClientId?: number;
  useCustomDomainPaths?: boolean;
};

export default function CoachingPortalPage({
  resolvedClientId,
  useCustomDomainPaths = false,
}: PublicCoachingPortalPageProps = {}) {
  const { client_id: rawClientId } = useParams<{ client_id?: string }>();
  const pageClientId = resolvedClientId ?? Number(rawClientId);
  const backPath = useCustomDomainPaths ? '/' : `/c/${pageClientId}`;

  const [data, setData] = useState<PortalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState<string | null>(null);
  const [horizon, setHorizon] = useState<'year' | 'quarter' | 'month'>('quarter');
  const radarRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
      setError('Некорректная ссылка.');
      setLoading(false);
      return;
    }

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const raw = await coachingApi.getClientCoachingPortal(pageClientId);
        setData({
          clientName: raw.client?.name ?? '',
          intention: raw.client?.intention?.trim() || raw.client?.focus?.trim() || '',
          goals: Array.isArray(raw.goals) ? raw.goals : [],
          competencies: Array.isArray(raw.competencies) ? raw.competencies : [],
          milestones: Array.isArray(raw.milestones) ? raw.milestones : [],
        });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          setError('Войдите через Telegram, VK или email, чтобы увидеть свой прогресс.');
        } else if (err instanceof ApiError && err.status === 404) {
          setData({
            clientName: '',
            intention: '',
            goals: [],
            competencies: [],
            milestones: [],
          });
        } else {
          setError('Не удалось загрузить данные.');
        }
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [pageClientId]);

  useEffect(() => {
    if (!radarRef.current || !data?.competencies.length) {
      return;
    }
    drawRadar(radarRef.current, data.competencies);
  }, [data?.competencies]);

  async function handleToggleStep(goalId: string, step: CoachGoalStep) {
    if (completing) {
      return;
    }

    const nextDone = !step.done;
    setCompleting(step.id);
    setData((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        goals: current.goals.map((goal) => (
          goal.id === goalId
            ? {
                ...goal,
                steps: goal.steps.map((goalStep) => (
                  goalStep.id === step.id
                    ? { ...goalStep, done: nextDone }
                    : goalStep
                )),
              }
            : goal
        )),
      };
    });

    try {
      const updated = await apiFetch<CoachGoalStep>(`/public/client-page/${pageClientId}/steps/${step.id}/`, {
        method: 'PATCH',
        body: { done: nextDone },
      });
      setData((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          goals: current.goals.map((goal) => (
            goal.id === goalId
              ? {
                  ...goal,
                  steps: goal.steps.map((goalStep) => (
                    goalStep.id === step.id
                      ? {
                          ...goalStep,
                          ...updated,
                          doneAt: updated.doneAt ?? null,
                          dueDate: updated.dueDate ?? goalStep.dueDate ?? null,
                        }
                      : goalStep
                  )),
                }
              : goal
          )),
        };
      });
    } catch {
      setData((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          goals: current.goals.map((goal) => (
            goal.id === goalId
              ? {
                  ...goal,
                  steps: goal.steps.map((goalStep) => (
                    goalStep.id === step.id
                      ? { ...goalStep, done: step.done }
                      : goalStep
                  )),
                }
              : goal
          )),
        };
      });
      setError('Не удалось обновить статус задания.');
    } finally {
      setCompleting(null);
    }
  }

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-xl space-y-4 p-6">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          {error}
        </div>
        <Link href={backPath} className="text-[12px] text-[#73726c] hover:text-[#1a1a18]">
          ← Назад
        </Link>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const visibleGoals = data.goals.filter((goal) => goal.horizon === horizon && goal.status === 'active');
  const activeSteps = visibleGoals.flatMap((goal) => goal.steps.filter((step) => !step.done));
  const avgProgress = visibleGoals.length > 0
    ? Math.round(visibleGoals.reduce((sum, goal) => sum + goal.progress, 0) / visibleGoals.length)
    : 0;

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-5">
      <Link href={backPath} className="inline-block text-[11px] text-[#73726c] hover:text-[#1a1a18]">
        ← Назад
      </Link>

      {data.intention ? (
        <div className="rounded-xl border-l-4 border-[#7F77DD] bg-[#f5f4f0] px-4 py-3">
          <p className="mb-1 text-[10px] font-medium uppercase tracking-[0.5px] text-[#7F77DD]">
            Моё намерение
          </p>
          <p className="text-[14px] leading-relaxed text-[#1a1a18]">{data.intention}</p>
        </div>
      ) : null}

      <div className="grid grid-cols-3 gap-3">
        <StatCard value={`${avgProgress}%`} label="прогресс" />
        <StatCard value={activeSteps.length} label="заданий" />
        <StatCard value={data.milestones.length} label="milestone" accent />
      </div>

      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-[16px] font-medium text-[#1a1a18]">
            {data.clientName ? `Прогресс ${data.clientName}` : 'Мой прогресс'}
          </h1>
        </div>
        <div className="flex gap-1 rounded-lg bg-[#f1efe8] p-0.5">
          {(['quarter', 'year', 'month'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setHorizon(value)}
              className={`rounded-md px-3 py-1 text-[11px] transition-colors ${
                horizon === value
                  ? 'bg-white font-medium text-[#1a1a18] shadow-sm'
                  : 'text-[#73726c] hover:text-[#1a1a18]'
              }`}
            >
              {value === 'quarter' ? 'Квартал' : value === 'year' ? 'Год' : 'Месяц'}
            </button>
          ))}
        </div>
      </div>

      {visibleGoals.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#e0ddd6] p-6 text-center text-[12px] text-[#73726c]">
          Целей пока нет. Коуч добавит их на сессии.
        </div>
      ) : (
        <div className="space-y-3">
          {visibleGoals.map((goal) => (
            <GoalCard
              key={goal.id}
              goal={goal}
              completing={completing}
              onToggleStep={handleToggleStep}
            />
          ))}
        </div>
      )}

      {data.competencies.length > 0 ? (
        <div className="rounded-xl border border-[#e0ddd6] bg-white p-5">
          <h2 className="mb-4 text-[13px] font-medium text-[#1a1a18]">Мой рост</h2>
          <canvas ref={radarRef} width={300} height={260} className="mx-auto block" />
          <div className="mt-4 flex justify-center gap-5">
            <LegendItem color="#1D9E75" label="Сейчас" />
            <LegendItem color="#b4b2a9" label="Старт" dashed />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2">
            {data.competencies.map((competency) => (
              <div key={competency.id}>
                <div className="mb-1 flex justify-between text-[11px]">
                  <span className="text-[#1a1a18]">{competency.name}</span>
                  <span className="font-medium" style={{ color: competency.color ?? '#1D9E75' }}>
                    {competency.score}%
                  </span>
                </div>
                <div className="h-[3px] overflow-hidden rounded-full bg-[#f1efe8]">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${competency.score}%`,
                      background: competency.color ?? '#1D9E75',
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {data.milestones.length > 0 ? (
        <div className="rounded-xl border border-[#e0ddd6] bg-white p-5">
          <h2 className="mb-4 text-[13px] font-medium text-[#1a1a18]">Мои milestone</h2>
          <div className="space-y-4">
            {data.milestones.map((milestone) => (
              <div key={milestone.id} className="flex gap-3">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[rgba(186,117,23,0.1)] text-[11px] text-[#633806]">
                  ★
                </div>
                <div>
                  <p className="text-[13px] leading-relaxed text-[#1a1a18]">{milestone.text}</p>
                  {milestone.note ? (
                    <span className="mt-1 inline-block rounded-full bg-[rgba(186,117,23,0.1)] px-2 py-0.5 text-[10px] text-[#633806]">
                      {milestone.note}
                    </span>
                  ) : null}
                  <p className="mt-0.5 text-[10px] text-[#73726c]">{formatDate(milestone.createdAt)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function GoalCard({
  goal,
  completing,
  onToggleStep,
}: {
  goal: CoachGoalTreeNode;
  completing: string | null;
  onToggleStep: (goalId: string, step: CoachGoalStep) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const doneCount = goal.steps.filter((step) => step.done).length;
  const totalSteps = goal.steps.length;

  return (
    <div className="overflow-hidden rounded-xl border border-[#e0ddd6] bg-white">
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-[#f5f4f0]"
      >
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium leading-snug text-[#1a1a18]">{goal.title}</p>
          {totalSteps > 0 ? (
            <p className="mt-0.5 text-[10px] text-[#73726c]">
              {doneCount} из {totalSteps} шагов выполнено
            </p>
          ) : null}
        </div>
        <span className="shrink-0 text-[13px] font-medium" style={{ color: progressColor(goal.progress) }}>
          {goal.progress}%
        </span>
        <span className="shrink-0 text-[10px] text-[#73726c]">{expanded ? '▾' : '▸'}</span>
      </button>

      <div className="mx-4 h-[3px] overflow-hidden rounded-full bg-[#f1efe8]">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${goal.progress}%`, background: progressColor(goal.progress) }}
        />
      </div>

      {expanded && goal.steps.length > 0 ? (
        <div className="mt-2 space-y-1 px-3 pb-3">
          {goal.steps.map((step) => {
            const isOverdue = !step.done && Boolean(step.dueDate) && new Date(step.dueDate!).getTime() < Date.now();
            return (
              <button
                key={step.id}
                type="button"
                onClick={() => void onToggleStep(goal.id, step)}
                disabled={completing === step.id}
                className={`flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors disabled:cursor-wait ${
                  step.done
                    ? 'bg-[#f5f4f0] opacity-70'
                    : 'hover:bg-[#f5f4f0]'
                }`}
              >
                <div
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
                    step.done
                      ? 'border-[#1D9E75] bg-[#1D9E75]'
                      : 'border-[#d3d1c7] hover:border-[#1D9E75]'
                  }`}
                >
                  {step.done ? (
                    <svg width="9" height="9" viewBox="0 0 10 10" aria-hidden="true">
                      <path d="M2 5l2.5 2.5L8 3" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                    </svg>
                  ) : null}
                </div>

                <div className="min-w-0 flex-1">
                  <p className={`text-[12px] leading-relaxed ${step.done ? 'text-[#73726c] line-through' : 'text-[#1a1a18]'}`}>
                    {step.text}
                  </p>
                  {step.dueDate ? (
                    <p className={`mt-0.5 text-[10px] ${
                      step.done
                        ? 'text-[#b4b2a9]'
                        : isOverdue
                          ? 'font-medium text-red-500'
                          : 'text-[#73726c]'
                    }`}
                    >
                      {isOverdue ? 'Просрочено · ' : 'До '}
                      {formatDate(step.dueDate)}
                    </p>
                  ) : null}
                </div>

                {step.isMilestone && !step.done ? (
                  <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[#EF9F27]" />
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function StatCard({
  value,
  label,
  accent,
}: {
  value: string | number;
  label: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-[#e0ddd6] bg-white p-4 text-center">
      <p className={`text-[22px] font-medium ${accent ? 'text-[#EF9F27]' : 'text-[#1a1a18]'}`}>{value}</p>
      <p className="mt-0.5 text-[11px] text-[#73726c]">{label}</p>
    </div>
  );
}

function LegendItem({
  color,
  label,
  dashed,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <div
        className="h-0.5 w-5"
        style={{
          background: dashed ? undefined : color,
          borderTop: dashed ? `1.5px dashed ${color}` : undefined,
        }}
      />
      <span className="text-[11px] text-[#73726c]">{label}</span>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="mx-auto max-w-2xl animate-pulse space-y-4 p-5">
      <div className="h-4 w-12 rounded bg-[#ece7dd]" />
      <div className="h-14 rounded-xl bg-[#ece7dd]" />
      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3].map((index) => (
          <div key={index} className="h-16 rounded-xl bg-[#ece7dd]" />
        ))}
      </div>
      <div className="h-32 rounded-xl bg-[#ece7dd]" />
      <div className="h-32 rounded-xl bg-[#ece7dd]" />
      <div className="h-64 rounded-xl bg-[#ece7dd]" />
    </div>
  );
}

function drawRadar(canvas: HTMLCanvasElement, competencies: CoachingCompetency[]) {
  const ctx = canvas.getContext('2d');
  if (!ctx || competencies.length === 0) {
    return;
  }

  const width = canvas.width;
  const height = canvas.height;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 2 - 36;
  const count = competencies.length;
  const angle = (index: number) => (Math.PI * 2 * index) / count - Math.PI / 2;

  ctx.clearRect(0, 0, width, height);

  for (let ring = 1; ring <= 4; ring += 1) {
    ctx.beginPath();
    for (let index = 0; index < count; index += 1) {
      const ringRadius = radius * (ring / 4);
      ctx.lineTo(centerX + Math.cos(angle(index)) * ringRadius, centerY + Math.sin(angle(index)) * ringRadius);
    }
    ctx.closePath();
    ctx.strokeStyle = 'rgba(0,0,0,0.07)';
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }

  for (let index = 0; index < count; index += 1) {
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(centerX + Math.cos(angle(index)) * radius, centerY + Math.sin(angle(index)) * radius);
    ctx.strokeStyle = 'rgba(0,0,0,0.07)';
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }

  const drawPolygon = (points: number[], fill: string, stroke: string, dashed: boolean) => {
    ctx.beginPath();
    points.forEach((value, index) => {
      const pointRadius = radius * (value / 100);
      const x = centerX + Math.cos(angle(index)) * pointRadius;
      const y = centerY + Math.sin(angle(index)) * pointRadius;
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.setLineDash(dashed ? [4, 3] : []);
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);
  };

  drawPolygon(competencies.map((competency) => competency.startScore), 'transparent', 'rgba(0,0,0,0.12)', true);
  drawPolygon(competencies.map((competency) => competency.score), 'rgba(29,158,117,0.12)', '#1D9E75', false);

  ctx.fillStyle = '#73726c';
  ctx.font = '11px system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  competencies.forEach((competency, index) => {
    const currentAngle = angle(index);
    ctx.fillText(
      competency.name,
      centerX + Math.cos(currentAngle) * (radius + 22),
      centerY + Math.sin(currentAngle) * (radius + 22),
    );
  });
}

function progressColor(progress: number) {
  if (progress >= 70) {
    return '#1D9E75';
  }
  if (progress >= 40) {
    return '#7F77DD';
  }
  return '#888780';
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
