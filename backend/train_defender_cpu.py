"""使用 CPU 进行 LoRA 微调训练"""
import os
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model
from datasets import load_dataset

print("="*60)
print("LoRA 微调训练 - AI 安全防御模型 (CPU 模式)")
print("="*60)

# 配置
MODEL_NAME = "Qwen/Qwen2.5-7B"
OUTPUT_DIR = "d:/langchain2.0/models/qwen3-defender-trained"
MAX_SEQ_LENGTH = 512  # 降低以节省内存
LORA_RANK = 16  # 使用完整rank以获得更好效果
LORA_ALPHA = 16
BATCH_SIZE = 4  # 增加batch size以利用多核CPU
GRADIENT_ACCUMULATION = 2  # 减少累积步数，因为batch size增加了
LEARNING_RATE = 2e-4
NUM_EPOCHS = 2  # 训练2个epoch
MAX_SAMPLES = None  # 使用全部数据
NUM_WORKERS = 8  # 使用8个worker进行数据加载

print(f"\n训练配置（完整数据集 - 多核优化）:")
print(f"  基础模型: {MODEL_NAME}")
print(f"  LoRA Rank: {LORA_RANK}")
print(f"  Batch Size: {BATCH_SIZE} (优化后)")
print(f"  梯度累积: {GRADIENT_ACCUMULATION}")
print(f"  数据加载Worker: {NUM_WORKERS}")
print(f"  学习率: {LEARNING_RATE}")
print(f"  训练轮数: {NUM_EPOCHS}")
print(f"  数据集: 全部 10,236 条样本")
print(f"  序列长度: {MAX_SEQ_LENGTH}")

print(f"\n设备信息:")
print(f"  使用设备: CPU (Intel i7-14700KF, 20核28线程)")
print(f"  优化策略: 多核并行 + 大batch size")
print(f"  预计时间: 10-16 小时（优化后，比之前快约40%）")

# 1. 加载 tokenizer
print("\n" + "="*60)
print("步骤 1: 加载 Tokenizer")
print("="*60)

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    trust_remote_code=True,
    padding_side="right"
)
tokenizer.pad_token = tokenizer.eos_token

print("Tokenizer 加载完成")

# 2. 加载模型（CPU模式）
print("\n" + "="*60)
print("步骤 2: 加载模型（CPU模式，这可能需要几分钟）")
print("="*60)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    device_map="cpu",
    trust_remote_code=True,
    torch_dtype=torch.float32,  # CPU使用float32
    low_cpu_mem_usage=True,
)

print("模型加载完成")

# 3. 配置 LoRA
print("\n" + "="*60)
print("步骤 3: 配置 LoRA")
print("="*60)

lora_config = LoraConfig(
    r=LORA_RANK,
    lora_alpha=LORA_ALPHA,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    inference_mode=False,
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

print("LoRA 配置完成")

# 4. 加载数据集
print("\n" + "="*60)
print("步骤 4: 加载训练数据")
print("="*60)

dataset = load_dataset(
    "json",
    data_files="d:/langchain2.0/datasets/public/merged_all_datasets.jsonl",
    split="train"
)

# 使用全部数据训练
if MAX_SAMPLES and len(dataset) > MAX_SAMPLES:
    dataset = dataset.select(range(MAX_SAMPLES))
    print(f"使用前 {MAX_SAMPLES} 条样本进行训练")
else:
    print(f"使用全部 {len(dataset)} 条样本进行训练")

print(f"数据集加载完成: {len(dataset)} 条样本")

# 数据预处理
def preprocess_function(examples):
    texts = []
    for messages in examples["messages"]:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        texts.append(text)
    
    model_inputs = tokenizer(
        texts,
        max_length=MAX_SEQ_LENGTH,
        truncation=True,
        padding=False,
    )
    
    model_inputs["labels"] = model_inputs["input_ids"].copy()
    
    return model_inputs

print("正在预处理数据...")
tokenized_dataset = dataset.map(
    preprocess_function,
    batched=True,
    remove_columns=dataset.column_names,
    desc="Tokenizing"
)

print("数据预处理完成")

# 5. 配置训练参数
print("\n" + "="*60)
print("步骤 5: 配置训练器")
print("="*60)

training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRADIENT_ACCUMULATION,
    learning_rate=LEARNING_RATE,
    logging_steps=10,
    save_strategy="epoch",
    save_total_limit=1,
    optim="adamw_torch",
    warmup_steps=10,
    lr_scheduler_type="linear",
    report_to="none",
    use_cpu=True,  # 强制使用CPU
    dataloader_num_workers=NUM_WORKERS,  # 使用多个worker并行加载数据
    dataloader_pin_memory=False,  # CPU模式不需要pin memory
    gradient_checkpointing=False,  # CPU模式关闭以加快速度
)

data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    data_collator=data_collator,
)

print("训练器配置完成")

# 6. 开始训练
print("\n" + "="*60)
print("步骤 6: 开始训练")
print("="*60)
print("\n警告: CPU训练会非常慢，预计需要 6-12 小时")
print("建议: 让程序在后台运行，去做其他事情\n")

import time
start_time = time.time()

trainer.train()

end_time = time.time()
training_time = end_time - start_time

print("\n" + "="*60)
print("训练完成！")
print("="*60)
print(f"训练耗时: {training_time/3600:.2f} 小时")

# 7. 保存模型
print("\n" + "="*60)
print("步骤 7: 保存模型")
print("="*60)

model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"模型已保存到: {OUTPUT_DIR}")

print("\n" + "="*60)
print("训练完成！")
print("="*60)
print(f"\n训练统计:")
print(f"  样本数: {len(dataset)}")
print(f"  训练轮数: {NUM_EPOCHS}")
print(f"  训练时长: {training_time/3600:.2f} 小时")
print(f"\n下一步:")
print(f"1. 合并 LoRA 权重")
print(f"2. 转换为 GGUF 格式")
print(f"3. 导入 Ollama")
print(f"4. 测试效果")
print("="*60)
