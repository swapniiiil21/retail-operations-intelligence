from datetime import datetime, timedelta
import random
from .db_utils import get_connection

def seed():
    conn = get_connection()
    if not conn:
        print("❌ DB connection failed")
        return
    cur = conn.cursor()

    # Clear existing data (dev only)
    cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for tbl in ["alerts", "incidents", "inventory_snapshots",
                "sales_transactions", "customers", "products", "stores"]:
        cur.execute(f"TRUNCATE TABLE {tbl};")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1;")

    # --- STORES ---
    stores = [
        (1, "Pune Flagship", "West", "Pune", "2022-01-10"),
        (2, "Mumbai Central", "West", "Mumbai", "2021-09-01"),
        (3, "Delhi City Mall", "North", "Delhi", "2020-03-15"),
    ]
    cur.executemany(
        "INSERT INTO stores (store_id, store_name, region, city, open_date) VALUES (%s,%s,%s,%s,%s)",
        stores
    )

    # --- CUSTOMERS ---
    customers = [
        (1, "Rahul Sharma", "Male", 28, "Pune"),
        (2, "Sneha Patel", "Female", 25, "Mumbai"),
        (3, "Amit Verma", "Male", 32, "Delhi"),
        (4, "Priya Singh", "Female", 30, "Pune"),
    ]
    cur.executemany(
        "INSERT INTO customers (customer_id, customer_name, gender, age, city) VALUES (%s,%s,%s,%s,%s)",
        customers
    )

    # --- PRODUCTS ---
    products = [
        (1, "SKU1", "Formal Shirt", "Apparel", "Shirts", 700.00, 1199.00),
        (2, "SKU2", "Casual T-Shirt", "Apparel", "Tops", 300.00, 699.00),
        (3, "SKU3", "Jeans", "Apparel", "Bottomwear", 900.00, 1899.00),
        (4, "SKU4", "Sneakers", "Footwear", "Shoes", 1500.00, 2999.00),
    ]
    cur.executemany("""
        INSERT INTO products (product_id, sku, product_name, category, subcategory, cost_price, selling_price)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, products)

    # --- SALES TRANSACTIONS (last 60 days) ---
    base_time = datetime.now() - timedelta(days=60)
    txns = []
    txn_id = 100000
    for day_offset in range(60):
        for _ in range(random.randint(10, 30)):
            store_id = random.choice([1, 2, 3])
            product_id = random.choice([1, 2, 3, 4])
            customer_id = random.choice([1, 2, 3, 4])
            ts = base_time + timedelta(days=day_offset,
                                       hours=random.randint(9, 21),
                                       minutes=random.randint(0, 59))
            qty = random.randint(1, 4)
            price = {1: 1199.0, 2: 699.0, 3: 1899.0, 4: 2999.0}[product_id]
            total = qty * price
            payment_method = random.choice(["Cash", "Card", "UPI"])
            txns.append((txn_id, store_id, product_id, customer_id, ts,
                         qty, total, payment_method))
            txn_id += 1

    cur.executemany("""
        INSERT INTO sales_transactions
        (txn_id, store_id, product_id, customer_id, txn_timestamp, quantity, total_amount, payment_method)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, txns)

    # --- INVENTORY SNAPSHOTS (today) ---
    inv_rows = []
    today = datetime.today().date()
    for store_id in [1, 2, 3]:
        for product_id in [1, 2, 3, 4]:
            inv_rows.append((
                store_id, product_id, today,
                random.randint(10, 150),   # on-hand
                random.randint(0, 50)      # on-order
            ))

    cur.executemany("""
        INSERT INTO inventory_snapshots (store_id, product_id, snapshot_date, on_hand_qty, on_order_qty)
        VALUES (%s,%s,%s,%s,%s)
    """, inv_rows)

    # --- INCIDENTS ---
    incident_types = ["POS Error", "SQL Error", "Esocket Error", "Register Down"]
    severities = ["Low", "Medium", "High"]
    incidents = []
    inc_id = 1
    for day_offset in range(20):
        for _ in range(random.randint(0, 3)):
            store_id = random.choice([1, 2, 3])
            created = datetime.now() - timedelta(days=day_offset,
                                                 hours=random.randint(9, 20))
            resolved = created + timedelta(hours=random.randint(1, 10))
            incidents.append((
                inc_id, store_id, created, resolved,
                random.choice(incident_types),
                random.choice(severities),
                "Auto-generated incident for demo",
                "Resolved by restarting POS / DB.",
                "Closed"
            ))
            inc_id += 1

    cur.executemany("""
        INSERT INTO incidents
        (incident_id, store_id, created_at, resolved_at, incident_type,
         severity, description, resolution_note, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, incidents)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Sample data inserted successfully!")

if __name__ == "__main__":
    seed()
