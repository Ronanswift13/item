
# LiDAR Distance Measurement & Fusion – Project README

本 README 专门用于说明本项目中 **激光雷达测距与融合** 相关的代码结构、功能和使用方法，方便你后续继续维护、调试和扩展。

---

## 1. 项目定位

本工程以 **TOF 激光雷达** 为核心传感器，实现：

1. **基础测距功能**：串口通信 + 单次/连续测距。
2. **机位/柜位判定**：根据距离区间判断人员当前所在机柜位置，区分授权/未授权机柜。
3. **多传感器融合**：将激光雷达测距结果与视觉识别（姿态、手势、站位）进行逻辑融合，给出更稳定、更安全的状态判定。
4. **演示与 UI**：提供 CLI 演示脚本与 Flet UI 界面，方便现场演示和后续科研扩展。

> 你可以把这一套 LiDAR + Vision + Fusion 理解为后面做攻防博弈、平均场建模的“前端感知层”。

---

## 2. 代码结构总览（与激光相关部分）

按照新的工作树，激光相关模块主要分布在：

```text
laser_camera/
  lidar_distance/
    PythonCode/
      core/          # 核心算法与驱动
      demo/          # 演示脚本（CLI/UI/记录/回放）
      log/           # 运行产生的日志（fusion_log.csv 等）
      test/          # 纯软件测试（如融合逻辑单元测试）
      ui/            # Flet 图形界面
      data/          # 示例配置与样本数据
```

### 2.1 core 目录中的关键模块

- `core/new_lidar.py`
  - 功能：**命令式激光雷达驱动**。
  - 特色：
    - 自动探测可用串口（支持 macOS `/dev/cu.usbserial-*` / Windows `COMx` 等）。
    - 发送单次测距命令，读取返回帧并解析出距离值（单位 cm 或 m）。
    - 内部包含重试机制和异常封装（如 `NewLidarError`）。

- `core/new_lidar_debug.py`
  - 功能：调试版本雷达驱动，用于快速排查串口、数据帧格式、异常情况。
  - 一般不被上层直接调用，但在调试硬件通信问题时非常有用。

- `core/lidar_tof.py`
  - 功能：**流式 TOF 雷达驱动**。
  - 特点：
    - 适配持续输出距离数据的 TOF 雷达（不需要命令触发）。
    - 提供 `ToFLidar` 类，支持按帧读取 `(distance_m, strength)`。

- `core/cabinet_positioning.py`
  - 功能：**基础机位判定逻辑**。
  - 核心变量：
    - `CABINETS: dict[int, tuple[float, float]]`
      - 例：`{1: (1.8, 2.2), 2: (3.3, 3.7), 3: (4.8, 5.2)}`
      - 每个键为机柜编号，值为对应的距离区间（米）。
  - 作用：给定测得距离 `distance_m`，返回对应机柜 ID 或 N/A。

- `core/lidar_zone_logic.py`
  - 功能：**高级机位与状态机逻辑**。
  - 主要内容：
    - `CabinetZone`：表示一个机柜区间 `[d_min_m, d_max_m]`。
    - `LidarStatus`：枚举，包含 `IDLE`, `WALKING`, `STABLE_AUTH`, `STABLE_UNAUTH`, `OUT_OF_RANGE` 等。
    - `LidarDecision`：数据类，包含 `distance_m`, `cabinet_index`, `status`, `is_safe`, `reason`。
    - `LidarZoneTracker`：核心状态机，维护时间窗内历史数据，根据距离波动和机柜一致性判断：
      - 是否在**行走**（移动中）；
      - 是否在某一机柜前**稳定停留**；
      - 机柜是否在授权列表中（授权 / 未授权）；
      - 是否处于配置区间之外（OUT_OF_RANGE）。

- `core/realtime_lidar.py`
  - 功能：将 `ToFLidar` 或 `new_lidar` 封装成更上层的“实时测距源”。
  - 可用作 CLI 工具或被融合模块调用，打印当前距离、机柜判断等信息。

- `core/vision_logic.py`
  - 功能：定义视觉相关的状态枚举与数据结构，例如：
    - `VisionState`
    - `LinePosition`（站位偏左/偏右/居中）
    - `BodyOrientation`（朝向）
    - `GestureCode`（手势编号）
  - 这些定义会在融合阶段被用来与 LiDAR 数据组合。

- `core/fusion_logic.py`
  - 功能：**核心传感器融合算法**。
  - 输入：雷达距离与机柜判定结果 + 视觉状态（站位、姿态、手势等）。
  - 输出：融合后的 `FusionState`，用于安全逻辑或 UI 展示。

- `core/safety_logic.py`（如果存在）
  - 功能：在融合结果基础上输出安全等级（如 `AlarmLevel`），并给出告警原因。

### 2.2 demo 目录中的演示脚本

常见的演示脚本包括：

- `demo/demo_ranging.py`
  - 功能：**纯测距 CLI 演示**。
  - 逻辑：调用 `new_lidar` 或 `ToFLidar` 持续读取距离，打印距离和强度信息。

- `demo/lidar_zone_live_demo.py`
  - 功能：实时展示机位判定。
  - 逻辑：持续读取距离 → 丢给 `LidarZoneTracker.update()` → 打印当前机柜、状态、是否安全。

- `demo/fusion_demo.py`
  - 功能：实时融合演示（命令行版本）。
  - 逻辑：
    1. 读取 LiDAR 距离；
    2. 读取视觉状态（可能是模拟输入）；
    3. 调用 `fuse_sensors` 得到融合状态；
    4. 打印融合结果。

- `demo/fusion_record_demo.py`
  - 功能：实时采集 + 记录到 `fusion_log.csv`。

- `demo/fusion_replay_demo.py`
  - 功能：从已有 `fusion_log.csv` 回放数据，用于调参与分析。

- `demo/analyze_fusion_log.py`
  - 功能：离线分析 `fusion_log.csv`（最小值、最大值、平均距离、告警统计等）。

### 2.3 ui 目录中的界面

- `ui/final_ui_flet.py`（或同名文件）
  - 功能：基于 Flet 的图形界面，展示：
    - 当前距离；
    - 当前机柜编号；
    - 授权/未授权状态；
    - 视觉识别结果（线位、朝向、手势）；
    - 当前告警等级和提示信息。

---

## 3. 依赖与环境配置

### 3.1 Python 版本

建议使用：

- **Python 3.9+**（若使用 `X | None` 联合类型语法，推荐 3.10+）。

### 3.2 关键依赖

在虚拟环境中安装：

```bash
pip install pyserial flet
```

根据实际脚本可能还需要：

- `numpy`
- `opencv-python`
- 其他图像处理 / 可视化库

### 3.3 串口配置

- macOS 常见端口示例：`/dev/cu.usbserial-xxxx`、`/dev/tty.usbserial-xxxx`
- Windows 常见端口示例：`COM3`, `COM5` 等

`new_lidar.py` 中的 `_resolve_port()` 会：

1. 优先使用函数参数中显式传入的端口；
2. 否则遍历候选端口列表（包含 Windows 与 Unix 风格端口名）；
3. 在 macOS 下通常需要将实际的 `/dev/cu.usbserial-XXXX` 加入候选列表或写入配置。

---

## 4. 常见使用方式

### 4.1 纯测距测试（命令行）

```bash
cd /Users/ronan/Desktop/item/laser_camera/lidar_distance/PythonCode
python3 -m PythonCode.demo.demo_ranging
```

观察：

- 是否能读取到稳定的距离；
- 是否存在明显跳变或异常值。

### 4.2 机位判定测试

```bash
python3 -m PythonCode.demo.lidar_zone_live_demo
```

观察：

- 切换不同机柜位置时，`cabinet_index` 是否随距离改变；
- 行走时是否被识别为 `WALKING`；
- 在授权机柜前稳定站立时，是否输出 `STABLE_AUTH`；
- 在未授权机柜前站立时，是否输出 `STABLE_UNAUTH` 并标记为不安全。

### 4.3 融合逻辑测试（无硬件环境）

若只想测试融合算法本身，可以：

```bash
python3 -m PythonCode.test.test_fusion_logic
```

该脚本通过构造虚拟 LiDAR 与视觉输入，验证 `fuse_sensors` 的逻辑是否符合预期。

---

## 5. 配置与参数调整

### 5.1 机柜区间（CABINETS）

修改 `core/cabinet_positioning.py` 中的 `CABINETS` 字典，将距离区间替换为现场实际测量值：

```python
CABINETS = {
    1: (1.80, 2.20),
    2: (3.30, 3.70),
    3: (4.80, 5.20),
}
```

或在 `LidarZoneTracker` 初始化时传入自定义的 `CabinetZone` 列表。

### 5.2 状态机参数

在 `LidarZoneTracker` 中可以调整：

- `movement_threshold_m`：判断“行走”的最小距离波动；
- `static_threshold_m`：判定“稳定站立”时允许的最大距离波动；
- `static_window_s`：检查稳定状态的时间窗口长度；
- `walk_window_s`：检查行走状态的时间窗口。

这些参数可以根据实际场景（走路速度、雷达噪声等）进行调参。

---

## 6. 调试建议

1. **先确认串口与数据帧是否正常**：
   - 用 `new_lidar_debug.py` 或最简单的 `demo_ranging.py` 检查裸数据是否正常。

2. **再接入机位判定**：
   - 使用 `lidar_zone_live_demo.py`，观察 `cabinet_index` 与状态机输出是否符合预期。

3. **最后接入融合与 UI**：
   - 确认 LiDAR 工作稳定后，再逐步接入 `fusion_logic` 和 Flet UI。

4. **如果出现 `ModuleNotFoundError`**：
   - 检查是否使用了 `from PythonCode.core.xxx import ...` 的形式；
   - 确认 `PythonCode` 以及子目录下都存在 `__init__.py` 文件。

---

## 7. 后续扩展方向

- 用采集到的 `fusion_log.csv` 构建数据集，分析不同场景下的行为模式。
- 把 LiDAR + Vision 的状态序列作为 **PDE/平均场博弈模型** 的观测输入，继续你的博士研究主线。
- 在 UI 中加入更多维度（如风险评分、推荐动作等），为安全控制和攻防模拟提供接口。

> 这份 README 只针对激光雷达测距与融合部分。后续如果你在平均场理论、攻防博弈建模上形成稳定代码结构，也可以用类似方式再写一份“理论模型层”的 README，与本感知层文档互相对应。
