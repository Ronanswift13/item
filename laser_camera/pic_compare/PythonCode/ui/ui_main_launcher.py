#!/usr/bin/env python3
"""
ui_main_launcher.py

Simple text menu to launch different vision safety demos:

1) Live vision safety UI (ui_vision_safety.py)
2) CLI motion + yellow-line demo (demo_motion_line.py)
3) Analyze vision_log.csv (analyze_vision_log.py)
"""

from pathlib import Path
import subprocess
import sys


def run_script(relative_path: str) -> None:
    """
    Run another Python script located inside the PythonCode tree.

    relative_path: path relative to the PythonCode root, e.g. "ui/ui_vision_safety.py".
    """
    # Locate project root: .../pic_compare/PythonCode
    current_file = Path(__file__).resolve()
    python_code_root = current_file.parent.parent

    script_path = python_code_root / relative_path
    if not script_path.exists():
        print(f"[ERROR] Script not found: {script_path}")
        return

    print(f"[INFO] Running: {script_path}")
    # Use the same Python interpreter that runs this launcher
    cmd = [sys.executable, str(script_path)]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Script exited with non-zero code: {e.returncode}")


def main_menu() -> None:
    while True:
        print("\n=== Vision Safety Launcher ===")
        print("1) Live vision safety UI")
        print("2) CLI motion + yellow-line demo")
        print("3) Analyze vision_log.csv")
        print("q) Quit")
        choice = input("Select option: ").strip().lower()

        if choice == "1":
            # UI script: /PythonCode/ui/ui_vision_safety.py
            run_script("ui/ui_vision_safety.py")
        elif choice == "2":
            # CLI demo: /PythonCode/demo/demo_motion_line.py
            # If your demo file name is different (e.g. demo_motion_line_record.py),
            # adjust the relative path here.
            run_script("demo/demo_motion_line.py")
        elif choice == "3":
            # Log analysis script: /PythonCode/demo/analyze_vision_log.py
            run_script("demo/analyze_vision_log.py")
        elif choice == "q":
            print("Bye.")
            break
        else:
            print("Invalid choice, please try again.")


if __name__ == "__main__":
    main_menu()
