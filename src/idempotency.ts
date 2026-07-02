import crypto from "node:crypto";

type Entry<T> =
  | { state: "processing"; expiresAt: number }
  | { state: "completed"; expiresAt: number; value: T };

export class DuplicatePaymentInProgressError extends Error {
  constructor() {
    super("payment is already being processed");
    this.name = "DuplicatePaymentInProgressError";
  }
}

export class IdempotencyStore<T> {
  private readonly entries = new Map<string, Entry<T>>();

  constructor(private readonly ttlMs = 60 * 60 * 1000) {}

  key(input: string): string {
    return crypto.createHash("sha256").update(input).digest("hex");
  }

  async run(key: string, fn: () => Promise<T>): Promise<T> {
    const now = Date.now();
    this.cleanup(now);
    const existing = this.entries.get(key);
    if (existing?.state === "completed" && existing.expiresAt > now) {
      return existing.value;
    }
    if (existing?.state === "processing" && existing.expiresAt > now) {
      throw new DuplicatePaymentInProgressError();
    }
    this.entries.set(key, { state: "processing", expiresAt: now + this.ttlMs });
    try {
      const value = await fn();
      this.entries.set(key, { state: "completed", expiresAt: Date.now() + this.ttlMs, value });
      return value;
    } catch (error) {
      this.entries.delete(key);
      throw error;
    }
  }

  private cleanup(now: number): void {
    for (const [key, entry] of this.entries.entries()) {
      if (entry.expiresAt <= now) {
        this.entries.delete(key);
      }
    }
  }
}
