export interface PostGenerationEventDetail {
  count?: number;
  templateName?: string;
}

const EVENT_NAME = 'post-generation:start';

/**
 * Notify listeners that post generation has started.
 */
export function emitPostGenerationStart(detail: PostGenerationEventDetail = {}) {
  if (typeof window === 'undefined') {
    return;
  }
  window.dispatchEvent(new CustomEvent<PostGenerationEventDetail>(EVENT_NAME, { detail }));
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

  window.addEventListener(EVENT_NAME, handler);

  return () => {
    window.removeEventListener(EVENT_NAME, handler);
  };
}
