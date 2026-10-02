"""Generate a small synthetic retail dataset (seeded, reproducible) into ./data."""
import random
import pandas as pd

random.seed(42)
regions = ["North", "South", "East", "West"]
cats = {"Electronics": (8000, 60000), "Fashion": (500, 4000), "Home": (800, 9000), "Grocery": (100, 1500), "Sports": (700, 7000)}

products = []
for i, (cat, (lo, hi)) in enumerate(cats.items()):
    for j in range(6):
        products.append({"product_id": i * 10 + j + 1, "product_name": f"{cat} Item {j+1}", "category": cat,
                         "unit_price": random.randrange(lo, hi, 50)})
products = pd.DataFrame(products)

customers = pd.DataFrame([{"customer_id": i, "name": f"Customer {i}", "region": random.choice(regions),
                           "segment": random.choice(["Retail", "Corporate", "Online"])} for i in range(1, 121)])

rows = []
for oid in range(1, 1501):
    p = products.sample(1, random_state=oid).iloc[0]
    qty = random.randint(1, 5)
    month = random.randint(1, 12)
    rows.append({"order_id": oid, "customer_id": random.randint(1, 120), "product_id": int(p.product_id),
                 "quantity": qty, "amount": int(p.unit_price) * qty,
                 "order_date": f"2025-{month:02d}-{random.randint(1, 28):02d}"})
orders = pd.DataFrame(rows)

for name, df in [("products", products), ("customers", customers), ("orders", orders)]:
    df.to_csv(f"data/{name}.csv", index=False)
print("sample data written")
