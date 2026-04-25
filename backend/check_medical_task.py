import sqlite3, json
conn = sqlite3.connect('proxy_logs.db')
c = conn.cursor()
c.execute('SELECT proxy_id, name, api_key, security_prompt, audit_config, custom_regex_rules FROM proxy_tasks')
for r in c.fetchall():
    print('proxy_id:', r[0])
    print('name:', r[1])
    key = r[2]
    print('api_key:', key[:12]+'...' if key else 'EMPTY')
    print('security_prompt:', r[3][:200])
    try:
        ac = json.loads(r[4]) if r[4] else {}
        print('audit_config:', json.dumps(ac, ensure_ascii=False, indent=2))
    except:
        print('audit_config raw:', r[4][:200])
    print('custom_regex:', r[5][:200] if r[5] else '[]')
    print('---')
conn.close()
