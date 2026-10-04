"""Builds returns.db and runs the SQL layer using Python's built-in sqlite3.
No SQL install needed. Run from the repo root:  python sql/run_sql.py"""
import os, re, sqlite3, subprocess, sys

DB = "returns.db"
if os.path.exists(DB):
    os.remove(DB)

# 1. regenerate seed_data.sql from the CSVs
subprocess.run([sys.executable, "sql/make_seed.py"], check=True)

# 2. build the database
db = sqlite3.connect(DB)
db.executescript(open("sql/schema.sql").read())
db.executescript(open("sql/seed_data.sql").read())
for t in ("customers", "products", "orders"):
    print(f"{t}: {db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} rows")

# 3. run every report and print its output (copy these into reports.sql)
raw = open("sql/reports.sql").read()
for chunk in re.split(r"(?m)^(?=-- \([a-i]\d?\))", raw)[1:]:
    label = chunk.splitlines()[0]
    code = re.sub(r"--.*", "", chunk)
    for stmt in [s.strip() for s in code.split(";") if s.strip()]:
        cur = db.execute(stmt)
        if cur.description:
            print("\n" + label)
            print(" | ".join(d[0] for d in cur.description))
            for row in cur.fetchall():
                print(" | ".join(str(v) for v in row))
db.commit()
db.close()
