"""
Google Colab LoRA 微调训练脚本
使用免费 T4 GPU 进行训练
"""

# ============================================================
# 步骤 1: 安装依赖（在 Colab 中运行）
# ============================================================
print("安装依赖包...")
import subprocess
import sys

packages = [
    "transformers",
    "peft",
    "datasets",
    "accelerate",
    "bitsandbytes",
    "trl"
]

for package in packages:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])

print("依赖安装完成！")

# ============================================================
# 步骤 2: 导入库
# ============================================================
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset
import os

print("="*60)
print("LoRA 微调训练 - AI 安全防御模型")
print("Google Colab GPU 训练")
print("="*60)

# ============================================================
# 步骤 3: 配置
# ============================================================
MODEL_NAME = "Qwen/Qwen2.5-7B"
OUTPUT_DIR = "./qwen3-defender-trained"
MAX_SEQ_LENGTH = 1024
LORA_RANK = 16
LORA_ALPHA = 16
BATCH_SIZE = 4  # T4 GPU 可以使用更大的 batch size
GRADIENT_ACCUMULATION = 2
LEARNING_RATE = 2e-4
NUM_EPOCHS = 3

print(f"\n训练配置:")
print(f"  基础模型: {MODEL_NAME}")
print(f"  LoRA Rank: {LORA_RANK}")
print(f"  Batch Size: {BATCH_SIZE}")
print(f"  梯度累积: {GRADIENT_ACCUMULATION}")
print(f"  学习率: {LEARNING_RATE}")
print(f"  训练轮数: {NUM_EPOCHS}")
print(f"  序列长度: {MAX_SEQ_LENGTH}")

# 检查 GPU
if torch.cuda.is_available():
    print(f"\nGPU 信息:")
    print(f"  设备: {torch.cuda.get_device_name(0)}")
    print(f"  显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
else:
    print("\n警告: 未检测到 GPU，将使用 CPU（非常慢）")

# ============================================================
# 步骤 4: 加载 Tokenizer
# ============================================================
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

# ============================================================
# 步骤 5: 加载模型（8-bit 量化）
# ============================================================
print("\n" + "="*60)
print("步骤 2: 加载模型（8-bit 量化）")
print("="*60)

quantization_config = BitsAndBytesConfig(
    load_in_8bit=True,
    llm_int8_threshold=6.0,
    llm_int8_has_fp16_weight=False,
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=quantization_config,
    device_map="auto",
    trust_remote_code=True,
    torch_dtype=torch.float16,
)

print("模型加载完成")

# ============================================================
# 步骤 6: 准备模型用于训练
# ============================================================
model = prepare_model_for_kbit_training(model)

# ============================================================
# 步骤 7: 配置 LoRA
# ============================================================
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

# ============================================================
# 步骤 8: 加载数据集
# ============================================================
print("\n" + "="*60)
print("步骤 4: 加载训练数据")
print("="*60)

# 从上传的文件加载数据
# 注意: 需要先在 Colab 中上传 merged_all_datasets.jsonl
dataset = load_dataset(
    "json",
    data_files="merged_all_datasets.jsonl",
    split="train"
)

print(f"数据集加载完成: {len(dataset)} 条样本")

# ============================================================
# 步骤 9: 数据预处理
# ============================================================
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

# ============================================================
# 步骤 10: 配置训练参数
# ============================================================
print("\n" + "="*60)
print("步骤 5: 配置训练器")
print("="*60)

training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRADIENT_ACCUMULATION,
    learning_rate=LEARNING_RATE,
    logging_steps=50,
    save_strategy="epoch",
    save_total_limit=2,
    optim="adamw_torch",
    warmup_steps=100,
    lr_scheduler_type="cosine",
    fp16=True,  # 使用混合精度训练
    report_to="none",
    gradient_checkpointing=True,  # 节省显存
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

# ============================================================
# 步骤 11: 开始训练
# ============================================================
print("\n" + "="*60)
print("步骤 6: 开始训练")
print("="*60)
print("\n使用 GPU 训练，预计 2-3 小时完成\n")

import time
start_time = time.time()

trainer.train()

end_time = time.time()
training_time = end_time - start_time

print("\n" + "="*60)
print("训练完成！")
print("="*60)
print(f"训练耗时: {training_time/3600:.2f} 小时")

# ============================================================
# 步骤 12: 保存模型
# ============================================================
print("\n" + "="*60)
print("步骤 7: 保存模型")
print("="*60)

model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"模型已保存到: {OUTPUT_DIR}")

# ============================================================
# 步骤 13: 打包模型以供下载
# ============================================================
print("\n" + "="*60)
print("步骤 8: 打包模型")
print("="*60)

import shutil
shutil.make_archive("qwen3-defender-trained", "zip", OUTPUT_DIR)

print("模型已打包为: qwen3-defender-trained.zip")
print("请从 Colab 文件浏览器中下载此文件")

print("\n" + "="*60)
print("全部完成！")
print("="*60)
print(f"\n训练统计:")
print(f"  样本数: {len(dataset)}")
print(f"  训练轮数: {NUM_EPOCHS}")
print(f"  训练时长: {training_time/3600:.2f} 小时")
print(f"\n下一步:")
print(f"1. 下载 qwen3-defender-trained.zip")
print(f"2. 解压到本地")
print(f"3. 转换为 GGUF 格式")
print(f"4. 导入 Ollama")
print(f"5. 测试效果")
print("="*60)
