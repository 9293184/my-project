"""导出对抗训练数据为模型训练格式"""
import requests
import json
import sys
from pathlib import Path


def export_adversarial_data(
    api_url: str = "http://127.0.0.1:5001/api/adversarial/history",
    output_file: str = "adversarial_training_data.jsonl",
    format_type: str = "openai"
):
    """
    导出对抗训练数据
    
    Args:
        api_url: API 地址
        output_file: 输出文件路径
        format_type: 格式类型 (openai, huggingface)
    """
    print(f"正在从 {api_url} 获取对抗历史...")
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('success'):
            print(f"获取数据失败: {data.get('error')}")
            return
        
        history = data['data']['history']
        print(f"获取到 {len(history)} 条对抗记录")
        
        # 转换为训练格式
        training_data = []
        
        for i, round_data in enumerate(history):
            attack = round_data.get('attack', {})
            defense = round_data.get('defense', {})
            
            attack_text = attack.get('text', '')
            is_attack = defense.get('is_attack', False)
            confidence = defense.get('confidence', 0.5)
            attack_type = attack.get('attack_type', 'unknown')
            
            if not attack_text:
                continue
            
            if format_type == "openai":
                # OpenAI fine-tuning 格式
                sample = {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"请分析以下输入是否为攻击：{attack_text}"
                        },
                        {
                            "role": "assistant",
                            "content": json.dumps({
                                "is_attack": is_attack,
                                "confidence": confidence,
                                "attack_type": attack_type,
                                "reason": defense.get('reason', '')
                            }, ensure_ascii=False)
                        }
                    ]
                }
            elif format_type == "huggingface":
                # HuggingFace 格式
                sample = {
                    "text": attack_text,
                    "label": 1 if is_attack else 0,
                    "attack_type": attack_type,
                    "confidence": confidence
                }
            else:
                # 自定义格式
                sample = {
                    "input": attack_text,
                    "output": {
                        "is_attack": is_attack,
                        "confidence": confidence,
                        "attack_type": attack_type
                    }
                }
            
            training_data.append(sample)
        
        # 保存为 JSONL
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in training_data:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        print(f"✅ 成功导出 {len(training_data)} 条训练样本到 {output_path}")
        
        # 统计信息
        attack_samples = sum(1 for s in training_data 
                           if (s.get('messages', [{}])[1].get('content', '{}') and 
                               json.loads(s['messages'][1]['content']).get('is_attack', False)))
        
        print(f"\n统计信息:")
        print(f"  总样本数: {len(training_data)}")
        print(f"  攻击样本: {attack_samples}")
        print(f"  正常样本: {len(training_data) - attack_samples}")
        print(f"  格式类型: {format_type}")
        
        return output_path
        
    except requests.RequestException as e:
        print(f"❌ 请求失败: {str(e)}")
        return None
    except Exception as e:
        print(f"❌ 导出失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def export_failed_defenses(
    api_url: str = "http://127.0.0.1:5001/api/adversarial/history",
    output_file: str = "failed_defenses.jsonl"
):
    """
    只导出防御失败的样本（用于重点训练）
    """
    print("正在导出防御失败的样本...")
    
    try:
        response = requests.get(api_url)
        data = response.json()
        history = data['data']['history']
        
        # 筛选防御失败的样本
        failed_samples = []
        
        for round_data in history:
            attack = round_data.get('attack', {})
            defense = round_data.get('defense', {})
            
            # 防御失败 = 攻击成功 = 未被识别为攻击
            if not defense.get('is_attack', False):
                attack_text = attack.get('text', '')
                if attack_text:
                    sample = {
                        "messages": [
                            {
                                "role": "user",
                                "content": f"请分析以下输入是否为攻击：{attack_text}"
                            },
                            {
                                "role": "assistant",
                                "content": json.dumps({
                                    "is_attack": True,  # 正确答案应该是 True
                                    "confidence": 0.95,
                                    "attack_type": attack.get('attack_type', 'unknown'),
                                    "reason": "这是一个攻击样本，应该被检测到"
                                }, ensure_ascii=False)
                            }
                        ]
                    }
                    failed_samples.append(sample)
        
        # 保存
        with open(output_file, 'w', encoding='utf-8') as f:
            for sample in failed_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        print(f"✅ 导出 {len(failed_samples)} 条防御失败样本到 {output_file}")
        return output_file
        
    except Exception as e:
        print(f"❌ 导出失败: {str(e)}")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="导出对抗训练数据")
    parser.add_argument("--api-url", default="http://127.0.0.1:5001/api/adversarial/history",
                       help="API 地址")
    parser.add_argument("--output", default="adversarial_training_data.jsonl",
                       help="输出文件路径")
    parser.add_argument("--format", default="openai", choices=["openai", "huggingface", "custom"],
                       help="输出格式")
    parser.add_argument("--failed-only", action="store_true",
                       help="只导出防御失败的样本")
    
    args = parser.parse_args()
    
    if args.failed_only:
        export_failed_defenses(args.api_url, args.output)
    else:
        export_adversarial_data(args.api_url, args.output, args.format)
