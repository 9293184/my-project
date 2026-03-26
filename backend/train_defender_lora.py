"""使用 LoRA 微调防御模型"""
import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import os

print("="*60)
print("开始 LoRA 微调训练 - AI 安全防御模型")
print("="*60)

# 配置
MAX_SEQ_LENGTH = 2048
LORA_RANK = 16
LORA_ALPHA = 16
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 4
LEARNING_RATE = 2e-4
NUM_EPOCHS = 3
OUTPUT_DIR = "d:/langchain2.0/models/qwen3-defender-trained"

print(f"\n训练配置:")
print(f"  LoRA Rank: {LORA_RANK}")
print(f"  Batch Size: {BATCH_SIZE}")
print(f"  梯度累积: {GRADIENT_ACCUMULATION}")
print(f"  学习率: {LEARNING_RATE}")
print(f"  训练轮数: {NUM_EPOCHS}")
print(f"  最大序列长度: {MAX_SEQ_LENGTH}")

# 检查 GPU
print(f"\nGPU 信息:")
print(f"  CUDA 可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  显存: {round(torch.cuda.get_device_properties(0).total_memory/1024**3, 2)} GB")

# 1. 加载基础模型
print("\n" + "="*60)
print("步骤 1: 加载基础模型 (Qwen2.5-7B)")
print("="*60)

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-7B",
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,  # 自动选择
    load_in_4bit=True,  # 4-bit 量化，节省显存
)

print("✓ 模型加载完成")

# 2. 配置 LoRA
print("\n" + "="*60)
print("步骤 2: 配置 LoRA 适配器")
print("="*60)

model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_RANK,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"],
    lora_alpha=LORA_ALPHA,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

print("✓ LoRA 配置完成")

# 3. 加载训练数据
print("\n" + "="*60)
print("步骤 3: 加载训练数据")
print("="*60)

dataset = load_dataset(
    "json",
    data_files="d:/langchain2.0/datasets/public/merged_all_datasets.jsonl",
    split="train"
)

print(f"✓ 数据集加载完成: {len(dataset)} 条样本")

# 数据格式化函数
def formatting_prompts_func(examples):
    texts = []
    for messages in examples["messages"]:
        # 转换为 Qwen 格式
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        texts.append(text)
    return {"text": texts}

# 4. 配置训练器
print("\n" + "="*60)
print("步骤 4: 配置训练器")
print("="*60)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    packing=False,
    formatting_func=formatting_prompts_func,
    args=TrainingArguments(
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        warmup_steps=10,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir=OUTPUT_DIR,
        save_strategy="epoch",
        save_total_limit=2,
        report_to="none",
    ),
)

print("✓ 训练器配置完成")

# 5. 开始训练
print("\n" + "="*60)
print("步骤 5: 开始训练")
print("="*60)
print("\n这可能需要 1-3 小时，请耐心等待...\n")

trainer_stats = trainer.train()

print("\n" + "="*60)
print("训练完成！")
print("="*60)
print(f"训练统计:")
print(f"  总步数: {trainer_stats.global_step}")
print(f"  训练损失: {trainer_stats.training_loss:.4f}")
print(f"  训练时长: {trainer_stats.metrics['train_runtime']:.2f} 秒")

# 6. 保存模型
print("\n" + "="*60)
print("步骤 6: 保存模型")
print("="*60)

# 保存 LoRA 适配器
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"✓ 模型已保存到: {OUTPUT_DIR}")

# 7. 保存合并后的完整模型（可选）
print("\n保存合并后的完整模型...")
model.save_pretrained_merged(
    f"{OUTPUT_DIR}/merged",
    tokenizer,
    save_method="merged_16bit",
)

print(f"✓ 完整模型已保存到: {OUTPUT_DIR}/merged")

print("\n" + "="*60)
print("🎉 训练完成！")
print("="*60)
print(f"\n下一步:")
print(f"1. 转换为 GGUF 格式")
print(f"2. 导入 Ollama")
print(f"3. 测试效果")
print("="*60)
