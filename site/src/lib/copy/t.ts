import { copy } from '#gen/copy.ts';

export type Key = keyof typeof copy;
export type Params = Record<string, string | number>;

// A placeholder without a value stays as written, so a missing one shows up on
// the page and in the tests instead of disappearing.
export function fill(text: string, params: Params = {}): string {
  return text.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole
  );
}

export function t(key: Key, params?: Params): string {
  return fill(copy[key], params);
}

// For keys built from data, such as `dir.${code}`, which the type checker
// cannot follow.
export function has(key: string): key is Key {
  return key in copy;
}
