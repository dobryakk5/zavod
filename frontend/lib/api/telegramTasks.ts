import { apiFetch } from '../api';
import type { TelegramTask } from '../types';

export const telegramTasksApi = {
  list() {
    return apiFetch<TelegramTask[]>('/telegram-tasks/');
  }
};
