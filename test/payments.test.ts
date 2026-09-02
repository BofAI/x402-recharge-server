import assert from "node:assert/strict";
import test from "node:test";
import { networkConfigs } from "../src/config.js";
import { bankofaiChainId, buildRechargeChallenge, normalizeToken, supportedTokens } from "../src/payments.js";

test("supported tokens are restricted to recharge payment scope", () => {
  assert.deepEqual(supportedTokens(), ["USDD", "USDT"]);
  assert.equal(normalizeToken("usdt"), "USDT");
  assert.equal(normalizeToken("usdd"), "USDD");
  assert.throws(() => normalizeToken("usdc"), /Unsupported TRC20 token/);
});

test("BANK OF AI chain ids are mainnet only", () => {
  assert.equal(networkConfigs.mainnet.paymentNetwork, "tron:0x2b6653dc");
  assert.equal(bankofaiChainId("tron:0x2b6653dc"), "eip155:728126428");
  assert.equal(bankofaiChainId("tron:mainnet"), "eip155:728126428");
  assert.equal(bankofaiChainId("eip155:56"), "eip155:56");
  assert.throws(() => bankofaiChainId("tron:nile"), /Unsupported chain mapping/);
});

test("recharge challenge uses the current production recipient addresses", async () => {
  const challenge = await buildRechargeChallenge("1", "USDT", "https://recharge.bankofai.io/mcp");

  assert.deepEqual(
    challenge.accepts.map(({ scheme, network, payTo }) => ({ scheme, network, payTo })),
    [
      {
        scheme: "exact",
        network: "tron:0x2b6653dc",
        payTo: "TSNEPtuCagKEgF2EU4pAKWLzXLz1bekfTE"
      },
      {
        scheme: "exact_gasfree",
        network: "tron:0x2b6653dc",
        payTo: "TSNEPtuCagKEgF2EU4pAKWLzXLz1bekfTE"
      },
      {
        scheme: "exact",
        network: "eip155:56",
        payTo: "0x060f7fd9c9622bdcf9f2887c8171d6e6b4b4ba17"
      }
    ]
  );
});
