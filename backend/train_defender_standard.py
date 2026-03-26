"""使用标准 transformers + PEFT 进行 LoRA 微调"""
import os
# 设置环境变量强制兼容
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
os.environ['TORCH_CUDA_ARCH_LIST'] = '8.0;8.6;8.9;9.0'  # 强制使用兼容架构

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset

print("="*60)
print("LoRA 微调训练 - AI 安全防御模型")
print("使用标准 transformers + PEFT")
print("="*60)

# 配置
MODEL_NAME = "Qwen/Qwen2.5-7B"
OUTPUT_DIR = "d:/langchain2.0/models/qwen3-defender-trained"
MAX_SEQ_LENGTH = 2048
LORA_RANK = 16
LORA_ALPHA = 16
BATCH_SIZE = 1  # 降低以节省显存
GRADIENT_ACCUMULATION = 8
LEARNING_RATE = 2e-4
NUM_EPOCHS = 3

print(f"\n训练配置:")
print(f"  基础模型: {MODEL_NAME}")
print(f"  LoRA Rank: {LORA_RANK}")
print(f"  Batch Size: {BATCH_SIZE}")
print(f"  梯度累积: {GRADIENT_ACCUMULATION}")
print(f"  学习率: {LEARNING_RATE}")
print(f"  训练轮数: {NUM_EPOCHS}")

# 检查 GPU
print(f"\nGPU 信息:")
print(f"  CUDA 可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  显存: {round(torch.cuda.get_device_properties(0).total_memory/1024**3, 2)} GB")

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

# 2. 加载模型（8-bit 量化）
print("\n" + "="*60)
print("步骤 2: 加载模型（8-bit 量化）")
print("="*60)

# 尝试先在CPU加载，然后手动移动到GPU
print("尝试在CPU上加载模型...")

try:
    # 方法1：直接加载到CPU
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="cpu",
        trust_remote_code=True,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    print("模型已在CPU上加载，准备移动到GPU...")
    
    # 手动移动到GPU（如果可用）
    if torch.cuda.is_available():
        try:
            model = model.to('cuda:0')
            print("模型已成功移动到GPU")
        except Exception as e:
            print(f"移动到GPU失败，继续使用CPU: {e}")
            print("警告：将使用CPU训练，速度会很慢")
    
except Exception as e:
    print(f"加载失败: {e}")
    print("尝试使用量化加载...")
    
    # 方法2：使用量化
    from transformers import BitsAndBytesConfig
    quantization_config = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_threshold=6.0,
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=quantization_config,
        device_map="cpu",
        trust_remote_code=True,
    )

print("模型加载完成")

# 3. 准备模型用于训练
# 跳过 prepare_model_for_kbit_training 以避免 CUDA 兼容性问题
print("跳过量化准备步骤（CUDA 兼容性问题）")
# model = prepare_model_for_kbit_training(model)

# 4. 配置 LoRA
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

# 5. 加载数据集
print("\n" + "="*60)
print("步骤 4: 加载训练数据")
print("="*60)

dataset = load_dataset(
    "json",
    data_files="d:/langchain2.0/datasets/public/merged_all_datasets.jsonl",
    split="train"
)

print(f"数据集加载完成: {len(dataset)} 条样本")

# 数据预处理
def preprocess_function(examples):
    texts = []
    for messages in examples["messages"]:
        # 格式化为对话格式
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        texts.append(text)
    
    # Tokenize
    model_inputs = tokenizer(
        texts,
        max_length=MAX_SEQ_LENGTH,
        truncation=True,
        padding=False,
    )
    
    # 设置 labels
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

# 6. 配置训练参数
print("\n" + "="*60)
print("步骤 5: 配置训练器")
print("="*60)

training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRADIENT_ACCUMULATION,
    learning_rate=LEARNING_RATE,
    fp16=True,
    logging_steps=10,
    save_strategy="epoch",
    save_total_limit=2,
    optim="adamw_torch",
    warmup_steps=10,
    lr_scheduler_type="linear",
    report_to="none",
)

# 数据整理器
data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False,
)

# 创建训练器
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    data_collator=data_collator,
)

print("训练器配置完成")

# 7. 开始训练
print("\n" + "="*60)
print("步骤 6: 开始训练")
print("="*60)
print("\n这可能需要 1-3 小时，请耐心等待...\n")

trainer.train()

print("\n" + "="*60)
print("训练完成！")
print("="*60)

# 8. 保存模型
print("\n" + "="*60)
print("步骤 7: 保存模型")
print("="*60)

model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"模型已保存到: {OUTPUT_DIR}")

print("\n" + "="*60)
print("训练完成！")
print("="*60)
print(f"\n下一步:")
print(f"1. 合并 LoRA 权重")
print(f"2. 转换为 GGUF 格式")
print(f"3. 导入 Ollama")
print(f"4. 测试效果")
print("="*60)
