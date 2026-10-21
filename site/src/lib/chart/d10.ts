// The days the 10-day table shows. A model counts for a day only when it has
// every hour of it, so the last days can have no model at all: those are left
// out, never drawn as a day without data.
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
