from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from ..models import AnalysisContext


@dataclass(frozen=True)
class OptionalAnalysisSpec:
    name: str
    label: str
    version: str
    description: str


class OptionalAnalyzer(Protocol):
    spec: OptionalAnalysisSpec

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        ...


_REGISTRY: dict[str, OptionalAnalyzer] = {}


def register(analyzer: OptionalAnalyzer) -> None:
    name = analyzer.spec.name
    if name in _REGISTRY:
        raise ValueError(f"Optional analyzer already registered: {name}")
    _REGISTRY[name] = analyzer


def names() -> list[str]:
    return sorted(_REGISTRY)


def run_selected(
    context: AnalysisContext,
    selected: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name in selected:
        if name not in _REGISTRY:
            raise KeyError(
                f"Optional analyzer is not registered: {name}. "
                f"Available: {', '.join(names()) or '(none)'}"
            )
        results[name] = _REGISTRY[name].analyze(context)
    return results
