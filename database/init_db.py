"""
数据库初始化脚本
运行此脚本创建数据库和表
"""

import pymysql
import os
import sys

# 修复 Windows 控制台编码问题
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# ============================================
# 数据库配置（请根据实际情况修改）
# ============================================
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',  # MySQL root 密码
    'charset': 'utf8mb4'
}

DATABASE_NAME = 'ai_security_system'


def get_connection(with_db=False):
    """获取数据库连接"""
    config = DB_CONFIG.copy()
    if with_db:
        config['database'] = DATABASE_NAME
    return pymysql.connect(**config)


def execute_sql_file(cursor, filepath):
    """执行 SQL 文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # 分割多条 SQL 语句
    statements = sql_content.split(';')
    
    for statement in statements:
        statement = statement.strip()
        # 移除开头的注释行，保留实际 SQL
        lines = statement.split('\n')
        clean_lines = [line for line in lines if line.strip() and not line.strip().startswith('--')]
        clean_statement = '\n'.join(clean_lines).strip()
        
        if clean_statement:
            try:
                cursor.execute(statement)  # 执行原始语句（MySQL 能处理注释）
                print(f"✅ 执行成功: {clean_statement[:50]}...")
            except pymysql.Error as e:
                # 忽略某些预期的错误（如表已存在）
                if e.args[0] not in [1050, 1062]:  # 表已存在、重复键
                    print(f"⚠️ 执行警告: {e}")


def init_database():
    """初始化数据库"""
    print("=" * 60)
    print("🚀 开始初始化数据库")
    print("=" * 60)
    
    # 检查密码是否已设置
    if not DB_CONFIG['password']:
        DB_CONFIG['password'] = input("请输入 MySQL root 密码: ").strip()
    
    try:
        # 1. 连接 MySQL 服务器
        print("\n📡 连接 MySQL 服务器...")
        conn = get_connection(with_db=False)
        cursor = conn.cursor()
        print("✅ 连接成功！")
        
        # 2. 创建数据库
        print(f"\n📦 创建数据库 {DATABASE_NAME}...")
        cursor.execute(f"""
            CREATE DATABASE IF NOT EXISTS {DATABASE_NAME}
            CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        """)
        print(f"✅ 数据库 {DATABASE_NAME} 已创建/已存在")
        
        # 3. 切换到该数据库
        cursor.execute(f"USE {DATABASE_NAME}")
        
        # 4. 执行 SQL 脚本
        print("\n📝 执行数据库脚本...")
        script_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        
        if os.path.exists(script_path):
            execute_sql_file(cursor, script_path)
        else:
            # 如果没有 SQL 文件，直接创建表
            create_tables(cursor)
        
        conn.commit()
        print("\n" + "=" * 60)
        print("🎉 数据库初始化完成！")
        print("=" * 60)
        
        # 5. 显示表信息
        print("\n📊 已创建的表：")
        cursor.execute("SHOW TABLES")
        for table in cursor.fetchall():
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"   - {table[0]} ({count} 条记录)")
        
        cursor.close()
        conn.close()
        
    except pymysql.Error as e:
        print(f"\n❌ 数据库错误: {e}")
        print("\n💡 请检查：")
        print("   1. MySQL 服务是否已启动")
        print("   2. 用户名和密码是否正确")
        print("   3. 端口 3306 是否正确")
        return False
    
    return True


def create_tables(cursor):
    """直接创建表（备用方案）"""
    
    # 模型表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL UNIQUE,
            model_id VARCHAR(100) NOT NULL UNIQUE,
            url VARCHAR(500) DEFAULT NULL,
            api_key VARCHAR(255) DEFAULT NULL,
            security_prompt TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("✅ 创建表: models")
    
    # API 密钥表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INT PRIMARY KEY AUTO_INCREMENT,
            key_name VARCHAR(100) NOT NULL UNIQUE,
            key_value VARCHAR(255) NOT NULL,
            description VARCHAR(500) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("✅ 创建表: api_keys")
    
    # 对话记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            model_id INT NOT NULL,
            user_id VARCHAR(100) DEFAULT NULL,
            user_input TEXT NOT NULL,
            ai_response TEXT DEFAULT NULL,
            input_blocked BOOLEAN DEFAULT FALSE,
            output_blocked BOOLEAN DEFAULT FALSE,
            block_reason VARCHAR(500) DEFAULT NULL,
            confidence INT DEFAULT NULL,
            context_summary TEXT DEFAULT NULL,
            response_time_ms INT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("✅ 创建表: chat_logs")
    
    # 系统配置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            id INT PRIMARY KEY AUTO_INCREMENT,
            config_key VARCHAR(100) NOT NULL UNIQUE,
            config_value TEXT DEFAULT NULL,
            description VARCHAR(500) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("✅ 创建表: system_config")


def test_connection():
    """测试数据库连接"""
    print("🔍 测试数据库连接...")
    
    if not DB_CONFIG['password']:
        DB_CONFIG['password'] = input("请输入 MySQL root 密码: ").strip()
    
    try:
        conn = get_connection(with_db=False)
        conn.close()
        print("✅ MySQL 连接成功！")
        return True
    except pymysql.Error as e:
        print(f"❌ 连接失败: {e}")
        return False


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_connection()
    else:
        init_database()
