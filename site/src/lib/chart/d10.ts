// The days the 10-day table shows. A model counts for a day only when it has
// every hour of it, so the last days can have no model at all: those are left
// out, never drawn as a day without data.
import type { Key } from '#lib/copy/t.ts';
import type { ForecastFile } from '#lib/data/decode.ts';

export function daysShown(daily: ForecastFile['daily']): number[] {
  return daily.day.flatMap((_, k) =>
    (daily.tmin_c.m_models[k] ?? 0) === 0 &&
    (daily.tmax_c.m_models[k] ?? 0) === 0 &&
    (daily.rain.m_models[k] ?? 0) === 0
      ? []
      : [k]
  );
}

// The note above the table when the minimum, the maximum or both did not get
// the correction, so the page never calls them corrected.
export function rawNote(daily: ForecastFile['daily']): Key | null {
  const min = !daily.tmin_c.corrected;
  const max = !daily.tmax_c.corrected;
  return min && max ? 'd10.note_raw' : min ? 'd10.note_raw_min' : max ? 'd10.note_raw_max' : null;
}
