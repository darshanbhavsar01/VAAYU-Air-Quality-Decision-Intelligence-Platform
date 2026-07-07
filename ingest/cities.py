"""City registry loader — config/cities.yaml is the single source of truth
for which cities VAAYU knows about (CLAUDE.md §2.1, §5.1). Adding a city is
a YAML edit here, not a code change.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from config import REPO_ROOT

CITIES_YAML = REPO_ROOT / "config" / "cities.yaml"


@dataclass
class City:
    city_id: str
    name: str
    state: str
    bbox: tuple[float, float, float, float]  # lon_min, lat_min, lon_max, lat_max
    tier: str
    ward_geojson_path: str | None
    languages: list[str]
    priority: int

    @property
    def bbox_str(self) -> str:
        """lon_min,lat_min,lon_max,lat_max — the format OpenAQ/WAQI expect."""
        return ",".join(str(v) for v in self.bbox)


def load_cities(path: Path = CITIES_YAML, only: list[str] | None = None) -> list[City]:
    """Load the city registry. `only` filters to specific city_ids (for
    single-city ingest / onboarding); unknown ids raise so typos fail loudly."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cities = [
        City(
            city_id=c["city_id"],
            name=c["name"],
            state=c["state"],
            bbox=tuple(c["bbox"]),
            tier=c["tier"],
            ward_geojson_path=c.get("ward_geojson_path"),
            languages=c.get("languages", []),
            priority=c.get("priority", 999),
        )
        for c in raw["cities"]
    ]
    if only is not None:
        want = set(only)
        known = {c.city_id for c in cities}
        missing = want - known
        if missing:
            raise KeyError(f"Unknown city_id(s): {sorted(missing)}. Known: {sorted(known)}")
        cities = [c for c in cities if c.city_id in want]
    return sorted(cities, key=lambda c: c.priority)


def get_city(city_id: str, path: Path = CITIES_YAML) -> City:
    for c in load_cities(path):
        if c.city_id == city_id:
            return c
    raise KeyError(f"City '{city_id}' not found in {path}. Add it to config/cities.yaml first.")


if __name__ == "__main__":
    for c in load_cities():
        print(f"{c.priority}. {c.name} ({c.city_id}) — tier {c.tier} — bbox {c.bbox_str}")
