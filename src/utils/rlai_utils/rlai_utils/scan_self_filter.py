"""移除车体轮廓内部的激光自反射；不读取里程计、速度指令或仿真真值。"""

import copy

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformException, TransformListener

from .laser_geometry import mask_body_returns


class ScanSelfFilter(Node):
    """输入 /scan 和安装 TF；输出 /scan_filtered；不影响机器人运动。"""

    def __init__(self):
        super().__init__('scan_self_filter')
        defaults = {
            'base_frame': 'base_footprint', 'input_topic': '/scan',
            'output_topic': '/scan_filtered',
            'min_x': -0.28, 'max_x': 0.28, 'min_y': -0.23, 'max_y': 0.23,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        self.base_frame = self.get_parameter('base_frame').value
        self.bounds = tuple(self.get_parameter(name).value
                            for name in ('min_x', 'max_x', 'min_y', 'max_y'))
        if self.bounds[0] >= self.bounds[1] or self.bounds[2] >= self.bounds[3]:
            raise ValueError('车体过滤范围必须满足 min_x < max_x、min_y < max_y')
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.publisher = self.create_publisher(
            LaserScan, self.get_parameter('output_topic').value, qos_profile_sensor_data)
        self.subscription = self.create_subscription(
            LaserScan, self.get_parameter('input_topic').value,
            self.filter_scan, qos_profile_sensor_data)

    def filter_scan(self, scan):
        """按扫描时间查询真实安装 TF，过滤后保留时间戳、角度、坐标系和强度信息。"""
        try:
            transform = self.tf_buffer.lookup_transform(
                self.base_frame, scan.header.frame_id, Time.from_msg(scan.header.stamp))
        except TransformException as error:
            self.get_logger().warning(
                f'等待激光到车体的 TF，暂不输出扫描: {error}', throttle_duration_sec=5.0)
            return
        q = transform.transform.rotation
        t = transform.transform.translation
        filtered = copy.deepcopy(scan)
        filtered.ranges = mask_body_returns(
            scan.ranges, scan.angle_min, scan.angle_increment,
            (q.x, q.y, q.z, q.w), (t.x, t.y), self.bounds)
        self.publisher.publish(filtered)


def main():
    rclpy.init()
    node = ScanSelfFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
