from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 当前目录（laser_distance）
ROOT = Path(__file__).resolve().parent


def run_script(script_name: str, *extra_args: str) -> None:
    """
    用当前虚拟环境的 Python 去运行同目录下的脚本，
    不再依赖脚本里有没有定义 run_xxx() 之类的函数。
    """
    script_path = ROOT / script_name
    cmd = [sys.executable, str(script_path), *extra_args]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lidar / Vision fusion main entry.",
    )
    parser.add_argument(
        "mode",
        choices=["ui", "record", "replay", "analyze", "cli", "test"],
        help=(
            "ui      - start live Flet UI with LIDAR\n"
            "record  - record fusion_log.csv\n"
            "replay  - replay fusion_log.csv in console\n"
            "analyze - print statistics from fusion_log.csv\n"
            "cli     - run terminal fusion demo\n"
            "test    - execute fusion self-tests"
        ),
    )

    args = parser.parse_args()

    if args.mode == "ui":
        # 打开 Flet UI 界面
        run_script("demo/fusion_ui_demo.py")

    elif args.mode == "record":
        # 确保 data 目录存在，然后录制 fusion_log.csv
        (ROOT / "data").mkdir(exist_ok=True)
        run_script("demo/fusion_record_demo.py")

    elif args.mode == "replay":
        # 在终端重放 fusion_log.csv
        run_script("demo/fusion_replay_demo.py")

    elif args.mode == "analyze":
        # 对 fusion_log.csv 做统计分析
        run_script("log/analyze_fusion_log.py")

    elif args.mode == "cli":
        # 只在终端里实时打印融合结果
        run_script("demo/fusion_demo.py")

    elif args.mode == "test":
        # self-test
        run_script("test/test_fusion_logic.py")


if __name__ == "__main__":
    main()