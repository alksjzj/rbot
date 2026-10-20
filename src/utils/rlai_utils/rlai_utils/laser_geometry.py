"""激光车体回波的几何过滤，可独立于 ROS 验证。"""

import math


def mask_body_returns(ranges, angle_min, angle_increment, rotation, translation, bounds):
    """作用：屏蔽车体内部回波；输入：扫描、雷达到车体的 TF、轮廓；输出：新距离列表。

    保留车体外的测量；被屏蔽的测量使用 NaN 表示无效，不伪造障碍物距离。
    """
    qx, qy, qz, qw = rotation
    tx, ty = translation
    min_x, max_x, min_y, max_y = bounds
    r00, r01 = 1 - 2*(qy*qy + qz*qz), 2*(qx*qy - qw*qz)
    r10, r11 = 2*(qx*qy + qw*qz), 1 - 2*(qx*qx + qz*qz)
    output = list(ranges)
    for index, distance in enumerate(ranges):
        if not math.isfinite(distance) or distance <= 0:
            continue
        angle = angle_min + index*angle_increment
        sx, sy = distance*math.cos(angle), distance*math.sin(angle)
        x, y = r00*sx + r01*sy + tx, r10*sx + r11*sy + ty
        if min_x <= x <= max_x and min_y <= y <= max_y:
            output[index] = math.nan
    return output
