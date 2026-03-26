"""
数据库迁移脚本：添加 context_summary 字段
用于支持多轮对话安全审查
"""

import pymysql
import sys

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'ai_security_system',
    'charset': 'utf8mb4'
}


def migrate():
    """添加 context_summary 字段"""
    print("=" * 60)
    print("🚀 开始数据库迁移：添加 context_summary 字段")
    print("=" * 60)
    
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 检查字段是否已存在
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'chat_logs' AND COLUMN_NAME = 'context_summary'
        """, (DB_CONFIG['database'],))
        
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            print("✅ context_summary 字段已存在，无需迁移")
        else:
            # 添加字段
            cursor.execute("""
                ALTER TABLE chat_logs 
                ADD COLUMN context_summary TEXT DEFAULT NULL 
                COMMENT '对话上下文摘要（用于多轮审查）'
                AFTER confidence
            """)
            conn.commit()
            print("✅ 成功添加 context_summary 字段")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("🎉 迁移完成！")
        print("=" * 60)
        return True
        
    except pymysql.Error as e:
        print(f"❌ 数据库错误: {e}")
        return False


if __name__ == '__main__':
    migrate()
