import test from "node:test";
import assert from "node:assert/strict";
import { authRedirect, googleCallbackRedirect, shouldWaitForSession } from "../lib/auth-routing.ts";

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
  assert.equal(googleCallbackRedirect("authenticated", null), "/progress");
});

test("Google callback waits for a slow session and never detours through Login on success", () => {
  const destinations = ["loading", "loading", "authenticated"]
    .map((status) => googleCallbackRedirect(status, null)).filter(Boolean);
  assert.deepEqual(destinations, ["/progress"]);
  for (const status of ["loading", "anonymous", "authenticated"]) {
    assert.equal(authRedirect("/auth/callback", status), null); // One redirect owner.
  }
});

test("Google failure and a missing session return to Login with an actionable error", () => {
  assert.equal(googleCallbackRedirect("anonymous", null), "/login?google_error=session_unavailable");
  for (const status of ["loading", "anonymous", "authenticated"]) {
    assert.equal(googleCallbackRedirect(status, "cancelled"), "/login?google_error=cancelled");
  }
  assert.equal(googleCallbackRedirect("anonymous", "bad&next=/elsewhere"), "/login?google_error=bad%26next%3D%2Felsewhere");
});

test("Login hides the form only until session restoration resolves", () => {
  assert.equal(shouldWaitForSession("/login", "loading"), true);
  assert.equal(shouldWaitForSession("/login", "anonymous"), false);
  assert.equal(shouldWaitForSession("/login", "authenticated"), false);
  for (const path of ["/", "/about", "/privacy", "/auth/callback", "/progress"]) {
    assert.equal(shouldWaitForSession(path, "loading"), false);
  }
});
