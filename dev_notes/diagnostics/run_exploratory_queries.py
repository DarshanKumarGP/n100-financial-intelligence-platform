import sqlite3

with open("notebooks/exploratory_queries.sql") as f:
    raw_lines = f.readlines()

# Strip comment lines individually, THEN join and split into statements --
# the earlier version filtered whole blocks if they started with a comment,
# which silently dropped every query since each one begins with a `--` note.
code_lines = [line for line in raw_lines if not line.strip().startswith("--")]
script = "".join(code_lines)

statements = [s.strip() for s in script.split(";") if s.strip()]

print(f"Parsed {len(statements)} SQL statements from the file.\n")

conn = sqlite3.connect("data/nifty100.db")

for i, stmt in enumerate(statements, 1):
    try:
        cur = conn.execute(stmt)
        rows = cur.fetchall()
        print(f"--- Query {i}: {len(rows)} rows returned ---")
        for r in rows[:5]:
            print(f"   {r}")
        if len(rows) > 5:
            print(f"   ... ({len(rows) - 5} more rows)")
        print()
    except Exception as e:
        print(f"--- Query {i}: ERROR: {e} ---\n")

conn.close()