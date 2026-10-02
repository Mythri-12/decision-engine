import pytest
from engine import is_safe


@pytest.mark.parametrize("sql", [
    "SELECT * FROM orders",
    "select category, sum(amount) from orders group by category;",
    "WITH t AS (SELECT 1) SELECT * FROM t",
])
def test_allows_select(sql):
    assert is_safe(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE orders",
    "DELETE FROM orders",
    "UPDATE orders SET amount = 0",
    "SELECT 1; DROP TABLE orders",
    "INSERT INTO orders VALUES (1)",
    "PRAGMA table_info(orders)",
    "",
])
def test_blocks_writes(sql):
    assert not is_safe(sql)
