#!/usr/bin/env python3
"""
tools/verify_lidar_adapter.py

验证激光雷达适配器的完整性和功能
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parents[1]))


def check_imports():
    """检查所有必需的导入"""
    print("=" * 70)
    print("检查导入...")
    print("=" * 70)

    checks = []

    # 1. 检查基类
    try:
        from adapters.base.range_base import RangeAdapter, RangeMeasurement
        checks.append(("✓", "基类 RangeAdapter 导入成功"))
    except ImportError as e:
        checks.append(("✗", f"基类导入失败: {e}"))

    # 2. 检查适配器
    try:
        from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter
        checks.append(("✓", "适配器 ToFLidarAdapter 导入成功"))
    except ImportError as e:
        checks.append(("✗", f"适配器导入失败: {e}"))

    # 3. 检查现有激光雷达代码
    try:
        import importlib.util
        lidar_tof_path = Path(__file__).parents[3] / "lidar_distance" / "PythonCode" / "core" / "lidar_tof.py"
        spec = importlib.util.spec_from_file_location("lidar_tof_module", lidar_tof_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module spec from {lidar_tof_path}")
        lidar_tof_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lidar_tof_module)
        ToFLidar = lidar_tof_module.ToFLidar
        checks.append(("✓", f"原有激光雷达代码导入成功"))
        checks.append(("ℹ", f"  路径: {lidar_tof_path}"))
    except Exception as e:
        checks.append(("✗", f"原有激光雷达代码导入失败: {e}"))

    for symbol, msg in checks:
        print(f"  {symbol} {msg}")

    return all(c[0] == "✓" or c[0] == "ℹ" for c in checks)


def check_file_structure():
    """检查文件结构"""
    print("\n" + "=" * 70)
    print("检查文件结构...")
    print("=" * 70)

    root = Path(__file__).parents[1]

    required_files = [
        ("adapters/base/range_base.py", "基类定义"),
        ("adapters/legacy/lidar_tof_adapter.py", "激光雷达适配器"),
        ("tests/test_lidar_adapter.py", "适配器测试"),
        ("docs/LIDAR_ADAPTER_GUIDE.md", "使用指南"),
    ]

    all_exist = True
    for file_path, description in required_files:
        full_path = root / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            print(f"  ✓ {file_path:<45} ({size:>6} bytes) - {description}")
        else:
            print(f"  ✗ {file_path:<45} 缺失!")
            all_exist = False

    return all_exist


def check_adapter_interface():
    """检查适配器接口"""
    print("\n" + "=" * 70)
    print("检查适配器接口...")
    print("=" * 70)

    try:
        from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter
        from adapters.base.range_base import RangeAdapter

        # 检查继承
        if issubclass(ToFLidarAdapter, RangeAdapter):
            print(f"  ✓ ToFLidarAdapter 正确继承自 RangeAdapter")
        else:
            print(f"  ✗ ToFLidarAdapter 未继承 RangeAdapter")
            return False

        # 检查必需方法
        required_methods = [
            'read_measurement',
            'get_range_type',
            'get_status',
            'get_max_range',
            'close'
        ]

        missing_methods = []
        for method in required_methods:
            if hasattr(ToFLidarAdapter, method):
                print(f"  ✓ 方法: {method}")
            else:
                print(f"  ✗ 缺失方法: {method}")
                missing_methods.append(method)

        return len(missing_methods) == 0

    except Exception as e:
        print(f"  ✗ 检查失败: {e}")
        return False


def run_quick_tests():
    """运行快速测试"""
    print("\n" + "=" * 70)
    print("运行快速测试...")
    print("=" * 70)

    try:
        import pytest
        result = pytest.main([
            "tests/test_lidar_adapter.py",
            "-v",
            "--tb=short",
            "-q"
        ])

        if result == 0:
            print("\n  ✓ 所有测试通过!")
            return True
        else:
            print(f"\n  ✗ 测试失败 (退出码: {result})")
            return False

    except ImportError:
        print("  ⚠ pytest 未安装，跳过测试")
        print("    安装: pip3 install pytest")
        return None


def show_usage_example():
    """显示使用示例"""
    print("\n" + "=" * 70)
    print("使用示例")
    print("=" * 70)

    example = '''
from adapters.legacy.lidar_tof_adapter import ToFLidarAdapter

# 方式 1: 基本使用
adapter = ToFLidarAdapter(port="/dev/ttyUSB0")
measurements = adapter.read_measurement()
if measurements:
    m = measurements[0]
    print(f"距离: {m.distance_m:.2f}m")
    print(f"置信度: {m.confidence:.2f}")
adapter.close()

# 方式 2: 上下文管理器（推荐）
with ToFLidarAdapter(port="/dev/ttyUSB0") as adapter:
    measurements = adapter.read_measurement()
    if measurements:
        print(f"距离: {measurements[0].distance_m:.2f}m")
'''
    print(example)


def show_next_steps():
    """显示下一步建议"""
    print("=" * 70)
    print("下一步")
    print("=" * 70)
    print()
    print("1. 硬件测试（需要连接激光雷达）:")
    print("   python3 -m adapters.legacy.lidar_tof_adapter")
    print()
    print("2. 查看详细文档:")
    print("   cat docs/LIDAR_ADAPTER_GUIDE.md")
    print()
    print("3. 集成到应用:")
    print("   参考 docs/LIDAR_ADAPTER_GUIDE.md 的集成部分")
    print()
    print("4. 下一个适配器:")
    print("   - 相机适配器: adapters/legacy/camera_yolo_adapter.py")
    print("   - 融合模块: adapters/legacy/fusion_legacy_adapter.py")
    print()


def main():
    """主函数"""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 18 + "激光雷达适配器验证工具" + " " * 24 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    results = {}

    # 运行所有检查
    results['imports'] = check_imports()
    results['files'] = check_file_structure()
    results['interface'] = check_adapter_interface()
    results['tests'] = run_quick_tests()

    # 显示使用示例
    show_usage_example()

    # 总结
    print("\n" + "=" * 70)
    print("验证总结")
    print("=" * 70)

    status_map = {
        True: "✓ 通过",
        False: "✗ 失败",
        None: "⚠ 跳过"
    }

    for check_name, result in results.items():
        status = status_map.get(result, "? 未知")
        print(f"  {status:<10} {check_name}")

    all_passed = all(r in [True, None] for r in results.values())

    print()
    if all_passed:
        print("  " + "=" * 66)
        print("  🎉 验证成功! 激光雷达适配器已准备就绪!")
        print("  " + "=" * 66)
    else:
        print("  " + "=" * 66)
        print("  ⚠ 发现问题，请检查上述错误信息")
        print("  " + "=" * 66)

    print()
    show_next_steps()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
