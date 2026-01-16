const TRIAL_LIMIT_EVENT_NAME = 'trial-limit:open';
const TRIAL_LIMIT_MATCH = 'Лимит ознакомительного тарифа';
const TRIAL_LIMIT_DETAILS_PATTERN = /для\s+[«"]?(.+?)[»"]?\s+исчерпан\s+\((\d+)\/(\d+)\)/i;

export const TRIAL_LIMIT_MESSAGE = 'Лимит ознакомительного тарифа исчерпан';
export const TRIAL_LIMIT_PAYMENT_URL = 'http://localhost:3000/settings?tab=payment';

export type TrialLimitDetails = {
  label?: string;
  used?: number;
  limit?: number;
  message?: string;
};

export const isTrialLimitMessage = (message: unknown): message is string =>
  typeof message === 'string' && message.includes(TRIAL_LIMIT_MATCH);

export const parseTrialLimitDetails = (message: unknown): TrialLimitDetails | null => {
  if (typeof message !== 'string') {
    return null;
  }
  const match = message.match(TRIAL_LIMIT_DETAILS_PATTERN);
  if (!match) {
    return null;
  }
  const [, label, used, limit] = match;
  return {
    label,
    used: Number(used),
    limit: Number(limit),
    message,
  };
};

export const emitTrialLimitModalOpen = (detail?: TrialLimitDetails) => {
  if (typeof window === 'undefined') {
    return;
  }
  window.dispatchEvent(new CustomEvent<TrialLimitDetails | undefined>(TRIAL_LIMIT_EVENT_NAME, { detail }));
};

export const subscribeToTrialLimitModalOpen = (callback: (detail?: TrialLimitDetails) => void) => {
  if (typeof window === 'undefined') {
    return () => {};
  }

  const handler = (event: Event) => {
    const customEvent = event as CustomEvent<TrialLimitDetails | undefined>;
    callback(customEvent.detail);
  };

  window.addEventListener(TRIAL_LIMIT_EVENT_NAME, handler);

  return () => {
    window.removeEventListener(TRIAL_LIMIT_EVENT_NAME, handler);
  };
};
