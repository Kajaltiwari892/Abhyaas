import { QueryClient, queryOptions, type FetchQueryOptions, type QueryKey } from "@tanstack/react-query";
import { ApiError, sessionController } from "./auth-api";

export function createAppQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 10 * 60_000,
        retry: (count, error) => count < 1 && error instanceof ApiError
          && (error.status === 0 || error.status >= 500),
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
      },
      mutations: { retry: false, networkMode: "always" },
    },
  });
}

let browserClient: QueryClient | undefined;
export function getQueryClient() {
  // Server renders never share a student's query cache across requests.
  if (typeof window === "undefined") return createAppQueryClient();
  if (!browserClient) {
    browserClient = createAppQueryClient();
    let generation = sessionController.getGeneration();
    sessionController.subscribe(() => {
      const next = sessionController.getGeneration();
      if (next === generation) return; // Access-token renewal keeps the same cache.
      generation = next;
      browserClient!.removeQueries({ queryKey: ["private"] });
      const mutations = browserClient!.getMutationCache();
      const pending = mutations.getAll().filter(mutation => mutation.state.status === "pending");
      mutations.clear();
      // Removed scope queues still need to settle their promises. The guarded
      // mutation function rejects the old generation before starting any write.
      for (const mutation of pending) void mutation.continue().catch(() => {});
    });
  }
  return browserClient;
}

export function privateKey(resource: string, ...parameters: unknown[]) {
  return ["private", sessionController.getGeneration(), sessionController.getSnapshot().session?.user.id ?? "anonymous", resource, ...parameters] as const;
}

export function assertSession(token: string | null, generation: number) {
  if (!token || !sessionController.ownsToken(token) || generation !== sessionController.getGeneration()) {
    throw new ApiError("Your session has changed. Please try again.", 401);
  }
}

export function privateQuery<T>(resource: string, token: string | null, load: (signal: AbortSignal) => Promise<T>, parameters: unknown[] = [], staleTime = 30_000) {
  const queryKey = privateKey(resource, ...parameters);
  return queryOptions({
    queryKey,
    enabled: !!token,
    staleTime,
    queryFn: async ({ signal }) => {
      assertSession(token, queryKey[1]);
      const result = await load(AbortSignal.any([signal, AbortSignal.timeout(30_000)]));
      assertSession(token, queryKey[1]);
      signal.throwIfAborted();
      return result;
    },
  });
}

// Imperative callers share the same queries as React observers. Cancelling one
// caller's wait must not cancel another screen's shared request.
export function fetchCached<T, TKey extends QueryKey>(options: FetchQueryOptions<T, Error, T, TKey>, signal?: AbortSignal): Promise<T> {
  if (signal?.aborted) return Promise.reject(signal.reason);
  const request = getQueryClient().fetchQuery(options);
  if (!signal) return request;
  return new Promise((resolve, reject) => {
    const abort = () => reject(signal.reason);
    signal.addEventListener("abort", abort, { once: true });
    request.then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}

export function invalidateStudyQueries(resources: string[], scope = privateKey("")) {
  const client = getQueryClient();
  const filters = { predicate: (query: { queryKey: QueryKey }) =>
    query.queryKey[0] === "private" && query.queryKey[1] === scope[1]
    && query.queryKey[2] === scope[2] && resources.includes(query.queryKey[3] as string) };
  // Cancel older reads even if they haven't produced their first result yet.
  void client.cancelQueries(filters);
  void client.invalidateQueries(filters);
}

export async function studyMutation<T>(resources: string[], request: () => Promise<T>): Promise<T> {
  const scope = privateKey("");
  try { return await request(); }
  finally { invalidateStudyQueries(resources, scope); }
}
