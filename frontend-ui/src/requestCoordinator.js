/**
 * Connector-neutral request coordinator for interactive FE work.
 * Coordinates duplicate requests, cancellation, stale-response protection,
 * and optional debounce without retaining result datasets.
 */
export function createRequestCoordinator({ debounceMs = 0 } = {}) {
  const pending = new Map();
  const timers = new Map();
  let sequence = 0;

  const abortError = () => {
    const error = new DOMException("The request was aborted.", "AbortError");
    return error;
  };

  function cancel(key) {
    const entry = pending.get(key);
    if (entry) entry.controller.abort();
    const timer = timers.get(key);
    if (timer) {
      clearTimeout(timer);
      timers.delete(key);
    }
  }

  function request(key, operation, { signal, debounce = debounceMs } = {}) {
    const requestKey = String(key);
    if (pending.has(requestKey)) return pending.get(requestKey).promise;

    const controller = new AbortController();
    const id = ++sequence;
    let resolvePromise;
    let rejectPromise;
    const promise = new Promise((resolve, reject) => {
      resolvePromise = resolve;
      rejectPromise = reject;
    });
    const entry = { id, controller, promise };
    pending.set(requestKey, entry);

    const abortFromCaller = () => controller.abort();
    if (signal) {
      if (signal.aborted) controller.abort();
      else signal.addEventListener("abort", abortFromCaller, { once: true });
    }

    const run = async () => {
      try {
        if (controller.signal.aborted) throw abortError();
        const result = await operation({ signal: controller.signal, requestId: id });
        if (controller.signal.aborted) throw abortError();
        if (pending.get(requestKey)?.id !== id) throw abortError();
        resolvePromise(result);
      } catch (error) {
        rejectPromise(error);
      } finally {
        if (signal) signal.removeEventListener("abort", abortFromCaller);
        if (pending.get(requestKey)?.id === id) pending.delete(requestKey);
      }
    };

    if (debounce > 0) {
      const timer = setTimeout(() => {
        timers.delete(requestKey);
        void run();
      }, debounce);
      timers.set(requestKey, timer);
    } else {
      void run();
    }

    return promise;
  }

  return { request, cancel, has: (key) => pending.has(String(key)), clear: () => {
    for (const key of pending.keys()) cancel(key);
    pending.clear();
    for (const timer of timers.values()) clearTimeout(timer);
    timers.clear();
  } };
}
