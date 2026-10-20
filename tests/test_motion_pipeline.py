"""在隔离 ROS 域中启动真实 ROS 节点，验证传感器估计与打滑修正。

运行前 source ROS 与工作空间；设置 RBOT_ROS_INTEGRATION=1、ROS_DOMAIN_ID=117。
测试仅发布合成观测，不连接 Gazebo。应在独立 Docker 网络中运行。
"""

import math
import os
from pathlib import Path
import subprocess
import time

import pytest


INTEGRATION_ENABLED = os.environ.get("RBOT_ROS_INTEGRATION") == "1"
pytestmark = pytest.mark.skipif(
    not INTEGRATION_ENABLED, reason="需要显式启用隔离 ROS 集成测试")
if INTEGRATION_ENABLED:
    if int(os.environ.get("ROS_DOMAIN_ID", "0")) < 100:
        raise RuntimeError("请使用独立 Docker 网络和专用 ROS_DOMAIN_ID >= 100")
    rclpy = pytest.importorskip("rclpy")
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import Imu, LaserScan
    from geometry_msgs.msg import TransformStamped
    from lifecycle_msgs.srv import ChangeState
    from rclpy.qos import qos_profile_sensor_data
    from tf2_ros import Buffer, TransformBroadcaster, StaticTransformBroadcaster, TransformListener


ROOT = Path(__file__).resolve().parents[1]
EKF = ROOT / "src/localization/rlai_localization/config/ekf.yaml"
SLAM = ROOT / "src/mapping/rlai_mapping/config/slam_toolbox_online_async.yaml"


@pytest.fixture
def pipeline(tmp_path):
    rclpy.init()
    node = rclpy.create_node("motion_pipeline_test")
    processes = []
    logs = []

    def launch(command, params, overrides):
        log = (tmp_path / f"node_{len(logs)}.log").open("w+")
        logs.append(log)
        env = dict(os.environ)
        env['PYTHONPATH'] = str(ROOT / 'src/utils/rlai_utils') + os.pathsep + env.get('PYTHONPATH', '')
        processes.append(subprocess.Popen(command + [
            "--ros-args", "--params-file", str(params),
            "-p", "use_sim_time:=false", *overrides,
        ], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True))

    def start(package, executable, params, *overrides):
        launch(['ros2', 'run', package, executable], params, overrides)

    def start_filter():
        launch(['python3', '-m', 'rlai_utils.scan_self_filter'], SLAM, [])

    try:
        yield node, start, start_filter
    finally:
        import signal
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        for log in logs:
            log.close()
        node.destroy_node()
        rclpy.shutdown()


def test_ekf_ignores_encoder_pose_jump_and_unused_acceleration(pipeline):
    node, start, _ = pipeline
    start("robot_localization", "ekf_node", EKF,
          "-r", "__node:=ekf_node", "-p", "publish_tf:=false")
    wheels = node.create_publisher(Odometry, "/diff_drive_controller/odom", 10)
    imu = node.create_publisher(Imu, "/imu/data", 10)
    output = []
    node.create_subscription(
        Odometry, "/odometry/filtered", lambda msg: output.append(msg), 10)

    deadline = time.monotonic() + 3.5
    next_pub = 0
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.01)
        now = time.monotonic()
        if now < next_pub:
            continue
        next_pub = now + 0.02
        stamp = node.get_clock().now().to_msg()
        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_footprint"
        odom.pose.pose.position.x = 100.0
        odom.pose.pose.position.y = 100.0
        odom.pose.pose.position.z = 10.0
        odom.pose.pose.orientation.w = 1.0
        for index in (0, 7, 14, 21, 28, 35):
            odom.pose.covariance[index] = 0.001
            odom.twist.covariance[index] = 0.001
        wheels.publish(odom)
        msg = Imu()
        msg.header.stamp = stamp
        msg.header.frame_id = "base_footprint"
        msg.orientation.w = 1.0
        msg.linear_acceleration.x = 1.0
        msg.linear_acceleration.y = 1.0
        msg.linear_acceleration.z = 9.81
        for index in (0, 4, 8):
            msg.angular_velocity_covariance[index] = 0.0001
            msg.linear_acceleration_covariance[index] = 0.001
        imu.publish(msg)
    assert output, "EKF 未发布估计结果"
    for msg in output[-10:]:
        p = msg.pose.pose.position
        assert math.hypot(p.x, p.y) < 0.02
        assert abs(p.z) < 1e-6
        assert abs(msg.twist.twist.linear.x) < 0.01


def test_stationary_laser_corrects_continuously_slipping_odometry(pipeline):
    """真实 SLAM + 过滤节点：车体静止，编码器虚增超过 1.5 m，地图位置仍稳定。"""
    node, start, start_filter = pipeline
    start_filter()
    start('slam_toolbox', 'async_slam_toolbox_node', SLAM,
          '-r', '__node:=slam_toolbox', '-p', 'use_lifecycle_manager:=false')
    client = node.create_client(ChangeState, '/slam_toolbox/change_state')
    assert client.wait_for_service(timeout_sec=10), 'SLAM 未启动'
    for transition in (1, 3):  # configure → activate
        request = ChangeState.Request()
        request.transition.id = transition
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=10)
        assert future.done() and future.result().success

    broadcaster = TransformBroadcaster(node)
    static = StaticTransformBroadcaster(node)
    mounting = TransformStamped()
    mounting.header.stamp = node.get_clock().now().to_msg()
    mounting.header.frame_id = 'base_footprint'
    mounting.child_frame_id = 'laser'
    mounting.transform.translation.x = 0.2
    mounting.transform.rotation.w = 1.0
    static.sendTransform(mounting)
    buffer = Buffer()
    listener = TransformListener(buffer, node)
    raw = node.create_publisher(LaserScan, '/scan', qos_profile_sensor_data)
    filtered = []
    node.create_subscription(LaserScan, '/scan_filtered', filtered.append, qos_profile_sensor_data)
    # 固定房间 x=[-5,5], y=[-3,3]；雷达 x=0.2。
    scan = LaserScan()
    scan.header.frame_id = 'laser'
    scan.angle_min = -math.pi
    scan.angle_increment = 2 * math.pi / 720
    scan.angle_max = scan.angle_min + 719 * scan.angle_increment
    scan.range_min, scan.range_max = 0.12, 25.0
    ranges = []
    for i in range(720):
        angle = scan.angle_min + i * scan.angle_increment
        c, s = math.cos(angle), math.sin(angle)
        dx = (4.8 if c >= 0 else 5.2) / max(abs(c), 1e-9)
        dy = 3.0 / max(abs(s), 1e-9)
        ranges.append(min(dx, dy))
    ranges[0] = 0.4  # 向后照到车体内部，须过滤
    scan.ranges = ranges
    estimates = []
    started = time.monotonic()
    next_scan = 0
    while (elapsed := time.monotonic() - started) < 10.0:
        stamp = node.get_clock().now().to_msg()
        transform = TransformStamped()
        transform.header.stamp = stamp
        transform.header.frame_id = 'odom'
        transform.child_frame_id = 'base_footprint'
        transform.transform.rotation.w = 1.0
        transform.transform.translation.x = max(0, elapsed - 1) * 0.2
        broadcaster.sendTransform(transform)
        if elapsed >= next_scan:
            scan.header.stamp = stamp
            raw.publish(scan)
            next_scan = elapsed + 1 / 15
        rclpy.spin_once(node, timeout_sec=0.01)
        if elapsed > 8:
            try:
                pose = buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            except Exception:
                continue
            # 要求是近期 TF，不能以旧位姿冒充修正成功。
            age = (node.get_clock().now().nanoseconds -
                   rclpy.time.Time.from_msg(pose.header.stamp).nanoseconds) / 1e9
            if abs(age) < 0.3:
                p = pose.transform.translation
                estimates.append(math.hypot(p.x, p.y))
    assert transform.transform.translation.x > 1.5
    assert len(filtered) > 60 and math.isnan(filtered[-1].ranges[0])
    assert filtered[-1].ranges[360] == pytest.approx(4.8)
    assert len(estimates) > 20, '缺少新鲜的地图位置'
    assert max(estimates) < 0.15, '静止激光未能纠正持续虚增的里程计'
