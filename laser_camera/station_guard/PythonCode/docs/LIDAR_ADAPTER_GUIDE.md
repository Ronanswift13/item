# TOF 激光雷达适配器指南

## 概述

`ToFLidarAdapter` 是一个将您现有的 TOF 激光雷达代码封装为标准化接口的适配器。

**核心转换：**
```
现有代码：lidar.read_measurement() → (distance_m, strength)
       ↓
适配器输出：RangeMeasurement(distance_m, confidence, angle_or_sector, timestamp)
```

## 关键特性

✅ **零修改原有代码** - 您的 `lidar_tof.py` 保持不变
✅ **标准化接口** - 继承自 `RangeAdapter` 基类
✅ **完整测试覆盖** - 16个测试用例全部通过
✅ **硬件无关** - 核心系统不知道具体硬件类型

## 文件位置

```
station_guard/PythonCode/
├── adapters/
│   ├── base/
│   │   └── range_base.py          # 基类和标准数据结构
│   └── legacy/
│       └── lidar_tof_adapter.py   # TOF 激光雷达适配器 ✨
├── tests/
│   └── test_lidar_adapter.py      # 适配器测试
└── docs/
    └── LIDAR_ADAPTER_GUIDE.md     # 本文档
```

## 数据流

```
┌─────────────────┐
│  TOF 激光雷达    │
│  (硬件)         │
└────────┬────────┘
         │ 串口通信
         ↓
┌─────────────────┐
│ lidar_tof.py    │  ← 您现有的代码（未修改）
│ ToFLidar        │
└────────┬────────┘
         │ read_measurement()
         │ → (distance_m, strength)
         ↓
┌─────────────────┐
│ lidar_tof_      │  ← 新建的适配器
│ adapter.py      │
│ ToFLidarAdapter │
└────────┬────────┘
         │ read_measurement()
         │ → [RangeMeasurement]
         ↓
┌─────────────────┐
│ 核心系统         │  ← 硬件无关的核心逻辑
│ (fusion等)      │
└─────────────────┘
```

## 快速开始

### 1. 基本使用

```python
from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter

# 创建适配器
adapter = ToFLidarAdapter(port="/dev/ttyUSB0")

# 读取测量
measurements = adapter.read_measurement()

if measurements:
    for m in measurements:
        print(f"距离: {m.distance_m:.2f}m")
        print(f"置信度: {m.confidence:.2f}")
        print(f"强度: {m.signal_strength}")

# 关闭
adapter.close()
```

### 2. 使用上下文管理器（推荐）

```python
from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter

with ToFLidarAdapter(port="/dev/ttyUSB0") as adapter:
    measurements = adapter.read_measurement()
    if measurements:
        print(f"距离: {measurements[0].distance_m:.2f}m")
# 自动调用 close()
```

### 3. 自动端口检测

```python
# port=None 表示使用配置文件中的默认端口
adapter = ToFLidarAdapter(port=None)
```

## 核心类和方法

### `ToFLidarAdapter` 类

继承自 `RangeAdapter` 基类，实现了以下方法：

#### `__init__(port, baudrate, timeout, strength_normalization_factor, max_range_m)`

初始化适配器。

**参数：**
- `port`: 串口路径（例如 `"/dev/ttyUSB0"`），`None` 表示自动检测
- `baudrate`: 波特率，默认 `115200`
- `timeout`: 串口超时（秒），默认 `1.0`
- `strength_normalization_factor`: 强度归一化因子，默认 `1000.0`
  - 置信度 = strength / strength_normalization_factor
  - 结果限制在 [0, 1] 范围内
- `max_range_m`: 最大测量距离（米），默认 `10.0`

#### `read_measurement() -> Optional[List[RangeMeasurement]]`

读取一次距离测量。

**返回值：**
- 成功：包含单个 `RangeMeasurement` 对象的列表
- 失败：`None`

**RangeMeasurement 对象包含：**
```python
@dataclass
class RangeMeasurement:
    distance_m: float          # 距离（米）
    confidence: float          # 置信度 [0.0, 1.0]
    angle_or_sector: Optional[float]  # None（单点传感器）
    timestamp: float           # Unix 时间戳（秒）
    signal_strength: Optional[int]    # 原始强度值（调试用）
```

#### `get_range_type() -> RangeType`

获取传感器类型。

**返回值：** `RangeType.SINGLE_POINT`

#### `get_status() -> RangeStatus`

获取传感器当前状态。

**可能的状态：**
- `READY`: 就绪
- `INITIALIZING`: 初始化中
- `DISCONNECTED`: 断开连接
- `ERROR`: 错误
- `STOPPED`: 已停止

#### `get_max_range() -> float`

获取最大测量距离（米）。

#### `close() -> None`

释放串口资源。

#### `get_measurement_rate() -> float`

获取估计的测量频率（Hz），TOF 激光雷达通常为 10-20 Hz。

## 测试

### 运行所有适配器测试

```bash
cd /Users/ronan/Desktop/item/laser_camera/station_guard/PythonCode
python3 -m pytest tests/test_lidar_adapter.py -v
```

### 测试覆盖

- ✅ 结构测试：适配器继承、方法存在性
- ✅ 功能测试：读取、转换、置信度计算
- ✅ 边界测试：空值处理、置信度上限
- ✅ 集成测试：连续读取、上下文管理器

### 测试结果

```
16 passed in 0.06s
```

## 独立测试程序

适配器内置了独立测试程序，可以验证硬件连接：

```bash
cd /Users/ronan/Desktop/item/laser_camera/station_guard/PythonCode
python3 -m adapters.legacy.lidar_tof_adapter
```

**输出示例：**
```
======================================================================
TOF 激光雷达适配器测试
======================================================================

正在初始化适配器...
  状态: ready
  类型: single_point
  最大量程: 10.0m
  采样率: 10.0 Hz

读取测量数据（10秒）...
按 Ctrl+C 可提前停止

序号    距离(m)   置信度     强度      时间戳
----------------------------------------------------------------------
  1✓     2.456m     0.85      850  1234567890.123
  2✓     2.463m     0.87      870  1234567890.223
  3✓     2.451m     0.84      840  1234567890.323
...
```

## 实现细节

### 1. 导入路径计算

```python
# 从 station_guard/PythonCode/adapters/legacy/lidar_tof_adapter.py
# 计算到 laser_camera/lidar_distance/PythonCode
LIDAR_CODE_PATH = Path(__file__).parents[4] / "lidar_distance" / "PythonCode"
sys.path.insert(0, str(LIDAR_CODE_PATH))

from core.lidar_tof import ToFLidar, SerialException
```

**路径解析：**
```
lidar_tof_adapter.py                          # Path(__file__)
    ↑ parents[0]: legacy/
    ↑ parents[1]: adapters/
    ↑ parents[2]: PythonCode/
    ↑ parents[3]: station_guard/
    ↑ parents[4]: laser_camera/              ← 这里！
        → lidar_distance/PythonCode/
```

### 2. 置信度计算

```python
confidence = min(strength / strength_normalization_factor, 1.0)
```

**示例：**
- strength = 850, factor = 1000 → confidence = 0.85
- strength = 1200, factor = 1000 → confidence = 1.0（上限）
- strength = 500, factor = 1000 → confidence = 0.50

### 3. 状态管理

```python
class ToFLidarAdapter(RangeAdapter):
    def __init__(self, ...):
        self._status = RangeStatus.INITIALIZING
        try:
            self.lidar = ToFLidar(...)
            self._status = RangeStatus.READY
        except:
            self._status = RangeStatus.ERROR

    def close(self):
        self.lidar.close()
        self._status = RangeStatus.STOPPED
```

## 配置参数调优

### strength_normalization_factor

**默认值：** `1000.0`

**如何调整：**

1. 观察实际强度值范围：
```python
adapter = ToFLidarAdapter(port="/dev/ttyUSB0")
for _ in range(100):
    m = adapter.read_measurement()
    if m:
        print(f"Strength: {m[0].signal_strength}")
```

2. 如果典型强度值在 500-1500 范围：
```python
# 使用中间值作为归一化因子
adapter = ToFLidarAdapter(
    port="/dev/ttyUSB0",
    strength_normalization_factor=1000.0
)
```

3. 如果典型强度值在 200-600 范围：
```python
# 降低归一化因子以获得更高的置信度
adapter = ToFLidarAdapter(
    port="/dev/ttyUSB0",
    strength_normalization_factor=400.0
)
```

### max_range_m

**默认值：** `10.0` 米

根据实际部署环境调整：

```python
# 短距离应用（机柜监控）
adapter = ToFLidarAdapter(
    port="/dev/ttyUSB0",
    max_range_m=5.0
)

# 长距离应用
adapter = ToFLidarAdapter(
    port="/dev/ttyUSB0",
    max_range_m=15.0
)
```

## 故障排除

### 问题 1: ImportError: Cannot import lidar_tof

**原因：** 导入路径错误

**解决：**
```bash
# 检查路径是否正确
ls /Users/ronan/Desktop/item/laser_camera/lidar_distance/PythonCode/core/lidar_tof.py
```

### 问题 2: SerialException: Cannot open serial port

**原因：** 串口权限或占用

**解决：**
```bash
# 检查串口权限
ls -l /dev/ttyUSB0

# 添加用户到 dialout 组（Linux）
sudo usermod -a -G dialout $USER

# 检查串口是否被占用
lsof /dev/ttyUSB0
```

### 问题 3: 测量返回 None

**可能原因：**
1. 激光雷达未连接或断电
2. 串口参数不匹配（波特率、超时等）
3. 硬件故障

**调试：**
```python
adapter = ToFLidarAdapter(port="/dev/ttyUSB0", timeout=2.0)  # 增加超时
status = adapter.get_status()
print(f"Status: {status}")  # 应该是 READY

# 检查原始 lidar 对象
result = adapter.lidar.read_measurement()
print(f"Raw result: {result}")
```

## 与核心系统集成

适配器已准备好与融合模块集成：

```python
from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter
from core.fusion import FusionEngine  # 未来实现

# 初始化传感器适配器
lidar = ToFLidarAdapter(port="/dev/ttyUSB0")
camera = CameraYoloAdapter(camera_id=0)

# 创建融合引擎
fusion = FusionEngine(
    range_sensor=lidar,
    camera_sensor=camera
)

# 运行融合
while True:
    fusion.update()
    positions = fusion.get_positions()
    # ... 状态分类和报警 ...
```

## 下一步

1. ✅ **激光雷达适配器** - 已完成
2. ⏳ **相机适配器** - `camera_yolo_adapter.py`
3. ⏳ **融合模块** - `fusion_legacy_adapter.py`
4. ⏳ **主应用** - 整合所有模块

## 总结

`ToFLidarAdapter` 成功将您现有的激光雷达代码封装为标准化接口：

- ✅ 零修改原有代码
- ✅ 标准化数据输出
- ✅ 完整测试覆盖（16/16 通过）
- ✅ 硬件无关的核心系统
- ✅ 支持上下文管理器
- ✅ 详细的状态管理
- ✅ 独立测试工具

适配器已准备好用于实际部署和与核心系统集成！
