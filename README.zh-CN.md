<p align="center">
  <img src="docs/assets/rbot-logo.png" alt="rbot 自主移动机器人标志" width="360">
</p>

<h1 align="center">rbot</h1>

<p align="center">
  面向 ROS 2 Jazzy 和 Gazebo Harmonic 的开源自主移动机器人仿真栈。
</p>

<p align="center">
  <a href="LICENSE"><img alt="许可证：Apache 2.0" src="https://img.shields.io/badge/License-Apache%202.0-blue.svg"></a>
  <img alt="ROS 2 Jazzy" src="https://img.shields.io/badge/ROS%202-Jazzy-22314E.svg">
  <img alt="Gazebo Harmonic" src="https://img.shields.io/badge/Gazebo-Harmonic-F58113.svg">
  <img alt="Ubuntu 24.04" src="https://img.shields.io/badge/Ubuntu-24.04-E95420.svg">
</p>

---

<p align="center">
  <a href="https://youtu.be/B-d64c-2Mw0">
    <img src="https://img.youtube.com/vi/B-d64c-2Mw0/maxresdefault.jpg" alt="观看 rbot 开源 ROS 2 AMR 仿真演示" width="720">
  </a>
</p>

<p align="center">
  <a href="https://youtu.be/B-d64c-2Mw0">观看演示视频</a>
</p>

---

## 项目概览

`rbot` 是一个以仿真为优先的自主移动机器人（AMR）参考栈，面向 ROS 2 Jazzy 和 Gazebo Harmonic。它将机器人描述、Gazebo 仿真、`ros2_control`、遥操作、传感器仿真、定位、建图和 Nav2 导航整合到同一个 ROS 2 工作空间中。

本项目适合需要运行、研究和改造实用 AMR 基线的 ROS 用户、学生和机器人团队。它的价值在于完整的集成：现代 ROS 2 工作空间、以 Docker 为优先的工作流、现代化的 Nav2 配置，以及覆盖从建图到导航完整流程的文档。

Gazebo Harmonic 是当前支持的仿真器。项目中已包含 Isaac Sim 软件包脚手架，用于未来集成。

---

## 项目提供的能力

`rbot` 将 AMR 仿真流程整合到一个工作空间中，包括 Gazebo Harmonic 机器人模型、ROS-Gazebo 桥接、`ros2_control`、遥操作、传感器话题、EKF 定位、SLAM Toolbox 建图、AMCL 和 Nav2。

| 领域 | 当前支持 |
| --- | --- |
| 仿真 | Gazebo Harmonic 演示与基准场景、URDF/Xacro 机器人描述、生成的网格资源，以及可配置的启动参数。 |
| 控制与遥操作 | `ros2_control`、差速驱动控制器、手柄/键盘遥操作，以及便捷的软件急停服务。 |
| 传感器与感知扩展 | 2D 激光雷达、IMU、深度相机、双目相机、GPS，以及可选的 3D 激光雷达桥接路径。 |
| 建图与定位 | SLAM Toolbox、AMCL、EKF、保存地图工作流和示例地图。 |
| 导航 | Nav2 启动文件、MPPI 控制器、SMAC Hybrid-A* 规划器、行为树和简单的动作客户端。 |
| 开发工作流 | Docker、Docker Compose、VS Code Dev Container、原生 Ubuntu 24.04 配置、CI 和测试。 |
| Isaac Sim | 面向未来集成的软件包脚手架。目前支持的仿真器是 Gazebo。 |

---

## 建图与导航快速流程

以下命令用于完成建图和自主导航流程。

前置条件：需要支持 Compose 的 Docker。若要在 Linux 上使用 RViz，请确保已启用 X11 转发。

1. 使用 RViz 启动建图：

   ```bash
   bash scripts/run_sim.sh --headless --rviz-mapping
   ```

   - 使用遥操作驱动机器人遍历地图（见下一条命令）。
   - 关于如何保存地图，请参阅[使用 SLAM Toolbox 建图](#使用-slam-toolbox-建图)。

2. 启动遥操作：

   ```bash
   docker compose -f docker/docker-compose.yml run --rm teleop
   ```

   - 使用手柄或键盘控制机器人覆盖开阔通道、拐角和门口等区域。

3. 使用 RViz 启动导航：

   ```bash
   bash scripts/run_sim.sh --headless --rviz-nav --map /ros2_ws/maps/my_map.yaml
   ```

   - 在 RViz2 顶部工具栏中使用 **Set Initial Pose**，使 AMCL 与机器人位姿对齐。
   - 使用顶部工具栏中的 **Nav2 Goal** 向目标位姿发送导航目标。

---

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 目标操作系统 | Ubuntu 24.04 LTS |
| ROS 发行版 | ROS 2 Jazzy Jalisco |
| 主要仿真器 | Gazebo Harmonic |
| 中间件 | CycloneDDS |
| 机器人模型 | URDF/Xacro + 生成的网格资源 |
| 控制 | `ros2_control`、`diff_drive_controller`、`joint_state_broadcaster` |
| 遥操作 | `joy_linux`、`teleop_twist_joy`、便捷的软件急停 |
| 感知 | 2D 激光雷达、可选的 3D 点云过滤、双目/深度处理 |
| 定位 | `robot_localization` EKF、AMCL |
| 建图 | SLAM Toolbox 在线异步配置和长期建图配置 |
| 导航 | 使用 MPPI 控制器和 SMAC Hybrid-A* 规划器的 Nav2 |
| 容器 | Docker、Docker Compose、VS Code Dev Container |

---

## 仓库结构

```text
rbot/
├── .devcontainer/        # VS Code Dev Container 配置
├── .github/workflows/    # CI 构建、检查和测试工作流
├── docker/               # Dockerfile、Compose 服务和入口脚本
├── docs/                 # 架构说明、传感器文档和教程
├── maps/                 # 示例栅格地图及元数据
├── scripts/              # 构建、依赖、仿真和网格资源辅助脚本
└── src/
    ├── bringup/          # 顶层仿真启动编排
    ├── control/          # ros2_control 和遥操作软件包
    ├── localization/     # EKF 和 AMCL 启动/配置软件包
    ├── mapping/          # SLAM Toolbox 启动/配置软件包
    ├── navigation/       # Nav2 启动文件、参数、行为树和客户端
    ├── perception/       # 激光雷达和相机处理软件包
    ├── robot/            # 机器人描述和网格资源软件包
    ├── simulation/       # Gazebo 软件包和 Isaac 脚手架
    └── utils/            # 共享工具软件包占位
```

---

## 快速开始：Docker

Docker 是首次使用时推荐的方式，因为它可以隔离 ROS、Gazebo 和系统依赖。

### 1. 安装主机依赖

安装支持 Compose 的 Docker。若要在 Linux 上运行图形化仿真，请确保已启用 X11 转发。

### 2. 构建并运行 Gazebo 栈

```bash
bash scripts/run_sim.sh
```

常用变体：

```bash
bash scripts/run_sim.sh --headless
bash scripts/run_sim.sh --rviz
bash scripts/run_sim.sh --rviz-nav
bash scripts/run_sim.sh --headless --rviz-nav --map /ros2_ws/maps/my_map.yaml
bash scripts/run_sim.sh --headless --rviz-mapping
bash scripts/run_sim.sh --headless world:=large_warehouse gps_enabled:=true
```

该脚本会启动 `docker/docker-compose.yml` 中的服务，并在容器内启动仿真栈。当 AMCL/Nav2 需要基于指定地图进行定位时，请将 `--map` 与 `--rviz-nav` 一起使用；地图 YAML 文件会挂载到 `/ros2_ws/maps/` 下。

脚本标志之后的其他参数会转发给仿真启动服务。请将它们作为不含空格的标准 ROS 启动参数传入，例如 `name:=value`。

内置 Gazebo 场景包括默认仓库，以及更丰富的演示和基准场景：

```bash
bash scripts/run_sim.sh world:=demo_warehouse_visual
bash scripts/run_sim.sh world:=benchmark_warehouse_easy
bash scripts/run_sim.sh world:=benchmark_warehouse_medium
bash scripts/run_sim.sh world:=benchmark_warehouse_hard
```

使用 `--rviz-mapping` 时也可以传入相同的 `world:=...` 参数，在不同场景中创建地图。

### 3. 另一种 Docker 辅助脚本

```bash
zsh scripts/sim_docker.sh
zsh scripts/sim_docker.sh --headless
zsh scripts/sim_docker.sh --shell
zsh scripts/sim_docker.sh world:=large_warehouse
```

当你需要更直接地控制 `docker run`，或需要在仿真镜像中打开交互式 Shell 时，可以使用该辅助脚本。

---

## 快速开始：原生 Ubuntu 24.04

如果你已经在 ROS 2 Jazzy 环境中工作，原生安装方式会比较方便。

```bash
bash scripts/install_deps.sh
bash scripts/build.sh
source install/setup.bash
ros2 launch rlai_bringup simulation.launch.py
```

启动指定场景：

```bash
ros2 launch rlai_bringup simulation.launch.py world:=small_warehouse
```

无头模式运行 Gazebo：

```bash
ros2 launch rlai_bringup simulation.launch.py headless:=true
```

---

## 常见工作流

### 启动带默认定位的仿真

```bash
ros2 launch rlai_bringup simulation.launch.py localization_enabled:=true
```

该命令会启动 Gazebo、机器人描述发布、ros2_control 和 EKF 定位。

### 启用手柄遥操作

```bash
ros2 launch rlai_bringup simulation.launch.py teleop_enabled:=true
```

手柄配置位于：

```text
src/control/rlai_teleop/config/joystick.yaml
```

便捷的软件急停服务：

```bash
ros2 service call /e_stop std_srvs/srv/Trigger {}
```

该服务在启用期间会发布零速度指令。

### 使用 SLAM Toolbox 建图

```bash
ros2 launch rlai_bringup simulation.launch.py \
  mapping_enabled:=true \
  slam_rviz_enabled:=true
```

当覆盖范围满足要求后，从建图容器中保存地图。通过快速流程启动时，建图容器名称为 `rlai_sim_mapping`：

```bash
docker exec -it rlai_sim_mapping ros2 run nav2_map_server map_saver_cli -f /ros2_ws/maps/my_map
```

不要同时启用 `mapping_enabled:=true` 和 `use_amcl:=true`，因为两者都会发布 `map -> odom`。

### 使用保存的地图运行 AMCL

```bash
ros2 launch rlai_bringup simulation.launch.py \
  use_amcl:=true \
  map_yaml_file:=/absolute/path/to/map.yaml
```

示例地图存放在 `maps/` 目录中。

### 直接启动 Nav2

```bash
ros2 launch rlai_navigation navigation.launch.py \
  map:=/absolute/path/to/map.yaml
```

当定位已经运行、你希望专注于 Nav2 行为时，可以使用此命令。

### 以编程方式发送导航目标

```bash
ros2 run rlai_navigation nav_client --ros-args \
  -p x:=3.0 \
  -p y:=2.0 \
  -p yaw:=0.0
```

巡逻模式：

```bash
ros2 run rlai_navigation nav_client --ros-args -p mode:=patrol
```

---

## 软件包索引

| 软件包 | 类型 | 用途 |
| --- | --- | --- |
| `rlai_description` | `ament_cmake` | 机器人 URDF/Xacro、传感器安装座、载荷平台和 RViz 配置 |
| `rlai_meshes` | `ament_cmake` | 机器人描述使用的网格资源 |
| `rlai_gazebo` | `ament_cmake` | Gazebo 场景、启动文件和 ROS-Gazebo 桥接配置 |
| `rlai_isaac` | `ament_python` | 计划中的 Isaac Sim 集成脚手架软件包 |
| `rlai_control` | `ament_cmake` | `ros2_control` 控制器配置和启动文件 |
| `rlai_teleop` | `ament_python` | 手柄遥操作和便捷的软件急停节点 |
| `rlai_lidar_processing` | `ament_cmake` | 可选的 3D 点云高度过滤和体素下采样 |
| `rlai_camera_processing` | `ament_cmake` | 双目视差和深度点云处理启动/配置 |
| `rlai_localization` | `ament_python` | IMU 过滤、EKF 和 AMCL 启动/配置 |
| `rlai_mapping` | `ament_python` | SLAM Toolbox 建图和地图服务器启动/配置 |
| `rlai_navigation` | `ament_python` | Nav2 参数、行为树、启动文件和动作客户端 |
| `rlai_bringup` | `ament_python` | 顶层仿真启动和栈编排 |
| `rlai_utils` | `ament_python` | 共享工具软件包脚手架 |

---

## 架构说明

### TF 所有权

该栈采用标准移动机器人 TF 链：

```text
map -> odom -> base_footprint -> base_link -> sensor frames
```

所有权划分如下：

- EKF 发布 `odom -> base_footprint`。
- AMCL 或 SLAM Toolbox 发布 `map -> odom`。
- Robot State Publisher 发布 `base_footprint -> base_link` 和传感器坐标系。

避免启用多个发布同一变换的节点。

### 速度指令路径

```text
teleop / Nav2 -> /cmd_vel -> velocity_smoother -> /diff_drive_controller/cmd_vel
```

由于 Jazzy 版本的 `diff_drive_controller` 需要带时间戳的速度输入，该栈使用 `TwistStamped` 指令。软件急停节点也会向 `/cmd_vel` 发布指令；这是用于仿真和开发的便捷机制。

### 仿真桥接

Gazebo 话题通过以下配置进行桥接：

```text
src/simulation/rlai_gazebo/config/ros_gz_bridge.yaml
```

`/joint_states` 有意不进行桥接，因为 `joint_state_broadcaster` 负责该 ROS 话题。

---

## 参考资料与相关项目

`rbot` 建立在成熟的 ROS 2 项目和示例之上：

- [ROS 2 Jazzy 文档](https://docs.ros.org/en/jazzy/)
- [Gazebo Harmonic 文档](https://gazebosim.org/docs/harmonic/)
- [Nav2 文档与教程](https://docs.nav2.org/)
- [SLAM Toolbox](https://github.com/SteveMacenski/slam_toolbox)
- [`robot_localization`](https://github.com/cra-ros-pkg/robot_localization)
- [`ros2_control`](https://control.ros.org/jazzy/index.html)
- [BCR Bot](https://github.com/blackcoffeerobotics/bcr_bot)
- [Linorobot2](https://github.com/linorobot/linorobot2)
- [ROSNav](https://github.com/ApolloAuto/rosnav)

---

## 开发

### 构建

```bash
bash scripts/build.sh
```

或手动构建：

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
```

### 测试

```bash
source install/setup.bash
colcon test --event-handlers console_cohesion+ --return-code-on-test-failure
colcon test-result --verbose
```

### 检查 Python 软件包

```bash
flake8 src --max-line-length=100 --extend-ignore=E203 --exclude=__pycache__
```

### 快速验证启动文件语法

```bash
python3 -m compileall -q src scripts
```

---

## 故障排查

### Docker 中 Gazebo 卡顿或使用 CPU 渲染

NVIDIA 显卡需要在宿主机安装 NVIDIA 驱动和 Container Toolkit，仅挂载
`/dev/dri` 不保证容器能够使用 NVIDIA 图形加速。驱动已正常工作时，先停止
所有容器，再执行一次：

```bash
sudo bash scripts/setup_nvidia_docker.sh
```

该脚本从 NVIDIA 官方软件源安装工具包、注册 Docker 运行时并重启 Docker。
随后启动仿真（无须重新构建镜像）：

```bash
bash scripts/run_sim.sh --nvidia
bash scripts/run_sim.sh --nvidia --rviz
```

启动脚本默认自动检测 NVIDIA 运行时；`--nvidia` 要求启用该运行时，缺失时
会报错。`--no-nvidia` 使用原有 Intel/AMD 配置。NVIDIA 配置位于
`docker/docker-compose.nvidia.yml`，同时覆盖 Gazebo GUI、传感器渲染及 RViz；
默认选用 GPU 0，可用 `RLAI_NVIDIA_DEVICE` 指定其他 GPU 的索引或 UUID。

直接使用 Compose 时也要包含 NVIDIA 配置：

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.nvidia.yml up sim
```

验证实际渲染器：

```bash
docker exec rlai_sim grep -a GL_RENDERER /root/.gz/rendering/ogre2.log
```

应显示 NVIDIA 显卡名称。`llvmpipe` 表示 CPU 软件渲染；仅能运行
`nvidia-smi` 不能证明 Gazebo 正在使用 GPU 渲染。物理仿真仍由 CPU 执行。

### Docker 中无法打开 Gazebo 图形界面

允许本地 Docker 容器连接 X Server：

```bash
xhost +local:docker
```

然后重新运行仿真脚本。

### ROS 命令找不到软件包

构建后加载工作空间：

```bash
source install/setup.bash
```

如果使用 Docker，请进入已构建的容器，并在容器内加载已安装的工作空间。

### Nav2 或 AMCL 无法配置

启用 `use_amcl:=true` 时，请确认提供了有效的地图文件：

```bash
ros2 launch rlai_bringup simulation.launch.py \
  use_amcl:=true \
  map_yaml_file:=/absolute/path/to/map.yaml
```

### TF 冲突或定位不稳定

确保每个变换只由一个组件发布：

- EKF：`odom -> base_footprint`
- AMCL 或 SLAM Toolbox：`map -> odom`
- Robot State Publisher：机器人连杆和传感器坐标系

除非你有意修改 TF 所有权，否则不要同时运行 AMCL 和 SLAM 建图。

### Docker 构建速度较慢

Gazebo 镜像会安装 ROS、Gazebo、Nav2、SLAM、感知和控制依赖。首次构建可能需要几分钟；后续构建应能复用 Docker 层。

---

## 路线图

未来扩展方向：

- Isaac Sim 集成
- 扩展基准测试和自动化场景测试
- 增加仓库、室外和混合布局环境
- 增加更多感知和自主能力示例

---

## 参与贡献

欢迎贡献代码。请先阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)，了解开发流程、代码规范和 Pull Request 指引。

适合作为首次贡献的内容包括：

- 改进安装说明或故障排查文档。
- 添加可复现的仿真场景。
- 基于前后对比证据调优导航、定位或建图配置。
- 为启动文件、URDF/Xacro 和 Gazebo 场景添加测试或验证脚本。

---

## 许可证

本项目采用 [Apache License 2.0](LICENSE) 许可证。

版权所有 2026 Robolabs AI（RLXAI ROBOLABSAI PRIVATE LIMITED）。
