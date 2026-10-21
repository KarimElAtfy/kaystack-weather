// Every read of the public account goes through here. The account closes
// itself at 20,000 reads an hour, so a file is read at most once a minute,
// never while the tab is hidden or the device is offline, and otherwise only
// when its own content says a newer one should be out.

export const FLOOR = 60_000;
const SLOW = 5 * 60_000;
// After this many reads past the due time with nothing new, read every five minutes.
const PATIENCE = 10;
const BACK_OFF = [1, 2, 5, 10].map((minutes) => minutes * 60_000);

export type Problem = 'offline' | 'missing' | 'unavailable' | 'invalid';

export type Reading<T> = {
  value: T | null;
  // When the value was read, for "Dati controllati alle".
  at: number | null;
  problem: Problem | null;
};

export type Response = { status: number; etag: string | null; body: () => Promise<unknown> };

export type Env = {
  now(): number;
  hidden(): boolean;
  online(): boolean;
  wait(ms: number, then: () => void): () => void;
  // Calls back when the tab becomes visible or the device comes back online.
  onShow(then: () => void): () => void;
  // Rejects when the request does not get an answer at all.
  get(url: string, kind: 'json' | 'blob'): Promise<Response>;
};

export type Source<T> = {
  url: string;
  kind?: 'json' | 'blob';
  decode(body: unknown): T;
  // When a newer file should be out, from the file itself.
  due(value: T): number;
  // Read only when asked, as the sources list in the footer is.
  lazy?: boolean;
};

export type Follower = { stop(): void; ask(): void };

export function follow<T>(
  env: Env,
  source: Source<T>,
  update: (reading: Reading<T>) => void
): Follower {
  let reading: Reading<T> = { value: null, at: null, problem: null };
  let etag: string | null = null;
  let last = -Infinity;
  let late = 0;
  let errors = 0;
  let cancel: (() => void) | null = null;
  let busy = false;
  let stopped = false;

  const set = (next: Reading<T>) => {
    reading = next;
    update(next);
  };

  const schedule = (delay: number) => {
    cancel?.();
    const floor = FLOOR - (env.now() - last);
    cancel = env.wait(Math.max(delay, floor, 0), () => void read());
  };

  async function read() {
    cancel = null;
    if (stopped || busy || env.hidden()) return;
    if (!env.online()) {
      if (reading.problem !== 'offline') set({ ...reading, problem: 'offline' });
      return;
    }
    if (env.now() - last < FLOOR) return schedule(0);
    busy = true;
    last = env.now();
    let problem: Problem | null = null;
    try {
      const response = await env.get(source.url, source.kind ?? 'json');
      if (response.status === 404) problem = 'missing';
      else if (response.status !== 200) problem = 'unavailable';
      else if (response.etag === null || response.etag !== etag) {
        try {
          const value = source.decode(await response.body());
          etag = response.etag;
          set({ value, at: env.now(), problem: null });
        } catch {
          problem = 'invalid';
        }
      } else if (reading.problem !== null) {
        set({ ...reading, at: env.now(), problem: null });
      }
    } catch {
      problem = env.online() ? 'unavailable' : 'offline';
    }
    busy = false;
    if (stopped) return;
    if (problem) {
      if (problem !== reading.problem) set({ ...reading, problem });
      schedule(BACK_OFF[Math.min(errors, BACK_OFF.length - 1)] ?? SLOW);
      errors += 1;
      return;
    }
    errors = 0;
    const due = reading.value === null ? Infinity : source.due(reading.value);
    if (due > env.now()) {
      late = 0;
      if (Number.isFinite(due)) schedule(due - env.now());
      return;
    }
    late += 1;
    schedule(late <= PATIENCE ? FLOOR : SLOW);
  }

  const offShow = env.onShow(() => {
    if (!source.lazy) schedule(0);
  });
  if (!source.lazy) void read();

  return {
    stop() {
      stopped = true;
      cancel?.();
      offShow();
    },
    ask() {
      if (!stopped) schedule(0);
    }
  };
}
