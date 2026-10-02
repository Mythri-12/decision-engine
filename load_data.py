"""Load every CSV in ./data into data.db (one table per file)."""
import glob, os, sqlite3
import pandas as pd

conn = sqlite3.connect("data.db")
for path in glob.glob("data/*.csv"):
    table = os.path.splitext(os.path.basename(path))[0].lower().replace(" ", "_")
    pd.read_csv(path).to_sql(table, conn, if_exists="replace", index=False)
    print(f"loaded {table}")
conn.close()
