import type { OperatorTask, OperatorTaskHistory, OperatorTaskStatus } from '../types';

// ---------------------------------------------------------------------------
// Mock store — replace with real apiFetch calls once backend is ready
// ---------------------------------------------------------------------------

let taskIdCounter = 10;
let historyIdCounter = 100;

const mockTasks: OperatorTask[] = [
  {
    id: 1,
    level_id: 1,
    title: 'Низкая оценка от клиента @ivan_petrov',
    description: 'Клиент поставил оценку 5/10 и оставил комментарий о задержках.',
    status: 'open',
    created_by: 0,
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
    history: [],
  },
  {
    id: 2,
    level_id: null,
    title: 'Уточнить детали договора',
    description: null,
    status: 'done',
    created_by: 1,
    created_at: new Date(Date.now() - 172800000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
    history: [
      {
        id: 1,
        task_id: 2,
        note: 'Связался с клиентом, договор уточнён.',
        status: 'in_progress',
        created_by: 1,
        created_at: new Date(Date.now() - 7200000).toISOString(),
      },
      {
        id: 2,
        task_id: 2,
        note: 'Клиент подтвердил все условия.',
        status: 'done',
        created_by: 1,
        created_at: new Date(Date.now() - 3600000).toISOString(),
      },
    ],
  },
];

export const operatorTasksApi = {
  list(params?: { level_id?: number }): Promise<OperatorTask[]> {
    let result = [...mockTasks];
    if (params?.level_id != null) {
      result = result.filter((t) => t.level_id === params.level_id);
    }
    return Promise.resolve(result.map((t) => ({ ...t, history: [...(t.history ?? [])] })));
  },

  get(id: number): Promise<OperatorTask> {
    const task = mockTasks.find((t) => t.id === id);
    if (!task) return Promise.reject(new Error(`Task ${id} not found`));
    return Promise.resolve({ ...task, history: [...(task.history ?? [])] });
  },

  create(data: {
    level_id?: number | null;
    title: string;
    description?: string | null;
    created_by?: number;
  }): Promise<OperatorTask> {
    const now = new Date().toISOString();
    const task: OperatorTask = {
      id: ++taskIdCounter,
      level_id: data.level_id ?? null,
      title: data.title,
      description: data.description ?? null,
      status: 'open',
      created_by: data.created_by ?? 0,
      created_at: now,
      updated_at: now,
      history: [],
    };
    mockTasks.push(task);
    return Promise.resolve({ ...task });
  },

  addHistory(
    taskId: number,
    data: {
      note: string;
      status?: OperatorTaskStatus | null;
      created_by?: number;
    },
  ): Promise<OperatorTaskHistory> {
    const task = mockTasks.find((t) => t.id === taskId);
    if (!task) return Promise.reject(new Error(`Task ${taskId} not found`));

    const entry: OperatorTaskHistory = {
      id: ++historyIdCounter,
      task_id: taskId,
      note: data.note,
      status: data.status ?? null,
      created_by: data.created_by ?? 0,
      created_at: new Date().toISOString(),
    };

    task.history = [...(task.history ?? []), entry];

    if (data.status != null) {
      task.status = data.status;
      task.updated_at = entry.created_at;
    }

    return Promise.resolve({ ...entry });
  },

  delete(id: number): Promise<void> {
    const idx = mockTasks.findIndex((t) => t.id === id);
    if (idx !== -1) mockTasks.splice(idx, 1);
    return Promise.resolve();
  },
};
