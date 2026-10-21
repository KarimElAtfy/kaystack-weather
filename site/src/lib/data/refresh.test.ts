import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { FLOOR, follow, type Env, type Reading, type Response } from './refresh.ts';

const MIN = 60_000;
const HOUR = 60 * MIN;

type Server = (url: string) => Response | 'network';

let hidden: boolean;
let online: boolean;
let shows: (() => void)[];
let server: Server;
let reads: number[];

const env: Env = {
  now: () => Date.now(),
  hidden: () => hidden,
  online: () => online,
  wait: (ms, then) => {
    const id = setTimeout(then, ms);
    return () => clearTimeout(id);
  },
  onShow: (then) => {
    shows.push(then);
    return () => (shows = shows.filter((f) => f !== then));
  },
  get: async (url) => {
    reads.push(Date.now());
    const answer = server(url);
    if (answer === 'network') throw new TypeError('Failed to fetch');
    return answer;
  }
};

const ok = (body: unknown, etag: string | null = null): Response => ({
  status: 200,
  etag,
  body: async () => body
});
const status = (code: number): Response => ({ status: code, etag: null, body: async () => null });
const show = () => shows.forEach((f) => f());

// A file that says when the next one is due, like a radar frame time.
const source = (due: (value: { next: number }) => number = (v) => v.next) => ({
  url: '/v1/pedrengo/now.json',
  decode: (body: unknown) => {
    const value = body as { next: unknown };
    if (typeof value.next !== 'number') throw new Error('next is not a time');
    return value as { next: number };
  },
  due
});

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse('2026-10-24T13:10:00Z'));
  hidden = false;
  online = true;
  shows = [];
  reads = [];
  server = () => ok({ next: Date.now() + 10 * MIN });
});
afterEach(() => vi.useRealTimers());

test('reads at once, then when a newer file is due', async () => {
  const seen: Reading<{ next: number }>[] = [];
  follow(env, source(), (r) => seen.push(r));
  await vi.advanceTimersByTimeAsync(0);
  expect(reads).toHaveLength(1);
  expect(seen[0]?.value?.next).toBe(Date.now() + 10 * MIN);
  await vi.advanceTimersByTimeAsync(10 * MIN - 1);
  expect(reads).toHaveLength(1);
  await vi.advanceTimersByTimeAsync(1);
  expect(reads).toHaveLength(2);
});

test('never reads a file twice within a minute, even when it is overdue', async () => {
  server = () => ok({ next: 0 });
  follow(env, source(), () => {});
  await vi.advanceTimersByTimeAsync(HOUR);
  const gaps = reads.slice(1).map((t, i) => t - (reads[i] ?? 0));
  expect(Math.min(...gaps)).toBeGreaterThanOrEqual(FLOOR);
  // Ten tries a minute apart, then one every five minutes.
  expect(reads.length).toBeLessThanOrEqual(1 + 10 + 10);
});

test('stays under the breaker for an hour of the worst case', async () => {
  server = () => ok({ next: 0 });
  follow(env, source(), () => {});
  const asks = setInterval(show, 1000);
  await vi.advanceTimersByTimeAsync(HOUR);
  clearInterval(asks);
  expect(reads.length).toBeLessThanOrEqual(60);
});

test('does not read while the tab is hidden', async () => {
  hidden = true;
  follow(env, source(), () => {});
  await vi.advanceTimersByTimeAsync(HOUR);
  expect(reads).toHaveLength(0);
  hidden = false;
  show();
  show();
  await vi.advanceTimersByTimeAsync(0);
  expect(reads).toHaveLength(1);
});

test('reads once on becoming visible again, after the minute', async () => {
  follow(env, source(), () => {});
  await vi.advanceTimersByTimeAsync(0);
  hidden = true;
  await vi.advanceTimersByTimeAsync(30 * 1000);
  hidden = false;
  show();
  await vi.advanceTimersByTimeAsync(29 * 1000);
  expect(reads).toHaveLength(1);
  await vi.advanceTimersByTimeAsync(1000);
  expect(reads).toHaveLength(2);
});

test('waits for the network while offline and keeps the last value', async () => {
  const seen: Reading<{ next: number }>[] = [];
  follow(env, source(), (r) => seen.push(r));
  await vi.advanceTimersByTimeAsync(0);
  online = false;
  await vi.advanceTimersByTimeAsync(HOUR);
  expect(reads).toHaveLength(1);
  expect(seen.at(-1)).toMatchObject({ problem: 'offline', value: { next: expect.any(Number) } });
  online = true;
  show();
  await vi.advanceTimersByTimeAsync(0);
  expect(reads).toHaveLength(2);
  expect(seen.at(-1)?.problem).toBeNull();
});

test('says a file is missing or unavailable and backs off', async () => {
  const seen: Reading<{ next: number }>[] = [];
  server = () => status(404);
  follow(env, source(), (r) => seen.push(r));
  await vi.advanceTimersByTimeAsync(0);
  expect(seen.at(-1)?.problem).toBe('missing');
  server = () => status(409);
  await vi.advanceTimersByTimeAsync(MIN);
  expect(seen.at(-1)?.problem).toBe('unavailable');
  await vi.advanceTimersByTimeAsync(2 * MIN + 5 * MIN + 10 * MIN);
  const gaps = reads.slice(1).map((t, i) => (t - (reads[i] ?? 0)) / MIN);
  expect(gaps).toEqual([1, 2, 5, 10]);
});

test('tells an answer it cannot read from a network failure', async () => {
  const seen: Reading<{ next: number }>[] = [];
  server = () => ok({ next: 'soon' });
  follow(env, source(), (r) => seen.push(r));
  await vi.advanceTimersByTimeAsync(0);
  expect(seen.at(-1)?.problem).toBe('invalid');
});

test('takes a refused request as unavailable while online', async () => {
  const seen: Reading<{ next: number }>[] = [];
  server = () => 'network';
  follow(env, source(), (r) => seen.push(r));
  await vi.advanceTimersByTimeAsync(0);
  expect(seen.at(-1)?.problem).toBe('unavailable');
});

test('does not decode an unchanged file again', async () => {
  const decode = vi.fn((body: unknown) => body as { next: number });
  server = () => ok({ next: 0 }, '0x8DF2EA7203D27F9');
  follow(env, { ...source(), decode }, () => {});
  await vi.advanceTimersByTimeAsync(5 * MIN);
  expect(reads.length).toBeGreaterThan(1);
  expect(decode).toHaveBeenCalledTimes(1);
});

test('reads a lazy file only when asked', async () => {
  const follower = follow(env, { ...source(), lazy: true }, () => {});
  show();
  await vi.advanceTimersByTimeAsync(HOUR);
  expect(reads).toHaveLength(0);
  follower.ask();
  follower.ask();
  await vi.advanceTimersByTimeAsync(0);
  expect(reads).toHaveLength(1);
});

test('stops reading once stopped', async () => {
  server = () => ok({ next: 0 });
  const follower = follow(env, source(), () => {});
  await vi.advanceTimersByTimeAsync(0);
  follower.stop();
  await vi.advanceTimersByTimeAsync(HOUR);
  expect(reads).toHaveLength(1);
});
