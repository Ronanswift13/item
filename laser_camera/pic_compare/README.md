pic_compare：机柜操作安全监测（图像对比 + 激光雷达融合）

本工程用于实现变电站 / 机柜现场的安全操作监测原型，核心目标是：
	•	监控操作人员相对于地面黄线的位置：
	•	远离黄线 → SAFE（绿色）
	•	踩在安全线带内 → CAUTION（黄色，可放宽为 SAFE）
	•	越过黄线靠近机柜 → DANGER（红色）
	•	结合激光雷达测距，判定操作人员是否站在授权机柜前；
	•	输出结构化的安全状态（SAFE/CAUTION/DANGER）以及 output_enabled 信号，可接继电器 / 报警灯 / PLC。

⸻

1. 目录结构（PythonCode/pic_compare）

当前项目主要目录如下：
	•	core/
	•	图像对比与安全判定的核心算法：
	•	黄线几何建模与区域判别
	•	人体 / 脚部相对黄线的位置判断
	•	帧间运动检测（has_motion）
	•	安全状态机（SAFE / CAUTION / DANGER + 抖动抑制）
	•	与激光雷达测距逻辑的接口
	•	demo/
	•	用于本地终端调试的场景模拟脚本：
	•	构造“脚尖坐标 + 距离 + 是否有运动”等输入，打印 zone / state / SAFE 等信息；
	•	用于验证算法逻辑是否正确。
	•	ui/
	•	未来与主 UI 集成的接口层：
	•	将 core 输出的状态映射到 UI 上的颜色、文字提示、按钮等。
	•	canmv/
	•	针对 CANMV 摄像头侧的脚本与协议逻辑（后续逐步打通）。
	•	data/
	•	录制/回放用的示例数据（如图像、标注、CSV 日志等）。
	•	log/
	•	运行日志，例如：

[LOG] t=2025-11-22T15:15:46.685673 state=TRANSITION zone=OUTSIDE_SAFE SAFE=True has_motion=True dist=12.0 foot=(1039,768)


	•	tools/ / notebooks/
	•	实验性脚本、算法验证、可视化脚本等。

⸻

2. 黄线几何建模与脚部位置判别

2.1 黄线模型

在图像坐标系中，用一条直线近似地面黄线的中心线：

a x + b y + c = 0
	•	(x, y)：图像像素坐标；
	•	(a, b, c)：由标定过程拟合得到的直线参数。

为了考虑黄线存在宽度，我们引入有符号距离 d：

d(x_f, y_f) = \frac{a x_f + b y_f + c}{\sqrt{a^2 + b^2}}
	•	d>0：点在黄线的“安全侧”（远离机柜一侧）；
	•	d<0：点在黄线的“危险侧”（靠近机柜一侧）；
	•	|d| 的大小反映了点到黄线的距离（像素尺度）。

再定义几个阈值（s 表示像素距离）：
	•	d_{\text{outer\_safe}}：安全线外侧边界
	•	d_{\text{line}}：黄线中心附近的区域（容许一定厚度）
	•	d_{\text{inner\_danger}}：内侧危险区域边界（靠机柜）

示意分类：
	•	OUTSIDE_SAFE（安全区外侧）：
	•	d \ge d_{\text{outer\_safe}}
	•	ON_LINE_SAFE（在线带内）：
	•	d_{\text{inner\_danger}} < d < d_{\text{outer\_safe}}
	•	INSIDE_DANGER（越线靠近机柜）：
	•	d \le d_{\text{inner\_danger}}

这些阈值在代码中可以配置，方便根据实际相机视角做微调。

2.2 脚部定位

当前原型中，脚部坐标 (x_f, y_f) 可以通过两种方式获取：
	1.	模拟/手动输入（用于 demo 验证）：
	•	脚尖坐标在测试脚本中硬编码或通过鼠标选择；
	2.	后续接入人体检测模型：
	•	先通过人体检测框出人的 bounding box，再在框底部区域搜索脚部关键点；
	•	识别得到脚尖位置后直接带入上面的几何计算。

核心逻辑是：一旦知道脚尖的像素坐标，就能通过 d(x_f, y_f) 判断其相对黄线的位置和安全区域。

⸻

3. 帧间运动检测（人物是否移动）

为了控制雷达采样频率和状态机抖动，我们引入 帧间运动检测（has_motion）：
	•	对比当前帧 t 与上一帧 t-1 的图像（或关键点位置）；
	•	若一段时间 [t, t+K] 内，脚步位移 \Delta 小于某个阈值（例如 0.2–0.3m 对应的像素距离），则认为人物基本静止；
	•	若位移超过阈值，则认为人物处于移动中。

在当前 demo 中：
	•	has_motion 可以由简单的阈值判断或帧差法模拟；
	•	日后可以接入更复杂的光流 / 关键点跟踪算法。

运动检测的意义在于：
	•	静止时：可以降低雷达采样频率，仅监视越线状态；
	•	移动时：提高雷达采样频率，并动态更新“当前站位的机柜区间”。

⸻

4. 激光雷达与授权机柜区间

激光雷达沿机柜一排方向放置，测得的距离 D 被映射到一维“机柜坐标轴”上。

示例设定：
	•	雷达到第 1 号机柜前沿距离：150 cm；
	•	每个机柜宽度：90 cm；
	•	某些机柜之间存在空档，例如 2、3号机柜之间间隔 55.5 cm。

在代码中，将这些区间写成一组区间表：

CABINETS = [
    # (cabinet_id, dist_min_cm, dist_max_cm)
    (1, d1_min, d1_max),
    (2, d2_min, d2_max),
    ...
]

当雷达测得距离 dist_cm 时：
	1.	查表找到 dist_cm 落在哪个 cabinet_id 区间；
	2.	对比当前已授权机柜列表，判断是否为已授权机柜；
	3.	将这一信息与图像黄线判别结果融合，得出最终安全状态。

⸻

5. 安全状态机与输出逻辑

5.1 状态机设计

为避免状态频繁抖动，引入简单的状态机，例如：
	•	SAFE_STABLE：持续安全；
	•	TRANSITION：过渡状态（短时间内刚进入或离开危险）；
	•	DANGER_STABLE：持续危险。

状态机的输入包括：
	•	zone：OUTSIDE_SAFE / ON_LINE_SAFE / INSIDE_DANGER
	•	is_authorized_cabinet：雷达 + 授权机柜判断
	•	has_motion：是否检测到移动
	•	distance_cm：雷达测距结果

通过一组规则（伪代码）更新状态：

if zone == INSIDE_DANGER:
    state = DANGER_STABLE
    safe = False
elif zone == ON_LINE_SAFE:
    state = TRANSITION  # 或 CAUTION
    safe = True
else:  # OUTSIDE_SAFE
    state = SAFE_STABLE
    safe = True

# 再结合是否在授权机柜前
if not is_authorized_cabinet:
    # 即使线外，仍可标记为 CAUTION 或禁止输出
    safe = False

5.2 output_enabled 信号

最终输出一个布尔量 output_enabled，用于驱动外部硬件（继电器 / 报警灯 / PLC）：
	•	output_enabled = True：允许操作（如解锁某些设备）；
	•	output_enabled = False：禁止操作或触发报警。

简单规则示例：
	•	当 safe == True 且 is_authorized_cabinet == True 且 zone != INSIDE_DANGER 时：
	•	output_enabled = True
	•	其他情况：
	•	output_enabled = False

这样可以在软件层直接控制硬件输出口，例如：
	•	GPIO 输出；
	•	通过串口发送控制帧给下位机；
	•	或通过 Modbus/TCP 写 PLC 寄存器。

⸻

6. 典型工作流程（时序逻辑）
	1.	人物进入监控区域
	•	红外人体感应触发 + 图像检测到新的人体轮廓；
	•	系统开始以较高频率抓取帧，启动雷达采样。
	2.	人物移动到某一机柜前并停下
	•	帧间运动逐渐减小，has_motion → False；
	•	雷达测距稳定后，映射到某个 cabinet_id；
	•	若该机柜被授权，且脚尖在 OUTSIDE_SAFE 或 ON_LINE_SAFE 区域内，则状态为 SAFE（或 CAUTION），output_enabled=True。
	3.	人物向机柜方向越线靠近
	•	脚尖坐标落入 INSIDE_DANGER 区：
	•	zone=INSIDE_DANGER
	•	状态机切换到 DANGER_STABLE
	•	output_enabled=False，触发红色报警灯 / 蜂鸣器 / PLC 断开。
	4.	人物离开机柜区域
	•	检测到远离黄线，zone=OUTSIDE_SAFE；
	•	若持续一段时间不再越线，状态回到 SAFE_STABLE；
	•	可选择延时若干秒后重新允许授权下一次操作。

⸻

7. 后续扩展方向

后续可以在现有框架基础上逐步升级：
	•	在 canmv/ 中运行轻量级人体检测 / 关键点检测模型，直接输出脚部关键点；
	•	引入多目标跟踪，支持多人同时在画面中的情况；
	•	在 UI 中集成：
	•	实时视频流显示；
	•	三色状态指示（SAFE/CAUTION/DANGER）；
	•	当前授权机柜 ID 与检测到的实际机柜 ID；
	•	实时日志和历史回放。

