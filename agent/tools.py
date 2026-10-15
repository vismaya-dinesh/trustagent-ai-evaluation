
import sqlite3
from pathlib import Path

# Find our existing shop database.
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "shop.db"


def lookup_order(order_id: int) -> dict:
    """Look up an order using its ID."""

    # Reject invalid inputs.
    if isinstance(order_id, bool) or not isinstance(order_id, int):
        return {"success": False, "error": "Order ID must be an integer."}

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                """
                SELECT
                    orders.order_id,
                    customers.name AS customer_name,
                    orders.product,
                    orders.amount,
                    orders.status,
                    orders.address
                FROM orders
                JOIN customers
                    ON orders.customer_id = customers.customer_id
                WHERE orders.order_id = ?
                """,
                (order_id,),
            ).fetchone()

        if row is None:
            return {
                "success": False,
                "error": f"Order {order_id} was not found."
            }

        return {
            "success": True,
            "order": dict(row)
        }

    except sqlite3.Error:
        return {
            "success": False,
            "error": "The order database could not be accessed."
        }


if __name__ == "__main__":
    print("Testing order lookup...")
    print(lookup_order(102))
    print(lookup_order(999))
