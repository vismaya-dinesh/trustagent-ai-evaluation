
import sqlite3
from pathlib import Path

# Store the database inside our project.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "shop.db"


def initialize_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        # Customers
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            )
        """)

        # Orders
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                product TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount >= 0),
                status TEXT NOT NULL
                    CHECK(status IN (
                        'processing', 'shipped', 'delivered',
                        'cancelled'
                    )),
                address TEXT NOT NULL,
                FOREIGN KEY(customer_id)
                    REFERENCES customers(customer_id)
            )
        """)

        # Refund records
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refunds (
                refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                status TEXT NOT NULL
                    CHECK(status IN ('pending', 'processed')),
                FOREIGN KEY(order_id) REFERENCES orders(order_id)
            )
        """)

        # Fictional customers
        conn.executemany("""
            INSERT OR IGNORE INTO customers
                (customer_id, name, email)
            VALUES (?, ?, ?)
        """, [
            (1, "Aisha Khan", "aisha@example.com"),
            (2, "Rahul Nair", "rahul@example.com"),
            (3, "Sara Thomas", "sara@example.com"),
        ])

        # Fictional orders
        conn.executemany("""
            INSERT OR IGNORE INTO orders
                (order_id, customer_id, product,
                 amount, status, address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            (101, 1, "Blue Dress", 100.00,
             "delivered", "Dubai Marina"),
            (102, 2, "White Sneakers", 200.00,
             "shipped", "Al Nahda, Sharjah"),
            (103, 3, "Black Handbag", 150.00,
             "processing", "Ajman Corniche"),
        ])

    print("TrustAgent database initialized!")
    print(f"Database location: {DB_PATH}")


def show_orders():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT
                orders.order_id,
                customers.name,
                orders.product,
                orders.amount,
                orders.status
            FROM orders
            JOIN customers
                ON orders.customer_id = customers.customer_id
            ORDER BY orders.order_id
        """).fetchall()

    print("\nOur shop's orders:")
    for order_id, name, product, amount, status in rows:
        print(
            f"Order #{order_id} | {name} | {product} | "
            f"AED {amount:.2f} | {status}"
        )


if __name__ == "__main__":
    initialize_database()
    show_orders()
