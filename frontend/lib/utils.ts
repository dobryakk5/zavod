import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const TEMPLATE_NAME_MAP: Record<string, string> = {
  'Продающий пост': 'Продающий',
  'Экспертный пост': 'Экспертный',
  'Триггерный пост': 'Триггерный'
};

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(...inputs));
}

export function formatTemplateDisplayName(name?: string | null) {
  if (!name) {
    return '';
  }
  return TEMPLATE_NAME_MAP[name] ?? name;
}
