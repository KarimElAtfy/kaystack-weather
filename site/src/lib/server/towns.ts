// The towns come from ../towns/*.toml, the files the pipeline reads, so the
// station and its distance are in the page before any data arrives.
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'smol-toml';

export type Town = {
  slug: string;
  lat: number;
  lon: number;
  station: string;
  km: number;
};

type Point = { lat: number; lon: number };
type File = Point & { slug: string; reference: Point & { name: string } };

// Haversine on the mean Earth radius, to one decimal, as the contract computes it.
export function distance(a: Point, b: Point): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLon = (b.lon - a.lon) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return Math.round(2 * 6371.0088 * Math.asin(Math.sqrt(h)) * 10) / 10;
}

export function towns(folder = '../towns'): Town[] {
  return readdirSync(folder)
    .filter((name) => name.endsWith('.toml'))
    .sort()
    .map((name) => {
      const file = parse(readFileSync(join(folder, name), 'utf8')) as unknown as File;
      return {
        slug: file.slug,
        lat: file.lat,
        lon: file.lon,
        station: file.reference.name,
        km: distance(file, file.reference)
      };
    });
}
