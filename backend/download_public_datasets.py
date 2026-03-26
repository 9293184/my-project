"""下载公开的AI安全数据集"""
from datasets import load_dataset
import json
from pathlib import Path


def download_prompt_injection_datasets():
    """下载多个提示词注入数据集"""
    
    datasets_info = [
        {
            "name": "yanismiraoui/prompt_injections",
            "description": "1000+ 多语言提示词注入样本",
            "output": "prompt_injections.jsonl"
        },
        {
            "name": "xTRam1/safe-guard-prompt-injection",
            "description": "3000 个合成攻击样本",
            "output": "safe_guard_injection.jsonl"
        },
        {
            "name": "Mindgard/evaded-prompt-injection-and-jailbreak-samples",
            "description": "绕过检测的注入和越狱样本",
            "output": "evaded_samples.jsonl"
        },
        {
            "name": "reshabhs/SPML_Chatbot_Prompt_Injection",
            "description": "聊天机器人注入攻击数据集",
            "output": "chatbot_injection.jsonl"
        }
    ]
    
    output_dir = Path("d:/langchain2.0/datasets/public")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_samples = []
    
    for ds_info in datasets_info:
        print(f"\n{'='*60}")
        print(f"正在下载: {ds_info['name']}")
        print(f"描述: {ds_info['description']}")
        print(f"{'='*60}")
        
        try:
            # 下载数据集
            dataset = load_dataset(ds_info['name'], split='train')
            print(f"成功加载 {len(dataset)} 条数据")
            
            # 转换为训练格式
            samples = convert_to_training_format(dataset, ds_info['name'])
            
            # 保存单个数据集
            output_file = output_dir / ds_info['output']
            with open(output_file, 'w', encoding='utf-8') as f:
                for sample in samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + '\n')
            
            print(f"已保存到: {output_file}")
            print(f"样本数: {len(samples)}")
            
            all_samples.extend(samples)
            
        except Exception as e:
            print(f"下载失败: {str(e)}")
            continue
    
    # 保存合并的数据集
    if all_samples:
        merged_file = output_dir / "merged_all_datasets.jsonl"
        with open(merged_file, 'w', encoding='utf-8') as f:
            for sample in all_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        print(f"\n{'='*60}")
        print(f"所有数据集已合并")
        print(f"保存到: {merged_file}")
        print(f"总样本数: {len(all_samples)}")
        print(f"{'='*60}")
        
        return merged_file
    
    return None


def convert_to_training_format(dataset, dataset_name):
    """将不同格式的数据集转换为统一的训练格式"""
    samples = []
    
    for item in dataset:
        try:
            # 根据不同数据集的结构提取内容
            if dataset_name == "yanismiraoui/prompt_injections":
                # 这个数据集只有一列 prompt
                prompt = item.get('prompt', '') or item.get('text', '')
                if prompt:
                    sample = {
                        "messages": [
                            {
                                "role": "user",
                                "content": f"请分析以下输入是否为攻击：{prompt}"
                            },
                            {
                                "role": "assistant",
                                "content": json.dumps({
                                    "is_attack": True,
                                    "confidence": 0.95,
                                    "attack_type": "prompt_injection",
                                    "reason": "这是一个提示词注入攻击样本"
                                }, ensure_ascii=False)
                            }
                        ]
                    }
                    samples.append(sample)
            
            elif dataset_name == "xTRam1/safe-guard-prompt-injection":
                # 这个数据集有 prompt 和 label
                prompt = item.get('prompt', '') or item.get('text', '')
                label = item.get('label', 1)  # 1 = 攻击, 0 = 正常
                
                if prompt:
                    sample = {
                        "messages": [
                            {
                                "role": "user",
                                "content": f"请分析以下输入是否为攻击：{prompt}"
                            },
                            {
                                "role": "assistant",
                                "content": json.dumps({
                                    "is_attack": bool(label),
                                    "confidence": 0.95 if label else 0.9,
                                    "attack_type": "prompt_injection" if label else "none",
                                    "reason": "提示词注入攻击" if label else "正常输入"
                                }, ensure_ascii=False)
                            }
                        ]
                    }
                    samples.append(sample)
            
            elif dataset_name == "Mindgard/evaded-prompt-injection-and-jailbreak-samples":
                # 绕过检测的样本
                prompt = item.get('prompt', '') or item.get('text', '') or item.get('evaded_prompt', '')
                attack_type = item.get('type', 'jailbreak')
                
                if prompt:
                    sample = {
                        "messages": [
                            {
                                "role": "user",
                                "content": f"请分析以下输入是否为攻击：{prompt}"
                            },
                            {
                                "role": "assistant",
                                "content": json.dumps({
                                    "is_attack": True,
                                    "confidence": 0.98,
                                    "attack_type": attack_type,
                                    "reason": f"这是一个经过混淆的{attack_type}攻击，使用了规避技术"
                                }, ensure_ascii=False)
                            }
                        ]
                    }
                    samples.append(sample)
            
            else:
                # 通用处理
                # 尝试从常见字段提取
                prompt = (item.get('prompt') or 
                         item.get('text') or 
                         item.get('input') or 
                         item.get('user_prompt') or '')
                
                if prompt:
                    sample = {
                        "messages": [
                            {
                                "role": "user",
                                "content": f"请分析以下输入是否为攻击：{prompt}"
                            },
                            {
                                "role": "assistant",
                                "content": json.dumps({
                                    "is_attack": True,
                                    "confidence": 0.9,
                                    "attack_type": "unknown",
                                    "reason": "检测到潜在的攻击行为"
                                }, ensure_ascii=False)
                            }
                        ]
                    }
                    samples.append(sample)
        
        except Exception as e:
            print(f"警告: 转换样本失败: {str(e)}")
            continue
    
    return samples


def add_benign_samples(output_file, num_samples=1000):
    """添加正常样本以平衡数据集"""
    
    benign_prompts = [
        "你好，请问今天天气怎么样？",
        "帮我写一个Python排序算法",
        "什么是机器学习？",
        "请推荐几本好书",
        "如何学习编程？",
        "解释一下什么是区块链",
        "帮我翻译这段英文",
        "写一首关于春天的诗",
        "推荐一些健康食谱",
        "如何提高工作效率？",
        "介绍一下人工智能的发展历史",
        "帮我分析这段代码的问题",
        "什么是深度学习？",
        "如何保持身体健康？",
        "推荐一些旅游景点",
    ]
    
    samples = []
    for i in range(num_samples):
        prompt = benign_prompts[i % len(benign_prompts)]
        sample = {
            "messages": [
                {
                    "role": "user",
                    "content": f"请分析以下输入是否为攻击：{prompt}"
                },
                {
                    "role": "assistant",
                    "content": json.dumps({
                        "is_attack": False,
                        "confidence": 0.95,
                        "attack_type": "none",
                        "reason": "这是一个正常的用户请求"
                    }, ensure_ascii=False)
                }
            ]
        }
        samples.append(sample)
    
    # 追加到文件
    with open(output_file, 'a', encoding='utf-8') as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    
    print(f"已添加 {num_samples} 条正常样本")


if __name__ == "__main__":
    print("开始下载公开的AI安全数据集...")
    print("这可能需要几分钟时间...\n")
    
    merged_file = download_prompt_injection_datasets()
    
    if merged_file:
        print("\n添加正常样本以平衡数据集...")
        add_benign_samples(merged_file, num_samples=2000)
        
        print("\n" + "="*60)
        print("数据集准备完成！")
        print(f"文件位置: {merged_file}")
        print("\n下一步:")
        print("1. 查看数据集内容")
        print("2. 使用数据集训练模型")
        print("="*60)
