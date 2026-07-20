import assert from "node:assert/strict";
import test from "node:test";
import { bankofaiChainId, normalizeToken, supportedTokens } from "../src/payments.js";

test("supported tokens are restricted to recharge payment scope", () => {
  assert.deepEqual(supportedTokens(), ["USDD", "USDT"]);
  assert.equal(normalizeToken("usdt"), "USDT");
  assert.equal(normalizeToken("usdd"), "USDD");
  assert.throws(() => normalizeToken("usdc"), /Unsupported TRC20 token/);
});

test("BANK OF AI chain ids are mainnet only", () => {
  assert.equal(bankofaiChainId("tron:mainnet"), "eip155:728126428");
  assert.equal(bankofaiChainId("eip155:56"), "eip155:56");
  assert.throws(() => bankofaiChainId("tron:nile"), /Unsupported chain mapping/);
});
