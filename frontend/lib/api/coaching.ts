import { apiFetch } from '../api';

export type CoachStats = {
  activeClients: number;
  completedTasks: number;
  tasksCompletionRate?: number;
  avgProgress: number;
  sessionsToday: number;
};

export type CoachingClientStatus = {
  kind: 'today' | 'tomorrow' | 'overdue' | 'milestone' | 'new' | 'inactive';
  label: string;
  at: string | null;
} | null;

export type CoachingClient = {
  id: string;
  name: string;
  initials: string;
  focus: string;
  intention?: string;
  sessionsCount: number;
  avgProgress: number;
  nextSession: string | null;
  clientStatus: CoachingClientStatus;
  coachId: string;
  createdAt: string;
};

export type CoachingCompetency = {
  id: string;
  name: string;
  score: number;
  startScore: number;
  color?: string;
};

export type CoachGoalStep = {
  id: string;
  text: string;
  done: boolean;
  isMilestone: boolean;
  milestoneNote: string;
  doneAt: string | null;
  dueDate: string | null;
  goalId?: string;
  goalTitle?: string;
};

export type CoachGoalCompetencyLink = {
  competencyId: string;
  competencyName: string;
  weight: number;
};

export type CoachGoalTreeNode = {
  id: string;
  title: string;
  progress: number;
  horizon: 'year' | 'quarter' | 'month';
  status: 'active' | 'paused' | 'achieved' | 'revised';
  competencyLinks: CoachGoalCompetencyLink[];
  steps: CoachGoalStep[];
  createdAt: string;
};

export type CoachMilestone = {
  id: string;
  clientId: number;
  goalId: string;
  text: string;
  note: string;
  createdAt: string;
};

export type CoachSession = {
  id: string;
  clientId: number;
  number: number;
  date: string;
  notes: string;
  coachNotes: string;
};

export const coachingApi = {
  getCoachStats: async (): Promise<CoachStats> => {
    return apiFetch<CoachStats>('/coach/stats/');
  },

  getCoachClients: async (): Promise<CoachingClient[]> => {
    return apiFetch<CoachingClient[]>('/coach/clients/');
  },

  getCoachClient: async (clientId: number | string): Promise<CoachingClient> => {
    return apiFetch<CoachingClient>(`/clients/${clientId}/`);
  },

  getCoachClientCompetencies: async (clientId: number | string): Promise<CoachingCompetency[]> => {
    return apiFetch<CoachingCompetency[]>(`/clients/${clientId}/competencies/`);
  },

  getCoachClientGoals: async (clientId: number | string): Promise<CoachGoalTreeNode[]> => {
    const goals = await apiFetch<CoachGoalTreeNode[]>(`/clients/${clientId}/goals/edit/`);
    return goals.map(normalizeCoachGoal);
  },

  replaceCoachClientGoals: async (clientId: number | string, goals: CoachGoalTreeNode[]): Promise<CoachGoalTreeNode[]> => {
    const response = await apiFetch<CoachGoalTreeNode[]>(`/clients/${clientId}/goals/edit/`, {
      method: 'PUT',
      body: goals,
    });
    return response.map(normalizeCoachGoal);
  },

  addCoachGoalStep: async (
    goalId: string,
    payload: { text: string; dueDate?: string | null },
  ): Promise<CoachGoalStep> => {
    return apiFetch<CoachGoalStep>(`/goals/${goalId}/steps/`, {
      method: 'POST',
      body: payload,
    });
  },

  deleteCoachGoalStep: async (goalId: string, stepId: string): Promise<void> => {
    await apiFetch<void>(`/goals/${goalId}/steps/${stepId}/`, { method: 'DELETE' });
  },

  getClientSteps: async (
    clientId: number | string,
    filters?: { done?: boolean },
  ): Promise<CoachGoalStep[]> => {
    const qs = filters?.done !== undefined ? `?done=${filters.done}` : '';
    return apiFetch<CoachGoalStep[]>(`/clients/${clientId}/steps/${qs}`);
  },

  toggleCoachGoalStep: async (
    goalId: string,
    stepId: string,
    done: boolean,
  ): Promise<{ id: string; steps: CoachGoalStep[] }> => {
    return apiFetch<{ id: string; steps: CoachGoalStep[] }>(`/goals/${goalId}/steps/${stepId}/`, {
      method: 'PATCH',
      body: { done },
    });
  },

  getCoachClientMilestones: async (clientId: number | string): Promise<CoachMilestone[]> => {
    return apiFetch<CoachMilestone[]>(`/clients/${clientId}/milestones/`);
  },

  createCoachMilestone: async (
    clientId: number | string,
    payload: { goalId?: string; text: string; note?: string },
  ): Promise<CoachMilestone> => {
    return apiFetch<CoachMilestone>(`/clients/${clientId}/milestones/`, {
      method: 'POST',
      body: payload,
    });
  },

  getCoachClientSessions: async (clientId: number | string): Promise<CoachSession[]> => {
    return apiFetch<CoachSession[]>(`/clients/${clientId}/sessions/`);
  },

  createCoachSession: async (
    clientId: number | string,
    payload: { date?: string; notes?: string; coachNotes?: string },
  ): Promise<CoachSession> => {
    return apiFetch<CoachSession>(`/clients/${clientId}/sessions/`, {
      method: 'POST',
      body: payload,
    });
  },

  updateCoachGoal: async (goalId: string, payload: { progress: number }): Promise<{ id: string; progress: number }> => {
    return apiFetch<{ id: string; progress: number }>(`/goals/${goalId}/`, {
      method: 'PATCH',
      body: payload,
    });
  },

  updateCoachGoalStep: async (
    goalId: string,
    stepId: string,
    payload: { done: boolean },
  ): Promise<{ id: string; steps: CoachGoalStep[] }> => {
    return apiFetch<{ id: string; steps: CoachGoalStep[] }>(`/goals/${goalId}/steps/${stepId}/`, {
      method: 'PATCH',
      body: payload,
    });
  },
};

function normalizeCoachGoal(goal: CoachGoalTreeNode): CoachGoalTreeNode {
  return {
    ...goal,
    competencyLinks: Array.isArray(goal.competencyLinks) ? goal.competencyLinks : [],
    steps: Array.isArray(goal.steps)
      ? goal.steps.map((step) => ({
          ...step,
          doneAt: step.doneAt || null,
          dueDate: step.dueDate || null,
        }))
      : [],
    createdAt: goal.createdAt || new Date().toISOString(),
  };
}

export type CoachTask = {
  id: string;
  clientId: number;
  goalId: string | null;
  goalTitle: string;
  sessionId: string | null;
  text: string;
  status: 'pending' | 'done' | 'overdue';
  dueDate: string | null;
  doneAt: string | null;
  createdAt: string;
};

Object.assign(coachingApi, {
  getCoachClientTasks: async (clientId: number | string): Promise<CoachTask[]> => {
    return apiFetch<CoachTask[]>(`/clients/${clientId}/tasks/`);
  },

  completeCoachTask: async (taskId: string): Promise<CoachTask> => {
    return apiFetch<CoachTask>(`/tasks/${taskId}/`, {
      method: 'PATCH',
      body: { status: 'done' },
    });
  },

  saveCoachClientCompetencies: async (
    clientId: number | string,
    competencies: CoachingCompetency[],
  ): Promise<CoachingCompetency[]> => {
    return apiFetch<CoachingCompetency[]>(`/clients/${clientId}/competencies/`, {
      method: 'PUT',
      body: competencies,
    });
  },
});

export type CoachingApiExtended = typeof coachingApi & {
  getCoachClientTasks(clientId: number | string): Promise<CoachTask[]>;
  completeCoachTask(taskId: string): Promise<CoachTask>;
  saveCoachClientCompetencies(clientId: number | string, competencies: CoachingCompetency[]): Promise<CoachingCompetency[]>;
};

export const coachingApiExt = coachingApi as CoachingApiExtended;
