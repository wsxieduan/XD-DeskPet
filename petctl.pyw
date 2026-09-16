"""petctl.pyw —— 双击启动器（保持这个文件名，桌面快捷方式指向它）

真正的代码在 petctl.py，这样打包时可以直接 import。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import petctl

# 精简版：把 AI 相关文案换成用户能看懂的说法
if petctl.paths.is_lite():
    petctl.LITE_MODE = True

if __name__ == "__main__":
    sys.exit(petctl.main())