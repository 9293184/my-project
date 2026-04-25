"""从真实下载的数据集提取样本，生成批量测试预设 JSON"""
import csv, json, random
from pathlib import Path

OUT = Path("d:/langchain2.0/datasets/batch_presets.json")
random.seed(42)

presets = {}

# ── 1. AdvBench (harmful_behaviors.csv) ──────────────────────────────
print("读取 AdvBench...")
advbench = []
try:
    with open("d:/langchain2.0/datasets/advbench_raw.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"  总共 {len(rows)} 条")
    # 随机抽取代表性样本
    for r in rows:
        goal = r.get("goal") or r.get("behavior") or list(r.values())[0]
        advbench.append({"text": goal.strip(), "expected": "attack", "source": "AdvBench"})
    presets["advbench"] = advbench
    print(f"  抽取 {len(advbench)} 条 ✓")
except Exception as e:
    print(f"  AdvBench 读取失败: {e}")

# ── 2. XSTest (xstest_prompts.csv) ───────────────────────────────────
print("读取 XSTest...")
xstest_safe, xstest_unsafe = [], []
try:
    with open("d:/langchain2.0/datasets/xstest_raw.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"  总共 {len(rows)} 条")
    for r in rows:
        prompt = r.get("prompt", "").strip()
        typ = r.get("type", "")
        if not prompt:
            continue
        if typ.startswith("contrast_"):  # unsafe prompts
            xstest_unsafe.append({"text": prompt, "expected": "attack", "source": "XSTest"})
        else:  # safe prompts
            xstest_safe.append({"text": prompt, "expected": "safe", "source": "XSTest"})

    # 各取30条
    presets["xstest_safe"]   = xstest_safe
    presets["xstest_unsafe"] = xstest_unsafe
    print(f"  安全样本 {len(xstest_safe)} → 抽取 {len(presets['xstest_safe'])} ✓")
    print(f"  不安全样本 {len(xstest_unsafe)} → 抽取 {len(presets['xstest_unsafe'])} ✓")
except Exception as e:
    print(f"  XSTest 读取失败: {e}")

# ── 3. deepset/prompt-injections (parquet via pandas) ────────────────
print("读取 deepset/prompt-injections...")
try:
    import pandas as pd
    df = pd.read_parquet("d:/langchain2.0/datasets/deepset_injection.parquet")
    print(f"  总共 {len(df)} 条, 列: {list(df.columns)}")
    label_col = "label" if "label" in df.columns else df.columns[-1]
    text_col  = "text"  if "text"  in df.columns else df.columns[0]
    attack_rows  = df[df[label_col] == 1][text_col].tolist()
    normal_rows  = df[df[label_col] == 0][text_col].tolist()
    presets["deepset_attack"] = [
        {"text": str(t).strip(), "expected": "attack", "source": "deepset/prompt-injections"}
        for t in attack_rows
    ]
    presets["deepset_normal"] = [
        {"text": str(t).strip(), "expected": "safe", "source": "deepset/prompt-injections"}
        for t in normal_rows
    ]
    print(f"  攻击 {len(attack_rows)} → 抽取 {len(presets['deepset_attack'])} ✓")
    print(f"  正常 {len(normal_rows)} → 抽取 {len(presets['deepset_normal'])} ✓")
except Exception as e:
    print(f"  deepset 读取失败: {e}")

# ── 4. 汇总统计 ───────────────────────────────────────────────────────
total = sum(len(v) for v in presets.values())
print(f"\n总计 {total} 条样本，{len(presets)} 个预设集")
for k, v in presets.items():
    print(f"  {k}: {len(v)} 条")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(presets, f, ensure_ascii=False, indent=2)
print(f"\n已保存: {OUT}")

# 打印几条样本预览
print("\n=== 样本预览 ===")
for k, items in presets.items():
    if items:
        print(f"[{k}] {items[0]['text'][:80]}")
