"""
rlai_gazebo/launch/gazebo.launch.py

Main Gazebo Harmonic simulation entrypoint.

What this launches:
  1. gz sim  — Gazebo server + GUI (world chosen via 'world' arg)
  2. robot_state_publisher  — publishes /robot_description and static TF
  3. ros_gz_sim/create  — spawns rlai_bot into the running world (TimerAction 3 s delay)
  4. ros_gz_bridge/parameter_bridge  — bridges topics per ros_gz_bridge.yaml

Usage:
  ros2 launch rlai_gazebo gazebo.launch.py
  ros2 launch rlai_gazebo gazebo.launch.py world:=empty x:=1.0 y:=2.0
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    OpaqueFunction,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def _path_entries(path_value):
    """将资源搜索路径字符串拆分为非空路径列表。

    输入：path_value（str），使用系统路径分隔符 os.pathsep 分隔的路径字符串。
    输出：list[str]，按原顺序排列的非空路径；空字符串返回空列表。
    """
    return [entry for entry in path_value.split(os.pathsep) if entry]


def _unique_paths(paths):
    """过滤空路径并去重，保留每个路径首次出现的顺序。

    输入：paths，可迭代的路径字符串集合。
    输出：list[str]，不含空路径和重复字符串的路径列表。
    """
    unique = []
    seen = set()
    for path in paths:
        if path and path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def _find_world_in_paths(world, paths):
    """按搜索路径顺序查找指定名称的世界文件。

    输入：world（str），不含 .sdf 扩展名的世界名称；paths，搜索目录集合。
    输出：str 或 None。依次检查各目录下的 <world>.sdf 和
        worlds/<world>.sdf，返回首个存在的路径；均不存在时返回 None。
    """
    for path in paths:
        for candidate in (
            os.path.join(path, f"{world}.sdf"),
            os.path.join(path, "worlds", f"{world}.sdf"),
        ):
            if os.path.exists(candidate):
                return candidate
    return None


def _resolve_world_path(context):
    """解析启动参数 world，确定传给 Gazebo 的世界文件路径。

    输入：context（LaunchContext），用于读取 world 和 extra_gz_resource_path。
        同时读取当前进程的 GZ_SIM_RESOURCE_PATH 环境变量。
    输出：str。绝对路径、包含目录分隔符或以 .sdf 结尾的参数原样返回；
        纯世界名称先在额外资源路径、再在环境变量路径中查找，最后回退到
        rlai_gazebo 包的 worlds/<world>.sdf。回退路径不检查是否存在。
    """
    world = LaunchConfiguration("world").perform(context)
    if os.path.isabs(world):
        return world

    if os.sep in world or (os.altsep and os.altsep in world) or world.endswith(".sdf"):
        return world

    extra_paths = _path_entries(
        LaunchConfiguration("extra_gz_resource_path").perform(context)
    )
    existing_paths = _path_entries(os.environ.get("GZ_SIM_RESOURCE_PATH", ""))

    found_world = _find_world_in_paths(world, extra_paths)
    if found_world:
        return found_world

    found_world = _find_world_in_paths(world, existing_paths)
    if found_world:
        return found_world

    return os.path.join(
        get_package_share_directory("rlai_gazebo"),
        "worlds",
        f"{world}.sdf",
    )


def _launch_gz_sim(context, *, headless):
    """构建启动 Gazebo 并自动运行仿真的进程动作。

    输入：context（LaunchContext），用于解析世界路径；headless（bool），
        必须通过关键字传入，True 时仅启动服务器，False 时同时启动 GUI。
    输出：list[ExecuteProcess]，包含一个执行 gz sim -r 的动作；无界面模式
        额外传入 -s，进程日志输出到屏幕。动作由 launch 执行时启动进程。
    """
    cmd = ["gz", "sim", "-r"]
    if headless:
        cmd.append("-s")
    cmd.append(_resolve_world_path(context))

    return [ExecuteProcess(cmd=cmd, output="screen")]


def _gazebo_resource_path(context):
    """合并 Gazebo 模型、世界和网格资源的搜索路径。

    输入：context（LaunchContext），用于读取 extra_gz_resource_path；
        同时读取当前进程的 GZ_SIM_RESOURCE_PATH 和相关包的共享目录。
    输出：str，按内置资源路径、已有环境变量路径、额外资源路径的顺序合并，
        过滤空项并按字符串去重后，以 os.pathsep 连接的环境变量值。
    """
    gazebo_share = get_package_share_directory("rlai_gazebo")
    meshes_share = get_package_share_directory("rlai_meshes")
    bundled_paths = [
        os.path.join(gazebo_share, "models"),
        gazebo_share,
        meshes_share,
        # model://rlai_meshes/meshes/... 从包的上一级开始查找。
        os.path.dirname(meshes_share),
    ]
    existing_paths = _path_entries(os.environ.get("GZ_SIM_RESOURCE_PATH", ""))
    extra_paths = _path_entries(
        LaunchConfiguration("extra_gz_resource_path").perform(context)
    )

    return os.pathsep.join(
        _unique_paths(bundled_paths + existing_paths + extra_paths)
    )


def generate_launch_description():
    """构建完整的 Gazebo 机器人仿真启动描述，供 ros2 launch 调用。

    输入：无函数参数。运行时通过启动参数配置世界、机器人初始位置和朝向、
        机器人命名空间、传感器开关、RViz 开关、无界面模式及额外资源路径。
    输出：LaunchDescription，包含参数声明、资源环境变量设置、Gazebo 进程、
        robot_state_publisher、延迟 3 秒的机器人生成动作、ROS/Gazebo 话题桥、
        延迟 5 秒的控制器启动动作，以及按 rviz_enabled 启用的 RViz 节点。
        此函数仅构建启动描述，具体动作由 launch 系统执行。
    """
    pkg_gz = FindPackageShare("rlai_gazebo")
    pkg_desc = FindPackageShare("rlai_description")
    pkg_control = FindPackageShare("rlai_control")

    # Launch arguments
    declared_args = [
        DeclareLaunchArgument(
            "world",
            default_value="small_warehouse",
            description="World name (must match a .sdf file in rlai_gazebo/worlds/)",
        ),
        DeclareLaunchArgument("x",   default_value="0.0",
                              description="Robot spawn X position [m]"),
        DeclareLaunchArgument("y",   default_value="0.0",
                              description="Robot spawn Y position [m]"),
        DeclareLaunchArgument("z",   default_value="0.1",
                              description="Robot spawn Z position [m]"),
        DeclareLaunchArgument("yaw", default_value="0.0",
                              description="Robot spawn yaw angle [rad]"),
        DeclareLaunchArgument(
            "robot_namespace",
            default_value="",
            description="ROS namespace for all robot nodes (empty = no namespace)",
        ),
        # Sensor toggles must stay in sync with robot.urdf.xacro arguments.
        DeclareLaunchArgument("lidar_2d_enabled",     default_value="true"),
        DeclareLaunchArgument("lidar_3d_enabled",     default_value="false"),
        DeclareLaunchArgument("depth_camera_enabled", default_value="true"),
        DeclareLaunchArgument("stereo_camera_enabled", default_value="false"),
        DeclareLaunchArgument("imu_enabled",          default_value="true"),
        DeclareLaunchArgument("gps_enabled",          default_value="false"),
        DeclareLaunchArgument(
            "rviz_enabled",
            default_value="false",
            description="Launch RViz2 with the gazebo_live.rviz config",
        ),
        DeclareLaunchArgument(
            "headless",
            default_value="false",
            description="Run Gazebo server-only (no GUI). Physics and sensors remain active.",
        ),
        DeclareLaunchArgument(
            "extra_gz_resource_path",
            default_value="",
            description="Additional Gazebo resource path entries for external worlds and models.",
        ),
    ]

    robot_description = ParameterValue(
        Command([
            FindExecutable(name="xacro"), " ",
            PathJoinSubstitution([pkg_desc, "urdf", "robot.urdf.xacro"]),
            " sim_mode:=gazebo",
            " robot_namespace:=",      LaunchConfiguration("robot_namespace"),
            " lidar_2d_enabled:=",     LaunchConfiguration("lidar_2d_enabled"),
            " lidar_3d_enabled:=",     LaunchConfiguration("lidar_3d_enabled"),
            " depth_camera_enabled:=", LaunchConfiguration("depth_camera_enabled"),
            " stereo_camera_enabled:=", LaunchConfiguration("stereo_camera_enabled"),
            " imu_enabled:=",          LaunchConfiguration("imu_enabled"),
            " gps_enabled:=",          LaunchConfiguration("gps_enabled"),
        ]),
        value_type=str,
    )

    gz_resource_path = OpaqueFunction(
        function=lambda context: [
            SetEnvironmentVariable(
                name="GZ_SIM_RESOURCE_PATH",
                value=_gazebo_resource_path(context),
            )
        ],
    )

    gz_sim_gui = OpaqueFunction(
        function=lambda context: _launch_gz_sim(context, headless=False),
        condition=UnlessCondition(LaunchConfiguration("headless")),
    )
    gz_sim_headless = OpaqueFunction(
        function=lambda context: _launch_gz_sim(context, headless=True),
        condition=IfCondition(LaunchConfiguration("headless")),
    )

    # Node 用于描述要启动的 ROS 节点：package 指定所属包，executable 指定可执行程序，
    # name 指定运行时节点名，output="screen" 将日志输出到终端。
    # parameters 是节点参数，arguments 是传给可执行程序的命令行参数。
    # 这里只创建启动动作，加入 LaunchDescription 后才会由 launch 系统执行。

    # 启动机器人状态发布节点：读取 URDF 和 /joint_states，计算各连杆之间的坐标变换。
    # 输出：固定关节的变换发布到 /tf_static，可动关节的变换随关节状态发布到 /tf；
    # 同时发布 /robot_description，供后面的 Gazebo 生成节点获取机器人模型。
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{
            # 输入：由 xacro 生成的 URDF XML 字符串，描述机器人连杆、关节和模型。
            "robot_description": robot_description,
            # 使用 /clock 提供的仿真时间，与 Gazebo 中的仿真保持时间一致。
            "use_sim_time": True,
        }],
    )

    # 延迟执行机器人生成动作，为 Gazebo 世界启动和机器人描述发布预留时间。
    # TimerAction 使用固定延迟，不会检查 Gazebo 是否已经就绪。
    spawn_robot = TimerAction(
        period=3.0,
        actions=[
            # 调用 ros_gz_sim 包的 create 程序，请求在 Gazebo 世界中创建机器人实体。
            # 输入：机器人描述话题、实体名称、初始位置和朝向；结果：世界中出现 rlai_bot。
            Node(
                package="ros_gz_sim",
                executable="create",
                name="spawn_rlai_bot",
                output="screen",
                arguments=[
                    # 从该 ROS 话题读取 URDF 模型；-name 指定 Gazebo 实体名称。
                    "-topic", "robot_description",
                    "-name",  "rlai_bot",
                    # 初始位置，单位为米；值来自同名启动参数。
                    "-x",  LaunchConfiguration("x"),
                    "-y",  LaunchConfiguration("y"),
                    "-z",  LaunchConfiguration("z"),
                    # 初始偏航角，单位为弧度；注意 create 的选项是大写 -Y。
                    "-Y",  LaunchConfiguration("yaw"),
                ],
            )
        ],
    )

    # 启动 ROS 与 Gazebo 的话题桥，按 YAML 配置转换消息类型并转发话题。
    # 当前配置将 Gazebo 的时钟、真实位姿里程计和传感器数据转发到 ROS。
    # /joint_states 和速度控制由 ros2_control 负责，不通过这里的桥转发。
    ros_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="ros_gz_bridge",
        output="screen",
        parameters=[{
            # 配置文件定义两侧话题名、消息类型以及转发方向。
            "config_file": PathJoinSubstitution(
                [pkg_gz, "config", "ros_gz_bridge.yaml"]
            ),
            "use_sim_time": True,
        }],
    )

    # 延迟 5 秒启动控制模块，为机器人加载和 Gazebo 的 ros2_control 插件初始化预留时间。
    # 这是固定延迟，不是对硬件接口就绪状态的检测。
    # control.launch.py 加载关节状态广播器、差速控制器、速度平滑器及其生命周期管理器。
    control_bringup = TimerAction(
        period=5.0,
        actions=[
            # 包含另一个启动文件，由它创建控制相关节点和控制器加载进程。
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution(
                        [pkg_control, "launch", "control.launch.py"]
                    )
                ),
                # 向子启动文件传入启动参数，让控制模块使用仿真时间。
                launch_arguments={"use_sim_time": "true"}.items(),
            )
        ],
    )

    # 启动 RViz2 可视化界面，用于查看机器人模型、坐标变换和传感器数据。
    # 输入：RViz 显示配置及配置中订阅的 ROS 话题；结果：打开可视化窗口。
    rviz2 = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        # 仅当启动参数 rviz_enabled 为 true 时启动该节点。
        condition=IfCondition(LaunchConfiguration("rviz_enabled")),
        arguments=[
            # -d 指定启动时加载的 RViz 配置文件。
            "-d",
            PathJoinSubstitution([pkg_gz, "rviz", "gazebo_live.rviz"]),
        ],
        parameters=[{"use_sim_time": True}],
    )

    # 先声明启动参数，再交给 launch 执行资源设置、Gazebo 和各节点的启动动作。
    # 节点启动后独立运行；列表顺序不保证前一个进程就绪后才启动下一个。
    return LaunchDescription(
        declared_args + [
            gz_resource_path,
            gz_sim_gui,
            gz_sim_headless,
            robot_state_publisher,
            spawn_robot,
            ros_gz_bridge,
            control_bringup,
            rviz2,
        ]
    )
