import numpy as np
import pytest

from photodiode_tia.lockin import estimate


def test_recovers_known_amplitude_with_jitter_and_ambient_interference():
    rng = np.random.default_rng(7)
    t = np.arange(4000) / 4000 + rng.normal(0, 5e-6, 4000)
    y = 1420 + 12 * np.cos(2 * np.pi * 137 * t + 0.3)
    y += 35 * np.sin(2 * np.pi * 60 * t) + rng.normal(0, 8, len(t))
    result = estimate(t, y, 137)
    assert result.amplitude == pytest.approx(12, abs=0.7)
    assert result.dc == pytest.approx(1420, abs=1)
    assert result.samples == 4000


def test_rejects_invalid_timing_and_unidentifiable_reference():
    t = np.arange(16) / 1000
    with pytest.raises(ValueError):
        estimate(t[::-1], np.ones(16), 137)
    with pytest.raises(ValueError):
        estimate(t, np.ones(16), 0)
    with pytest.raises(ValueError):
        estimate(t, np.ones(16), 1000)


def test_offset_does_not_look_like_modulated_signal():
    t = np.arange(4000) / 4000
    result = estimate(t, np.full_like(t, 1550.0), 137)
    assert result.amplitude < 1e-9
