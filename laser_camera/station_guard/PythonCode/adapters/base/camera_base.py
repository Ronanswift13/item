"""
adapters/base/camera_base.py

相机适配器抽象基类定义

所有视觉传感器（USB摄像头、RTSP网络摄像头、深度相机等）
必须实现此接口才能接入系统核心。

核心设计原则：
1. 适配器负责硬件访问和人员检测
2. 输出标准化的 CameraDetection 数据结构
3. 内核不需要知道具体使用的是什么硬件或检测算法
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


@dataclass
class CameraDetection:
    """
    单个人员检测结果的标准化表示
    
    这是相机适配器与系统核心之间的数据契约。
    无论底层使用 YOLO、SSD、还是其他检测算法，都必须转换为此格式。
    
    Attributes:
        track_id: 跟踪ID（由检测器分配，用于多帧关联）
        bbox: 边界框 (x1, y1, x2, y2) 像素坐标
        footpoint_u: 脚点的u坐标（像素），通常是边界框底边中心
        footpoint_v: 脚点的v坐标（像素），通常是边界框底边
        confidence: 检测置信度 [0.0, 1.0]
        timestamp: 检测时间戳（Unix时间，秒）
        person_id: 可选的人员身份标识（用于授权检查）
    """
    track_id: int
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    footpoint_u: float
    footpoint_v: float
    confidence: float
    timestamp: float
    person_id: Optional[str] = None  # 可选：人脸识别或工牌识别的结果
    
    def bbox_width(self) -> float:
        """边界框宽度（像素）"""
        return self.bbox[2] - self.bbox[0]
    
    def bbox_height(self) -> float:
        """边界框高度（像素）"""
        return self.bbox[3] - self.bbox[1]
    
    def bbox_area(self) -> float:
        """边界框面积（像素²）"""
        return self.bbox_width() * self.bbox_height()
    
    def bbox_center(self) -> tuple[float, float]:
        """边界框中心点 (u, v) 像素坐标"""
        return (
            (self.bbox[0] + self.bbox[2]) / 2,
            (self.bbox[1] + self.bbox[3]) / 2
        )


class CameraStatus(Enum):
    """相机运行状态"""
    READY = "ready"              # 就绪，正常运行
    INITIALIZING = "initializing"  # 初始化中
    DISCONNECTED = "disconnected"  # 断开连接
    ERROR = "error"              # 错误状态
    STOPPED = "stopped"          # 已停止


class CameraAdapter(ABC):
    """
    相机适配器抽象基类
    
    所有具体的相机实现（YOLOCameraAdapter, RTSPCameraAdapter等）
    必须继承此类并实现所有抽象方法。
    
    使用示例：
        camera = YOLOCameraAdapter(config)
        
        try:
            while True:
                detections = camera.read_frame()
                if detections:
                    for det in detections:
                        print(f"Person {det.track_id} at ({det.footpoint_u}, {det.footpoint_v})")
        finally:
            camera.close()
    """
    
    @abstractmethod
    def read_frame(self) -> Optional[List[CameraDetection]]:
        """
        读取并处理一帧图像，返回检测到的所有人员
        
        此方法应该：
        1. 从相机获取一帧图像
        2. 运行人员检测算法
        3. 将检测结果转换为 CameraDetection 格式
        4. 计算脚点坐标（通常是边界框底边中心）
        
        Returns:
            检测到的人员列表，如果读取失败返回 None
            空列表表示成功读取但未检测到人员
        
        注意：
            - 此方法应该是非阻塞的或有合理的超时
            - 如果连续多次返回 None，调用者应检查相机状态
        """
        pass
    
    @abstractmethod
    def get_image_dimensions(self) -> tuple[int, int]:
        """
        获取图像尺寸
        
        Returns:
            (width, height) 图像分辨率（像素）
        
        注意：
            - 投影器需要此信息进行像素到米的转换
            - 应该返回实际处理的图像尺寸（可能与原始分辨率不同）
        """
        pass
    
    @abstractmethod
    def get_status(self) -> CameraStatus:
        """
        获取相机当前状态
        
        Returns:
            CameraStatus 枚举值
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """
        释放相机资源
        
        应该释放：
        - 相机设备句柄
        - 检测模型占用的内存
        - 网络连接（如果是RTSP）
        """
        pass
    
    # 可选方法：高级功能
    
    def get_frame_rate(self) -> float:
        """
        获取实际帧率
        
        Returns:
            当前平均帧率（FPS），如果无法计算返回 0.0
        """
        return 0.0
    
    def set_detection_threshold(self, threshold: float) -> None:
        """
        设置检测置信度阈值
        
        Args:
            threshold: 置信度阈值 [0.0, 1.0]，低于此值的检测将被过滤
        
        注意：
            - 不是所有适配器都需要支持此功能
            - 默认实现为空操作
        """
        pass
    
    def get_raw_frame(self) -> Optional[object]:
        """
        获取原始图像帧（用于调试和可视化）
        
        Returns:
            原始图像对象（通常是 numpy array），如果不支持返回 None
        
        注意：
            - 这是可选功能，主要用于UI显示
            - 返回类型故意设为 object 以支持不同的图像格式
        """
        return None
    
    def __enter__(self):
        """支持上下文管理器协议"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议"""
        self.close()


# 工具函数：检测结果验证

def validate_detection(detection: CameraDetection, 
                       image_width: int, 
                       image_height: int) -> tuple[bool, str]:
    """
    验证检测结果的有效性
    
    Args:
        detection: 待验证的检测结果
        image_width: 图像宽度（像素）
        image_height: 图像高度（像素）
    
    Returns:
        (is_valid, error_message)
    """
    # 检查置信度范围
    if not (0.0 <= detection.confidence <= 1.0):
        return False, f"Invalid confidence: {detection.confidence}"
    
    # 检查边界框坐标
    x1, y1, x2, y2 = detection.bbox
    if x1 >= x2 or y1 >= y2:
        return False, f"Invalid bbox: ({x1}, {y1}, {x2}, {y2})"
    
    # 检查边界框是否在图像范围内
    if not (0 <= x1 < image_width and 0 <= x2 <= image_width):
        return False, f"Bbox x coordinates out of range: ({x1}, {x2})"
    if not (0 <= y1 < image_height and 0 <= y2 <= image_height):
        return False, f"Bbox y coordinates out of range: ({y1}, {y2})"
    
    # 检查脚点坐标
    if not (0 <= detection.footpoint_u <= image_width):
        return False, f"Footpoint u out of range: {detection.footpoint_u}"
    if not (0 <= detection.footpoint_v <= image_height):
        return False, f"Footpoint v out of range: {detection.footpoint_v}"
    
    # 检查脚点是否在边界框内或附近
    if not (x1 - 5 <= detection.footpoint_u <= x2 + 5):
        return False, f"Footpoint u not aligned with bbox"
    if not (y2 - 5 <= detection.footpoint_v <= y2 + 5):
        return False, f"Footpoint v not at bbox bottom"
    
    return True, ""


def compute_footpoint_from_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    """
    从边界框计算脚点坐标（通用辅助函数）
    
    Args:
        bbox: (x1, y1, x2, y2) 边界框
    
    Returns:
        (u, v) 脚点坐标（边界框底边中心）
    """
    x1, y1, x2, y2 = bbox
    footpoint_u = (x1 + x2) / 2.0
    footpoint_v = y2
    return footpoint_u, footpoint_v


if __name__ == "__main__":
    # 模块自检
    print("=" * 60)
    print("Camera Adapter Base - 模块自检")
    print("=" * 60)
    
    # 测试数据结构
    print("\n测试 CameraDetection 数据类:")
    det = CameraDetection(
        track_id=1,
        bbox=(100, 200, 200, 400),
        footpoint_u=150,
        footpoint_v=400,
        confidence=0.95,
        timestamp=1234567890.0
    )
    print(f"  Track ID: {det.track_id}")
    print(f"  Bbox: {det.bbox}")
    print(f"  Footpoint: ({det.footpoint_u}, {det.footpoint_v})")
    print(f"  Bbox size: {det.bbox_width():.0f} x {det.bbox_height():.0f} px")
    print(f"  Confidence: {det.confidence:.2f}")
    
    # 测试验证函数
    print("\n测试检测结果验证:")
    is_valid, msg = validate_detection(det, 1920, 1080)
    print(f"  Valid: {is_valid}")
    if not is_valid:
        print(f"  Error: {msg}")
    
    # 测试脚点计算
    print("\n测试脚点计算:")
    bbox = (100, 200, 200, 400)
    u, v = compute_footpoint_from_bbox(bbox)
    print(f"  Bbox: {bbox}")
    print(f"  Footpoint: ({u}, {v})")
    
    print("\n" + "=" * 60)
    print("所有自检完成")