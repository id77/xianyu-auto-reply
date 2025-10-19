#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 utils/xianyu_slider_stealth.py 编译为可直接 import 的二进制扩展模块（.pyd/.so）
- 使用 Nuitka 的 --module 模式
- 输出文件放到 utils/ 目录，名称为 xianyu_slider_stealth.<abi>.pyd/.so
- 这样 Python 将优先加载二进制扩展而不是同名 .py
"""

import sys
import subprocess
from pathlib import Path

SRC = Path("utils/xianyu_slider_stealth.py")
OUT_DIR = Path("utils")


def ensure_nuitka():
    try:
        import nuitka  # noqa: F401
        print("✓ Nuitka 已安装")
        return True
    except Exception:
        print("✗ 未检测到 Nuitka。请先允许我安装: pip install nuitka ordered-set zstandard")
        return False


def clean_old_files():
    """清理旧的编译产物"""
    import os
    import glob

    patterns = [
        "utils/xianyu_slider_stealth.*.pyd",
        "utils/xianyu_slider_stealth.*.so",
        "utils/xianyu_slider_stealth.build",
        "utils/xianyu_slider_stealth.dist"
    ]

    for pattern in patterns:
        for file_path in glob.glob(pattern):
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"✓ 已删除旧文件: {file_path}")
                elif os.path.isdir(file_path):
                    import shutil
                    shutil.rmtree(file_path)
                    print(f"✓ 已删除旧目录: {file_path}")
            except Exception as e:
                print(f"⚠️ 无法删除 {file_path}: {e}")


def check_permissions():
    """检查目录权限"""
    try:
        test_file = OUT_DIR / "test_write.tmp"
        test_file.write_text("test")
        test_file.unlink()
        return True
    except Exception as e:
        print(f"✗ 目录权限检查失败: {e}")
        print("💡 请尝试以管理员身份运行此脚本")
        return False


def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 检查权限
    if not check_permissions():
        return 1

    # 清理旧文件
    print("🧹 清理旧的编译产物...")
    clean_old_files()

    cmd = [
        sys.executable, "-m", "nuitka",
        "--module",
        "--output-dir=%s" % str(OUT_DIR),
        "--remove-output",
        "--assume-yes-for-downloads",
        "--show-progress",
        "--python-flag=no_docstrings",
        "--python-flag=no_warnings",
        "--enable-plugin=anti-bloat",
        # 降低内存占用，避免容器内 OOM
        "--lto=no",
        "--jobs=1",
        str(SRC)
    ]

    print("执行编译命令:\n ", " ".join(cmd))
    try:
        result = subprocess.run(cmd, text=True, timeout=300)  # 5分钟超时
        if result.returncode != 0:
            print("✗ 编译失败 (Nuitka 返回非零)")
            print("💡 可能的解决方案:")
            print("   1. 以管理员身份运行此脚本")
            print("   2. 关闭杀毒软件的实时保护")
            print("   3. 检查是否有其他Python进程在运行")
            return 1
    except subprocess.TimeoutExpired:
        print("✗ 编译超时 (5分钟)")
        return 1
    except Exception as e:
        print(f"✗ 编译过程中发生错误: {e}")
        return 1

    # 列出 utils 目录下的产物
    built = sorted(p for p in OUT_DIR.glob("xianyu_slider_stealth.*.pyd"))
    if not built:
        built = sorted(p for p in OUT_DIR.glob("xianyu_slider_stealth.*.so"))
    if not built:
        print("✗ 未找到编译产物。请检查输出日志。")
        return 2

    print("\n✓ 编译产物:")
    for p in built:
        print(" -", p)
    return 0


def main():
    print("🔨 开始编译 xianyu_slider_stealth 模块...")
    print("📁 项目目录:", Path.cwd())

    if not SRC.exists():
        print(f"✗ 源文件不存在: {SRC}")
        return 1

    print(f"📄 源文件: {SRC}")
    print(f"📂 输出目录: {OUT_DIR}")

    if not ensure_nuitka():
        return 2

    # 检查是否以管理员身份运行（Windows）
    import os
    if os.name == 'nt':  # Windows
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                print("⚠️ 建议以管理员身份运行此脚本以避免权限问题")
        except:
            pass

    return build()


if __name__ == "__main__":
    raise SystemExit(main())

