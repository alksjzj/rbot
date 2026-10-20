# 碰撞打滑时的传感器建图修复

## 目标和数据来源

可以继续用原来的键盘操作和速度建图。碰撞、滑动和车体停止由 Gazebo 的物理引擎处理。定位和建图只读取模拟传感器，不读取仿真器的真实位置，也不加入自动停车节点。

```text
轮子关节位置反馈 → diff_drive_controller → 轮式里程计 ─┐
IMU → /imu/data ───────────────────────────────────┴→ EKF → odom→base_footprint
激光 → /scan → 车体回波过滤 → /scan_filtered ──────────→ SLAM → map→odom + 地图
```

控制器仍为 `open_loop: false`、`position_feedback: true`，由轮子实际转过的角度计算里程计。没有根据速度指令伪造里程计。

**轮子转动不等于车体移动。** 车体顶住墙时，轮子可能继续转；编码器累计距离本身符合传感器的工作方式。IMU 陀螺仪也无法独立判断平移打滑。因此 EKF 的局部 `odom` 可以漂移，SLAM 必须通过激光观察环境，修正 `map→odom`。地图中的位置取整条 `map→odom→base_footprint` 变换，不能只看 `/odometry/filtered` 的坐标数字。

## 实际发现与修改

### 1. 去除激光看到自身车体的回波

原始激光中发现了车体范围内的回波。这些点跟随车体，不能作为环境定位依据。

新增 `src/utils/rlai_utils/rlai_utils/scan_self_filter.py`。每束激光使用扫描时间戳对应的安装 TF，转换到 `base_footprint`；只屏蔽车体矩形范围内的端点，设为 NaN。范围与当前导航轮廓一致：x 为 ±0.28 m，y 为 ±0.23 m，包含少量轮廓余量。车体外的近距离障碍物仍保留。

原始 `/scan` 保留；建图和建图 RViz 使用 `/scan_filtered`。角度、时间戳、坐标系、外部距离和强度保持原样。修改车体尺寸后应同步调整过滤边界。

### 2. 让扫描匹配及时修正打滑误差

在 `src/mapping/rlai_mapping/config/slam_toolbox_online_async.yaml` 中：

| 参数 | 修改后的值 | 作用 |
|---|---:|---|
| `minimum_time_interval` | 0.1 s | 缩短匹配间隔，避免错误里程计初值积累过大 |
| `minimum_travel_distance` | 0.05 m | 降低进行扫描匹配的位移门槛 |
| `minimum_travel_heading` | 0.05 rad | 降低转向匹配门槛 |
| `correlation_search_space_dimension` | 1.0 m | 总搜索宽度为 1 m，允许修正约 ±0.5 m 的平移初值 |
| `max_laser_range` | 12 m | 限制参与匹配的远距离范围 |
| `transform_timeout` | 0.1 s | 缩短地图修正 TF 的未来时间偏移及 TF 等待时间 |
| `use_lifecycle_manager` | true | 与已有生命周期管理器建立 bond，避免启动报错 |

原配置的 `minimum_laser_range`、`maximum_laser_range` 不被当前 Jazzy slam_toolbox 2.8.5 按预期使用，已去掉；该版本的最大量程参数是 `max_laser_range`，最小量程来自 LaserScan 消息。不是通过调大最小量程制造近处盲区。

该版本把 `map→odom` 时间戳设置为扫描时间加 `transform_timeout`，默认 0.5 s 在持续打滑时增加短暂位置偏差。设为 0.1 s 后已在完整传感器仿真中验证。依据：[Jazzy SLAM 源码](https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/src/slam_toolbox_common.cpp)、[激光量程处理源码](https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/src/laser_utils.cpp)。

### 3. 修正机器人网格资源的搜索路径

`src/simulation/rlai_gazebo/launch/gazebo.launch.py` 原来只把 `rlai_meshes` 包目录加入搜索路径，但 Gazebo 将网格 URI 解析为 `model://rlai_meshes/meshes/...`，需要从包的上一级搜索。现加入对应父目录；复测日志中的网格加载失败已消失。没有更改碰撞形状或物理参数。

### 4. 调整 EKF 输入，明确各层责任

`src/localization/rlai_localization/config/ekf.yaml` 开启平面模式，只融合轮式速度 vx、wz、差速车的 vy=0 约束，以及 IMU 的 z 轴角速度。不重复融合同一编码器积分得到的位置；暂不融合容易积累噪声和重力补偿误差的线加速度。

此修改本身不能识别持续打滑。独立的平移纠正来自 SLAM 的激光扫描匹配。定位入口中已移除此前的真值选择参数。

## 如何启动

先退出上一轮仿真，再从项目目录重新启动：

```bash
bash scripts/run_sim.sh --headless --rviz-mapping
```

键盘遥控方式保持原样：

```bash
docker compose -f docker/docker-compose.yml run --rm teleop
```

当前 Docker 使用源码挂载及 Python 包的符号链接安装，本次修改重启即可生效。已有失真地图不会因为参数更新自动恢复，应开始新的建图会话；原有地图文件已保留。

可在另一终端确认输入和激活状态：

```bash
docker exec rlai_sim_mapping ros2 param get /ekf_node odom0
docker exec rlai_sim_mapping ros2 param get /slam_toolbox scan_topic
docker exec rlai_sim_mapping ros2 lifecycle get /slam_toolbox
```

预期依次为 `/diff_drive_controller/odom`、`/scan_filtered` 和 `active`。

## 验证范围

使用独立 Docker 网络和 ROS_DOMAIN_ID=117，完整开启激光、IMU、深度与双目传感器，额外放置墙体复现顶墙空转。测试程序只将 Gazebo 真值作为误差对照，不向 EKF 或 SLAM 提供它。自由行驶、顶墙、倒车、转向均实际运行验证，见下方测试记录。

激光几何过滤有独立回归测试；EKF 有隔离的 ROS 节点测试，检查异常编码器积分位置和未使用的加速度不会污染估计。

```bash
python3 -m pytest -q tests/test_gazebo_assets.py tests/test_scan_self_filter.py
```

特征过少、动态物体过多或长时间丢失激光时，仍可能出现 SLAM 定位误差；本次验证针对已经复现的碰撞打滑扩散问题，不代表所有环境下定位误差为零。

### 2026-10-19 测试记录

| 测试 | 结果 |
|---|---|
| 旧 SLAM 配置，碰墙后停止 | 地图位置误差约 1.22 m，静止时地图仍从 408×397 扩到 414×397 栅格 |
| 最终配置、完整模型，同类碰墙后停止 | 地图位置误差约 0.014 m |
| 完整模型，以原有 0.5 m/s 指令继续顶墙 40 s | 轮式 x 累计至约 15.59 m、EKF x 约 16.50 m，实际车体 x 约 1.64 m；后 30 s 的地图位置误差约 0.029～0.096 m |
| 持续顶墙阶段地图范围 | 保持 370×397 栅格，没有随虚增里程计持续延伸 |
| 顶墙后倒车并停止 | 地图位置误差约 0.010 m |
| 随后转弯、前进并停止 | 地图位置误差约 0.016 m |

以上误差根据各阶段 0.5 s 间隔采样计算，属于近似值，不是严格同步传感器精度标定。0.5 m/s 是遥控指令；实际轮速仍受原有执行器限制。

早期对照与初次修复测试均使用旧资源路径，存在部分网格未加载；随后修正路径，完整模型重新执行自由行驶、碰墙和恢复行驶全流程。上表最终结果均来自完整模型复测。实际检查 61 对激光消息，每帧 720 束，其中 14 束车体回波被过滤，外部距离没有被改写。完整模型日志中网格加载错误为 0。

[保存的测量摘要](../validation/mapping-slip-20261019.json) 记录了全部阶段的实际坐标、地图坐标、地图大小及资源加载条件。`complete_basic`、`complete_extended` 是最终完整模型的结果。

主机基础测试 11 项通过；独立 ROS 集成测试 2 项通过，覆盖 EKF 输入，以及“激光保持静止、里程计持续虚增超过 1.5 m”时的真实过滤与 SLAM 节点行为。后者不需要 Gazebo 真值或任何位置回传。

在独立网络执行 ROS 集成测试（不会连接正在使用的仿真）：

```bash
docker run --rm --network bridge \
  -e ROS_DOMAIN_ID=118 -e RBOT_ROS_INTEGRATION=1 \
  -v "$PWD:/rbot:ro" --entrypoint /bin/bash rlai-bot:gazebo -lc \
  'source /opt/ros/jazzy/setup.bash; python3 -m pytest -q /rbot/tests/test_motion_pipeline.py -p no:cacheprovider'
```
