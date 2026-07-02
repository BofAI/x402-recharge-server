export type RateLimitResult = {
  allowed: boolean;
  remaining: number;
};

export class FixedWindowRateLimiter {
  private readonly hits = new Map<string, number[]>();

  constructor(private readonly limitPerMinute: number) {}

  consume(key: string): RateLimitResult {
    if (this.limitPerMinute <= 0) {
      return { allowed: true, remaining: Number.POSITIVE_INFINITY };
    }
    const now = Date.now() / 1000;
    const cutoff = now - 60;
    const bucket = this.hits.get(key) ?? [];
    while (bucket.length > 0 && bucket[0] < cutoff) {
      bucket.shift();
    }
    if (bucket.length >= this.limitPerMinute) {
      this.hits.set(key, bucket);
      return { allowed: false, remaining: 0 };
    }
    bucket.push(now);
    this.hits.set(key, bucket);
    return { allowed: true, remaining: Math.max(0, this.limitPerMinute - bucket.length) };
  }
}
