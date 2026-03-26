-- 添加模型类型字段，支持标准LLM和自定义接口
-- 执行方式：在 MySQL 中运行此脚本

USE ai_security_system;

-- 添加 model_type 字段
ALTER TABLE models 
ADD COLUMN model_type VARCHAR(20) DEFAULT 'openai' COMMENT '模型类型: openai=标准OpenAI格式, custom=自定义POST接口' 
AFTER model_id;

-- 添加 custom_config 字段，存储自定义接口的配置（JSON格式）
ALTER TABLE models 
ADD COLUMN custom_config TEXT COMMENT '自定义接口配置(JSON): {request_format, response_format, headers等}' 
AFTER security_prompt;

-- 更新现有数据为默认类型
UPDATE models SET model_type = 'openai' WHERE model_type IS NULL;

-- 查看表结构
DESC models;
