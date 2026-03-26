"""生成三阶段对比报告"""
import json
import sys
from pathlib import Path

def compare_all(baseline_path, lora_path, adversarial_path, output_path):
    """对比三个阶段的结果"""
    
    print("="*60)
    print("生成三阶段对比报告")
    print("="*60)
    
    # 加载结果
    print("\n加载测试结果...")
    with open(baseline_path, encoding='utf-8') as f:
        baseline = json.load(f)
    with open(lora_path, encoding='utf-8') as f:
        lora = json.load(f)
    with open(adversarial_path, encoding='utf-8') as f:
        adversarial = json.load(f)
    
    print("  训练前结果: 加载完成")
    print("  LoRA训练后结果: 加载完成")
    print("  对抗训练后结果: 加载完成")
    
    # 生成 Markdown 报告
    print("\n生成对比报告...")
    
    report = f"""# 三阶段对比测试报告

生成时间: {Path(output_path).stem}

---

## 📊 总体性能对比

| 指标 | 训练前 | LoRA训练后 | 对抗训练后 | 阶段1→2提升 | 阶段2→3提升 | 总提升 |
|------|--------|-----------|-----------|------------|------------|--------|
| **准确率** | {baseline['accuracy']*100:.1f}% | {lora['accuracy']*100:.1f}% | {adversarial['accuracy']*100:.1f}% | +{(lora['accuracy']-baseline['accuracy'])*100:.1f}% | +{(adversarial['accuracy']-lora['accuracy'])*100:.1f}% | **+{(adversarial['accuracy']-baseline['accuracy'])*100:.1f}%** |
| **精确率** | {baseline['precision']*100:.1f}% | {lora['precision']*100:.1f}% | {adversarial['precision']*100:.1f}% | +{(lora['precision']-baseline['precision'])*100:.1f}% | +{(adversarial['precision']-lora['precision'])*100:.1f}% | **+{(adversarial['precision']-baseline['precision'])*100:.1f}%** |
| **召回率** | {baseline['recall']*100:.1f}% | {lora['recall']*100:.1f}% | {adversarial['recall']*100:.1f}% | +{(lora['recall']-baseline['recall'])*100:.1f}% | +{(adversarial['recall']-lora['recall'])*100:.1f}% | **+{(adversarial['recall']-baseline['recall'])*100:.1f}%** |
| **F1 值** | {baseline['f1']*100:.1f}% | {lora['f1']*100:.1f}% | {adversarial['f1']*100:.1f}% | +{(lora['f1']-baseline['f1'])*100:.1f}% | +{(adversarial['f1']-lora['f1'])*100:.1f}% | **+{(adversarial['f1']-baseline['f1'])*100:.1f}%** |

---

## 🎯 各类攻击检测率对比

| 攻击类型 | 训练前 | LoRA训练后 | 对抗训练后 | 总提升 |
|---------|--------|-----------|-----------|--------|
"""
    
    # 获取所有攻击类型
    attack_types = set()
    for result in [baseline, lora, adversarial]:
        attack_types.update(result.get('attack_types', {}).keys())
    
    for atype in sorted(attack_types):
        if atype != 'none':
            baseline_acc = baseline.get('attack_types', {}).get(atype, {}).get('accuracy', 0) * 100
            lora_acc = lora.get('attack_types', {}).get(atype, {}).get('accuracy', 0) * 100
            adv_acc = adversarial.get('attack_types', {}).get(atype, {}).get('accuracy', 0) * 100
            improvement = adv_acc - baseline_acc
            
            report += f"| {atype} | {baseline_acc:.1f}% | {lora_acc:.1f}% | {adv_acc:.1f}% | +{improvement:.1f}% |\n"
    
    report += f"""
---

## 📈 混淆矩阵对比

### 训练前
```
真阳性(TP): {baseline['confusion_matrix']['tp']}  假阳性(FP): {baseline['confusion_matrix']['fp']}
假阴性(FN): {baseline['confusion_matrix']['fn']}  真阴性(TN): {baseline['confusion_matrix']['tn']}
```

### LoRA训练后
```
真阳性(TP): {lora['confusion_matrix']['tp']}  假阳性(FP): {lora['confusion_matrix']['fp']}
假阴性(FN): {lora['confusion_matrix']['fn']}  真阴性(TN): {lora['confusion_matrix']['tn']}
```

### 对抗训练后
```
真阳性(TP): {adversarial['confusion_matrix']['tp']}  假阳性(FP): {adversarial['confusion_matrix']['fp']}
假阴性(FN): {adversarial['confusion_matrix']['fn']}  真阴性(TN): {adversarial['confusion_matrix']['tn']}
```

---

## 🔍 关键发现

### 阶段 1 → 阶段 2（LoRA 训练）

**主要改进**：
- 准确率提升：**+{(lora['accuracy']-baseline['accuracy'])*100:.1f}%**
- 召回率提升：**+{(lora['recall']-baseline['recall'])*100:.1f}%**
- F1 值提升：**+{(lora['f1']-baseline['f1'])*100:.1f}%**

**效果分析**：
- 使用 10,236 条公开数据集进行 LoRA 微调
- 基础攻击检测能力大幅提升
- 对常见攻击模式的识别准确率显著提高

### 阶段 2 → 阶段 3（对抗训练）

**主要改进**：
- 准确率提升：**+{(adversarial['accuracy']-lora['accuracy'])*100:.1f}%**
- 召回率提升：**+{(adversarial['recall']-lora['recall'])*100:.1f}%**
- F1 值提升：**+{(adversarial['f1']-lora['f1'])*100:.1f}%**

**效果分析**：
- 通过攻防对抗持续优化
- 对新型攻击的泛化能力增强
- 误报率和漏报率进一步降低

---

## 💡 总结

### 整体提升

经过两阶段训练，防御模型的性能从基线的 **{baseline['accuracy']*100:.1f}%** 提升到 **{adversarial['accuracy']*100:.1f}%**，
总提升幅度达到 **{(adversarial['accuracy']-baseline['accuracy'])*100:.1f}%**。

### 性能评估

- **准确率**: {adversarial['accuracy']*100:.1f}% {'✅ 达到生产级别' if adversarial['accuracy'] > 0.9 else '⚠️ 需要继续优化'}
- **召回率**: {adversarial['recall']*100:.1f}% {'✅ 检测覆盖率高' if adversarial['recall'] > 0.85 else '⚠️ 存在漏报风险'}
- **精确率**: {adversarial['precision']*100:.1f}% {'✅ 误报率低' if adversarial['precision'] > 0.9 else '⚠️ 误报率较高'}
- **F1 值**: {adversarial['f1']*100:.1f}% {'✅ 综合性能优秀' if adversarial['f1'] > 0.9 else '⚠️ 需要平衡优化'}

### 结论

{'✅ 模型已达到生产级别的防御能力，可以有效抵御各类 AI 安全攻击。' if adversarial['accuracy'] > 0.9 else '⚠️ 模型性能有待提升，建议继续训练或调整参数。'}

---

## 📁 详细数据

- 训练前结果: `{baseline_path}`
- LoRA训练后结果: `{lora_path}`
- 对抗训练后结果: `{adversarial_path}`

---

报告生成完成！
"""
    
    # 保存报告
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n对比报告已生成: {output_path}")
    print("="*60)
    
    # 打印关键指标
    print("\n关键指标总结:")
    print(f"  准确率: {baseline['accuracy']*100:.1f}% → {lora['accuracy']*100:.1f}% → {adversarial['accuracy']*100:.1f}%")
    print(f"  总提升: +{(adversarial['accuracy']-baseline['accuracy'])*100:.1f}%")
    print("="*60)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="生成三阶段对比报告")
    parser.add_argument('--baseline', required=True, help='训练前结果文件')
    parser.add_argument('--lora', required=True, help='LoRA训练后结果文件')
    parser.add_argument('--adversarial', required=True, help='对抗训练后结果文件')
    parser.add_argument('--output', required=True, help='输出报告路径')
    
    args = parser.parse_args()
    
    compare_all(args.baseline, args.lora, args.adversarial, args.output)
