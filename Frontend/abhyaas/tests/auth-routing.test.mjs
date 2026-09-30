import test from "node:test";
import assert from "node:assert/strict";
import { authRedirect } from "../lib/auth-routing.ts";

test("Home renders without waiting for auth and never redirects signed-in students", () => {
  for (const status of ["loading", "authenticated", "anonymous"]) {
    assert.equal(authRedirect("/", status), null);
  }
});

test("public pages remain visible while the session server is slow", () => {
  for (const path of ["/", "/about", "/privacy", "/login"]) {
    assert.equal(authRedirect(path, "loading"), null);
  }
});

test("protected routes still redirect signed-out visitors", () => {
  assert.equal(authRedirect("/practice", "anonymous"), "/login?next=%2Fpractice");
  assert.equal(authRedirect("/progress", "anonymous"), "/login?next=%2Fprogress");
  assert.equal(authRedirect("/practice", "authenticated"), null);
});

test("completed sign-in still opens Progress", () => {
  assert.equal(authRedirect("/login", "authenticated"), "/progress");
  assert.equal(authRedirect("/auth/callback", "authenticated"), "/progress");
});
