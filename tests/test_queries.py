"""Golden tests: SQL answers must match an independent pandas calculation."""
import os
import pandas as pd
import pytest

os.environ.setdefault("DB_PATH", "data.db")
from engine import run_query, is_safe, get_schema

orders = pd.read_csv("data/orders.csv")
products = pd.read_csv("data/products.csv")
customers = pd.read_csv("data/customers.csv")


def test_total_revenue():
    df = run_query("SELECT SUM(amount) AS total FROM orders")
    assert df.iloc[0, 0] == orders["amount"].sum()


def test_revenue_by_category():
    df = run_query("""SELECT p.category, SUM(o.amount) AS revenue FROM orders o
                      JOIN products p ON o.product_id = p.product_id GROUP BY p.category""")
    expected = orders.merge(products, on="product_id").groupby("category")["amount"].sum()
    assert dict(zip(df["category"], df["revenue"])) == expected.to_dict()


def test_revenue_by_region():
    df = run_query("""SELECT c.region, SUM(o.amount) AS revenue FROM orders o
                      JOIN customers c ON o.customer_id = c.customer_id GROUP BY c.region""")
    expected = orders.merge(customers, on="customer_id").groupby("region")["amount"].sum()
    assert dict(zip(df["region"], df["revenue"])) == expected.to_dict()


def test_monthly_orders():
    df = run_query("SELECT substr(order_date,1,7) AS month, COUNT(*) AS n FROM orders GROUP BY month")
    expected = orders.assign(m=orders["order_date"].str[:7]).groupby("m").size()
    assert dict(zip(df["month"], df["n"])) == expected.to_dict()


def test_top_customer():
    df = run_query("SELECT customer_id, SUM(amount) AS s FROM orders GROUP BY customer_id ORDER BY s DESC LIMIT 1")
    assert df.iloc[0, 0] == orders.groupby("customer_id")["amount"].sum().idxmax()


def test_empty_result_is_handled():
    assert run_query("SELECT * FROM orders WHERE amount < 0").empty


def test_write_is_blocked_at_runtime():
    with pytest.raises(ValueError):
        run_query("DELETE FROM orders")


def test_unsafe_select_with_hidden_write_blocked():
    assert not is_safe("SELECT * FROM orders; DELETE FROM orders")


def test_schema_lists_all_tables():
    s = get_schema()
    assert all(t in s for t in ("orders", "products", "customers"))
