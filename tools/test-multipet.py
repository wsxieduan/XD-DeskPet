"""test-multipet.py —— 多桌宠：召唤 / 分别控制 / 全部关闭"""
import json, sys, time
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import paths, petlist
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok: fails.append(n)

import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)

# 从干净状态开始
ctl.stop_all_pets()
time.sleep(1.5)
for p in petlist.load_pets():
    petlist.remove_pet(p["id"])
say("清空实例列表")

say("== 1. 召唤 3 只 ==")
# 注意：add_pet 会先 ensure_first()，把 config.json 里原来那只迁成 pet1，
# 所以最终是 1（迁移的）+ 3（新召唤的）= 4 条。第一版测试没算这条，误报了三项。
chars = ["oc/view1", "oc/view2", "whale-girl"]
added = []
for i, ch in enumerate(chars):
    x, y = petlist.free_spot(i + 1)
    p = petlist.add_pet(ch, x, y, 0.8)
    added.append(p["id"])
    ctl.start_pet(p["id"])
    time.sleep(3.0)
pets = petlist.load_pets()
check("列表里 4 条（1 条迁移 + 3 条新召唤）", len(pets) == 4, str([p["id"] for p in pets]))
time.sleep(2)
dfg = petlist.load_pets()
for p in dfg:
    say("   %s %-12s pos=(%s,%s) pid=%s 运行=%s" % (
        p["id"], p.get("character"), p.get("x"), p.get("y"), p.get("pid"), ctl.pet_running(p["id"])))
alive = [p for p in dfg if ctl.pet_running(p["id"])]
check("新召唤的 3 只都在运行", len(alive) == 3, "%d 只" % len(alive))
check("4 条实例位置两两不同", len({(p.get("x"), p.get("y")) for p in dfg}) == 4,
      str(sorted({(p.get("x"), p.get("y")) for p in dfg})))

say()
say("== 2. 单独关掉中间那只 ==")
mid = added[1]
ctl.stop_pet(mid)
time.sleep(1.2)
rest = petlist.load_pets()
states = {p["id"]: ctl.pet_running(p["id"]) for p in rest}
say("   状态: " + str(states))
check("中间那只已关闭", not states.get(mid))
check("另外两只没受影响", sum(1 for v in states.values() if v) == 2)

say()
say("== 3. 单独再拉起来 ==")
ctl.start_pet(mid)
time.sleep(3.0)
check("又起来了", ctl.pet_running(mid), "pid=%s" % (petlist.get_pet(mid) or {}).get("pid"))

say()
say("== 4. 改某一只的形象（只影响它）==")
before = {p["id"]: p.get("character") for p in petlist.load_pets()}
petlist.update_pet(mid, character="oc/view3")
ctl.stop_pet(mid); time.sleep(0.6); ctl.start_pet(mid); time.sleep(3.0)
after = {p["id"]: p.get("character") for p in petlist.load_pets()}
other = added[0]
check("只有那一只换了形象", after[mid] == "oc/view3" and after[other] == before[other],
      "%s -> %s，另一只仍是 %s" % (before[mid], after[mid], after[other]))

say()
say("== 5. 全部关闭 ==")
ctl.stop_all_pets()
time.sleep(1.5)
left = [p["id"] for p in petlist.load_pets() if ctl.pet_running(p["id"])]
check("一只都不剩", not left, str(left))

say()
say("== 6. 移除实例 ==")
n_before = len(petlist.load_pets())
petlist.remove_pet(mid)
check("列表里少了一只", len(petlist.load_pets()) == n_before - 1,
      str([p["id"] for p in petlist.load_pets()]))
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-multipet.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")