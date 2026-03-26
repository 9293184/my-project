"""
初始化数据库脚本
"""
import pymysql

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'charset': 'utf8mb4',
}

def init_database():
    """初始化数据库"""
    try:
        # 连接到 MySQL（不指定数据库）
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 创建数据库
        print("创建数据库...")
        cursor.execute("CREATE DATABASE IF NOT EXISTS ai_security_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute("USE ai_security_system")
        
        # 读取并执行 schema.sql
        print("执行 schema.sql...")
        with open('../database/schema.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
            
        # 分割并执行每个语句
        statements = sql_script.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"执行语句时出错: {e}")
                    print(f"语句: {statement[:100]}...")
        
        conn.commit()
        print("✓ 数据库初始化成功！")
        
        # 检查表
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"\n已创建的表: {len(tables)} 个")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    init_database()
