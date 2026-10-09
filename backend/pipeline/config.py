"""Typed access to config/thresholds.yaml, loaded once per process."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS_PATH = REPO_ROOT / "config" / "thresholds.yaml"


@dataclass(frozen=True)
class FieldConfig:
    length_yd: float
    width_yd: float
    frame_rate_hz: int


@dataclass(frozen=True)
class EngagementConfig:
    distance_yd: float
    min_consecutive_frames: int


@dataclass(frozen=True)
class RusherConfig:
    getoff_speed_yps: float
    set_point_fallback_seconds: float
    set_point_search_seconds: float


@dataclass(frozen=True)
class Level2Config:
    free_rusher_qb_yd: float
    stunt_window_s: float
    excluded_block_types: tuple[str, ...]


@dataclass(frozen=True)
class Level3Config:
    rep_threshold: int
    rep_residual_sigma: float
    pressure_spike_delta: float
    pressure_spike_window: int


@dataclass(frozen=True)
class PatternsConfig:
    interval_confidence: float
    distance_bands: tuple[int, ...]
    min_opportunities: int


@dataclass(frozen=True)
class CostConfig:
    nflverse_offline_ok: bool


@dataclass(frozen=True)
class Thresholds:
    field: FieldConfig
    engagement: EngagementConfig
    rusher: RusherConfig
    level2: Level2Config
    level3: Level3Config
    patterns: PatternsConfig
    cost: CostConfig


@lru_cache(maxsize=1)
def load_thresholds(path: Path | None = None) -> Thresholds:
    raw_path = path or THRESHOLDS_PATH
    with open(raw_path) as f:
        raw = yaml.safe_load(f)

    return Thresholds(
        field=FieldConfig(**raw["field"]),
        engagement=EngagementConfig(**raw["engagement"]),
        rusher=RusherConfig(**raw["rusher"]),
        level2=Level2Config(
            free_rusher_qb_yd=raw["level2"]["free_rusher_qb_yd"],
            stunt_window_s=raw["level2"]["stunt_window_s"],
            excluded_block_types=tuple(raw["level2"]["excluded_block_types"]),
        ),
        level3=Level3Config(**raw["level3"]),
        patterns=PatternsConfig(
            interval_confidence=raw["patterns"]["interval_confidence"],
            distance_bands=tuple(raw["patterns"]["distance_bands"]),
            min_opportunities=raw["patterns"]["min_opportunities"],
        ),
        cost=CostConfig(**raw["cost"]),
    )
