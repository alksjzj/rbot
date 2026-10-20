"""检查雷达偏置、旋转和近距离外部障碍，避免误删有效测量。"""

import importlib.util
import math
from pathlib import Path

import pytest


MODULE = (Path(__file__).resolve().parents[1] /
          'src/utils/rlai_utils/rlai_utils/laser_geometry.py')
spec = importlib.util.spec_from_file_location('laser_geometry', MODULE)
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)
BOUNDS = (-0.28, 0.28, -0.23, 0.23)


def test_sensor_offset_masks_body_but_preserves_close_external_wall():
    # 雷达位于车头 x=0.2；前方 0.15 m 已在车外，后方 0.4 m 仍在车内。
    original = [0.15, 2.0, 0.4]
    result = geometry.mask_body_returns(
        original, 0, math.pi / 2, (0, 0, 0, 1), (0.2, 0), BOUNDS)
    assert result[:2] == original[:2]
    assert math.isnan(result[2])
    assert original == [0.15, 2.0, 0.4]


def test_rotated_sensor_uses_body_coordinates():
    # 雷达转了 90°；0.25 m 沿车体 y 方向已超出车宽。
    result = geometry.mask_body_returns(
        [0.25, 0.20], 0, math.pi / 2,
        (0, 0, math.sin(math.pi / 4), math.cos(math.pi / 4)), (0, 0), BOUNDS)
    assert result[0] == pytest.approx(0.25)
    assert math.isnan(result[1])


def test_invalid_and_outside_measurements_are_preserved():
    result = geometry.mask_body_returns(
        [math.nan, math.inf, 0.0, -1.0, 5.0], 0, 0.1,
        (0, 0, 0, 1), (0, 0), BOUNDS)
    assert math.isnan(result[0])
    assert result[1:] == [math.inf, 0.0, -1.0, 5.0]
