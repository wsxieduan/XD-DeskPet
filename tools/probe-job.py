# -*- coding: utf-8 -*-
"""探针：PySide6 的 QRunnable + 信号，到底怎样才能把结果送回主线程。"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QApplication
app = QApplication([])
POOL = QThreadPool()
POOL.setMaxThreadCount(1)


class Job(QRunnable):
    class Sig(QObject):
        done = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn
        self.sig = Job.Sig()

    def run(self):
        self.sig.done.emit(self._fn())


got = []

# 情形 A：不保存引用
def a():
    j = Job(lambda: ("A", time.time()))
    j.sig.done.connect(lambda r: got.append(r))
    POOL.start(j)


# 情形 B：保存引用
KEEP = []
def b():
    j = Job(lambda: ("B", time.time()))
    KEEP.append(j)
    j.sig.done.connect(lambda r: got.append(r))
    POOL.start(j)


a(); b()
end = time.time() + 3
while time.time() < end and len(got) < 2:
    app.processEvents()
    time.sleep(0.02)
print("收到结果:", got)
print("A（不留引用）到达:", any(g[0] == "A" for g in got))
print("B（留引用）到达:", any(g[0] == "B" for g in got))
