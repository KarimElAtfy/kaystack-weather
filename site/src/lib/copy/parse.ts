// Reads it.md: table rows `| key | where | max | text |` for the short strings,
// and `#### key` blocks under "Testi lunghi" for the paragraphs of the text pages.

export type Entry = { key: string; max: number | null; text: string };
export type Copy = { short: Entry[]; long: Entry[] };

const ROW = /^\|\s*`([^`]+)`\s*\|[^|]*\|\s*([^|]*?)\s*\|\s*(.*?)\s*\|\s*$/;

export function parse(markdown: string): Copy {
  const short: Entry[] = [];
  const long: Entry[] = [];
  let block: Entry | null = null;
  for (const line of markdown.split(/\r?\n/)) {
    const heading = /^####\s+(\S+)\s*$/.exec(line);
    if (heading) {
      block = { key: heading[1] ?? '', max: null, text: '' };
      long.push(block);
      continue;
    }
    if (line.startsWith('#')) {
      block = null;
      continue;
    }
    if (block) {
      block.text = [block.text, line.trim()].filter(Boolean).join(' ');
      continue;
    }
    const row = ROW.exec(line);
    if (row) {
      const max = Number(row[2]);
      short.push({
        key: row[1] ?? '',
        max: Number.isInteger(max) ? max : null,
        text: row[3] ?? ''
      });
    }
  }
  return { short, long };
}

// The length a reader sees, without the placeholders: the values that fill
// them vary, so the max in it.md bounds the fixed words only.
export const visible = (text: string) => text.replace(/\{\w+\}/g, '').length;

// The characters the repo's hooks refuse in committed text: odd spaces and
// dashes, curly quotes, the ellipsis, arrows, symbols and emoji.
export const BANNED =
  /[\u00a0\u2000-\u2015\u2018-\u201f\u2026\u2028-\u202f\u2060\ufeff\ufe0f\u2190-\u21ff\u27f0-\u27ff\u2900-\u297f\u2600-\u27bf\u2b00-\u2bff]|[\u{1f000}-\u{1ffff}]/u;
