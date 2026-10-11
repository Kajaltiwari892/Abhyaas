// Small, bounded, in-memory cache. Never persists credentials or private data.
// Each caller can cancel its own wait without cancelling another caller's request.
export function createRequestCache<T>(ttlMs: number, maxEntries = 32, now = Date.now) {
  type Entry = { value?: T; expires: number; pending?: Promise<T> };
  const entries = new Map<string, Entry>();
  const put = (key: string, entry: Entry) => {
    entries.delete(key);
    entries.set(key, entry);
    while (entries.size > maxEntries) entries.delete(entries.keys().next().value!);
  };
  return {
    clear() { entries.clear(); },
    set(key: string, value: T) { put(key, { value, expires: now() + ttlMs }); },
    get(key: string, load: () => Promise<T>, signal?: AbortSignal): Promise<T> {
      if (signal?.aborted) return Promise.reject(signal.reason);
      let entry = entries.get(key);
      if (entry && entry.expires > now() && "value" in entry) {
        return waitForCaller(Promise.resolve(entry.value as T), signal);
      }
      if (!entry?.pending) {
        entry = { expires: 0 };
        put(key, entry);
        const current = entry;
        current.pending = Promise.resolve().then(load).then(value => {
          // A mutation, sign-out, or eviction may have replaced this request.
          if (entries.get(key) === current) {
            current.value = value;
            current.expires = now() + ttlMs;
          }
          return value;
        }).finally(() => {
          if (entries.get(key) === current) {
            current.pending = undefined;
            if (!("value" in current)) entries.delete(key);
          }
        });
      }
      return waitForCaller(entry.pending!, signal);
    },
  };
}

function waitForCaller<T>(request: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return request;
  return new Promise((resolve, reject) => {
    const abort = () => { signal.removeEventListener("abort", abort); reject(signal.reason); };
    signal.addEventListener("abort", abort, { once: true });
    request.then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}
