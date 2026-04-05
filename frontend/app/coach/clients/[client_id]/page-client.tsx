'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '@/lib/api';
import {
  coachingApi,
  type CoachGoalTreeNode,
  type CoachMilestone,
  type CoachSession,
  type CoachingClient,
  type CoachingCompetency,
} from '@/lib/api/coaching';

type CoachClientSessionPageProps = {
  clientId: number;
  initialData?: WorkspaceData | null;
  onSessionsChange?: (sessions: CoachSession[]) => void;
  onMilestonesChange?: (milestones: CoachMilestone[]) => void;
  onGoalsChange?: (goals: CoachGoalTreeNode[]) => void;
};

type WorkspaceData = {
  client: CoachingClient | null;
  competencies: CoachingCompetency[];
  goals: CoachGoalTreeNode[];
  milestones: CoachMilestone[];
  sessions: CoachSession[];
};

type TimelineItem = {
  id: string;
  date: string;
  label: string;
  text: string;
  kind: 'milestone' | 'session' | 'goal';
  note?: string;
};

const PANEL_CLASS = 'rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white';
const HORIZONS = [
  { key: 'year', label: 'Год' },
  { key: 'quarter', label: 'Квартал' },
  { key: 'month', label: 'Месяц' },
] as const;

export default function CoachClientSessionPage({
  clientId,
  initialData,
  onSessionsChange,
  onMilestonesChange,
  onGoalsChange,
}: CoachClientSessionPageProps) {
  const newStepDueDateInputRef = useRef<HTMLInputElement | null>(null);
  const lastSavedSessionRef = useRef<{ sessionId: string | null; notes: string; coachNotes: string }>({
    sessionId: null,
    notes: '',
    coachNotes: '',
  });
  const [data, setData] = useState<WorkspaceData>(() => normalizeWorkspaceData(initialData));
  const [selectedHorizon, setSelectedHorizon] = useState<'year' | 'quarter' | 'month'>('quarter');
  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);
  const [sessionNotes, setSessionNotes] = useState('');
  const [nextTask, setNextTask] = useState('');
  const [newStepText, setNewStepText] = useState('');
  const [newStepDueDate, setNewStepDueDate] = useState('');
  const [quickGoalTitle, setQuickGoalTitle] = useState('');
  const [addingQuickGoal, setAddingQuickGoal] = useState(false);
  const [milestoneText, setMilestoneText] = useState('');
  const [milestoneNote, setMilestoneNote] = useState('');
  const [milestoneOpen, setMilestoneOpen] = useState(false);
  const [draftProgress, setDraftProgress] = useState(0);
  const [loading, setLoading] = useState(() => initialData == null);
  const [savingSession, setSavingSession] = useState(false);
  const [startingSession, setStartingSession] = useState(false);
  const [finishingSession, setFinishingSession] = useState(false);
  const [savingMilestone, setSavingMilestone] = useState(false);
  const [savingProgress, setSavingProgress] = useState(false);
  const [savingStepId, setSavingStepId] = useState<string | null>(null);
  const [savingGoalList, setSavingGoalList] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    if (initialData) {
      const normalizedInitialData = normalizeWorkspaceData(initialData);
      setData((current) => (
        current.client === normalizedInitialData.client
        && current.competencies === normalizedInitialData.competencies
        && current.goals === normalizedInitialData.goals
        && current.milestones === normalizedInitialData.milestones
        && current.sessions === normalizedInitialData.sessions
          ? current
          : normalizedInitialData
      ));

      const firstGoal = normalizedInitialData.goals.find((goal) => goal.horizon === 'quarter') ?? normalizedInitialData.goals[0] ?? null;
      if (firstGoal) {
        setSelectedHorizon(firstGoal.horizon);
        setSelectedGoalId(firstGoal.id);
        setDraftProgress(firstGoal.progress);
      } else {
        setSelectedGoalId(null);
        setDraftProgress(0);
      }

      setLoading(false);
      setError(null);
      return undefined;
    }

    let isActive = true;

    const loadWorkspace = async () => {
      setLoading(true);
      setError(null);

      const results = await Promise.allSettled([
        coachingApi.getCoachClient(clientId),
        coachingApi.getCoachClientCompetencies(clientId),
        coachingApi.getCoachClientGoals(clientId),
        coachingApi.getCoachClientMilestones(clientId),
        coachingApi.getCoachClientSessions(clientId),
      ]);

      if (!isActive) return;

      const [clientResult, competenciesResult, goalsResult, milestonesResult, sessionsResult] = results;
      const nextClient = clientResult.status === 'fulfilled' ? clientResult.value : null;
      const nextCompetencies = competenciesResult.status === 'fulfilled' ? competenciesResult.value : [];
      const nextGoals = goalsResult.status === 'fulfilled' ? goalsResult.value : [];
      const nextMilestones = milestonesResult.status === 'fulfilled' ? milestonesResult.value : [];
      const nextSessions = sessionsResult.status === 'fulfilled' ? sortCoachSessions(sessionsResult.value) : [];

      const nextData = normalizeWorkspaceData({
        client: nextClient,
        competencies: nextCompetencies,
        goals: nextGoals,
        milestones: nextMilestones,
        sessions: nextSessions,
      });
      setData(nextData);

      const firstGoal = nextData.goals.find((goal) => goal.horizon === 'quarter') ?? nextData.goals[0] ?? null;
      if (firstGoal) {
        setSelectedHorizon(firstGoal.horizon);
        setSelectedGoalId(firstGoal.id);
        setDraftProgress(firstGoal.progress);
      } else {
        setSelectedGoalId(null);
        setDraftProgress(0);
      }

      const failedRequests = results.filter((result) => result.status === 'rejected').length;
      if (clientResult.status === 'rejected') {
        const status = clientResult.reason instanceof ApiError ? clientResult.reason.status : null;
        setError(status === 404 ? 'Клиент не найден.' : 'Не удалось загрузить экран клиента.');
      } else if (failedRequests > 0) {
        setError('Часть данных клиента загрузить не удалось. Остальной экран доступен.');
      }

      setLoading(false);
    };

    void loadWorkspace();

    return () => {
      isActive = false;
    };
  }, [
    clientId,
    initialData?.client,
    initialData?.competencies,
    initialData?.goals,
    initialData?.milestones,
    initialData?.sessions,
  ]);

  useEffect(() => {
    if (!loading) {
      onSessionsChange?.(data.sessions);
    }
  }, [data.sessions, loading, onSessionsChange]);

  useEffect(() => {
    if (!loading) {
      onMilestonesChange?.(data.milestones);
    }
  }, [data.milestones, loading, onMilestonesChange]);

  useEffect(() => {
    if (!loading) {
      onGoalsChange?.(data.goals);
    }
  }, [data.goals, loading, onGoalsChange]);

  const visibleGoals = useMemo(
    () => data.goals.filter((goal) => goal.horizon === selectedHorizon),
    [data.goals, selectedHorizon],
  );

  useEffect(() => {
    if (visibleGoals.length === 0) {
      setSelectedGoalId(null);
      return;
    }

    if (selectedGoalId && visibleGoals.some((goal) => goal.id === selectedGoalId)) {
      return;
    }

    setSelectedGoalId(visibleGoals[0].id);
  }, [visibleGoals, selectedGoalId]);

  const selectedGoal = useMemo(
    () => visibleGoals.find((goal) => goal.id === selectedGoalId) ?? visibleGoals[0] ?? null,
    [selectedGoalId, visibleGoals],
  );

  useEffect(() => {
    if (!selectedGoal) {
      setDraftProgress(0);
      return;
    }
    setDraftProgress(selectedGoal.progress);
  }, [selectedGoal]);

  useEffect(() => {
    if (!actionMessage) return undefined;
    const timeoutId = window.setTimeout(() => setActionMessage(null), 2800);
    return () => window.clearTimeout(timeoutId);
  }, [actionMessage]);

  const activeSession = useMemo(
    () => data.sessions.find((session) => session.status === 'draft') ?? null,
    [data.sessions],
  );

  const completedSessions = useMemo(
    () => data.sessions.filter((session) => session.status !== 'draft'),
    [data.sessions],
  );

  const lastCompletedSession = completedSessions[0] ?? null;

  const nextSessionNumber = useMemo(() => {
    if (data.sessions.length === 0) return 1;
    return Math.max(...data.sessions.map((session) => session.number)) + 1;
  }, [data.sessions]);

  const currentSessionNumber = activeSession?.number ?? nextSessionNumber;

  useEffect(() => {
    if (!activeSession) return undefined;
    if (!selectedGoal) return undefined;
    if (draftProgress === selectedGoal.progress) return undefined;

    const timeoutId = window.setTimeout(async () => {
      setSavingProgress(true);
      try {
        await coachingApi.updateCoachGoal(selectedGoal.id, { progress: draftProgress });
        setData((current) => ({
          ...current,
          goals: current.goals.map((goal) => (goal.id === selectedGoal.id ? { ...goal, progress: draftProgress } : goal)),
        }));
      } catch {
        setActionMessage('Не удалось обновить прогресс цели.');
        setDraftProgress(selectedGoal.progress);
      } finally {
        setSavingProgress(false);
      }
    }, 450);

    return () => window.clearTimeout(timeoutId);
  }, [activeSession, draftProgress, selectedGoal]);

  const timelineItems = useMemo(() => {
    if (!selectedGoal) return [];

    const relatedMilestones = data.milestones
      .filter((milestone) => !milestone.goalId || milestone.goalId === selectedGoal.id)
      .map<TimelineItem>((milestone) => ({
        id: `milestone-${milestone.id}`,
        date: milestone.createdAt,
        label: formatTimelineDate(milestone.createdAt),
        text: milestone.text,
        kind: 'milestone',
        note: milestone.note,
      }));

    const sessionItems = data.sessions.map<TimelineItem>((session) => ({
      id: `session-${session.id}`,
      date: session.date,
      label: formatTimelineDate(session.date),
      text: session.notes || `Сессия ${session.number}`,
      kind: 'session',
      note: session.coachNotes,
    }));

    const createdItem: TimelineItem = {
      id: `goal-created-${selectedGoal.id}`,
      date: selectedGoal.createdAt,
      label: formatTimelineDate(selectedGoal.createdAt),
      text: `Цель добавлена. Стартовый прогресс: ${selectedGoal.progress}%`,
      kind: 'goal',
    };

    return [...relatedMilestones, ...sessionItems, createdItem].sort(
      (left, right) => new Date(right.date).getTime() - new Date(left.date).getTime(),
    );
  }, [data.milestones, data.sessions, selectedGoal]);

  useEffect(() => {
    if (!activeSession) {
      setSessionNotes('');
      setNextTask('');
      lastSavedSessionRef.current = { sessionId: null, notes: '', coachNotes: '' };
      return;
    }

    const notes = activeSession.notes ?? '';
    const coachNotes = activeSession.coachNotes ?? '';
    setSessionNotes(notes);
    setNextTask(coachNotes);
    lastSavedSessionRef.current = {
      sessionId: activeSession.id,
      notes,
      coachNotes,
    };
  }, [activeSession]);

  useEffect(() => {
    if (!activeSession) {
      setMilestoneOpen(false);
    }
  }, [activeSession]);

  const intentionText = data.client?.intention?.trim() || data.client?.focus || 'Намерение пока не заполнено';

  const upsertSession = useCallback((session: CoachSession) => {
    setData((current) => ({
      ...current,
      sessions: sortCoachSessions([
        session,
        ...current.sessions.filter((item) => item.id !== session.id),
      ]),
    }));
  }, []);

  const persistActiveSession = useCallback(async (options?: { status?: 'draft' | 'done'; force?: boolean }) => {
    if (!activeSession) return null;

    const payload = {
      notes: sessionNotes,
      coachNotes: nextTask,
      ...(options?.status ? { status: options.status } : {}),
    };
    const lastSaved = lastSavedSessionRef.current;
    const hasContentChanges = (
      lastSaved.sessionId !== activeSession.id
      || lastSaved.notes !== payload.notes
      || lastSaved.coachNotes !== payload.coachNotes
    );

    if (!hasContentChanges && !options?.status && !options?.force) {
      return activeSession;
    }

    setSavingSession(true);
    try {
      const updated = await coachingApi.updateCoachSession(activeSession.id, payload);
      lastSavedSessionRef.current = {
        sessionId: updated.id,
        notes: updated.notes ?? '',
        coachNotes: updated.coachNotes ?? '',
      };
      upsertSession(updated);
      return updated;
    } catch {
      setActionMessage(options?.status === 'done' ? 'Не удалось завершить сессию.' : 'Не удалось сохранить заметки сессии.');
      return null;
    } finally {
      setSavingSession(false);
    }
  }, [activeSession, nextTask, sessionNotes, upsertSession]);

  useEffect(() => {
    if (!activeSession) return undefined;

    const lastSaved = lastSavedSessionRef.current;
    if (lastSaved.sessionId === activeSession.id && lastSaved.notes === sessionNotes && lastSaved.coachNotes === nextTask) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      void persistActiveSession();
    }, 1600);

    return () => window.clearTimeout(timeoutId);
  }, [activeSession, sessionNotes, nextTask, persistActiveSession]);

  const handleToggleStep = async (stepId: string, done: boolean) => {
    if (!selectedGoal) return;

    const goalId = selectedGoal.id;
    const previousSteps = selectedGoal.steps;

    setData((current) => ({
      ...current,
      goals: current.goals.map((goal) => (
        goal.id === goalId
          ? {
              ...goal,
              steps: goal.steps.map((step) => (
                step.id === stepId
                  ? {
                      ...step,
                      done,
                      doneAt: done ? new Date().toISOString() : null,
                    }
                  : step
              )),
            }
          : goal
      )),
    }));

    setSavingStepId(stepId);
    try {
      const response = await coachingApi.updateCoachGoalStep(goalId, stepId, { done });
      setData((current) => ({
        ...current,
        goals: current.goals.map((goal) => (goal.id === goalId ? { ...goal, steps: response.steps } : goal)),
      }));
    } catch {
      setData((current) => ({
        ...current,
        goals: current.goals.map((goal) => (goal.id === goalId ? { ...goal, steps: previousSteps } : goal)),
      }));
      setActionMessage('Не удалось обновить шаг.');
    } finally {
      setSavingStepId(null);
    }
  };

  const handleAddStep = async () => {
    if (!selectedGoal || !newStepText.trim()) return;

    setSavingGoalList(true);
    try {
      const step = await coachingApi.addCoachGoalStep(selectedGoal.id, {
        text: newStepText.trim(),
        dueDate: newStepDueDate || '',
      });
      setData((current) => ({
        ...current,
        goals: current.goals.map((goal) => (
          goal.id === selectedGoal.id ? { ...goal, steps: [...goal.steps, step] } : goal
        )),
      }));
      setNewStepText('');
      setNewStepDueDate('');
      setActionMessage('Шаг добавлен.');
    } catch {
      setActionMessage('Не удалось добавить шаг.');
    } finally {
      setSavingGoalList(false);
    }
  };

  const handleDeleteStep = async (stepId: string) => {
    if (!selectedGoal) return;

    setSavingStepId(stepId);
    try {
      await coachingApi.deleteCoachGoalStep(selectedGoal.id, stepId);
      setData((current) => ({
        ...current,
        goals: current.goals.map((goal) => (
          goal.id === selectedGoal.id
            ? { ...goal, steps: goal.steps.filter((step) => step.id !== stepId) }
            : goal
        )),
      }));
      setActionMessage('Шаг удалён.');
    } catch {
      setActionMessage('Не удалось удалить шаг.');
    } finally {
      setSavingStepId(null);
    }
  };

  const handleToggleStepMilestone = async (stepId: string, isMilestone: boolean) => {
    if (!selectedGoal) return;

    setSavingStepId(stepId);
    try {
      const response = await coachingApi.updateCoachGoalStep(selectedGoal.id, stepId, { isMilestone });
      setData((current) => ({
        ...current,
        goals: current.goals.map((goal) => (goal.id === selectedGoal.id ? { ...goal, steps: response.steps } : goal)),
      }));
    } catch {
      setActionMessage('Не удалось обновить веху шага.');
    } finally {
      setSavingStepId(null);
    }
  };

  const handleAddQuickGoal = async () => {
    const title = quickGoalTitle.trim();
    if (!title) return;

    setAddingQuickGoal(true);
    try {
      const nextGoals = await coachingApi.replaceCoachClientGoals(clientId, [
        ...data.goals,
        createMinimalGoal(title, selectedHorizon),
      ]);
      setData((current) => ({
        ...current,
        goals: nextGoals,
      }));
      const createdGoal = nextGoals.find((goal) => (
        goal.title === title
        && goal.horizon === selectedHorizon
        && goal.steps.length === 0
        && goal.progress === 0
      ));
      if (createdGoal) {
        setSelectedGoalId(createdGoal.id);
      }
      setQuickGoalTitle('');
      setActionMessage('Цель добавлена. Компетенции можно привязать позже в редакторе.');
    } catch {
      setActionMessage('Не удалось добавить цель.');
    } finally {
      setAddingQuickGoal(false);
    }
  };

  const handleOpenDueDatePicker = () => {
    newStepDueDateInputRef.current?.showPicker?.();
    newStepDueDateInputRef.current?.click();
  };

  const handleStartSession = async () => {
    setStartingSession(true);
    try {
      const session = await coachingApi.createCoachSession(clientId, {
        date: new Date().toISOString(),
      });
      upsertSession(session);
      setActionMessage(`Сессия ${session.number} начата.`);
    } catch {
      setActionMessage('Не удалось начать сессию.');
    } finally {
      setStartingSession(false);
    }
  };

  const handleFinishSession = async () => {
    if (!activeSession) return;

    setFinishingSession(true);
    try {
      const session = await persistActiveSession({ status: 'done', force: true });
      if (session) {
        setActionMessage(`Сессия ${session.number} завершена.`);
      }
    } finally {
      setFinishingSession(false);
    }
  };

  const handleSaveMilestone = async () => {
    if (!selectedGoal || !activeSession || !milestoneText.trim()) return;

    setSavingMilestone(true);
    try {
      const milestone = await coachingApi.createCoachMilestone(clientId, {
        goalId: selectedGoal.id,
        text: milestoneText.trim(),
        note: milestoneNote.trim(),
      });
      setData((current) => ({ ...current, milestones: [milestone, ...current.milestones] }));
      setMilestoneText('');
      setMilestoneNote('');
      setMilestoneOpen(false);
      setActionMessage('Веха добавлена.');
    } catch {
      setActionMessage('Не удалось создать веху.');
    } finally {
      setSavingMilestone(false);
    }
  };

  if (loading) {
    return <LoadingState />;
  }

  return (
    <div className="min-h-full bg-[#f5f4f0] p-3 text-[#1a1a18] sm:p-5">
      <div className="mx-auto flex min-h-[calc(100vh-72px)] max-w-[1400px] flex-col rounded-none border-[0.5px] border-[#e0ddd6] bg-[#f5f4f0] sm:rounded-[12px] lg:flex-row">
        <div className="w-full border-b-[0.5px] border-[#e0ddd6] bg-white lg:w-[340px] lg:border-b-0 lg:border-r-[0.5px]">
          <div className="flex border-b-[0.5px] border-[#e0ddd6]">
            {HORIZONS.map((horizon) => (
              <button
                key={horizon.key}
                type="button"
                onClick={() => setSelectedHorizon(horizon.key)}
                className={`flex-1 border-b-2 px-1 py-2 text-center text-[11px] transition-colors ${
                  selectedHorizon === horizon.key
                    ? 'border-[#185fa5] font-medium text-[#185fa5]'
                    : 'border-transparent text-[#73726c]'
                }`}
              >
                {horizon.label}
              </button>
            ))}
          </div>

          <div className="max-h-none overflow-visible p-3 lg:h-[calc(100vh-190px)] lg:max-h-[calc(100vh-190px)] lg:overflow-y-auto">
            {error ? (
              <div className="mb-3 rounded-[8px] border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
                {error}
              </div>
            ) : null}

            <div className="mb-[10px] rounded-[8px] border-l-[3px] border-[#7F77DD] bg-[#f5f4f0] px-3 py-[10px]">
              <div className="mb-[2px] text-[10px] font-medium uppercase tracking-[0.5px] text-[#7F77DD]">Намерение</div>
              <div className="text-[12px] leading-[1.5] text-[#1a1a18]">{intentionText}</div>
            </div>

            {visibleGoals.length > 0 ? (
              <div className="flex flex-col gap-2">
                {visibleGoals.map((goal) => {
                  const isActive = goal.id === selectedGoal?.id;
                  const goalColor = getGoalColor(goal);
                  return (
                    <div key={goal.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedGoalId(goal.id)}
                        className={`flex w-full items-center gap-2 rounded-[8px] border-[0.5px] px-[10px] py-[9px] text-left transition-colors ${
                          isActive
                            ? 'border-[#1D9E75] bg-[rgba(29,158,117,0.04)]'
                            : 'border-[#e0ddd6] bg-white hover:border-[#b4b2a9]'
                        }`}
                      >
                        <div className="flex h-6 w-6 shrink-0 items-center justify-center text-[#73726c]">
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 12 12"
                            aria-hidden="true"
                            className={`transition-transform ${isActive ? 'rotate-90' : ''}`}
                          >
                            <path
                              d="M4 2.5 8 6 4 9.5"
                              stroke="currentColor"
                              strokeWidth="1.8"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              fill="none"
                            />
                          </svg>
                        </div>
                        <div className="min-w-0 flex-1 text-[12px] leading-[1.4] text-[#1a1a18]">{goal.title}</div>
                        <div className="shrink-0 text-[11px] font-medium" style={{ color: goalColor }}>
                          {goal.progress}%
                        </div>
                      </button>
                      <div className="mx-[10px] mt-1 h-[3px] overflow-hidden rounded-[2px] bg-[#f1efe8] pl-6">
                        <div className="h-full rounded-[2px]" style={{ width: `${goal.progress}%`, backgroundColor: goalColor }} />
                      </div>

                      {isActive ? (
                        <div className="ml-6 mt-1 flex flex-col gap-1">
                          {goal.steps.map((step) => {
                            return (
                              <div
                                key={step.id}
                                className="rounded-[6px] border-[0.5px] border-[#e0ddd6] bg-white px-[10px] py-[7px]"
                              >
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => void handleToggleStep(step.id, !step.done)}
                                    disabled={savingStepId === step.id}
                                    className="flex h-[14px] w-[14px] shrink-0 items-center justify-center rounded-[3px] border-[0.5px] border-[#d3d1c7] disabled:cursor-not-allowed disabled:opacity-70"
                                  >
                                    <div
                                      className={`flex h-[14px] w-[14px] items-center justify-center rounded-[3px] ${
                                        step.done ? 'border-transparent bg-[#e1f5ee]' : ''
                                      }`}
                                    >
                                      {step.done ? (
                                        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                                          <path
                                            d="M2 5l2.5 2.5L8 3"
                                            stroke="#0f6e56"
                                            strokeWidth="1.5"
                                            fill="none"
                                            strokeLinecap="round"
                                          />
                                        </svg>
                                      ) : null}
                                    </div>
                                  </button>

                                  <div className="min-w-0 flex-1">
                                    <Link
                                      href={`/coach/clients/${clientId}/steps/${step.id}`}
                                      className={`block text-[11px] transition-colors hover:text-[#185fa5] hover:underline ${
                                        step.done ? 'text-[#73726c] opacity-60 line-through' : 'text-[#73726c]'
                                      }`}
                                    >
                                      {step.text}
                                    </Link>
                                  </div>

                                  {step.dueDate && !step.done ? (
                                    <div className="shrink-0 rounded-full bg-[rgba(186,117,23,0.1)] px-[6px] py-[1px] text-[10px] text-[#633806]">
                                      {formatShortDate(step.dueDate)}
                                    </div>
                                  ) : null}

                                  <div className="flex shrink-0 items-center gap-1">
                                    <button
                                      type="button"
                                      onClick={() => void handleToggleStepMilestone(step.id, !step.isMilestone)}
                                      disabled={savingStepId === step.id}
                                      className={`flex h-[27px] w-[27px] items-center justify-center rounded-[6px] border text-[13px] leading-none transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                                        step.isMilestone
                                          ? 'border-[#EF9F27] bg-[rgba(186,117,23,0.08)] text-[#BA7517]'
                                          : 'border-[#d7d2c7] text-[#b4b2a9] hover:bg-[#f5f4f0]'
                                      }`}
                                      aria-label={step.isMilestone ? `Убрать веху у шага ${step.text}` : `Сделать шаг вехой ${step.text}`}
                                      title={step.isMilestone ? 'Убрать веху' : 'Отметить как веху'}
                                    >
                                      ★
                                    </button>
                                  </div>
                                </div>
                              </div>
                            );
                          })}

                          <div className="flex flex-col gap-1.5">
                            <div className="flex flex-col gap-2 sm:flex-row">
                              <input
                                value={newStepText}
                                onChange={(event) => setNewStepText(event.target.value)}
                                onKeyDown={(event) => {
                                  if (event.key === 'Enter' && newStepText.trim()) {
                                    void handleAddStep();
                                  }
                                }}
                                disabled={false}
                                placeholder="Введите новый шаг"
                                className="min-w-0 h-[34px] flex-1 rounded-[6px] border-[0.5px] border-dashed border-[#e0ddd6] bg-white px-[10px] py-0 text-[11px] leading-[34px] text-[#1a1a18] outline-none placeholder:text-[#73726c] focus:border-[#b4b2a9]"
                              />
                              <input
                                ref={newStepDueDateInputRef}
                                type="date"
                                value={newStepDueDate}
                                onChange={(event) => setNewStepDueDate(event.target.value)}
                                title="Срок выполнения (необязательно)"
                                className="sr-only"
                                tabIndex={-1}
                                aria-hidden="true"
                              />
                              <button
                                type="button"
                                onClick={handleOpenDueDatePicker}
                                title={newStepDueDate ? `Срок: ${formatShortDate(newStepDueDate)}` : 'Выбрать срок'}
                                className={`shrink-0 rounded-[6px] border-[0.5px] px-[8px] py-[6px] transition-colors ${
                                  newStepDueDate
                                    ? 'border-[#BA7517] bg-[rgba(186,117,23,0.08)] text-[#633806]'
                                    : 'border-[#d3d1c7] text-[#73726c] hover:bg-[#f5f4f0]'
                                }`}
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                  <path
                                    d="M7 3v3M17 3v3M4 9h16M6 5h12a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z"
                                    stroke="currentColor"
                                    strokeWidth="1.7"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleAddStep()}
                                disabled={savingGoalList || !newStepText.trim()}
                                className="rounded-[6px] border-[0.5px] border-[#d3d1c7] px-3 py-[6px] text-[11px] text-[#73726c] transition-colors hover:bg-[#f5f4f0] disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {savingGoalList ? '...' : 'Добавить'}
                              </button>
                            </div>
                            <div className="text-[10px] text-[#b4b2a9]">Клиент увидит этот шаг как задание в своём кабинете</div>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-[8px] border-[0.5px] border-dashed border-[#e0ddd6] bg-white px-3 py-4">
                <div className="text-[12px] text-[#73726c]">
                  Для горизонта «{getHorizonLabel(selectedHorizon)}» пока нет целей.
                </div>
                <Link
                  href={`/coach/clients/${clientId}?tab=edit`}
                  className="mt-3 inline-flex rounded-[6px] bg-[#185fa5] px-3 py-2 text-[11px] text-white transition-opacity hover:opacity-90"
                >
                  + Добавить цели к кварталу →
                </Link>
                <div className="mt-1 text-[10px] text-[#73726c]">Откроется редактор в текущей вкладке.</div>
              </div>
            )}

            <div className="mt-3 rounded-[8px] bg-[#f5f4f0] p-3">
              <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.4px] text-[#73726c]">
                Быстрое добавление цели
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  value={quickGoalTitle}
                  onChange={(event) => setQuickGoalTitle(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && quickGoalTitle.trim()) {
                      event.preventDefault();
                      void handleAddQuickGoal();
                    }
                  }}
                  placeholder="Только название цели"
                  className="min-w-0 flex-1 rounded-[6px] border border-[#d7d2c7] bg-white px-3 py-2 text-[12px] text-[#1a1a18] outline-none placeholder:text-[#9a978f] focus:border-[#185fa5]"
                />
                <button
                  type="button"
                  onClick={() => void handleAddQuickGoal()}
                  disabled={addingQuickGoal || !quickGoalTitle.trim()}
                  className="rounded-[6px] border border-[#d7d2c7] px-3 py-2 text-[11px] text-[#4f4b45] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {addingQuickGoal ? '...' : 'Добавить'}
                </button>
              </div>
              <div className="mt-2 text-[10px] text-[#73726c]">
                Компетенции и точную структуру можно привязать позже в редакторе.
              </div>
            </div>
          </div>
        </div>

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-col gap-3 border-b-[0.5px] border-[#e0ddd6] px-4 py-[14px] sm:flex-row sm:items-center sm:justify-between">
            <div className="text-[13px] font-medium">{selectedGoal?.title || 'Цель не выбрана'}</div>
            <div className="flex flex-wrap items-center gap-[6px]">
              <button
                type="button"
                onClick={() => setMilestoneOpen((current) => !current)}
                disabled={!activeSession}
                className="rounded-[6px] border-[0.5px] border-[#EF9F27] bg-[rgba(186,117,23,0.06)] px-3 py-[5px] text-[11px] text-[#633806] transition-colors hover:bg-[rgba(186,117,23,0.12)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                ★ Веха
              </button>
              {activeSession ? (
                <button
                  type="button"
                  onClick={() => void handleFinishSession()}
                  disabled={finishingSession || savingSession}
                  className="rounded-[6px] bg-[#1D9E75] px-3 py-[5px] text-[11px] text-[#E1F5EE] transition-opacity disabled:cursor-wait disabled:opacity-70"
                >
                  {finishingSession ? 'Завершаю...' : 'Завершить сессию'}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleStartSession()}
                  disabled={startingSession}
                  className="rounded-[6px] bg-[#1D9E75] px-3 py-[5px] text-[11px] text-[#E1F5EE] transition-opacity disabled:cursor-wait disabled:opacity-70"
                >
                  {startingSession ? 'Создаю...' : `Начать сессию #${currentSessionNumber}`}
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {actionMessage ? <div className="mb-3 text-[11px] text-[#73726c]">{actionMessage}</div> : null}

            <div className="flex flex-col gap-[14px]">
              <div className={`${PANEL_CLASS} p-[14px]`}>
                <div className="mb-2 text-[11px] font-medium text-[#73726c]">Связанные компетенции</div>
                {selectedGoal && selectedGoal.competencyLinks.length > 0 ? (
                  <>
                    <div>
                      {selectedGoal.competencyLinks.map((link) => (
                        <span
                          key={`${selectedGoal.id}-${link.competencyId}`}
                          className={`mb-1 mr-1 inline-flex items-center gap-[5px] rounded-full px-[9px] py-[3px] text-[11px] font-medium ${getCompetencyTagClass(link.competencyName)}`}
                          style={getCompetencyTagStyle(link.competencyName, data.competencies)}
                        >
                          {link.competencyName} · {link.weight}%
                        </span>
                      ))}
                    </div>
                    <div className="mt-[10px] text-[11px] text-[#73726c]">
                      Прогресс по этой цели влияет на компетенции пропорционально весу.
                    </div>
                  </>
                ) : (
                  <div className="text-[12px] text-[#73726c]">У выбранной цели пока нет связанных компетенций.</div>
                )}
              </div>

              <div className={`${PANEL_CLASS} p-[14px]`}>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="text-[11px] font-medium text-[#73726c]">Заметки сессии {currentSessionNumber}</div>
                  {activeSession ? (
                    <div className="text-[10px] text-[#73726c]">
                      {savingSession ? 'Автосохранение...' : 'Автосохранение включено'}
                    </div>
                  ) : null}
                </div>

                {!activeSession ? (
                  <div className="space-y-3">
                    <div className="rounded-[8px] bg-[#f5f4f0] p-3">
                      <div className="mb-2 text-[11px] font-medium text-[#73726c]">
                        {lastCompletedSession ? `Последняя завершённая сессия #${lastCompletedSession.number}` : 'Последняя завершённая сессия'}
                      </div>
                      <div className="text-[12px] leading-[1.6] text-[#1a1a18]">
                        {lastCompletedSession?.notes || 'Заметок по завершённым сессиям пока нет.'}
                      </div>
                      <div className="mt-3 text-[11px] font-medium text-[#73726c]">Задание до следующей сессии</div>
                      <div className="mt-1 text-[12px] leading-[1.6] text-[#1a1a18]">
                        {lastCompletedSession?.coachNotes || 'Не задано.'}
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <textarea
                      value={sessionNotes}
                      onChange={(event) => setSessionNotes(event.target.value)}
                      onBlur={() => {
                        void persistActiveSession({ force: true });
                      }}
                      rows={4}
                      placeholder="Что происходит сегодня по этой цели? Инсайты, сопротивление, движение..."
                      className="w-full resize-none rounded-[6px] border-[0.5px] border-[#e0ddd6] bg-[#f5f4f0] px-[10px] py-2 text-[12px] leading-[1.5] text-[#1a1a18] outline-none placeholder:text-[#73726c] focus:border-[#b4b2a9]"
                    />
                    <div className="mt-[10px]">
                      <div className="mb-2 text-[11px] font-medium text-[#73726c]">Задание до следующей сессии</div>
                      <textarea
                        value={nextTask}
                        onChange={(event) => setNextTask(event.target.value)}
                        onBlur={() => {
                          void persistActiveSession({ force: true });
                        }}
                        rows={2}
                        placeholder="Конкретное действие до следующей встречи..."
                        className="w-full resize-none rounded-[6px] border-[0.5px] border-[#e0ddd6] bg-[#f5f4f0] px-[10px] py-2 text-[12px] leading-[1.5] text-[#1a1a18] outline-none placeholder:text-[#73726c] focus:border-[#b4b2a9]"
                      />
                    </div>
                  </>
                )}
              </div>

              {!activeSession ? (
                <div className={`${PANEL_CLASS} p-[14px]`}>
                  <div className="flex flex-col gap-2 text-[12px]">
                    <Link
                      href={`/contact/${clientId}?tab=schedule`}
                      className="text-[#185fa5] transition-colors hover:text-[#11497f] hover:underline"
                    >
                      Запланируйте сессию
                    </Link>
                    <Link
                      href="/clients/schedule"
                      className="text-[#185fa5] transition-colors hover:text-[#11497f] hover:underline"
                    >
                      Обзор календаря
                    </Link>
                  </div>
                </div>
              ) : null}

              <div className={`${PANEL_CLASS} p-[14px]`}>
                <div className="mb-2 text-[11px] font-medium text-[#73726c]">Обновить прогресс цели</div>
                <div className="mt-1 flex items-center gap-[10px]">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={draftProgress}
                    onChange={(event) => setDraftProgress(Number(event.target.value))}
                    className="flex-1 accent-[#1D9E75]"
                    disabled={!selectedGoal || !activeSession}
                  />
                  <span className="min-w-[36px] text-[14px] font-medium">{draftProgress}%</span>
                </div>
                <div className="mt-[6px] text-[11px] text-[#73726c]">
                  {!activeSession
                    ? 'Прогресс редактируется только внутри активной сессии.'
                    : savingProgress
                      ? 'Обновляю прогресс...'
                      : 'Изменение автоматически обновит прогресс цели и связанные компетенции.'}
                </div>
              </div>

              <div className={`${PANEL_CLASS} p-[14px]`}>
                <div className="mb-2 text-[11px] font-medium text-[#73726c]">История и вехи</div>

                {milestoneOpen ? (
                  <div className="mb-3 rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-[#f5f4f0] p-3">
                    <input
                      value={milestoneText}
                      onChange={(event) => setMilestoneText(event.target.value)}
                      placeholder="Что стало вехой по этой цели?"
                      className="mb-2 w-full rounded-[6px] border-[0.5px] border-[#e0ddd6] bg-white px-[10px] py-2 text-[12px] outline-none placeholder:text-[#73726c] focus:border-[#b4b2a9]"
                    />
                    <textarea
                      value={milestoneNote}
                      onChange={(event) => setMilestoneNote(event.target.value)}
                      rows={2}
                      placeholder="Короткая заметка к вехе"
                      className="w-full rounded-[6px] border-[0.5px] border-[#e0ddd6] bg-white px-[10px] py-2 text-[12px] outline-none placeholder:text-[#73726c] focus:border-[#b4b2a9]"
                    />
                    <div className="mt-2 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void handleSaveMilestone()}
                        disabled={savingMilestone || !milestoneText.trim() || !selectedGoal}
                        className="rounded-[6px] bg-[#1D9E75] px-3 py-[5px] text-[11px] text-[#E1F5EE] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {savingMilestone ? 'Сохраняю...' : 'Сохранить веху'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setMilestoneOpen(false)}
                        className="rounded-[6px] border-[0.5px] border-[#d3d1c7] px-3 py-[5px] text-[11px] text-[#73726c]"
                      >
                        Отмена
                      </button>
                    </div>
                  </div>
                ) : null}

                {timelineItems.length > 0 ? (
                  <div className="relative pl-5">
                    <div className="absolute bottom-[6px] left-[6px] top-[6px] w-px bg-[#e0ddd6]" />
                    {timelineItems.map((item) => (
                      <div key={item.id} className="relative mb-3 last:mb-0">
                        <div
                          className={`absolute -left-[17px] top-[3px] h-2 w-2 rounded-full ${
                            item.kind === 'milestone'
                              ? 'bg-[#EF9F27]'
                              : item.kind === 'session'
                                ? 'bg-[#1D9E75]'
                                : 'bg-[#d3d1c7]'
                          }`}
                        />
                        <div className="text-[10px] text-[#73726c]">{item.label}</div>
                        <div className="text-[12px] leading-[1.4] text-[#1a1a18]">{item.text}</div>
                        {item.kind === 'milestone' && item.note ? (
                          <div className="mt-[2px] inline-block rounded-full bg-[rgba(186,117,23,0.12)] px-[6px] py-[1px] text-[10px] text-[#633806]">
                            ★ Веха - {item.note}
                          </div>
                        ) : null}
                        {item.kind === 'session' && item.note ? (
                          <div className="mt-[2px] text-[10px] text-[#73726c]">{item.note}</div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-[12px] text-[#73726c]">История по этой цели пока пустая.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="min-h-full bg-[#f5f4f0] p-3 sm:p-5">
      <div className="mx-auto flex min-h-[calc(100vh-72px)] max-w-[1400px] animate-pulse flex-col rounded-none border-[0.5px] border-[#e0ddd6] bg-[#f5f4f0] sm:rounded-[12px] lg:flex-row">
        <div className="w-full border-b-[0.5px] border-[#e0ddd6] bg-white p-4 lg:w-[340px] lg:border-b-0 lg:border-r-[0.5px]">
          <div className="h-10 rounded-[8px] bg-[#ece7dd]" />
          <div className="mt-4 h-8 rounded-[8px] bg-[#ece7dd]" />
          <div className="mt-4 h-24 rounded-[8px] bg-[#ece7dd]" />
          <div className="mt-3 h-56 rounded-[8px] bg-[#ece7dd]" />
        </div>
        <div className="flex-1 p-4">
          <div className="h-10 rounded-[8px] bg-[#ece7dd]" />
          <div className="mt-4 h-28 rounded-[8px] bg-[#ece7dd]" />
          <div className="mt-4 h-40 rounded-[8px] bg-[#ece7dd]" />
          <div className="mt-4 h-36 rounded-[8px] bg-[#ece7dd]" />
        </div>
      </div>
    </div>
  );
}

function normalizeWorkspaceData(source?: WorkspaceData | null): WorkspaceData {
  return {
    client: source?.client ?? null,
    competencies: source?.competencies ?? [],
    goals: source?.goals ?? [],
    milestones: source?.milestones ?? [],
    sessions: source?.sessions ?? [],
  };
}

function getGoalColor(goal: CoachGoalTreeNode) {
  if (goal.competencyLinks.some((item) => item.competencyName === 'Границы')) return '#1D9E75';
  if (goal.competencyLinks.some((item) => item.competencyName === 'Уверенность')) return '#7F77DD';
  if (goal.competencyLinks.some((item) => item.competencyName === 'Коммуникация')) return '#378ADD';
  return '#1D9E75';
}

function getCompetencyTagClass(name: string) {
  if (name === 'Границы') return 'bg-[rgba(29,158,117,0.1)] text-[#0F6E56]';
  if (name === 'Уверенность') return 'bg-[rgba(127,119,221,0.1)] text-[#3C3489]';
  if (name === 'Коммуникация') return 'bg-[rgba(55,138,221,0.1)] text-[#185FA5]';
  return 'bg-[rgba(239,159,39,0.12)] text-[#633806]';
}

function getCompetencyTagStyle(name: string, competencies: CoachingCompetency[]) {
  const competency = competencies.find((item) => item.name === name);
  if (!competency?.color) {
    return undefined;
  }
  return {
    backgroundColor: `${competency.color}1A`,
    color: competency.color,
  };
}

function formatTimelineDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Дата неизвестна';
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date);
}

function getInitials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('') || '—';
}

function getHorizonLabel(horizon: 'year' | 'quarter' | 'month') {
  if (horizon === 'year') return 'Год';
  if (horizon === 'month') return 'Месяц';
  return 'Квартал';
}

function sortCoachSessions(sessions: CoachSession[]) {
  return [...sessions].sort((left, right) => {
    if (left.status !== right.status) {
      return left.status === 'draft' ? -1 : 1;
    }
    return new Date(right.date).getTime() - new Date(left.date).getTime();
  });
}

function createMinimalGoal(title: string, horizon: 'year' | 'quarter' | 'month'): CoachGoalTreeNode {
  const goalId = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `goal-${Math.random().toString(36).slice(2, 10)}`;

  return {
    id: goalId,
    title,
    progress: 0,
    horizon,
    status: 'active',
    competencyLinks: [],
    steps: [],
    createdAt: new Date().toISOString(),
  };
}

function formatShortDate(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(d);
}
