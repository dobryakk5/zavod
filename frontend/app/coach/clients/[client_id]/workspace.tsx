'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Copy, ExternalLink, Undo2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  coachingApi,
  coachingApiExt,
  type CoachGoalTreeNode,
  type CoachingClient,
  type CoachingCompetency,
  type CoachMilestone,
  type CoachSession,
  type CoachTask,
} from '@/lib/api/coaching';
import CoachClientSessionPage from './page-client';

type Tab = 'overview' | 'session' | 'history' | 'edit';

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Обзор' },
  { id: 'session', label: 'Сессия' },
  { id: 'history', label: 'История' },
  { id: 'edit', label: 'Редактор' },
];

const COMPETENCY_COLOR_PALETTE = ['#1D9E75', '#7F77DD', '#378ADD', '#EF9F27', '#D96C75', '#5E8C61'];

type SideData = {
  client: CoachingClient | null;
  competencies: CoachingCompetency[];
  goals: CoachGoalTreeNode[];
  milestones: CoachMilestone[];
  sessions: CoachSession[];
  tasks: CoachTask[];
};

export default function CoachClientWorkspace({ clientId }: { clientId: number }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawTab = searchParams.get('tab') as Tab | null;
  const activeTab = TABS.some((tab) => tab.id === rawTab) ? rawTab : 'overview';

  const [sideData, setSideData] = useState<SideData>({
    client: null,
    competencies: [],
    goals: [],
    milestones: [],
    sessions: [],
    tasks: [],
  });
  const [loading, setLoading] = useState(true);

  const handleCopyPortalLink = useCallback(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const portalUrl = new URL(`/c/${clientId}/coaching`, window.location.origin).toString();
    navigator.clipboard.writeText(portalUrl).then(
      () => toast.success('Ссылка на кабинет клиента скопирована'),
      () => toast.error('Не удалось скопировать ссылку'),
    );
  }, [clientId]);

  useEffect(() => {
    let active = true;
    setLoading(true);

    const fetchAll = async () => {
      const [client, competencies, goals, milestones, sessions, tasks] = await Promise.all([
        coachingApi.getCoachClient(clientId).catch(() => null),
        coachingApi.getCoachClientCompetencies(clientId).catch(() => []),
        coachingApi.getCoachClientGoals(clientId).catch(() => []),
        coachingApi.getCoachClientMilestones(clientId).catch(() => []),
        coachingApi.getCoachClientSessions(clientId).catch(() => []),
        coachingApiExt.getCoachClientTasks(clientId).catch(() => []),
      ]);

      if (!active) {
        return;
      }

      setSideData({ client, competencies, goals, milestones, sessions, tasks });
      setLoading(false);
    };

    void fetchAll();
    return () => {
      active = false;
    };
  }, [clientId]);

  function switchTab(tab: Tab) {
    router.replace(`/coach/clients/${clientId}?tab=${tab}`, { scroll: false });
  }

  const handleSessionsChange = useCallback((sessions: CoachSession[]) => {
    setSideData((prev) => (
      prev.sessions === sessions
        ? prev
        : {
            ...prev,
            sessions,
          }
    ));
  }, []);

  const handleMilestonesChange = useCallback((milestones: CoachMilestone[]) => {
    setSideData((prev) => (
      prev.milestones === milestones
        ? prev
        : {
            ...prev,
            milestones,
          }
    ));
  }, []);

  const handleGoalsChange = useCallback((goals: CoachGoalTreeNode[]) => {
    setSideData((prev) => (
      prev.goals === goals
        ? prev
        : {
            ...prev,
            goals,
          }
    ));
  }, []);

  if (loading) {
    return <WorkspaceSkeleton />;
  }

  const { client, competencies, goals, milestones, sessions } = sideData;

  return (
    <div className="flex min-h-screen flex-col bg-[#f5f4f0]">
      <div className="border-b border-[#e0ddd6] bg-white px-3 py-3 sm:px-5 sm:py-2.5">
        <div className="flex min-w-0 items-start gap-3">
          <Link
            href="/dashboard"
            aria-label="Вернуться к dashboard"
            title="Вернуться"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center text-[#73726c] transition-colors hover:text-[#185fa5]"
          >
            <Undo2 className="h-4.5 w-4.5" />
          </Link>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#e1f5ee] text-[12px] font-medium text-[#0f6e56]">
            {client?.initials ?? '—'}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <Link
                href={`/contact/${clientId}`}
                className="truncate text-[14px] font-medium text-[#1a1a18] transition-colors hover:text-[#185fa5] hover:underline"
              >
                {client?.name ?? 'Клиент'}
              </Link>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  onClick={handleCopyPortalLink}
                  aria-label={`Скопировать ссылку кабинета клиента ${client?.name ?? 'Клиент'}`}
                  title="Скопировать ссылку"
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d8d4ca] text-[#73726c] transition-colors hover:border-[#5c52e0] hover:text-[#5c52e0]"
                >
                  <Copy className="h-4 w-4" />
                </button>
                <Link
                  href={`/c/${clientId}/coaching`}
                  aria-label={`Открыть кабинет клиента ${client?.name ?? 'Клиент'}`}
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d8d4ca] text-[#73726c] transition-colors hover:border-[#5c52e0] hover:text-[#5c52e0]"
                >
                  <ExternalLink className="h-4 w-4" />
                </Link>
              </div>
            </div>
            <p className="text-[11px] leading-4 text-[#73726c]">
              {client?.sessionsCount ?? 0} сессий · {client?.focus ?? ''}
            </p>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 sm:flex-nowrap">
          <div className="min-w-0 flex-1 overflow-x-auto pb-1">
            <div className="flex w-max gap-0.5 rounded-lg bg-[#f1efe8] p-0.5">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => switchTab(tab.id)}
                  className={`rounded-md px-4 py-1.5 text-[12px] transition-colors ${
                    activeTab === tab.id
                      ? 'bg-white font-medium text-[#1a1a18] shadow-sm'
                      : 'text-[#73726c] hover:text-[#1a1a18]'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1">
        {activeTab === 'overview' ? (
          <OverviewTab
            client={client}
            competencies={competencies}
            goals={goals}
            milestones={milestones}
            sessions={sessions}
            onStepComplete={async (goalId, stepId) => {
              const response = await coachingApi.updateCoachGoalStep(goalId, stepId, { done: true });
              setSideData((prev) => ({
                ...prev,
                goals: prev.goals.map((goal) => (
                  goal.id === goalId
                    ? { ...goal, steps: response.steps }
                    : goal
                )),
              }));
            }}
          />
        ) : null}

        {activeTab === 'session' ? (
          <CoachClientSessionPage
            clientId={clientId}
            onSessionsChange={handleSessionsChange}
            onMilestonesChange={handleMilestonesChange}
            onGoalsChange={handleGoalsChange}
          />
        ) : null}

        {activeTab === 'history' ? (
          <HistoryTab milestones={milestones} sessions={sessions} />
        ) : null}

        {activeTab === 'edit' ? (
          <EditTab
            client={client}
            competencies={competencies}
            goals={goals}
            clientId={clientId}
            onSaveGoals={async (nextGoals) => {
              const updatedGoals = await coachingApi.replaceCoachClientGoals(clientId, nextGoals);
              setSideData((prev) => ({
                ...prev,
                goals: updatedGoals,
              }));
            }}
            onSave={async ({ competencies: updated, intention }) => {
              const [result, updatedClient] = await Promise.all([
                coachingApiExt.saveCoachClientCompetencies(clientId, updated),
                coachingApiExt.updateCoachClient(clientId, { intention }),
              ]);
              const milestones = await coachingApi.getCoachClientMilestones(clientId).catch(() => null);
              setSideData((prev) => ({
                ...prev,
                client: updatedClient,
                competencies: result,
                milestones: milestones ?? prev.milestones,
              }));
            }}
          />
        ) : null}
      </div>
    </div>
  );
}

function OverviewTab({
  client,
  competencies,
  goals,
  milestones,
  sessions,
  onStepComplete,
}: {
  client: CoachingClient | null;
  competencies: CoachingCompetency[];
  goals: CoachGoalTreeNode[];
  milestones: CoachMilestone[];
  sessions: CoachSession[];
  onStepComplete: (goalId: string, stepId: string) => Promise<void>;
}) {
  const [completing, setCompleting] = useState<string | null>(null);

  const allSteps = goals.flatMap((goal) => (
    goal.steps.map((step) => ({
      ...step,
      goalId: goal.id,
      goalTitle: step.goalTitle || goal.title,
    }))
  ));
  const openSteps = allSteps
    .filter((step) => !step.done)
    .sort((left, right) => {
      const leftDue = left.dueDate || '9999-12-31';
      const rightDue = right.dueDate || '9999-12-31';
      return leftDue.localeCompare(rightDue) || (left.goalTitle || '').localeCompare(right.goalTitle || '');
    });
  const doneCount = allSteps.filter((step) => step.done).length;
  const avgProgress = client?.avgProgress ?? 0;
  const latestSession = sessions.find((session) => session.status !== 'draft') ?? null;

  async function handleComplete(goalId: string, stepId: string) {
    setCompleting(stepId);
    try {
      await onStepComplete(goalId, stepId);
    } finally {
      setCompleting(null);
    }
  }

  return (
    <div className="mx-auto max-w-[1200px] space-y-5 p-3 sm:p-5">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard value={`${avgProgress}%`} label="средний прогресс" />
        <StatCard value={`${doneCount} / ${allSteps.length}`} label="шагов выполнено" />
        <StatCard value={milestones.length} label="вехи" accent />
        <StatCard
          value={client?.nextSession ? formatShortDate(client.nextSession) : '—'}
          label="след. сессия"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4 xl:col-span-3">
          <SectionTitle>Компетенции</SectionTitle>
          {competencies.length === 0 ? (
            <Empty>Компетенции пока не заполнены</Empty>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
                {competencies.map((competency) => (
                  <div key={competency.id}>
                    <div className="mb-1 flex justify-between text-[11px]">
                      <span className="text-[#1a1a18]">{competency.name}</span>
                      <span
                        className="font-medium"
                        style={{ color: competency.color || '#1D9E75' }}
                      >
                        {competency.score}%
                      </span>
                    </div>
                    <CompetencyProgressBar competency={competency} />
                  </div>
              ))}
              </div>
              <RadarChart competencies={competencies} />
            </>
          )}
        </div>

        <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4 xl:col-span-2">
          <SectionTitle>Задания на неделе</SectionTitle>
          {openSteps.length === 0 ? (
            <Empty>Заданий пока нет</Empty>
          ) : (
            <div className="space-y-0.5">
              {openSteps.map((step) => {
                return (
                  <button
                    key={step.id}
                    type="button"
                    disabled={completing === step.id}
                    onClick={() => step.goalId ? void handleComplete(step.goalId, step.id) : undefined}
                    className="flex w-full items-start gap-2 border-b border-[#f1efe8] py-2 text-left last:border-0 disabled:cursor-default"
                  >
                    <div
                      className="mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border border-[#d3d1c7] transition-colors hover:border-[#b4b2a9]"
                    >
                      {completing === step.id ? <span className="text-[9px] text-[#73726c]">…</span> : null}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] leading-4 text-[#1a1a18]">{step.text}</p>
                      <p className="text-[10px] text-[#73726c]">{step.goalTitle}</p>
                    </div>
                    {step.dueDate ? (
                      <span className="mt-0.5 shrink-0 rounded-full bg-[rgba(186,117,23,0.1)] px-1.5 py-0.5 text-[10px] text-[#633806]">
                        {formatShortDate(step.dueDate)}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4">
          <SectionTitle>Последние вехи</SectionTitle>
          {milestones.length === 0 ? (
            <Empty>Вехи появятся после сессий</Empty>
          ) : (
            <div className="space-y-4">
              {milestones.slice(0, 4).map((milestone) => (
                <MilestoneRow key={milestone.id} milestone={milestone} />
              ))}
            </div>
          )}
        </div>

        <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4">
          <SectionTitle>Последняя сессия</SectionTitle>
          {latestSession ? (
            <div className="rounded-[6px] bg-[#f5f4f0] p-3">
              <p className="mb-1 text-[10px] text-[#73726c]">
                Сессия #{latestSession.number} · {formatDate(latestSession.date)}
              </p>
              <p className="text-[12px] leading-relaxed text-[#1a1a18]">
                {latestSession.notes || 'Без описания'}
              </p>
              {latestSession.coachNotes ? (
                <p className="mt-1 text-[11px] text-[#73726c]">{latestSession.coachNotes}</p>
              ) : null}
            </div>
          ) : (
            <Empty>Сессий пока нет</Empty>
          )}
        </div>
      </div>
    </div>
  );
}

function CompetencyProgressBar({ competency }: { competency: CoachingCompetency }) {
  const color = competency.color || '#1D9E75';
  const startScore = clampPercent(competency.startScore);
  const currentScore = clampPercent(competency.score);
  const solidWidth = Math.min(startScore, currentScore);
  const progressWidth = Math.max(currentScore - solidWidth, 0);
  const hasSolidPart = solidWidth > 0;

  return (
    <div className="relative h-[6px] overflow-hidden rounded-full bg-[#f1efe8]">
      {solidWidth > 0 ? (
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            width: `${solidWidth}%`,
            background: color,
          }}
        />
      ) : null}
      {progressWidth > 0 ? (
        <div
          className="absolute inset-y-0 bg-white"
          style={{
            left: hasSolidPart ? `calc(${solidWidth}% - 2px)` : `${solidWidth}%`,
            width: hasSolidPart ? `calc(${progressWidth}% + 2px)` : `${progressWidth}%`,
            borderTop: `1px solid ${color}`,
            borderRight: `1px solid ${color}`,
            borderBottom: `1px solid ${color}`,
          }}
        >
          {hasSolidPart ? (
            <div
              className="absolute inset-y-0 left-0 w-px"
              style={{ background: color }}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function HistoryTab({
  milestones,
  sessions,
}: {
  milestones: CoachMilestone[];
  sessions: CoachSession[];
}) {
  return (
    <div className="mx-auto max-w-[800px] space-y-5 p-3 sm:p-5">
      <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4">
        <SectionTitle>Все вехи</SectionTitle>
        {milestones.length === 0 ? (
          <Empty>Вехи появятся после сессий</Empty>
        ) : (
          <div className="space-y-4">
            {milestones.map((milestone) => (
              <MilestoneRow key={milestone.id} milestone={milestone} />
            ))}
          </div>
        )}
      </div>

      <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4">
        <SectionTitle>Сессии</SectionTitle>
        {sessions.length === 0 ? (
          <Empty>Сессий пока нет</Empty>
        ) : (
          <div className="space-y-2">
            {sessions.map((session) => (
              <div key={session.id} className="rounded-[6px] bg-[#f5f4f0] p-3">
                <p className="mb-1 text-[10px] text-[#73726c]">
                  Сессия #{session.number} · {formatDate(session.date)}
                </p>
                <p className="text-[12px] leading-relaxed text-[#1a1a18]">
                  {session.notes || 'Без описания'}
                </p>
                {session.coachNotes ? (
                  <p className="mt-1 text-[11px] text-[#73726c]">{session.coachNotes}</p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EditTab({
  client,
  competencies,
  goals,
  clientId,
  onSaveGoals,
  onSave,
}: {
  client: CoachingClient | null;
  competencies: CoachingCompetency[];
  goals: CoachGoalTreeNode[];
  clientId: number;
  onSaveGoals: (goals: CoachGoalTreeNode[]) => Promise<void>;
  onSave: (payload: { competencies: CoachingCompetency[]; intention: string }) => Promise<void>;
}) {
  const [localComps, setLocalComps] = useState<CoachingCompetency[]>(competencies);
  const [localGoals, setLocalGoals] = useState<CoachGoalTreeNode[]>(goals);
  const [intention, setIntention] = useState(client?.intention ?? '');
  const [profileSaveState, setProfileSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [goalSaveState, setGoalSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [adding, setAdding] = useState(false);
  const [newCompetencyName, setNewCompetencyName] = useState('');
  const [addError, setAddError] = useState<string | null>(null);
  const [newGoalTitle, setNewGoalTitle] = useState('');
  const [newGoalHorizon, setNewGoalHorizon] = useState<'year' | 'quarter' | 'month'>('quarter');
  const [newGoalCompetencyIds, setNewGoalCompetencyIds] = useState<string[]>([]);
  const [goalError, setGoalError] = useState<string | null>(null);
  const hasSyncedCompetencies = useRef(false);
  const hasSyncedGoals = useRef(false);
  const goalSaveTimeoutRef = useRef<number | null>(null);
  const profileSaveTimeoutRef = useRef<number | null>(null);
  const onSaveGoalsRef = useRef(onSaveGoals);
  const onSaveRef = useRef(onSave);

  useEffect(() => {
    onSaveGoalsRef.current = onSaveGoals;
  }, [onSaveGoals]);

  useEffect(() => {
    onSaveRef.current = onSave;
  }, [onSave]);

  useEffect(() => {
    if (!hasSyncedCompetencies.current) {
      hasSyncedCompetencies.current = true;
      return;
    }
    setLocalComps(competencies);
  }, [competencies]);

  useEffect(() => {
    if (!hasSyncedGoals.current) {
      hasSyncedGoals.current = true;
      return;
    }
    setLocalGoals(goals);
  }, [goals]);

  useEffect(() => {
    setIntention(client?.intention ?? '');
  }, [client?.id, client?.intention]);

  useEffect(() => {
    setNewGoalCompetencyIds((prev) => prev.filter((id) => localComps.some((comp) => comp.id === id)));
  }, [localComps]);

  useEffect(() => {
    setLocalGoals((prev) => prev.map((goal) => syncGoalCompetencies(goal, localComps)));
  }, [localComps]);

  useEffect(() => {
    const source = JSON.stringify({
      intention: client?.intention ?? '',
      competencies,
    });
    const draft = JSON.stringify({
      intention,
      competencies: localComps,
    });

    if (source === draft) {
      setProfileSaveState('idle');
      return undefined;
    }

    if (profileSaveTimeoutRef.current) {
      window.clearTimeout(profileSaveTimeoutRef.current);
    }

    profileSaveTimeoutRef.current = window.setTimeout(async () => {
      setProfileSaveState('saving');
      try {
        await onSaveRef.current({
          competencies: localComps,
          intention: intention.trim(),
        });
        setProfileSaveState('saved');
        window.setTimeout(() => {
          setProfileSaveState((current) => (current === 'saved' ? 'idle' : current));
        }, 1600);
      } catch {
        setProfileSaveState('error');
      }
    }, 900);

    return () => {
      if (profileSaveTimeoutRef.current) {
        window.clearTimeout(profileSaveTimeoutRef.current);
      }
    };
  }, [client?.intention, competencies, intention, localComps]);

  useEffect(() => {
    const source = JSON.stringify(goals);
    const draft = JSON.stringify(localGoals);
    if (source === draft) {
      setGoalSaveState('idle');
      return undefined;
    }

    if (goalSaveTimeoutRef.current) {
      window.clearTimeout(goalSaveTimeoutRef.current);
    }

    goalSaveTimeoutRef.current = window.setTimeout(async () => {
      setGoalSaveState('saving');
      try {
        await onSaveGoalsRef.current(localGoals);
        setGoalSaveState('saved');
        window.setTimeout(() => {
          setGoalSaveState((current) => (current === 'saved' ? 'idle' : current));
        }, 1600);
      } catch {
        setGoalSaveState('error');
      }
    }, 900);

    return () => {
      if (goalSaveTimeoutRef.current) {
        window.clearTimeout(goalSaveTimeoutRef.current);
      }
    };
  }, [goals, localGoals]);

  function update(id: string, field: 'score' | 'startScore', value: number) {
    setProfileSaveState('idle');
    setLocalComps((prev) => prev.map((comp) => (
      comp.id === id ? { ...comp, [field]: value } : comp
    )));
  }

  function remove(id: string) {
    setProfileSaveState('idle');
    setLocalComps((prev) => prev.filter((comp) => comp.id !== id));
  }

  function handleAddCompetency() {
    const name = newCompetencyName.trim();
    if (!name) {
      setAddError('Введите название компетенции.');
      return;
    }

    const normalizedName = name.toLocaleLowerCase('ru-RU');
    if (localComps.some((comp) => comp.name.trim().toLocaleLowerCase('ru-RU') === normalizedName)) {
      setAddError('Такая компетенция уже есть в списке.');
      return;
    }

    setProfileSaveState('idle');
    setLocalComps((prev) => [
      ...prev,
      {
        id: createCompetencyId(name),
        name,
        score: 0,
        startScore: 0,
        color: getNextCompetencyColor(prev),
      },
    ]);
    setNewCompetencyName('');
    setAddError(null);
    setAdding(false);
  }

  async function handleAddGoal() {
    const title = newGoalTitle.trim();
    if (!title) {
      setGoalError('Введите название цели.');
      return;
    }

    setGoalSaveState('idle');
    setLocalGoals((prev) => [
      ...prev,
      createCoachGoal({
        title,
        horizon: newGoalHorizon,
        competencies: localComps.filter((comp) => newGoalCompetencyIds.includes(comp.id)),
      }),
    ]);
    setNewGoalTitle('');
    setNewGoalHorizon('quarter');
    setNewGoalCompetencyIds([]);
    setGoalError(null);
  }

  function toggleGoalCompetency(competencyId: string) {
    setGoalError(null);
    setNewGoalCompetencyIds((prev) => (
      prev.includes(competencyId)
        ? prev.filter((id) => id !== competencyId)
        : [...prev, competencyId]
    ));
  }

  function updateGoalTitle(goalId: string, title: string) {
    setGoalSaveState('idle');
    setLocalGoals((prev) => prev.map((goal) => (
      goal.id === goalId ? { ...goal, title } : goal
    )));
  }

  function updateGoalCompetencies(goalId: string, competencyId: string) {
    setGoalSaveState('idle');
    setLocalGoals((prev) => prev.map((goal) => (
      goal.id === goalId ? toggleGoalCompetencyLink(goal, competencyId, localComps) : goal
    )));
  }

  function removeGoal(goalId: string) {
    setGoalSaveState('idle');
    setLocalGoals((prev) => prev.filter((goal) => goal.id !== goalId));
  }

  return (
    <div className="mx-auto max-w-[800px] space-y-4 p-3 sm:p-5">
      <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4">
        <SectionTitle>Намерение клиента</SectionTitle>
        <input
          type="text"
          value={intention}
          onChange={(event) => {
            setProfileSaveState('idle');
            setIntention(event.target.value);
          }}
          placeholder="Опишите, с каким намерением клиент пришёл в работу"
          className="w-full rounded-[6px] border border-[#d7d2c7] bg-[#f5f4f0] px-3 py-3 text-[16px] leading-none text-[#1a1a18] outline-none transition-colors placeholder:text-[#9a978f] focus:border-[#7F77DD] focus:bg-white"
        />
        <p className="mt-2 text-[10px] text-[#73726c]">
          {profileSaveState === 'saving'
            ? 'Автосохранение...'
            : profileSaveState === 'saved'
              ? 'Сохранено'
              : profileSaveState === 'error'
                ? 'Не удалось сохранить'
                : 'Автосохранение включено'}
        </p>
      </div>

      <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <SectionTitle className="mb-0">Цели</SectionTitle>
          <div className="text-[10px] text-[#73726c]">
            {goalSaveState === 'saving'
              ? 'Автосохранение...'
              : goalSaveState === 'saved'
                ? 'Сохранено'
                : goalSaveState === 'error'
                  ? 'Не удалось сохранить'
                  : 'Автосохранение включено'}
          </div>
        </div>

        {localGoals.length > 0 ? (
          <div className="mb-4 space-y-2">
            {localGoals.map((goal) => (
              <div key={goal.id} className="rounded-[8px] border border-[#dce9e2] bg-[#eef8f3] px-3 py-3">
                <div className="flex items-start gap-2">
                  <input
                    type="text"
                    value={goal.title}
                    onChange={(event) => updateGoalTitle(goal.id, event.target.value)}
                    className="min-w-0 flex-1 rounded-[6px] border border-[#d7d2c7] bg-white px-3 py-2 text-[13px] font-medium text-[#1a1a18] outline-none transition-colors focus:border-[#185fa5]"
                  />
                  <button
                    type="button"
                    onClick={() => removeGoal(goal.id)}
                    className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d7d2c7] text-[15px] leading-none text-[#7b766d] transition-colors hover:bg-white"
                    aria-label={`Удалить цель ${goal.title}`}
                    title={`Удалить цель ${goal.title}`}
                  >
                    -
                  </button>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-[#73726c]">
                    {goal.horizon === 'year' ? 'Год' : goal.horizon === 'month' ? 'Месяц' : 'Квартал'}
                  </span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-[#73726c]">
                    {goal.progress}%
                  </span>
                </div>
                {localComps.length > 0 ? (
                  <div className="mt-3">
                    <div className="mb-2 text-[10px] text-[#73726c]">Компетенции</div>
                    <div className="flex flex-wrap gap-2">
                      {localComps.map((competency) => {
                        const selected = goal.competencyLinks.some((link) => link.competencyId === competency.id);
                        return (
                          <button
                            key={`${goal.id}-${competency.id}`}
                            type="button"
                            onClick={() => updateGoalCompetencies(goal.id, competency.id)}
                            className={`rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                              selected
                                ? 'border-[#1D9E75] bg-[rgba(29,158,117,0.1)] text-[#0f6e56]'
                                : 'border-[#d7d2c7] bg-white text-[#4f4b45] hover:bg-[#f0ede6]'
                            }`}
                          >
                            {competency.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-[10px] text-[#73726c]">Сначала добавьте компетенции, затем можно связать их с целью.</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="mb-4 rounded-[8px] border-[0.5px] border-dashed border-[#d7d2c7] bg-[#f5f4f0] px-3 py-3 text-[12px] text-[#73726c]">
            Целей пока нет. Добавьте первые квартальные цели ниже.
          </div>
        )}

        <div className="rounded-[8px] border border-[#e6dfd2] bg-[#f7f2e8] p-3">
          <div className="mb-3 text-[11px] font-medium text-[#1a1a18]">Новая цель</div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_160px]">
            <label className="block">
              <span className="mb-1 block text-[10px] text-[#73726c]">Название</span>
              <input
                type="text"
                value={newGoalTitle}
                onChange={(event) => {
                  setNewGoalTitle(event.target.value);
                  if (goalError) {
                    setGoalError(null);
                  }
                }}
                placeholder="Например, спокойно обозначать границы в работе"
                className="w-full rounded-[6px] border border-[#d7d2c7] bg-white px-3 py-2 text-[12px] text-[#1a1a18] outline-none transition-colors placeholder:text-[#9a978f] focus:border-[#1D9E75]"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] text-[#73726c]">Горизонт</span>
              <select
                value={newGoalHorizon}
                onChange={(event) => setNewGoalHorizon(event.target.value as 'year' | 'quarter' | 'month')}
                className="w-full rounded-[6px] border border-[#d7d2c7] bg-white px-3 py-2 text-[12px] text-[#1a1a18] outline-none transition-colors focus:border-[#1D9E75]"
              >
                <option value="quarter">Квартал</option>
                <option value="month">Месяц</option>
                <option value="year">Год</option>
              </select>
            </label>
          </div>

          <div className="mt-3">
            <div className="mb-2 text-[10px] text-[#73726c]">Привязка к компетенциям</div>
            {localComps.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {localComps.map((competency) => {
                  const selected = newGoalCompetencyIds.includes(competency.id);
                  return (
                    <button
                      key={competency.id}
                      type="button"
                      onClick={() => toggleGoalCompetency(competency.id)}
                      className={`rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                        selected
                          ? 'border-[#1D9E75] bg-[rgba(29,158,117,0.1)] text-[#0f6e56]'
                          : 'border-[#d7d2c7] bg-white text-[#4f4b45] hover:bg-[#f0ede6]'
                      }`}
                    >
                      {competency.name}
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="text-[11px] text-[#73726c]">Сначала добавьте компетенции, затем можно привязать их к цели.</p>
            )}
          </div>

          {goalError ? (
            <p className="mt-3 text-[11px] text-[#b14d43]">{goalError}</p>
          ) : (
            <p className="mt-3 text-[10px] text-[#73726c]">
              Если выбрано несколько компетенций, вес между ними распределится поровну. Точные связи можно уточнить позже.
            </p>
          )}

          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={() => void handleAddGoal()}
              disabled={!newGoalTitle.trim()}
              className="rounded-[6px] bg-[#185fa5] px-3 py-2 text-[11px] text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              Добавить цель
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <SectionTitle className="mb-0">Компетенции</SectionTitle>
            <button
              type="button"
              onClick={() => {
                setAdding((prev) => !prev);
                setNewCompetencyName('');
                setAddError(null);
              }}
              className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-[#d7d2c7] text-[15px] leading-none text-[#4f4b45] transition-colors hover:bg-[#f5f4f0]"
              aria-label="Добавить компетенцию"
              title="Добавить компетенцию"
            >
              +
            </button>
          </div>
          <div className="text-[10px] text-[#73726c]">
            {profileSaveState === 'saving'
              ? 'Автосохранение...'
              : profileSaveState === 'saved'
                ? 'Сохранено'
                : profileSaveState === 'error'
                  ? 'Не удалось сохранить'
                  : 'Автосохранение включено'}
          </div>
        </div>

        {adding ? (
          <div className="mb-4 rounded-[6px] bg-[#f5f4f0] p-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <label className="block flex-1">
                <span className="mb-1 block text-[10px] text-[#73726c]">Новая компетенция</span>
                <input
                  type="text"
                  value={newCompetencyName}
                  onChange={(event) => {
                    setNewCompetencyName(event.target.value);
                    if (addError) {
                      setAddError(null);
                    }
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      handleAddCompetency();
                    }
                  }}
                  placeholder="Например, Эмпатия"
                  className="w-full rounded-[6px] border border-[#d7d2c7] bg-white px-3 py-2 text-[12px] text-[#1a1a18] outline-none transition-colors placeholder:text-[#9a978f] focus:border-[#1D9E75]"
                />
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleAddCompetency}
                  className="rounded-[6px] bg-[#1D9E75] px-3 py-2 text-[11px] text-[#E1F5EE]"
                >
                  Добавить
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAdding(false);
                    setNewCompetencyName('');
                    setAddError(null);
                  }}
                  className="rounded-[6px] border border-[#d7d2c7] px-3 py-2 text-[11px] text-[#4f4b45]"
                >
                  Отмена
                </button>
              </div>
            </div>
            {addError ? (
              <p className="mt-2 text-[11px] text-[#b14d43]">{addError}</p>
            ) : (
              <p className="mt-2 text-[10px] text-[#73726c]">
                После добавления скорректируйте стартовый и текущий уровень, затем сохраните изменения.
              </p>
            )}
          </div>
        ) : null}

        {localComps.length === 0 ? (
          <Empty>Компетенций пока нет</Empty>
        ) : (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {localComps.map((comp) => {
              const delta = comp.score - comp.startScore;

              return (
                <div key={comp.id}>
                  <div className="mb-2 flex items-center gap-2">
                    <div
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ background: comp.color || '#1D9E75' }}
                    />
                    <p className="text-[13px] font-medium text-[#1a1a18]">{comp.name}</p>
                    <div className="ml-auto flex items-center gap-2">
                      {delta > 0 ? (
                        <span className="text-[11px] font-medium text-[#1D9E75]">
                          +{delta}%
                        </span>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => remove(comp.id)}
                        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-[#d7d2c7] text-[14px] leading-none text-[#7b766d] transition-colors hover:bg-[#f5f4f0]"
                        aria-label={`Убрать компетенцию ${comp.name}`}
                        title={`Убрать компетенцию ${comp.name}`}
                      >
                        -
                      </button>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <div>
                      <p className="mb-1 text-[10px] text-[#73726c]">Старт (онбординг)</p>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={0}
                          max={100}
                          step={1}
                          value={comp.startScore}
                          onChange={(event) => update(comp.id, 'startScore', Number(event.target.value))}
                          className="flex-1 accent-[#9ca3af]"
                        />
                        <span className="w-8 text-right text-[11px] text-[#73726c]">
                          {comp.startScore}%
                        </span>
                      </div>
                    </div>

                    <div>
                      <p className="mb-1 text-[10px] text-[#73726c]">Сейчас</p>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={0}
                          max={100}
                          step={1}
                          value={comp.score}
                          onChange={(event) => update(comp.id, 'score', Number(event.target.value))}
                          className="flex-1 accent-[#1D9E75]"
                          style={{ accentColor: comp.color || '#1D9E75' }}
                        />
                        <span
                          className="w-8 text-right text-[11px] font-medium"
                          style={{ color: comp.color || '#1D9E75' }}
                        >
                          {comp.score}%
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-2 h-[3px] overflow-hidden rounded-full bg-[#f1efe8]">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${comp.score}%`, background: comp.color || '#1D9E75' }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <p className="text-center text-[11px] text-[#73726c]">
        Во время встречи в сессии лучше работать только с шагами и прогрессом:{' '}
        <Link href={`/coach/clients/${clientId}?tab=session`} className="text-[#185fa5] hover:underline">
          вкладка Сессия
        </Link>
      </p>
    </div>
  );
}

function SectionTitle({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={['text-[11px] font-medium uppercase tracking-[0.4px] text-[#73726c]', className ?? 'mb-3'].join(' ')}>
      {children}
    </p>
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
    <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white p-4">
      <p className={`text-[22px] font-medium ${accent ? 'text-[#EF9F27]' : 'text-[#1a1a18]'}`}>
        {value}
      </p>
      <p className="mt-1 text-[11px] text-[#73726c]">{label}</p>
    </div>
  );
}

function MilestoneRow({ milestone }: { milestone: CoachMilestone }) {
  return (
    <div className="flex gap-3">
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[rgba(186,117,23,0.1)] text-[11px] text-[#633806]">
        ★
      </div>
      <div>
        <p className="text-[12px] leading-relaxed text-[#1a1a18]">{milestone.text}</p>
        {milestone.note ? (
          <span className="mt-1 inline-block rounded-full bg-[rgba(186,117,23,0.1)] px-2 py-0.5 text-[10px] text-[#633806]">
            {milestone.note}
          </span>
        ) : null}
        <p className="mt-0.5 text-[10px] text-[#73726c]">{formatDate(milestone.createdAt)}</p>
      </div>
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-[12px] text-[#73726c]">{children}</p>;
}

function WorkspaceSkeleton() {
  return (
    <div className="min-h-screen animate-pulse bg-[#f5f4f0]">
      <div className="h-12 border-b border-[#e0ddd6] bg-white" />
      <div className="mx-auto max-w-[1200px] space-y-4 p-3 sm:p-5">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="h-20 rounded-[8px] bg-[#ece7dd]" />
          ))}
        </div>
        <div className="h-64 rounded-[8px] bg-[#ece7dd]" />
      </div>
    </div>
  );
}

function RadarChart({ competencies }: { competencies: CoachingCompetency[] }) {
  const width = 260;
  const height = 200;
  const cx = width / 2;
  const cy = height / 2 + 6;
  const radius = Math.min(width, height) / 2 - 34;
  const gridLevels = 10;
  const count = competencies.length;

  if (count === 0) {
    return null;
  }

  const angle = (index: number) => ((Math.PI * 2 * index) / count) - Math.PI / 2;
  const point = (index: number, value: number) => {
    const r = radius * (value / 100);
    return {
      x: cx + Math.cos(angle(index)) * r,
      y: cy + Math.sin(angle(index)) * r,
    };
  };
  const pointsToString = (values: number[]) => values.map((value, index) => {
    const { x, y } = point(index, value);
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="mx-auto mt-2 block overflow-visible"
      aria-label="Радар компетенций"
    >
      {Array.from({ length: gridLevels }, (_, index) => {
        const level = index + 1;
        return (
          <polygon
            key={`ring-${level}`}
            points={pointsToString(Array(count).fill((level / gridLevels) * 100))}
            fill="none"
            stroke="#ddd7cb"
            strokeWidth={level === gridLevels || level === gridLevels / 2 ? 0.9 : 0.55}
          />
        );
      })}

      {competencies.map((_, index) => {
        const outer = point(index, 100);
        return (
          <line
            key={`axis-${index}`}
            x1={cx}
            y1={cy}
            x2={outer.x}
            y2={outer.y}
            stroke="#d2cbbb"
            strokeWidth="0.7"
          />
        );
      })}

      <polygon
        points={pointsToString(competencies.map((comp) => comp.startScore))}
        fill="none"
        stroke="rgba(60,60,60,0.18)"
        strokeWidth="1.1"
        strokeDasharray="4 3"
      />
      <polygon
        points={pointsToString(competencies.map((comp) => comp.score))}
        fill="rgba(29,158,117,0.12)"
        stroke="#1D9E75"
        strokeWidth="1.6"
      />

      {competencies.map((comp, index) => {
        const labelPoint = point(index, 118);
        return (
          <text
            key={`label-${comp.id}`}
            x={labelPoint.x}
            y={labelPoint.y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="9"
            fill="#8a887f"
          >
            {comp.name}
          </text>
        );
      })}
    </svg>
  );
}

function createCoachGoal({
  title,
  horizon,
  competencies,
}: {
  title: string;
  horizon: 'year' | 'quarter' | 'month';
  competencies: CoachingCompetency[];
}): CoachGoalTreeNode {
  const goalId = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `goal-${Math.random().toString(36).slice(2, 10)}`;
  const weight = competencies.length > 0 ? Number((100 / competencies.length).toFixed(2)) : 0;

  return {
    id: goalId,
    title,
    progress: 0,
    horizon,
    status: 'active',
    competencyLinks: competencies.map((competency) => ({
      competencyId: competency.id,
      competencyName: competency.name,
      weight,
    })),
    steps: [],
    createdAt: new Date().toISOString(),
  };
}

function syncGoalCompetencies(goal: CoachGoalTreeNode, competencies: CoachingCompetency[]) {
  const activeCompetencies = competencies.filter((competency) => (
    goal.competencyLinks.some((link) => link.competencyId === competency.id)
  ));
  if (activeCompetencies.length === goal.competencyLinks.length && activeCompetencies.every((competency) => (
    goal.competencyLinks.some((link) => link.competencyId === competency.id && link.competencyName === competency.name)
  ))) {
    return goal;
  }

  return {
    ...goal,
    competencyLinks: rebalanceGoalCompetencies(activeCompetencies),
  };
}

function toggleGoalCompetencyLink(goal: CoachGoalTreeNode, competencyId: string, competencies: CoachingCompetency[]) {
  const nextCompetencies = competencies.filter((competency) => {
    const selected = goal.competencyLinks.some((link) => link.competencyId === competency.id);
    if (competency.id === competencyId) {
      return !selected;
    }
    return selected;
  });

  return {
    ...goal,
    competencyLinks: rebalanceGoalCompetencies(nextCompetencies),
  };
}

function rebalanceGoalCompetencies(competencies: CoachingCompetency[]) {
  if (competencies.length === 0) {
    return [];
  }

  const weight = Number((100 / competencies.length).toFixed(2));
  return competencies.map((competency) => ({
    competencyId: competency.id,
    competencyName: competency.name,
    weight,
  }));
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
}

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date);
}

function formatShortDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
  }).format(date);
}

function createCompetencyId(name: string) {
  const normalized = name
    .trim()
    .toLocaleLowerCase('ru-RU')
    .replace(/[^a-zа-яё0-9]+/gi, '-')
    .replace(/^-+|-+$/g, '');
  const suffix = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID().slice(0, 8)
    : Math.random().toString(36).slice(2, 10);
  return normalized ? `${normalized}-${suffix}` : `competency-${suffix}`;
}

function getNextCompetencyColor(competencies: CoachingCompetency[]) {
  const used = new Set(
    competencies
      .map((item) => item.color)
      .filter((value): value is string => Boolean(value)),
  );
  return COMPETENCY_COLOR_PALETTE.find((color) => !used.has(color)) ?? COMPETENCY_COLOR_PALETTE[competencies.length % COMPETENCY_COLOR_PALETTE.length];
}
