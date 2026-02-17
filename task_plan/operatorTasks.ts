import type { OperatorTask, OperatorTaskStatus, TaskType } from '../types';

// ---------------------------------------------------------------------------
// Mock store — replace with real apiFetch calls once backend is ready
// ---------------------------------------------------------------------------

let mockIdCounter = 100;
const mockStore: OperatorTask[] = [
  {
    id: 1,
    type: 2,
    title: 'Низкая оценка от клиента',
    description: 'Клиент поставил оценку 5/10 и оставил комментарий о задержках.',
    resolution_text: null,
    status: 'open',
    telegram_task_id: 1,
    contact_name: '@ivan_petrov',
    rating: 5,
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 2,
    type: 1,
    title: 'Уточнить детали договора',
    description: null,
    resolution_text: 'Договор уточнён, клиент подтвердил.',
    status: 'done',
    telegram_task_id: null,
    contact_name: null,
    rating: null,
    created_at: new Date(Date.now() - 172800000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
  },
];

export const operatorTasksApi = {
  list(): Promise<OperatorTask[]> {
    return Promise.resolve([...mockStore]);
  },

  create(data: {
    type: TaskType;
    title: string;
    description?: string | null;
    telegram_task_id?: number | null;
    contact_name?: string | null;
    rating?: number | null;
  }): Promise<OperatorTask> {
    const now = new Date().toISOString();
    const task: OperatorTask = {
      id: ++mockIdCounter,
      type: data.type,
      title: data.title,
      description: data.description ?? null,
      resolution_text: null,
      status: 'open',
      telegram_task_id: data.telegram_task_id ?? null,
      contact_name: data.contact_name ?? null,
      rating: data.rating ?? null,
      created_at: now,
      updated_at: now,
    };
    mockStore.push(task);
    return Promise.resolve({ ...task });
  },

  update(
    id: number,
    data: { resolution_text?: string | null; status?: OperatorTaskStatus },
  ): Promise<OperatorTask> {
    const idx = mockStore.findIndex((t) => t.id === id);
    if (idx === -1) return Promise.reject(new Error(`Task ${id} not found`));
    mockStore[idx] = { ...mockStore[idx], ...data, updated_at: new Date().toISOString() };
    return Promise.resolve({ ...mockStore[idx] });
  },

  delete(id: number): Promise<void> {
    const idx = mockStore.findIndex((t) => t.id === id);
    if (idx !== -1) mockStore.splice(idx, 1);
    return Promise.resolve();
  },
};
