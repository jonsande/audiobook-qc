"""El formato editorial es reutilizable sin importar una CLI o un adaptador."""

import pytest

from audiobook_qc.audio_position import format_audio_position


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_editorial_position_rejects_nonfinite_values(value):
    with pytest.raises(ValueError, match="finita"):
        format_audio_position(value)


def test_editorial_position_can_be_used_without_incident_or_cli():
    assert format_audio_position(120.999) == "00:02:00"
    assert format_audio_position(7384.98765) == "02:03:04"
