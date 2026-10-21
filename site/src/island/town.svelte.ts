// What one town page reads, kept as reactive state for the blocks to share.
import { follow, type Env, type Follower, type Reading } from '#lib/data/refresh.ts';
import { forecastFile, nowFile, statusFile } from '#lib/data/source.ts';
import { pageState, type PageState } from '#lib/data/states.ts';
import type { ForecastFile, NowFile } from '#lib/data/decode.ts';
import type { Status } from '#gen/status.ts';

export type TownInfo = { slug: string; lat: number; lon: number; station: string; km: number };

const MINUTE = 60_000;
const empty = <T>(): Reading<T> => ({ value: null, at: null, problem: null });

export class TownData {
  now = $state(empty<NowFile>());
  forecast = $state(empty<ForecastFile>());
  status = $state(empty<Status>());
  // The time the ages are counted from. It moves every minute without a read.
  clock = $state(0);
  readonly town: TownInfo;
  readonly env: Env;
  #status: Follower;

  constructor(town: TownInfo, env: Env) {
    this.town = town;
    this.env = env;
    this.clock = env.now();
    follow(env, nowFile(town.slug), (r) => (this.now = r));
    follow(env, forecastFile(town.slug), (r) => (this.forecast = r));
    this.#status = follow(env, statusFile(), (r) => (this.status = r));
    const tick = () => {
      this.clock = env.now();
      env.wait(MINUTE - (this.clock % MINUTE), tick);
    };
    tick();
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
