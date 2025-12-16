"""
adapters/base/lamp_base.py

三色灯控制适配器抽象基类定义

支持各种输出设备：
- GPIO控制的物理三色灯
- 串口控制的灯光模块
- 网络控制的智能灯（HTTP/MQTT）
- 虚拟灯（UI显示）

核心设计原则：
1. 适配器负责具体的硬件或协议控制
2. 接收标准化的 AlarmLevel 枚举值
3. 内核不需要知道灯光是如何实现的
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
import time


class AlarmLevel(Enum):
    """
    告警级别（对应三色灯颜色）
    
    这是系统核心与灯光控制之间的数据契约。
    状态机根据人员位置和违规情况输出此枚举值。
    """
    GREEN = 0   # 绿灯：正常状态，所有人员都在授权区域内
    YELLOW = 1  # 黄灯：警告状态，有人接近警戒线（ON_LINE）
    RED = 2     # 红灯：告警状态，有违规行为（CROSS_LINE/MISPLACED/HIGH_RISK）
    
    def to_color_name(self) -> str:
        """转换为颜色名称"""
        return self.name.lower()
    
    def to_rgb(self) -> tuple[int, int, int]:
        """
        转换为RGB值（用于可编程LED）
        
        Returns:
            (R, G, B) 每个分量范围 0-255
        """
        if self == AlarmLevel.GREEN:
            return (0, 255, 0)
        elif self == AlarmLevel.YELLOW:
            return (255, 255, 0)
        else:  # RED
            return (255, 0, 0)
    
    @classmethod
    def from_color_name(cls, color: str) -> Optional['AlarmLevel']:
        """
        从颜色名称创建枚举值
        
        Args:
            color: "green", "yellow", "red" (不区分大小写)
        
        Returns:
            对应的 AlarmLevel 或 None
        """
        color_upper = color.upper()
        try:
            return cls[color_upper]
        except KeyError:
            return None


class LampStatus(Enum):
    """灯光设备状态"""
    READY = "ready"              # 就绪
    INITIALIZING = "initializing"  # 初始化中
    DISCONNECTED = "disconnected"  # 断开连接
    ERROR = "error"              # 错误
    STOPPED = "stopped"          # 已停止


class LampAdapter(ABC):
    """
    三色灯适配器抽象基类
    
    所有具体的灯光实现（GPIOLampAdapter, SerialLampAdapter等）
    必须继承此类并实现所有抽象方法。
    
    使用示例：
        lamp = GPIOLampAdapter(green_pin=17, yellow_pin=27, red_pin=22)
        
        try:
            lamp.set_color(AlarmLevel.GREEN)
            time.sleep(2)
            lamp.set_color(AlarmLevel.YELLOW)
            time.sleep(2)
            lamp.set_color(AlarmLevel.RED)
        finally:
            lamp.close()
    """
    
    @abstractmethod
    def set_color(self, level: AlarmLevel) -> bool:
        """
        设置灯光颜色
        
        此方法应该：
        1. 将 AlarmLevel 枚举值转换为具体的控制信号
        2. 发送控制命令到硬件
        3. 验证命令是否成功执行
        
        Args:
            level: 告警级别（GREEN/YELLOW/RED）
        
        Returns:
            True if 设置成功，False if 失败
        
        注意：
            - 此方法应该是幂等的（重复设置相同颜色不应有副作用）
            - 如果硬件不支持某种颜色，应该选择最接近的颜色
        """
        pass
    
    @abstractmethod
    def get_status(self) -> LampStatus:
        """
        获取灯光设备状态
        
        Returns:
            LampStatus 枚举值
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """
        关闭灯光并释放资源
        
        应该：
        - 关闭所有灯光（或设置为安全状态）
        - 释放GPIO/串口/网络连接
        """
        pass
    
    # 可选方法：高级功能
    
    def test_all_colors(self, duration_per_color: float = 1.0) -> bool:
        """
        测试所有颜色（用于系统自检）
        
        Args:
            duration_per_color: 每种颜色显示时长（秒）
        
        Returns:
            True if 所有颜色测试成功
        """
        try:
            for level in [AlarmLevel.GREEN, AlarmLevel.YELLOW, AlarmLevel.RED]:
                if not self.set_color(level):
                    return False
                time.sleep(duration_per_color)
            return True
        except Exception:
            return False
    
    def set_brightness(self, brightness: float) -> bool:
        """
        设置亮度（如果设备支持）
        
        Args:
            brightness: 亮度值 [0.0, 1.0]
        
        Returns:
            True if 设置成功，False if 不支持或失败
        """
        return False
    
    def set_blink(self, enable: bool, frequency_hz: float = 1.0) -> bool:
        """
        设置闪烁模式（如果设备支持）
        
        Args:
            enable: True 启用闪烁，False 禁用
            frequency_hz: 闪烁频率（Hz）
        
        Returns:
            True if 设置成功，False if 不支持或失败
        """
        return False
    
    def get_current_color(self) -> Optional[AlarmLevel]:
        """
        获取当前灯光颜色
        
        Returns:
            当前的 AlarmLevel，如果无法获取返回 None
        """
        return None
    
    def __enter__(self):
        """支持上下文管理器协议"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议"""
        self.close()


# 工具类：虚拟灯（用于测试和开发）

class VirtualLampAdapter(LampAdapter):
    """
    虚拟灯适配器（终端输出模拟）
    
    用于测试和开发，不需要实际硬件。
    在终端打印彩色输出表示灯光状态。
    
    使用示例：
        lamp = VirtualLampAdapter()
        lamp.set_color(AlarmLevel.RED)
    """
    
    def __init__(self, enable_color_output: bool = True):
        """
        初始化虚拟灯
        
        Args:
            enable_color_output: 是否使用ANSI颜色代码（终端支持时）
        """
        self.enable_color_output = enable_color_output
        self.current_color = None
        self.status = LampStatus.READY
    
    def set_color(self, level: AlarmLevel) -> bool:
        """设置灯光颜色（打印到终端）"""
        if self.status != LampStatus.READY:
            return False
        
        self.current_color = level
        
        if self.enable_color_output:
            # ANSI颜色代码
            color_codes = {
                AlarmLevel.GREEN: '\033[92m',   # 亮绿色
                AlarmLevel.YELLOW: '\033[93m',  # 亮黄色
                AlarmLevel.RED: '\033[91m',     # 亮红色
            }
            reset_code = '\033[0m'
            
            color_code = color_codes.get(level, '')
            emoji = self._get_emoji(level)
            print(f"{color_code}{emoji} 灯光: {level.name}{reset_code}")
        else:
            emoji = self._get_emoji(level)
            print(f"{emoji} 灯光: {level.name}")
        
        return True
    
    def get_status(self) -> LampStatus:
        """获取设备状态"""
        return self.status
    
    def close(self) -> None:
        """关闭虚拟灯"""
        if self.current_color is not None:
            print("🔌 虚拟灯已关闭")
        self.current_color = None
        self.status = LampStatus.STOPPED
    
    def get_current_color(self) -> Optional[AlarmLevel]:
        """获取当前颜色"""
        return self.current_color
    
    @staticmethod
    def _get_emoji(level: AlarmLevel) -> str:
        """获取对应的emoji图标"""
        emoji_map = {
            AlarmLevel.GREEN: '🟢',
            AlarmLevel.YELLOW: '🟡',
            AlarmLevel.RED: '🔴',
        }
        return emoji_map.get(level, '⚪')


# 工具函数

class AlarmLevelAggregator:
    """
    告警级别聚合器
    
    用于将多个人员的状态聚合为单一的全局告警级别。
    遵循"最坏情况优先"原则：任何一个人的违规都会触发全局告警。
    
    使用示例：
        aggregator = AlarmLevelAggregator()
        
        # 多个人员状态
        person_states = {
            1: PersonStatus.NORMAL,
            2: PersonStatus.ON_LINE,
            3: PersonStatus.NORMAL
        }
        
        global_alarm = aggregator.aggregate_from_states(person_states)
        # 结果：AlarmLevel.YELLOW (因为有人ON_LINE)
    """
    
    @staticmethod
    def aggregate(levels: list[AlarmLevel]) -> AlarmLevel:
        """
        聚合多个告警级别
        
        Args:
            levels: 告警级别列表
        
        Returns:
            聚合后的全局告警级别（最高优先级）
        """
        if not levels:
            return AlarmLevel.GREEN
        
        # 按严重程度排序：RED > YELLOW > GREEN
        if AlarmLevel.RED in levels:
            return AlarmLevel.RED
        elif AlarmLevel.YELLOW in levels:
            return AlarmLevel.YELLOW
        else:
            return AlarmLevel.GREEN
    
    @staticmethod
    def aggregate_from_states(person_states: dict) -> AlarmLevel:
        """
        从人员状态字典聚合告警级别
        
        Args:
            person_states: {track_id: PersonStatus} 字典
        
        Returns:
            全局告警级别
        
        注意：
            需要导入 PersonStatus 枚举才能使用此方法
        """
        # 此处为占位实现，实际使用时需要导入 PersonStatus
        # 简化映射规则：
        # NORMAL -> GREEN
        # ON_LINE -> YELLOW
        # CROSS_LINE/MISPLACED/HIGH_RISK -> RED
        
        levels = []
        for status in person_states.values():
            status_name = status.name if hasattr(status, 'name') else str(status)
            
            if status_name == 'NORMAL':
                levels.append(AlarmLevel.GREEN)
            elif status_name == 'ON_LINE':
                levels.append(AlarmLevel.YELLOW)
            else:  # CROSS_LINE, MISPLACED, HIGH_RISK
                levels.append(AlarmLevel.RED)
        
        return AlarmLevelAggregator.aggregate(levels)


if __name__ == "__main__":
    # 模块自检
    print("=" * 60)
    print("Lamp Adapter Base - 模块自检")
    print("=" * 60)
    
    # 测试枚举值转换
    print("\n测试 AlarmLevel 枚举:")
    for level in AlarmLevel:
        print(f"  {level.name}:")
        print(f"    颜色名: {level.to_color_name()}")
        print(f"    RGB值: {level.to_rgb()}")
    
    # 测试虚拟灯
    print("\n测试 VirtualLampAdapter:")
    lamp = VirtualLampAdapter(enable_color_output=True)
    
    print("  测试所有颜色:")
    lamp.test_all_colors(duration_per_color=0.5)
    
    print(f"  当前颜色: {lamp.get_current_color()}")
    print(f"  设备状态: {lamp.get_status().name}")
    
    lamp.close()
    
    # 测试聚合器
    print("\n测试 AlarmLevelAggregator:")
    aggregator = AlarmLevelAggregator()
    
    test_cases = [
        ([AlarmLevel.GREEN, AlarmLevel.GREEN], "全部正常"),
        ([AlarmLevel.GREEN, AlarmLevel.YELLOW], "有警告"),
        ([AlarmLevel.GREEN, AlarmLevel.RED], "有违规"),
        ([AlarmLevel.YELLOW, AlarmLevel.RED], "有违规"),
    ]
    
    for levels, description in test_cases:
        result = aggregator.aggregate(levels)
        print(f"  {description}: {[l.name for l in levels]} -> {result.name}")
    
    print("\n" + "=" * 60)
    print("所有自检完成")