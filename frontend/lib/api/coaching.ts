import { API_BASE_URL, ApiError, apiFetch } from '../api';
import type { OperatorTaskHistory } from '../types';

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
  email?: string;
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

export type CoachStepHistoryEntry = OperatorTaskHistory;
export type CoachStepUpdatePayload = {
  done?: boolean;
  text?: string;
  dueDate?: string | null;
  isMilestone?: boolean;
  milestoneNote?: string;
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
  status: 'draft' | 'done';
};

export type PublicClientCoachingPortalResponse = {
  client?: {
    id?: number;
    name?: string;
    intention?: string;
    focus?: string;
  };
  goals?: CoachGoalTreeNode[];
  competencies?: CoachingCompetency[];
  milestones?: CoachMilestone[];
};

export type PublicClientCoachingStepResponse = CoachGoalStep;
export type PublicClientStepsResponse = {
  contact_id?: number;
  items?: CoachGoalStep[];
};

export type CoachInviteLink = {
  id: string;
  clientId: string;
  token: string;
  url: string;
  expiresAt: string | null;
  usedAt: string | null;
  createdAt: string;
};

async function publicCoachingFetch<TResponse>(endpoint: string, options: RequestInit = {}): Promise<TResponse> {
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const response = await fetch(`${API_BASE_URL}${normalizedEndpoint}`, {
    ...options,
    credentials: 'include',
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || 'API request failed', response.status, text);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  return (await response.json()) as TResponse;
}

function buildPublicCoachingEndpoint(
  baseEndpoint: string,
  options?: { contactId?: number | string | null },
): string {
  const normalizedBaseEndpoint = baseEndpoint.startsWith('/') ? baseEndpoint : `/${baseEndpoint}`;
  const rawContactId = options?.contactId;
  if (rawContactId === undefined || rawContactId === null || String(rawContactId).trim() === '') {
    return normalizedBaseEndpoint;
  }

  const params = new URLSearchParams();
  params.set('contact_id', String(rawContactId));
  const separator = normalizedBaseEndpoint.includes('?') ? '&' : '?';
  return `${normalizedBaseEndpoint}${separator}${params.toString()}`;
}

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
      body: goals
        .filter((goal) => !isSystemGroupGoalId(goal.id))
        .map(serializeCoachGoal),
    });
    return response.map(normalizeCoachGoal);
  },

  addCoachGoalStep: async (
    goalId: string,
    payload: { text: string; dueDate?: string | null },
  ): Promise<CoachGoalStep> => {
    const response = await apiFetch<CoachGoalStep>(`/goals/${goalId}/steps/`, {
      method: 'POST',
      body: payload,
    });
    return normalizeCoachStep(response);
  },

  deleteCoachGoalStep: async (goalId: string, stepId: string): Promise<void> => {
    await apiFetch<void>(`/goals/${goalId}/steps/${stepId}/`, { method: 'DELETE' });
  },

  getClientSteps: async (
    clientId: number | string,
    filters?: { done?: boolean },
  ): Promise<CoachGoalStep[]> => {
    const qs = filters?.done !== undefined ? `?done=${filters.done}` : '';
    const response = await apiFetch<CoachGoalStep[]>(`/clients/${clientId}/steps/${qs}`);
    return Array.isArray(response) ? response.map(normalizeCoachStep) : [];
  },

  toggleCoachGoalStep: async (
    goalId: string,
    stepId: string,
    done: boolean,
  ): Promise<{ id: string; steps: CoachGoalStep[] }> => {
    const response = await apiFetch<{ id: string; steps: CoachGoalStep[] }>(`/goals/${goalId}/steps/${stepId}/`, {
      method: 'PATCH',
      body: { done },
    });
    return {
      ...response,
      id: String(response.id),
      steps: Array.isArray(response.steps) ? response.steps.map(normalizeCoachStep) : [],
    };
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

  getClientCoachingPortal: async (
    clientId: number | string,
    options?: { contactId?: number | string | null },
  ): Promise<PublicClientCoachingPortalResponse> => {
    return publicCoachingFetch<PublicClientCoachingPortalResponse>(
      buildPublicCoachingEndpoint(`/public/client-page/${clientId}/coaching/`, options),
    );
  },

  getPublicClientSteps: async (
    clientId: number | string,
    filters?: { done?: boolean },
    options?: { contactId?: number | string | null },
  ): Promise<CoachGoalStep[]> => {
    const params = new URLSearchParams();
    if (filters?.done !== undefined) {
      params.set('done', String(filters.done));
    }
    const endpoint = buildPublicCoachingEndpoint(
      `/public/client-page/${clientId}/steps/${params.toString() ? `?${params.toString()}` : ''}`,
      options,
    );
    const response = await publicCoachingFetch<PublicClientStepsResponse | CoachGoalStep[]>(endpoint);
    const items = Array.isArray(response) ? response : response.items ?? [];
    return Array.isArray(items) ? items.map(normalizeCoachStep) : [];
  },

  editClientCoachingStep: async (
    clientId: number | string,
    stepId: string,
    payload: CoachStepUpdatePayload,
    options?: { contactId?: number | string | null },
  ): Promise<PublicClientCoachingStepResponse> => {
    const response = await publicCoachingFetch<PublicClientCoachingStepResponse>(
      buildPublicCoachingEndpoint(`/public/client-page/${clientId}/steps/${stepId}/`, options),
      {
        method: 'PATCH',
        body: JSON.stringify(payload),
      },
    );
    return normalizeCoachStep(response);
  },

  updateClientCoachingStep: async (
    clientId: number | string,
    stepId: string,
    done: boolean,
    options?: { contactId?: number | string | null },
  ): Promise<PublicClientCoachingStepResponse> => {
    return coachingApi.editClientCoachingStep(clientId, stepId, { done }, options);
  },

  getClientStepHistory: async (
    clientId: number | string,
    stepId: string,
    options?: { contactId?: number | string | null },
  ): Promise<CoachStepHistoryEntry[]> => {
    return publicCoachingFetch<CoachStepHistoryEntry[]>(
      buildPublicCoachingEndpoint(`/public/client-page/${clientId}/steps/${stepId}/history/`, options),
    );
  },

  addClientStepComment: async (
    clientId: number | string,
    stepId: string,
    note: string,
    options?: { contactId?: number | string | null },
  ): Promise<CoachStepHistoryEntry> => {
    return publicCoachingFetch<CoachStepHistoryEntry>(
      buildPublicCoachingEndpoint(`/public/client-page/${clientId}/steps/${stepId}/history/`, options),
      {
        method: 'POST',
        body: JSON.stringify({ note }),
      },
    );
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

  updateCoachSession: async (
    sessionId: string,
    payload: { notes?: string; coachNotes?: string; status?: 'draft' | 'done' },
  ): Promise<CoachSession> => {
    return apiFetch<CoachSession>(`/sessions/${sessionId}/`, {
      method: 'PATCH',
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
    payload: { done?: boolean; text?: string; dueDate?: string | null; isMilestone?: boolean; milestoneNote?: string },
  ): Promise<{ id: string; steps: CoachGoalStep[] }> => {
    const response = await apiFetch<{ id: string; steps: CoachGoalStep[] }>(`/goals/${goalId}/steps/${stepId}/`, {
      method: 'PATCH',
      body: payload,
    });
    return {
      ...response,
      id: String(response.id),
      steps: Array.isArray(response.steps) ? response.steps.map(normalizeCoachStep) : [],
    };
  },

  getCoachStepHistory: async (stepId: string): Promise<CoachStepHistoryEntry[]> => {
    return apiFetch<CoachStepHistoryEntry[]>(`/telegram-tasks/crm-tasks/${stepId}/history/`);
  },

  addCoachStepComment: async (stepId: string, note: string): Promise<CoachStepHistoryEntry> => {
    return apiFetch<CoachStepHistoryEntry>(`/telegram-tasks/crm-tasks/${stepId}/history/`, {
      method: 'POST',
      body: { note },
    });
  },
};

function normalizeCoachGoal(goal: CoachGoalTreeNode): CoachGoalTreeNode {
  return {
    ...goal,
    id: String(goal.id || ''),
    title: String(goal.title || ''),
    competencyLinks: Array.isArray(goal.competencyLinks)
      ? goal.competencyLinks.map((link) => ({
          ...link,
          competencyId: String(link.competencyId || ''),
          competencyName: String(link.competencyName || ''),
          weight: Number(link.weight || 0),
        }))
      : [],
    steps: Array.isArray(goal.steps)
      ? goal.steps.map(normalizeCoachStep)
      : [],
    createdAt: goal.createdAt || new Date().toISOString(),
  };
}

function normalizeCoachStep(step: CoachGoalStep): CoachGoalStep {
  return {
    ...step,
    id: String(step.id || ''),
    text: String(step.text || ''),
    milestoneNote: String(step.milestoneNote || ''),
    doneAt: step.doneAt || null,
    dueDate: step.dueDate || null,
    goalId: step.goalId != null && String(step.goalId).trim() ? String(step.goalId) : undefined,
    goalTitle: step.goalTitle != null ? String(step.goalTitle) : undefined,
  };
}

function serializeCoachGoal(goal: CoachGoalTreeNode): CoachGoalTreeNode {
  return {
    ...goal,
    title: String(goal.title || ''),
    createdAt: String(goal.createdAt || new Date().toISOString()),
    competencyLinks: Array.isArray(goal.competencyLinks)
      ? goal.competencyLinks.map((link) => ({
          ...link,
          weight: Number(((Number(link.weight || 0)) / 100).toFixed(4)),
        }))
      : [],
    steps: Array.isArray(goal.steps)
      ? goal.steps.map((step) => ({
          ...step,
          text: String(step.text || ''),
          milestoneNote: String(step.milestoneNote || ''),
          doneAt: String(step.doneAt || ''),
          dueDate: String(step.dueDate || ''),
          goalId: String(step.goalId || ''),
          goalTitle: String(step.goalTitle || goal.title || ''),
        }))
      : [],
  };
}

function isSystemGroupGoalId(goalId: string | null | undefined): boolean {
  return String(goalId || '').startsWith('group-');
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

  updateCoachClient: async (
    clientId: number | string,
    payload: { intention: string },
  ): Promise<CoachingClient> => {
    return apiFetch<CoachingClient>(`/clients/${clientId}/`, {
      method: 'PATCH',
      body: payload,
    });
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
  updateCoachClient(clientId: number | string, payload: { intention: string }): Promise<CoachingClient>;
  completeCoachTask(taskId: string): Promise<CoachTask>;
  saveCoachClientCompetencies(clientId: number | string, competencies: CoachingCompetency[]): Promise<CoachingCompetency[]>;
};

export const coachingApiExt = coachingApi as CoachingApiExtended;

export type CoachGroup = {
  id: string;
  name: string;
  initials: string;
  memberCount: number;
  createdAt: string;
};

export type CoachGroupMember = {
  clientId: string;
  name: string;
  initials: string;
  focus: string;
  avgProgress: number;
};

export type CoachGroupTask = {
  id: string;
  groupId: string;
  text: string;
  dueDate: string | null;
  createdAt: string;
  doneCount: number;
  totalCount: number;
};

export type CoachGroupDetail = {
  group: CoachGroup;
  members: CoachGroupMember[];
  tasks: CoachGroupTask[];
};

Object.assign(coachingApi, {
  getCoachGroups: async (): Promise<CoachGroup[]> => {
    return apiFetch<CoachGroup[]>('/coach/groups/');
  },

  createCoachGroup: async (name: string): Promise<CoachGroup> => {
    return apiFetch<CoachGroup>('/coach/groups/', {
      method: 'POST',
      body: { name },
    });
  },

  getCoachGroupDetail: async (groupId: string): Promise<CoachGroupDetail> => {
    return apiFetch<CoachGroupDetail>(`/coach/groups/${groupId}/`);
  },

  deleteCoachGroup: async (groupId: string): Promise<void> => {
    await apiFetch<void>(`/coach/groups/${groupId}/`, {
      method: 'DELETE',
    });
  },

  addGroupMember: async (groupId: string, clientId: string): Promise<CoachGroupMember> => {
    return apiFetch<CoachGroupMember>(`/coach/groups/${groupId}/members/`, {
      method: 'POST',
      body: { clientId: Number(clientId) },
    });
  },

  addGroupMembers: async (groupId: string, clientIds: string[]): Promise<CoachGroupMember[]> => {
    return apiFetch<CoachGroupMember[]>(`/coach/groups/${groupId}/members/bulk/`, {
      method: 'POST',
      body: { clientIds: clientIds.map((clientId) => Number(clientId)) },
    });
  },

  removeGroupMember: async (groupId: string, clientId: string): Promise<void> => {
    await apiFetch<void>(`/coach/groups/${groupId}/members/${clientId}/`, {
      method: 'DELETE',
    });
  },

  createGroupTask: async (
    groupId: string,
    payload: { text: string; dueDate?: string | null },
  ): Promise<CoachGroupTask> => {
    return apiFetch<CoachGroupTask>(`/coach/groups/${groupId}/tasks/`, {
      method: 'POST',
      body: {
        text: payload.text,
        dueDate: payload.dueDate || null,
      },
    });
  },

  deleteGroupTask: async (groupId: string, taskId: string): Promise<void> => {
    await apiFetch<void>(`/coach/groups/${groupId}/tasks/${taskId}/`, {
      method: 'DELETE',
    });
  },
});

export type CoachingApiWithGroups = typeof coachingApi & {
  getCoachGroups(): Promise<CoachGroup[]>;
  createCoachGroup(name: string): Promise<CoachGroup>;
  getCoachGroupDetail(groupId: string): Promise<CoachGroupDetail>;
  deleteCoachGroup(groupId: string): Promise<void>;
  addGroupMember(groupId: string, clientId: string): Promise<CoachGroupMember>;
  addGroupMembers(groupId: string, clientIds: string[]): Promise<CoachGroupMember[]>;
  removeGroupMember(groupId: string, clientId: string): Promise<void>;
  createGroupTask(groupId: string, payload: { text: string; dueDate?: string | null }): Promise<CoachGroupTask>;
  deleteGroupTask(groupId: string, taskId: string): Promise<void>;
};

export const coachingApiGroups = coachingApi as CoachingApiWithGroups;

Object.assign(coachingApi, {
  createInviteLink: async (clientId: string | number): Promise<CoachInviteLink> => {
    return apiFetch<CoachInviteLink>(`/clients/${clientId}/invite/`, {
      method: 'POST',
    });
  },

  revokeInviteLink: async (clientId: string | number): Promise<void> => {
    await apiFetch<void>(`/clients/${clientId}/invite/`, {
      method: 'DELETE',
    });
  },
});

export type CoachingApiWithInvites = typeof coachingApi & {
  createInviteLink(clientId: string | number): Promise<CoachInviteLink>;
  revokeInviteLink(clientId: string | number): Promise<void>;
};

export const coachingApiInvites = coachingApi as CoachingApiWithInvites;
