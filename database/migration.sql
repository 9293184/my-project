-- 数据库迁移脚本：添加 model_type 和 custom_config 字段
USE ai_security_system;

-- 添加 model_type 字段
ALTER TABLE models 
ADD COLUMN model_type VARCHAR(20) DEFAULT 'openai' 
COMMENT '模型类型: openai=标准OpenAI格式, custom=自定义POST接口' 
AFTER model_id;

-- 添加 custom_config 字段
ALTER TABLE models 
ADD COLUMN custom_config TEXT 
COMMENT '自定义接口配置(JSON)' 
AFTER security_prompt;

-- 更新现有数据
UPDATE models SET model_type = 'openai' WHERE model_type IS NULL;

-- 显示表结构
DESC models;
