"""
Google Colab 训练脚本 - 使用 Abliterated 模型
模型: Qwen2.5-32B-Instruct-abliterated (无限制版本)
"""

print("="*60)
print("安装依赖包...")
print("="*60)

import subprocess
import sys

packages = ["transformers", "peft", "datasets", "accelerate", "bitsandbytes", "trl"]
for pkg in packages:
    print(f"安装 {pkg}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

print("\n依赖安装完成！\n")

# 导入库
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

print("="*60)
print("LoRA 微调训练 - AI 安全防御模型")
print("使用 Abliterated 模型（无限制版本）")
print("="*60)

# 配置
MODEL_NAME = "Qwen2.5-32B-Instruct-abliterated"  # 使用 abliterated 模型
OUTPUT_DIR = "./qwen-defender-abliterated-trained"
MAX_SEQ_LENGTH = 1024
LORA_RANK = 16
LORA_ALPHA = 16
BATCH_SIZE = 2  # 32B 模型较大，减小 batch size
GRADIENT_ACCUMULATION = 4
LEARNING_RATE = 2e-4
NUM_EPOCHS = 3

print(f"\n训练配置:")
print(f"  基础模型: {MODEL_NAME}")
print(f"  模型类型: Abliterated (无限制)")
print(f"  LoRA Rank: {LORA_RANK}")
print(f"  Batch Size: {BATCH_SIZE}")
print(f"  梯度累积: {GRADIENT_ACCUMULATION}")
print(f"  学习率: {LEARNING_RATE}")
print(f"  训练轮数: {NUM_EPOCHS}")
print(f"  序列长度: {MAX_SEQ_LENGTH}")

# 检查 GPU
print(f"\n设备信息:")
if torch.cuda.is_available():
    print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
else:
    print("  警告: 未检测到 GPU")

# 加载 Tokenizer
print("\n" + "="*60)
print("步骤 1: 加载 Tokenizer")
print("="*60)

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    trust_remote_code=True,
    padding_side="right"
)
tokenizer.pad_token = tokenizer.eos_token
print("✓ Tokenizer 加载完成")

# 加载模型（4-bit 量化以节省显存）
print("\n" + "="*60)
print("步骤 2: 加载模型（4-bit 量化）")
print("="*60)
print("注意: 32B 模型较大，使用 4-bit 量化...")

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=quantization_config,
    device_map="auto",
    trust_remote_code=True,
    torch_dtype=torch.float16,
)

print("✓ 模型加载完成")

# 准备模型用于训练
print("\n准备模型用于 LoRA 训练...")
model = prepare_model_for_kbit_training(model)

# 配置 LoRA
print("\n" + "="*60)
print("步骤 3: 配置 LoRA")
print("="*60)

lora_config = LoraConfig(
    r=LORA_RANK,
    lora_alpha=LORA_ALPHA,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    inference_mode=False,
)

model = get_peft_model(model, lora_config)
print("\n可训练参数统计:")
model.print_trainable_parameters()

# 加载数据集
print("\n" + "="*60)
print("步骤 4: 加载训练数据")
print("="*60)

dataset = load_dataset(
    "json",
    data_files="merged_all_datasets.jsonl",
    split="train"
)

print(f"✓ 数据集加载完成: {len(dataset)} 条样本")

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

print("\n预处理数据...")
tokenized_dataset = dataset.map(
    preprocess_function,
    batched=True,
    remove_columns=dataset.column_names,
    desc="Tokenizing"
)

print("✓ 数据预处理完成")

# 配置训练参数
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
    optim="paged_adamw_8bit",  # 使用 8-bit 优化器节省显存
    warmup_steps=100,
    lr_scheduler_type="cosine",
    fp16=True,
    report_to="none",
    gradient_checkpointing=True,
    max_grad_norm=0.3,
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

print("✓ 训练器配置完成")

# 开始训练
print("\n" + "="*60)
print("步骤 6: 开始训练")
print("="*60)
print("\n使用 Abliterated 模型训练，预计 3-4 小时完成\n")

import time
start_time = time.time()

trainer.train()

end_time = time.time()
training_time = end_time - start_time

print("\n" + "="*60)
print("✓ 训练完成！")
print("="*60)
print(f"训练耗时: {training_time/3600:.2f} 小时")

# 保存模型
print("\n" + "="*60)
print("步骤 7: 保存模型")
print("="*60)

model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"✓ 模型已保存到: {OUTPUT_DIR}")

# 打包模型
print("\n" + "="*60)
print("步骤 8: 打包模型")
print("="*60)

import shutil
shutil.make_archive("qwen-defender-abliterated-trained", "zip", OUTPUT_DIR)

print("✓ 模型已打包为: qwen-defender-abliterated-trained.zip")

print("\n" + "="*60)
print("全部完成！")
print("="*60)
print(f"\n训练统计:")
print(f"  基础模型: Abliterated (无限制)")
print(f"  样本数: {len(dataset)}")
print(f"  训练轮数: {NUM_EPOCHS}")
print(f"  训练时长: {training_time/3600:.2f} 小时")
print(f"\n下一步:")
print(f"1. 下载 qwen-defender-abliterated-trained.zip")
print(f"2. 解压到本地")
print(f"3. 导入 Ollama 测试")
print("="*60)

print("\n准备下载...")
print("运行以下代码下载模型:")
print("from google.colab import files")
print("files.download('qwen-defender-abliterated-trained.zip')")
