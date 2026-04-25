"""一键为医疗项目启用对话历史检测"""
import sqlite3, json

conn = sqlite3.connect('proxy_logs.db')
c = conn.cursor()
c.execute('SELECT audit_config FROM proxy_tasks WHERE proxy_id="PX-c44d7ce8"')
row = c.fetchone()
cfg = json.loads(row[0])

cfg['context_history'] = {'enabled': True, 'window': 10}

conn.execute(
    'UPDATE proxy_tasks SET audit_config=? WHERE proxy_id="PX-c44d7ce8"',
    (json.dumps(cfg, ensure_ascii=False),)
)
conn.commit()
conn.close()
print("✓ 医疗项目对话历史检测已启用，窗口=10轮")
print("审查配置预览:")
print(json.dumps(cfg.get('context_history'), ensure_ascii=False, indent=2))
