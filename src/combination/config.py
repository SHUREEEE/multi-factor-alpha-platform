"""YAML configuration loader for Pillar 4 factor combination."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.combination.baseline import FactorSpec


@dataclass(frozen=True)
class CandidateFactor:
    """One configured Pillar 4 candidate factor."""

    alias: str
    source_name: str
    direction: int
    optional: bool
    research_transform: str


@dataclass(frozen=True)
class PortfolioConfig:
    """One configured comparison portfolio."""

    name: str
    factors: list[str]
    weighting: str


@dataclass(frozen=True)
class Pillar4Config:
    """Validated Pillar 4 YAML configuration."""

    source_factor_file: str
    price_file: str
    research_summary_file: str
    include_optional_default: bool
    candidates: list[CandidateFactor]
    portfolios: list[PortfolioConfig]


def load_pillar4_config(path: str | Path) -> Pillar4Config:
    """Load and validate the Pillar 4 candidate-factor YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Missing Pillar 4 config: {config_path.as_posix()}")
    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw_config, dict):
        raise ValueError("Pillar 4 config must be a YAML mapping.")
    return _parse_config(raw_config)


def specs_from_config(config: Pillar4Config, include_optional: bool | None = None) -> list[FactorSpec]:
    """Return factor specs for candidates included by the optional-factor rule."""
    use_optional = config.include_optional_default if include_optional is None else include_optional
    return [
        FactorSpec(name=candidate.source_name, sign=candidate.direction)
        for candidate in config.candidates
        if use_optional or not candidate.optional
    ]


def specs_for_portfolio(config: Pillar4Config, portfolio: PortfolioConfig) -> list[FactorSpec]:
    """Return factor specs for one named comparison portfolio."""
    candidates = {candidate.source_name: candidate for candidate in config.candidates}
    missing_names = sorted(set(portfolio.factors) - set(candidates))
    if missing_names:
        raise ValueError(f"Portfolio {portfolio.name} references missing factors: {missing_names}")
    return [FactorSpec(name=factor_name, sign=candidates[factor_name].direction) for factor_name in portfolio.factors]


def _parse_config(raw_config: dict[str, Any]) -> Pillar4Config:
    required_keys = ["source_factor_file", "price_file", "research_summary_file", "candidates", "portfolios"]
    _require_keys(raw_config, required_keys, "Pillar 4 config")
    candidates = _parse_candidates(raw_config["candidates"])
    portfolios = _parse_portfolios(raw_config["portfolios"])
    return Pillar4Config(
        source_factor_file=str(raw_config["source_factor_file"]),
        price_file=str(raw_config["price_file"]),
        research_summary_file=str(raw_config["research_summary_file"]),
        include_optional_default=bool(raw_config.get("include_optional_default", True)),
        candidates=candidates,
        portfolios=portfolios,
    )


def _parse_candidates(raw_candidates: Any) -> list[CandidateFactor]:
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("candidates must be a non-empty list.")
    candidates = [_parse_candidate(raw_candidate) for raw_candidate in raw_candidates]
    source_names = [candidate.source_name for candidate in candidates]
    if len(source_names) != len(set(source_names)):
        raise ValueError("candidate source_name values must be unique.")
    return candidates


def _parse_candidate(raw_candidate: Any) -> CandidateFactor:
    if not isinstance(raw_candidate, dict):
        raise ValueError("each candidate must be a YAML mapping.")
    _require_keys(raw_candidate, ["alias", "source_name", "direction", "optional"], "candidate")
    direction = int(raw_candidate["direction"])
    if direction not in {-1, 1}:
        raise ValueError("candidate direction must be either 1 or -1.")
    return CandidateFactor(
        alias=str(raw_candidate["alias"]),
        source_name=str(raw_candidate["source_name"]),
        direction=direction,
        optional=bool(raw_candidate["optional"]),
        research_transform=str(raw_candidate.get("research_transform", "none")),
    )


def _parse_portfolios(raw_portfolios: Any) -> list[PortfolioConfig]:
    if not isinstance(raw_portfolios, dict) or not raw_portfolios:
        raise ValueError("portfolios must be a non-empty mapping.")
    return [_parse_portfolio(name, raw_portfolio) for name, raw_portfolio in raw_portfolios.items()]


def _parse_portfolio(name: str, raw_portfolio: Any) -> PortfolioConfig:
    if not isinstance(raw_portfolio, dict):
        raise ValueError(f"portfolio {name} must be a YAML mapping.")
    _require_keys(raw_portfolio, ["factors", "weighting"], f"portfolio {name}")
    factors = raw_portfolio["factors"]
    if not isinstance(factors, list) or not factors:
        raise ValueError(f"portfolio {name} factors must be a non-empty list.")
    return PortfolioConfig(name=str(name), factors=[str(factor) for factor in factors], weighting=str(raw_portfolio["weighting"]))


def _require_keys(mapping: dict[str, Any], keys: list[str], label: str) -> None:
    missing_keys = sorted(set(keys) - set(mapping))
    if missing_keys:
        raise ValueError(f"{label} missing required keys: {missing_keys}")
