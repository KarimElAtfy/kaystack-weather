// What one town page reads, kept as reactive state for the blocks to share.
import { follow, type Env, type Follower, type Reading } from '#lib/data/refresh.ts';
import { forecastFile, nowFile, radarFile, spriteUrl, statusFile } from '#lib/data/source.ts';
import { pageState, type PageState } from '#lib/data/states.ts';
import { framesFrom } from '#lib/radar/sprite.ts';
import type { ForecastFile, NowFile, RadarFile } from '#lib/data/decode.ts';
import type { Status } from '#gen/status.ts';

export type TownInfo = { slug: string; lat: number; lon: number; station: string; km: number };

const MINUTE = 60_000;
const empty = <T>(): Reading<T> => ({ value: null, at: null, problem: null });

export class TownData {
  now = $state(empty<NowFile>());
  forecast = $state(empty<ForecastFile>());
  status = $state(empty<Status>());
  radar = $state(empty<RadarFile>());
  // The class index of every cell of every frame, once the sprite is read.
  frames = $state<{ sprite: string; frames: Uint8Array[] } | null>(null);
  spriteFailed = $state(false);
  // The time the ages are counted from. It moves every minute without a read.
  clock = $state(0);
  readonly town: TownInfo;
  readonly env: Env;
  #status: Follower;
  #radarSeen = false;
  #sprite = '';

  constructor(town: TownInfo, env: Env) {
    this.town = town;
    this.env = env;
    this.clock = env.now();
    follow(env, nowFile(town.slug), (r) => (this.now = r));
    follow(env, forecastFile(town.slug), (r) => (this.forecast = r));
    this.#status = follow(env, statusFile(), (r) => (this.status = r));
    follow(env, radarFile(town.slug), (r) => {
      this.radar = r;
      void this.#readSprite();
    });
    const tick = () => {
      this.clock = env.now();
      env.wait(MINUTE - (this.clock % MINUTE), tick);
    };
    tick();
  }

  // The sprite is the heaviest file, so it waits until the radar is close to view.
  seeRadar() {
    this.#radarSeen = true;
    void this.#readSprite();
  }

  async #readSprite() {
    const radar = this.radar.value;
    if (!radar || !this.#radarSeen || radar.sprite === this.#sprite) return;
    this.#sprite = radar.sprite;
    try {
      const response = await this.env.get(spriteUrl(this.town.slug, radar.sprite), 'blob');
      if (response.status !== 200) throw new Error(`sprite answered ${response.status}`);
      // No colour management: the greys must arrive exactly as written.
      const bitmap = await createImageBitmap((await response.body()) as Blob, {
        colorSpaceConversion: 'none',
        premultiplyAlpha: 'none'
      });
      const canvas = document.createElement('canvas');
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const context = canvas.getContext('2d', { willReadFrequently: true });
      if (!context) throw new Error('no 2d canvas');
      context.drawImage(bitmap, 0, 0);
      const pixels = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
      const grid = {
        width: radar.frame_width_px,
        height: radar.frame_height_px,
        columns: radar.columns
      };
      this.frames = {
        sprite: radar.sprite,
        frames: framesFrom(pixels, bitmap.width, grid, radar.frames.length)
      };
      this.spriteFailed = false;
    } catch {
      this.#sprite = '';
      this.spriteFailed = true;
    }
  }

  // The sources list reads status.json only when someone needs it.
  askStatus() {
    this.#status.ask();
  }

  get state(): PageState {
    return pageState([this.now, this.forecast], this.forecast, this.clock);
  }

  get lastRead(): number | null {
    const times = [this.now.at, this.forecast.at].filter((t): t is number => t !== null);
    return times.length ? Math.max(...times) : null;
  }
}
