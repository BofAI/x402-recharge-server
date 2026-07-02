import assert from "node:assert/strict";
import test from "node:test";
import { DuplicatePaymentInProgressError, IdempotencyStore } from "../src/idempotency.js";

test("idempotency store reuses completed results", async () => {
  const store = new IdempotencyStore<string>();
  let calls = 0;

  const first = await store.run("payment", async () => {
    calls += 1;
    return "settled";
  });
  const second = await store.run("payment", async () => {
    calls += 1;
    return "duplicate";
  });

  assert.equal(first, "settled");
  assert.equal(second, "settled");
  assert.equal(calls, 1);
});

test("idempotency store rejects concurrent duplicates", async () => {
  const store = new IdempotencyStore<string>();
  let release!: () => void;
  const pending = store.run("payment", async () => {
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    return "settled";
  });

  await assert.rejects(
    () => store.run("payment", async () => "duplicate"),
    DuplicatePaymentInProgressError
  );

  release();
  assert.equal(await pending, "settled");
});
