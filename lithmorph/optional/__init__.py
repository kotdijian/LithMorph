"""Optional morphology analyzers.

Planned analyzers are intentionally not implemented in v0.1.0-dev1.
The registry in base.py allows them to be added without modifying the
basic geometry pipeline.
"""

from .base import OptionalAnalysisSpec, names, register, run_selected

__all__ = ["OptionalAnalysisSpec", "names", "register", "run_selected"]
