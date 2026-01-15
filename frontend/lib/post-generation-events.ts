export interface PostGenerationEventDetail {
  count?: number;
  templateName?: string;
}

const START_EVENT_NAME = 'post-generation:start';
const COMPLETE_EVENT_NAME = 'post-generation:complete';

/**
 * Notify listeners that post generation has started.
 */
export function emitPostGenerationStart(detail: PostGenerationEventDetail = {}) {
  if (typeof window === 'undefined') {
    return;
  }
  window.dispatchEvent(new CustomEvent<PostGenerationEventDetail>(START_EVENT_NAME, { detail }));
}

/**
 * Subscribe to post generation start events.
 */
export function subscribeToPostGenerationStart(
  callback: (detail: PostGenerationEventDetail) => void
) {
  if (typeof window === 'undefined') {
    return () => {};
  }

  const handler = (event: Event) => {
    const customEvent = event as CustomEvent<PostGenerationEventDetail>;
    callback(customEvent.detail || {});
  };

  window.addEventListener(START_EVENT_NAME, handler);

  return () => {
    window.removeEventListener(START_EVENT_NAME, handler);
  };
}

/**
 * Notify listeners that post generation has finished.
 */
export function emitPostGenerationComplete(detail: PostGenerationEventDetail = {}) {
  if (typeof window === 'undefined') {
    return;
  }
  window.dispatchEvent(new CustomEvent<PostGenerationEventDetail>(COMPLETE_EVENT_NAME, { detail }));
}

/**
 * Subscribe to post generation completion events.
 */
export function subscribeToPostGenerationComplete(
  callback: (detail: PostGenerationEventDetail) => void
) {
  if (typeof window === 'undefined') {
    return () => {};
  }

  const handler = (event: Event) => {
    const customEvent = event as CustomEvent<PostGenerationEventDetail>;
    callback(customEvent.detail || {});
  };

  window.addEventListener(COMPLETE_EVENT_NAME, handler);

  return () => {
    window.removeEventListener(COMPLETE_EVENT_NAME, handler);
  };
}
