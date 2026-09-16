# -*- coding: utf-8 -*-
"""make-sounds.py —— 生成随包内置的互动音效（assets/sounds/*.wav）。

为什么是程序生成而不是找素材：零版权风险、体积可控（每个几十 KB）、
而且都是"短促的电子音"，比随便下载的音效更统一。

为什么只做 WAV：播放用的是 winsound.PlaySound，它只认 WAV。
换 QtMultimedia 能支持 MP3，但要额外背 ~10MB 的媒体模块，和轻量化目标冲突
（阿酉需求卡：v1 只收 WAV，把格式要求写在控制台文案里）。
"""
import math, os, struct, sys, wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"
RATE = 22050


def write(name, samples):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    data = bytearray()
    for s in samples:
        v = max(-1.0, min(1.0, s))
        data += struct.pack("<h", int(v * 30000))
    with wave.open(str(p), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(bytes(data))
    return p, len(samples) / RATE


def env(i, n, attack=0.01, power=1.6):
    a = max(1, int(n * attack))
    if i < a:
        return i / a
    return max(0.0, 1 - (i - a) / max(1, n - a)) ** power


def boop(ms=120):
    n = RATE * ms // 1000
    out = []
    for i in range(n):
        t = i / RATE
        f = 900 + 700 * (t / (ms / 1000))
        out.append(0.42 * env(i, n) * math.sin(2 * math.pi * f * t))
    return out


def pop(ms=70):
    n = RATE * ms // 1000
    out = []
    for i in range(n):
        t = i / RATE
        # 一点点噪声感 + 低频"啵"
        noise = math.sin(2 * math.pi * 1700 * t) * 0.25 + math.sin(2 * math.pi * 2300 * t) * 0.15
        low = math.sin(2 * math.pi * (420 - 260 * t / (ms / 1000)) * t)
        out.append(0.5 * env(i, n, 0.005, 2.2) * (low + noise))
    return out


def bell(ms=520):
    n = RATE * ms // 1000
    out = []
    for i in range(n):
        t = i / RATE
        s = (math.sin(2 * math.pi * 1318 * t) * 0.5
             + math.sin(2 * math.pi * 1976 * t) * 0.28
             + math.sin(2 * math.pi * 2637 * t) * 0.14)
        out.append(0.42 * env(i, n, 0.004, 2.6) * s)
    return out


def chirp(ms=260):
    """两声上滑：像小动物叫一下（合成得干净、不吓人）"""
    out = []
    for k, (f0, f1, dur) in enumerate(((680, 1180, 0.11), (900, 1500, 0.13))):
        n = int(RATE * dur)
        for i in range(n):
            t = i / RATE
            f = f0 + (f1 - f0) * (t / dur)
            out.append(0.4 * env(i, n, 0.02, 1.8) * math.sin(2 * math.pi * f * t))
        out += [0.0] * int(RATE * 0.03)
    return out


def boing(ms=300):
    """弹簧：先掉下去再弹回来"""
    n = RATE * ms // 1000
    out = []
    for i in range(n):
        t = i / RATE
        k = t / (ms / 1000)
        f = 300 + 900 * (k ** 2)
        out.append(0.4 * env(i, n, 0.005, 1.4) * math.sin(2 * math.pi * f * t))
    return out


def main():
    made = []
    for name, fn in (("boop.wav", boop), ("pop.wav", pop), ("bell.wav", bell),
                     ("chirp.wav", chirp), ("boing.wav", boing)):
        p, secs = write(name, fn())
        made.append("%s %.0fKB %.2fs" % (name, p.stat().st_size / 1024, secs))
    print("内置音效 -> %s" % OUT)
    for m in made:
        print("   " + m)


main()
