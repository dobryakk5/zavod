import { describe, expect, it, vi } from 'vitest';
import {
  TRIAL_LIMIT_MESSAGE,
  emitTrialLimitModalOpen,
  isTrialLimitMessage,
  parseTrialLimitDetails,
  subscribeToTrialLimitModalOpen,
} from '@/lib/trial-limit';

describe('trial-limit helpers', () => {
  it('detects trial limit messages only for matching strings', () => {
    expect(isTrialLimitMessage(`${TRIAL_LIMIT_MESSAGE}: для тарифа`)).toBe(true);
    expect(isTrialLimitMessage('Другая ошибка')).toBe(false);
    expect(isTrialLimitMessage(null)).toBe(false);
    expect(isTrialLimitMessage({ message: TRIAL_LIMIT_MESSAGE })).toBe(false);
  });

  it('parses trial limit details from message', () => {
    const message = 'Лимит ознакомительного тарифа для «Посты» исчерпан (3/3)';
    expect(parseTrialLimitDetails(message)).toEqual({
      label: 'Посты',
      used: 3,
      limit: 3,
      message,
    });
  });

  it('returns null for unparseable messages', () => {
    expect(parseTrialLimitDetails('Лимит ознакомительного тарифа')).toBeNull();
    expect(parseTrialLimitDetails(undefined)).toBeNull();
  });

  it('emits and subscribes to modal open events', () => {
    const callback = vi.fn();
    const unsubscribe = subscribeToTrialLimitModalOpen(callback);
    const detail = { label: 'Видео', used: 10, limit: 10 };

    emitTrialLimitModalOpen(detail);

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith(detail);

    unsubscribe();
    emitTrialLimitModalOpen({ label: 'Посты', used: 1, limit: 1 });

    expect(callback).toHaveBeenCalledTimes(1);
  });
});
