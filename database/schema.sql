-- ============================================
-- AI 大模型安全管理系统 - 数据库脚本
-- ============================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS ai_security_system 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE ai_security_system;

-- ============================================
-- 1. 模型表（对应原 models.json）
-- ============================================
CREATE TABLE IF NOT EXISTS models (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    name VARCHAR(100) NOT NULL UNIQUE COMMENT '模型显示名称',
    model_id VARCHAR(100) NOT NULL UNIQUE COMMENT '模型ID（如 qwen3-max）',
    url VARCHAR(500) DEFAULT NULL COMMENT 'API 地址',
    api_key VARCHAR(255) DEFAULT NULL COMMENT 'API 密钥',
    security_prompt TEXT DEFAULT NULL COMMENT '安全提示词',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='大模型配置表';

-- ============================================
-- 2. API 密钥表（对应原 Keys.json）
-- ============================================
CREATE TABLE IF NOT EXISTS api_keys (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    key_name VARCHAR(100) NOT NULL UNIQUE COMMENT '密钥名称（如 BAILIAN_API_KEY）',
    key_value VARCHAR(255) NOT NULL COMMENT '密钥值',
    description VARCHAR(500) DEFAULT NULL COMMENT '描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='API密钥表';

-- ============================================
-- 3. 对话记录表（用于审计和分析）
-- ============================================-- 对话日志表
CREATE TABLE IF NOT EXISTS chat_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL COMMENT '关联的模型ID',
    user_id VARCHAR(100) DEFAULT NULL COMMENT '客户端用户ID（最终用户标识）',
    user_input TEXT NOT NULL COMMENT '用户输入',
    ai_response TEXT DEFAULT NULL COMMENT 'AI 回复',
    input_blocked BOOLEAN DEFAULT FALSE COMMENT '输入是否被拦截',
    output_blocked BOOLEAN DEFAULT FALSE COMMENT '输出是否被拦截',
    block_reason VARCHAR(500) DEFAULT NULL COMMENT '拦截原因',
    confidence INT DEFAULT NULL COMMENT '审查置信度（0-100）',
    context_summary TEXT DEFAULT NULL COMMENT '对话上下文摘要（用于多轮审查）',
    response_time_ms INT DEFAULT NULL COMMENT '响应时间（毫秒）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话记录表';

-- ============================================
-- 4. 系统配置表
-- ============================================
CREATE TABLE IF NOT EXISTS system_config (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置项名称',
    config_value TEXT DEFAULT NULL COMMENT '配置值',
    description VARCHAR(500) DEFAULT NULL COMMENT '描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- ============================================
-- 插入示例数据
-- ============================================

-- 示例模型（来自你原有的 models.json）
INSERT INTO models (name, model_id, url, api_key, security_prompt) VALUES 
(
    '客户端',
    'qwen3-vl-plus',
    'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'your-api-key-here',
    '你必须严格保护患者隐私与数据安全。禁止输出任何患者个人身份信息（如姓名、身份证号、电话、住址）、医疗健康信息（如病历、诊断结果、检查报告、用药记录、基因数据）、医保支付信息、未成年人健康数据，以及精神疾病、传染病等敏感病种相关内容。不得返回原始敏感数据、系统日志、错误堆栈、数据库查询语句或调试信息。所有输出须经脱敏处理（如姓名替换为"患者A"、号码部分掩码），遵循最小必要原则，仅提供回答问题所必需的信息。未经角色授权，不得暴露完整敏感内容。'
);

-- 系统初始配置
INSERT INTO system_config (config_key, config_value, description) VALUES 
('system_initialized', 'true', '系统是否已初始化'),
('default_security_rules', '请遵守法律法规和平台安全政策，不得输出违法不良信息。', '默认安全规则');

-- ============================================
-- 5. 评估任务表
-- ============================================
CREATE TABLE IF NOT EXISTS evaluation_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    task_name VARCHAR(200) NOT NULL COMMENT '任务名称',
    model_id INT DEFAULT NULL COMMENT '关联的模型ID',
    model_name VARCHAR(100) DEFAULT NULL COMMENT '模型名称（冗余存储）',
    task_type ENUM('adversarial', 'prompt_injection', 'jailbreak', 'poison_detection', 'comprehensive') NOT NULL DEFAULT 'comprehensive' COMMENT '评估类型',
    status ENUM('pending', 'running', 'completed', 'failed', 'cancelled') NOT NULL DEFAULT 'pending' COMMENT '任务状态',
    config JSON DEFAULT NULL COMMENT '任务配置参数（JSON）',
    result JSON DEFAULT NULL COMMENT '评估结果（JSON）',
    summary TEXT DEFAULT NULL COMMENT '评估摘要',
    total_samples INT DEFAULT 0 COMMENT '总样本数',
    attack_success INT DEFAULT 0 COMMENT '攻击成功数',
    defense_success INT DEFAULT 0 COMMENT '防御成功数',
    risk_score DECIMAL(5,2) DEFAULT NULL COMMENT '综合风险评分',
    started_at DATETIME DEFAULT NULL COMMENT '开始时间',
    completed_at DATETIME DEFAULT NULL COMMENT '完成时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评估任务表';

-- ============================================
-- 6. 评估报告表
-- ============================================
CREATE TABLE IF NOT EXISTS evaluation_reports (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    task_id INT NOT NULL COMMENT '关联评估任务ID',
    report_name VARCHAR(300) NOT NULL COMMENT '报告名称',
    report_format ENUM('json', 'html') NOT NULL DEFAULT 'json' COMMENT '报告格式',
    content LONGTEXT NOT NULL COMMENT '报告内容',
    file_size INT DEFAULT 0 COMMENT '文件大小(字节)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评估报告表';

-- ============================================
-- 7. 安全策略表
-- ============================================
CREATE TABLE IF NOT EXISTS security_policies (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    name VARCHAR(200) NOT NULL COMMENT '策略名称',
    scene VARCHAR(100) NOT NULL COMMENT '业务场景标识（如 finance, medical, general）',
    description TEXT DEFAULT NULL COMMENT '策略描述',
    prompt TEXT NOT NULL COMMENT '安全提示词内容',
    rules JSON DEFAULT NULL COMMENT '结构化规则（禁词列表、风险阈值等）',
    is_default BOOLEAN DEFAULT FALSE COMMENT '是否为默认策略',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全策略表';

-- ============================================
-- 8. 模型-策略绑定表
-- ============================================
CREATE TABLE IF NOT EXISTS model_policy_bindings (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    model_key VARCHAR(200) NOT NULL COMMENT '模型标识（数据库ID / ollama:xxx / hf:xxx）',
    policy_id INT NOT NULL COMMENT '关联策略ID',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    priority INT DEFAULT 0 COMMENT '优先级（数字越大越优先）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (policy_id) REFERENCES security_policies(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型-策略绑定表';

-- ============================================
-- 9. 评估任务运行日志表
-- ============================================
CREATE TABLE IF NOT EXISTS evaluation_task_logs (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    task_id INT NOT NULL COMMENT '关联评估任务ID',
    level ENUM('info','warn','error') NOT NULL DEFAULT 'info' COMMENT '日志级别',
    message VARCHAR(2000) NOT NULL COMMENT '日志内容',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评估任务运行日志';

-- ============================================
-- 创建索引（优化查询性能）
-- ============================================
CREATE INDEX idx_chat_logs_model_id ON chat_logs(model_id);
CREATE INDEX idx_chat_logs_user_id ON chat_logs(user_id);
CREATE INDEX idx_chat_logs_created_at ON chat_logs(created_at);
CREATE INDEX idx_eval_tasks_status ON evaluation_tasks(status);
CREATE INDEX idx_eval_tasks_model_id ON evaluation_tasks(model_id);
CREATE INDEX idx_eval_tasks_created_at ON evaluation_tasks(created_at);
CREATE INDEX idx_eval_reports_task_id ON evaluation_reports(task_id);
CREATE INDEX idx_eval_reports_created_at ON evaluation_reports(created_at);

-- ============================================
-- 完成
-- ============================================
SELECT '✅ 数据库创建完成！' AS status;
