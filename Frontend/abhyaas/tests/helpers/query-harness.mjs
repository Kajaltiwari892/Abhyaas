import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { after } from "node:test";
import ts from "typescript";
import { createSessionController } from "../../lib/session-controller.ts";

const require = createRequire(import.meta.url);
const clients = [];
after(() => clients.forEach(client => client.clear()));
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
export const session = (id = "student", token = "token") => ({
  access_token: token, user: { id }, expires_at: new Date(Date.now() + 900_000).toISOString(),
});

export function queryHarness(handler = () => ({}), globals = {}) {
  let restored = null;
  const controller = createSessionController(async () => restored);
  controller.completeAuthentication(session());
  const calls = [], modules = new Map();
  const auth = { ApiError, sessionController: controller, apiRequest: async (path, init = {}) => {
    calls.push({ path, init });
    return handler(path, init, calls.length);
  } };
  function load(name) {
    if (modules.has(name)) return modules.get(name).exports;
    const loaded = { exports: {} };
    modules.set(name, loaded);
    const source = readFileSync(new URL(`../../lib/${name}.ts`, import.meta.url), "utf8");
    const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
    const resolve = id => id === "./auth-api" ? auth : id.startsWith("./") ? load(id.slice(2)) : require(id);
    new Function("require", "module", "exports", "window", ...Object.keys(globals), compiled)(resolve, loaded, loaded.exports, {}, ...Object.values(globals));
    return loaded.exports;
  }
  const query = load("query-client");
  const client = query.getQueryClient();
  client.setDefaultOptions({ ...client.getDefaultOptions(),
    queries: { ...client.getDefaultOptions().queries, gcTime: Infinity, retry: false },
    mutations: { ...client.getDefaultOptions().mutations, gcTime: Infinity },
  });
  clients.push(client);
  return { api: load, query, client, controller, calls, restoreAs: value => { restored = value; return controller.refresh(); } };
}
