type LogLevel = "debug" | "info" | "warn" | "error";

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40
};

const configuredLevel = (process.env.LOG_LEVEL ?? "info").toLowerCase() as LogLevel;
const minPriority = LEVEL_PRIORITY[configuredLevel] ?? LEVEL_PRIORITY.info;

function serializeError(error: unknown): Record<string, unknown> {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: process.env.NODE_ENV === "production" ? undefined : error.stack
    };
  }
  return { message: String(error) };
}

function log(level: LogLevel, msg: string, fields: Record<string, unknown> = {}): void {
  if (LEVEL_PRIORITY[level] < minPriority) {
    return;
  }
  const payload: Record<string, unknown> = {
    ts: new Date().toISOString(),
    level,
    msg,
    ...fields
  };
  for (const [key, value] of Object.entries(payload)) {
    if (value === undefined) {
      delete payload[key];
    }
  }
  const line = JSON.stringify(payload);
  if (level === "error") {
    console.error(line);
    return;
  }
  if (level === "warn") {
    console.warn(line);
    return;
  }
  console.info(line);
}

export const logger = {
  debug: (msg: string, fields?: Record<string, unknown>) => log("debug", msg, fields),
  info: (msg: string, fields?: Record<string, unknown>) => log("info", msg, fields),
  warn: (msg: string, fields?: Record<string, unknown>) => log("warn", msg, fields),
  error: (msg: string, fields?: Record<string, unknown>) => log("error", msg, fields),
  errorFields: (error: unknown): Record<string, unknown> => ({ err: serializeError(error) })
};
