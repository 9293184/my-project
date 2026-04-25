import sqlite3, json
c = sqlite3.connect("proxy_logs.db")
r = c.execute("SELECT audit_config, enable_input_audit, enable_output_audit, paused FROM proxy_tasks WHERE proxy_id='PX-c44d7ce8'").fetchone()
print("paused:", r[3])
print("input_audit:", r[1])
print("output_audit:", r[2])
cfg = json.loads(r[0])
print(json.dumps(cfg, indent=2, ensure_ascii=False))
