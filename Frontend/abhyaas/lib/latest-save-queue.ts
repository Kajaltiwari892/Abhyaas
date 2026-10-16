// One write in flight and at most one waiting snapshot. Slow connections must
// not accumulate a separate network request for every question and heartbeat.
export function createLatestSaveQueue<T>(write: (snapshot: T) => Promise<unknown>) {
  let pending: { value: T } | undefined;
  let running: Promise<void> | undefined;

  const drain = (): Promise<void> => {
    if (running) return running;
    if (!pending) return Promise.resolve();
    running = (async () => {
      while (pending) {
        const next = pending;
        pending = undefined;
        try { await write(next.value); }
        catch (error) {
          // Keep the latest snapshot for a later explicit/automatic retry.
          pending ??= next;
          throw error;
        }
      }
    })().then(() => {
      running = undefined;
      return drain(); // Also cover a snapshot queued during promise settlement.
    }, (error) => { running = undefined; throw error; });
    return running;
  };
  return {
    enqueue(value: T) { pending = { value }; return drain(); },
    drain,
  };
}
