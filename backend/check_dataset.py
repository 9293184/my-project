"""检查数据集统计信息"""
import json

dataset_file = "d:/langchain2.0/datasets/public/merged_all_datasets.jsonl"

count = 0
attack_count = 0

with open(dataset_file, 'r', encoding='utf-8') as f:
    for line in f:
        count += 1
        try:
            sample = json.loads(line)
            content = sample['messages'][1]['content']
            data = json.loads(content)
            if data.get('is_attack', False):
                attack_count += 1
        except:
            pass

benign_count = count - attack_count

print(f"总样本数: {count}")
print(f"攻击样本: {attack_count}")
print(f"正常样本: {benign_count}")
print(f"攻击比例: {attack_count/count*100:.1f}%")
print(f"\n数据集位置: {dataset_file}")

# 显示几个样本
print("\n样本预览:")
print("="*60)
with open(dataset_file, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        sample = json.loads(line)
        user_msg = sample['messages'][0]['content']
        print(f"\n样本 {i+1}:")
        print(f"输入: {user_msg[:100]}...")
