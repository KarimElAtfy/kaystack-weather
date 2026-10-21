"""The files the site reads from the public container, version 1.

These models are the source of the contract: every file is built from them, so it is
checked before it is written, and `schema/` is generated from them for the site.
Within v1 a change may only add something. Anything else is a v2, under new paths.

Every field is written every time, so the schema marks all of them required. A field
added later in v1 is missing from files written before it, and the site has to treat
it as optional.
"""

import itertools
import json
import sys
from datetime import UTC, date
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal, Self
from zoneinfo import ZoneInfo

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    model_validator,
)
from pydantic.json_schema import GenerateJsonSchema

DRAFT = "https://json-schema.org/draft/2020-12/schema"

# UTC with a Z and whole seconds, as status.json has always written its times.
# Fractions of a second are cut on the way in, so a file read back equals the one written.
Stamp = Annotated[
    AwareDatetime,
    AfterValidator(lambda t: t.astimezone(UTC).replace(microsecond=0)),
    PlainSerializer(lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ"), return_type=str),
    WithJsonSchema(
        {
            "type": "string",
            "format": "date-time",
            "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        }
    ),
]
Slug = Annotated[str, Field(pattern=r"^[a-z]+(-[a-z]+)*$")]
Count = Annotated[int, Field(ge=0)]

# The Function image is not known to carry a zone database, so tzdata is a dependency.
ROME = ZoneInfo("Europe/Rome")


class Model(BaseModel):
    # Extra fields are ignored, not forbidden: with additionalProperties false in
    # the schema, a site still on the older schema would reject any later addition.
    model_config = ConfigDict(
        serialize_by_alias=True,
        json_schema_serialization_defaults_required=True,
    )


class File(Model):
    PATH: ClassVar[str]
    CACHE: ClassVar[str]

    schema_: str = Field(alias="schema")
    license: str = Field(min_length=1)
    attribution: str = Field(min_length=1, description="The credit the sources ask for.")
    generated_at: Stamp

    @classmethod
    def path(cls, slug: str = "") -> str:
        return cls.PATH.format(slug=slug)


class Source(Model):
    checked_at: Stamp | None = Field(
        description="When the source was last reached in full; null if never."
    )
    data_time: Stamp | None = Field(
        description="The oldest of `parts`, or for model runs the newest."
    )
    parts: dict[str, Stamp] = Field(
        description="The newest data time per station, sensor, point or model."
    )


class Status(File):
    """When each source was last reached and how recent its data is."""

    # The one file outside v1/: status.py has written it at the root since M1, and
    # freshness.yml reads it there.
    PATH = "status.json"
    CACHE = "public, max-age=60"

    schema_: Literal["status/1"] = Field("status/1", alias="schema")
    sources: dict[str, Source]


class Reference(Model):
    name: str
    distance_km: float = Field(ge=0, description="From the town centre.")


class Metar(Model):
    icao: str = Field(pattern=r"^[A-Z]{4}$")
    name: str
    distance_km: float = Field(ge=0, description="From the town centre.")
    observed_at: Stamp
    temperature_c: float | None
    dew_point_c: float | None
    wind_kmh: float | None
    wind_dir_deg: int | None = Field(ge=0, le=360, description="Null when variable.")
    gust_kmh: float | None
    visibility_m: int | None = Field(ge=0, description="9999 means 10 km or more.")
    weather: str | None = Field(description="Present weather groups as reported, e.g. -RA BR.")
    stale_after_min: int = Field(90, gt=0, description="Minutes after observed_at.")


class RadarAtTown(Model):
    frame_time: Stamp
    rate_mm_h: float | None = Field(ge=0, description="At the town centre's cell.")
    max_5km_mm_h: float | None = Field(ge=0)
    max_10km_mm_h: float | None = Field(ge=0)
    no_data: bool = Field(description="The frame has no data within 10 km of the town.")
    stale_after_min: int = Field(15, gt=0, description="Minutes after frame_time.")


class Now(File):
    """The latest observation at the town. The METAR job and the radar job each write
    their own block, so either can be null until its job first runs."""

    PATH = "v1/{slug}/now.json"
    CACHE = "public, max-age=60"

    schema_: Literal["now/1"] = Field("now/1", alias="schema")
    town: Slug
    reference: Reference = Field(description="The station the forecast is corrected against.")
    metar: Metar | None
    radar: RadarAtTown | None


class Frame(Model):
    time: Stamp
    missing: bool = Field(
        description="DPC has no frame for this time; its cell in the sprite is all hatch."
    )


class Pixel(Model):
    x: int = Field(ge=0)
    y: int = Field(ge=0, description="From the top.")


class View(Model):
    """The area of a frame in metres on the DPC SRI grid, the same as the town file's."""

    west: int
    east: int
    south: int
    north: int

    @model_validator(mode="after")
    def not_empty(self) -> Self:
        if not (self.west < self.east and self.south < self.north):
            raise ValueError(f"empty view {self}")
        return self


class Bin(Model):
    index: int = Field(ge=1, le=6, description="The class in the sprite.")
    from_mm_h: float = Field(gt=0, description="Included.")
    to_mm_h: float | None = Field(description="Not included; null for the top class.")


class Radar(File):
    """The last frames around the town, drawn one after the other into a single sprite.

    The sprite is a lossless WebP that holds class indices rather than colours, so the
    site colours them for each theme. Index i is the grey round(255 (i + 0.5) / 9), and
    floor(grey * 9 / 256) gives it back. Index 0, no rain, is fully transparent; the
    others are opaque. 1 to 6 are the classes in `scale`, 7 and 8 the no-data hatch:
    the line where (x + y) mod 4 = 0 counting from the frame's top left pixel, the fill
    elsewhere. Read it pixel for pixel: any smoothing mixes the classes."""

    PATH = "v1/{slug}/radar.json"
    CACHE = "public, max-age=60"

    schema_: Literal["radar/1"] = Field("radar/1", alias="schema")
    town: Slug
    encoding: Literal["class-grey9/1"] = "class-grey9/1"
    sprite: str = Field(
        description=(
            "The image next to this file. It has a new name on every update and is written"
            " before this file, and the previous one stays at least 10 minutes, so a"
            " radar.json from the cache never meets a newer image."
        )
    )
    frame_width_px: int = Field(gt=0)
    frame_height_px: int = Field(gt=0)
    columns: int = Field(gt=0, description="Frames per sprite row.")
    frames: list[Frame] = Field(description="Oldest first, in sprite order, row by row.")
    view: View
    km_per_px: float = Field(gt=0)
    town_px: Pixel = Field(description="The town centre within a frame.")
    scale: list[Bin] = Field(
        description="Lowest first. v1 writes six classes from 0.2, 1, 2, 6, 15 and 40 mm/h."
    )

    @model_validator(mode="after")
    def frame_matches_view(self) -> Self:
        width = (self.view.east - self.view.west) / 1000 / self.km_per_px
        height = (self.view.north - self.view.south) / 1000 / self.km_per_px
        if (width, height) != (self.frame_width_px, self.frame_height_px):
            raise ValueError(f"the view is {width} x {height} px at {self.km_per_px} km per px")
        if self.town_px.x >= width or self.town_px.y >= height:
            raise ValueError(f"town at {self.town_px} outside the frame")
        return self

    @model_validator(mode="after")
    def six_classes(self) -> Self:
        if [b.index for b in self.scale] != [1, 2, 3, 4, 5, 6]:
            raise ValueError(f"scale indices {[b.index for b in self.scale]}")
        for low, high in itertools.pairwise(self.scale):
            if low.to_mm_h != high.from_mm_h:
                raise ValueError(f"class {low.index} ends at {low.to_mm_h}, not {high.from_mm_h}")
        if self.scale[-1].to_mm_h is not None:
            raise ValueError("the top class has an upper bound")
        return self


def same_length(steps: int, model: BaseModel) -> None:
    for series in dict(model).values():
        if not isinstance(series, BaseModel):
            continue
        for name, values in series:
            if isinstance(values, list) and len(values) != steps:
                raise ValueError(f"{name} has {len(values)} values for {steps} steps")


class Spread(Model):
    """The mean of the models and the range between the lowest and the highest. The
    range is the spread of the models, not a probability. When corrected is true every
    value is corrected: a step with no corrected model is null, never raw."""

    corrected: bool
    mean: list[float | None]
    low: list[float | None]
    high: list[float | None]
    m_models: list[Count] = Field(description="Models in the mean; 0 exactly when it is null.")
    lead_band: list[Annotated[int, Field(ge=0, le=7)]] = Field(
        description=(
            "The lead band of the bias applied, in days, at most 7. Hourly: per model"
            " floor((time - run_init) / 24 h), and the step takes the highest among the"
            " models in the mean. Daily: local days after the local day of the issue, 1 to 7."
        )
    )

    @model_validator(mode="after")
    def low_mean_high(self) -> Self:
        steps = zip(self.low, self.mean, self.high, self.m_models, strict=False)
        for low, mean, high, m in steps:
            if low is None or mean is None or high is None:
                if m or (low, mean, high) != (None, None, None):
                    raise ValueError(f"m_models {m} with mean {mean}, low {low}, high {high}")
            elif not m:
                raise ValueError(f"mean {mean} with m_models 0")
            elif not low <= mean <= high:
                raise ValueError(f"mean {mean} outside {low} to {high}")
        return self


class Consensus(Model):
    """The plain mean of the models, uncorrected in v1."""

    corrected: bool
    mean: list[float | None]


class RainCount(Model):
    threshold_mm: float = Field(gt=0, description="Included, so 0.2 counts at 0.2 mm.")
    n_models: list[Count] = Field(description="Models with at least threshold_mm.")
    m_models: list[Count] = Field(
        description="Models with a value for the step; for a day, only those with all its hours."
    )

    @model_validator(mode="after")
    def n_of_m(self) -> Self:
        for n, m in zip(self.n_models, self.m_models, strict=False):
            if not 0 <= n <= m:
                raise ValueError(f"{n} rainy models of {m}")
        return self


class Hourly(Model):
    """Hours 0 to 48 after the issue. Instants are at `time`; rain and gusts cover the
    hour ending at it. The wind direction is that of the mean wind vector."""

    time: list[Stamp]
    temperature_c: Spread
    dew_point_c: Consensus
    wind_kmh: Consensus
    wind_dir_deg: Consensus
    gust_kmh: Consensus
    cloud_pct: Consensus
    precipitation_mm: Consensus
    rain: RainCount

    @model_validator(mode="after")
    def steps(self) -> Self:
        same_length(len(self.time), self)
        return self


class Daily(Model):
    """Local days in Europe/Rome, 1 to 10 days after the day of the issue, so day 1 is
    tomorrow. Day D takes
    the hours whose end falls in (D 00:00, D+1 00:00]. A model counts for a day only if
    it has every hour of it: 24, or 23 and 25 on the days the clocks change. A model
    that stops partway through a day would pull Tmax down, Tmin up and rain counts down."""

    day: list[date]
    tmax_c: Spread
    tmin_c: Spread
    rain: RainCount

    @model_validator(mode="after")
    def steps(self) -> Self:
        same_length(len(self.day), self)
        return self


class Run(Model):
    model: str = Field(description="The Open-Meteo model name.")
    run_init: Stamp


class Forecast(File):
    """The multi-model forecast for the town's reference station. The hourly job issues
    it every hour from the newest runs it holds, so issued_at moves on every hour even
    when no model has a new run; `models` gives the age of each run."""

    PATH = "v1/{slug}/forecast.json"
    CACHE = "public, max-age=300"

    schema_: Literal["forecast/1"] = Field("forecast/1", alias="schema")
    town: Slug
    issued_at: Stamp
    method: Literal["mean60-v1"]
    models: list[Run] = Field(description="The run of each model in the mean, at any step.")
    stale_after_min: int = Field(180, gt=0, description="Minutes after issued_at.")
    expired_after_min: int = Field(1440, gt=0, description="Minutes after issued_at.")
    hourly: Hourly
    daily: Daily

    @model_validator(mode="after")
    def days_after_the_issue(self) -> Self:
        # Counted from the local day of the issue, not the UTC one: an issue at 23:45Z
        # in winter is already the next day in Rome.
        issue_day = self.issued_at.astimezone(ROME).date()
        for spread in (self.daily.tmax_c, self.daily.tmin_c):
            for day, band in zip(self.daily.day, spread.lead_band, strict=False):
                ahead = (day - issue_day).days
                if not 1 <= ahead <= 10:
                    raise ValueError(f"{day} is {ahead} days after the issue")
                if band != min(ahead, 7):
                    raise ValueError(f"lead band {band} on {day}, {ahead} days after the issue")
        return self


FILES: dict[str, type[File]] = {
    "status": Status,
    "now": Now,
    "radar": Radar,
    "forecast": Forecast,
}


class NoFieldTitles(GenerateJsonSchema):
    # A title on a field makes json-schema-to-typescript declare a named type for
    # each one; the model titles are enough.
    def field_title_should_be_set(self, schema: Any) -> bool:
        return False


def schemas() -> dict[str, str]:
    texts = {}
    for name, model in FILES.items():
        body = model.model_json_schema(mode="serialization", schema_generator=NoFieldTitles)
        text = json.dumps({"$schema": DRAFT, **body}, indent=2, ensure_ascii=False)
        texts[f"{name}.schema.json"] = text + "\n"
    return texts


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    for name, text in schemas().items():
        (folder / name).write_text(text, encoding="utf-8", newline="\n")
