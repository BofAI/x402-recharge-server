import assert from "node:assert/strict";
import test from "node:test";
import { FixedWindowRateLimiter } from "../src/rate-limit.js";

test("fixed window limiter enforces per-key limits", () => {
  const limiter = new FixedWindowRateLimiter(2);

  assert.equal(limiter.consume("a").allowed, true);
  assert.equal(limiter.consume("a").allowed, true);
  assert.equal(limiter.consume("a").allowed, false);
  assert.equal(limiter.consume("b").allowed, true);
});

test("fixed window limiter can be disabled", () => {
  const limiter = new FixedWindowRateLimiter(0);

  assert.equal(limiter.consume("a").allowed, true);
  assert.equal(limiter.consume("a").allowed, true);
});
