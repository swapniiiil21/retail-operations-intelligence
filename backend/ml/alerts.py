from datetime import datetime, timedelta
import pandas as pd
from ..db.db_utils import get_connection

def generate_low_stock_alerts(threshold: int = 20):
    conn = get_connection()
    if not conn:
        return

    cur = conn.cursor()
    query = """
        SELECT i.store_id, s.store_name, i.product_id, p.product_name,
               i.on_hand_qty
        FROM inventory_snapshots i
        JOIN stores s ON i.store_id = s.store_id
        JOIN products p ON i.product_id = p.product_id
        WHERE i.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots)
          AND i.on_hand_qty < %s;
    """
    df = pd.read_sql(query, conn, params=(threshold,))

    for _, row in df.iterrows():
        details = (f"Low stock for {row['product_name']} in {row['store_name']}. "
                   f"On hand: {row['on_hand_qty']} units.")
        cur.execute("""
            INSERT INTO alerts (store_id, created_at, alert_type, details, is_resolved)
            VALUES (%s,%s,%s,%s,%s)
        """, (int(row["store_id"]), datetime.now(), "Low-stock", details, False))

    conn.commit()
    cur.close()
    conn.close()
    return df  # for UI display
