"""Evidence labels shared across analysis/calibration/scripts.

Per docs/design-contract.md: "calculated, model-simulated, expected and
measured results explicitly labeled." This module gives one place that
defines the vocabulary so every script/plot/table uses the same words.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

CALCULATED = "CALCULATED"  # derived from formulas/known inputs, no instrument involved
SIMULATED = "SIMULATED"  # from a circuit/behavioral simulation (e.g. LTspice), not real hardware
EXPECTED = "EXPECTED"  # theoretical/model prediction to compare measurements against
MEASURED = "MEASURED"  # from real hardware over the WebSocket link
SYNTHETIC = "SYNTHETIC"  # from mock_server.py / test fixtures; must never land in measurements/

ALL_LABELS = (CALCULATED, SIMULATED, EXPECTED, MEASURED, SYNTHETIC)


@dataclass(frozen=True)
class Labeled:
    """A value tagged with its evidence label, unit, and free-text provenance.

    Printing/formatting should always show the label so a reader can never
    mistake a CALCULATED or SYNTHETIC number for a MEASURED one.
    """

    value: Any
    label: str
    unit: str = ""
    provenance: str = ""

    def __post_init__(self):
        if self.label not in ALL_LABELS:
            raise ValueError(f"label must be one of {ALL_LABELS}, got {self.label!r}")

    def __str__(self) -> str:
        unit = f" {self.unit}" if self.unit else ""
        prov = f" ({self.provenance})" if self.provenance else ""
        return f"[{self.label}] {self.value}{unit}{prov}"
