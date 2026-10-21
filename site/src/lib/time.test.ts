import { expect, test } from 'vitest';
import {
  ago,
  dayName,
  dstLabel,
  hm,
  isNight,
  localDate,
  repeatedHour,
  weekdayShort,
  ymd
} from './time.ts';

const utc = (iso: string) => Date.parse(iso);
const MIN = 60_000;

test('runs in a time zone other than Rome', () => {
  expect(new Date(utc('2026-10-24T12:00:00Z')).getHours()).not.toBe(14);
});

test('prints Rome time on both sides of the change back to winter time', () => {
  expect(hm(utc('2026-10-24T22:00:00Z'))).toBe('00:00');
  expect(hm(utc('2026-10-25T00:00:00Z'))).toBe('02:00');
  expect(hm(utc('2026-10-25T01:00:00Z'))).toBe('02:00');
  expect(hm(utc('2026-10-25T02:00:00Z'))).toBe('03:00');
});

test('skips 02:00 when summer time starts', () => {
  expect(hm(utc('2026-03-29T00:00:00Z'))).toBe('01:00');
  expect(hm(utc('2026-03-29T01:00:00Z'))).toBe('03:00');
});

test('labels the two 02:00 of 25 October', () => {
  const times = ['23:00', '00:00', '01:00', '02:00'].map((h, i) =>
    utc(`2026-10-${i === 0 ? '24' : '25'}T${h}:00Z`)
  );
  expect(times.map((_, i) => repeatedHour(times, i))).toEqual([null, 'summer', 'winter', null]);
  expect(dstLabel(times, 1)).toBe('ora legale');
  expect(dstLabel(times, 2)).toBe('ora solare');
  expect(dstLabel(times, 3)).toBeNull();
});

test('puts a late evening UTC time on the right local day', () => {
  expect(ymd(utc('2026-10-25T22:30:00Z'))).toBe('2026-10-25');
  expect(ymd(utc('2026-10-25T23:00:00Z'))).toBe('2026-10-26');
  expect(ymd(utc('2026-07-01T21:59:00Z'))).toBe('2026-07-01');
  expect(ymd(utc('2026-07-01T22:00:00Z'))).toBe('2026-07-02');
});

test('reads a contract date back as the same local day', () => {
  expect(ymd(localDate('2026-10-26'))).toBe('2026-10-26');
  expect(weekdayShort(localDate('2026-10-26'))).toBe('lun');
});

test('says how old a value is in the words of the copy file', () => {
  const now = utc('2026-10-24T13:10:00Z');
  expect(ago(now - 30_000, now)).toBe('adesso');
  expect(ago(now - 20 * MIN, now)).toBe('20 min fa');
  expect(ago(now - 60 * MIN, now)).toBe('1 ora fa');
  expect(ago(now - 80 * MIN, now)).toBe('1 h 20 min fa');
  expect(ago(now - 170 * MIN, now)).toBe('2 h 50 min fa');
  expect(ago(now - 190 * MIN, now)).toBe('3 ore fa');
  expect(ago(now + 5 * MIN, now)).toBe('adesso');
});

test('names nearby days in words and others by weekday', () => {
  const now = utc('2026-10-24T13:10:00Z');
  expect(dayName(utc('2026-10-24T18:00:00Z'), now)).toBe('oggi');
  expect(dayName(utc('2026-10-25T10:00:00Z'), now)).toBe('domani');
  expect(dayName(utc('2026-10-23T10:00:00Z'), now)).toBe('ieri');
  expect(dayName(utc('2026-10-26T10:00:00Z'), now)).toBe('lunedì');
});

test('knows night from day at Pedrengo', () => {
  expect(isNight(utc('2026-10-24T13:00:00Z'), 45.6959, 9.7392)).toBe(false);
  expect(isNight(utc('2026-10-24T21:00:00Z'), 45.6959, 9.7392)).toBe(true);
});
