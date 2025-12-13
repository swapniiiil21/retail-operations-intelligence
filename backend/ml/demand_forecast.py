import pandas as pd
from datetime import timedelta
from ..db.db_utils import get_connection

def get_daily_sales(store_id: int, product_id: int):
    conn = get_connection()
    if not conn:
        return None
    query = """
        SELECT DATE(txn_timestamp) as sale_date,
               SUM(quantity) as qty
        FROM sales_transactions
        WHERE store_id = %s AND product_id = %s
        GROUP BY DATE(txn_timestamp)
        ORDER BY sale_date;
    """
    df = pd.read_sql(query, conn, params=(store_id, product_id))
    conn.close()
    return df

def moving_average_forecast(store_id: int, product_id: int, window: int = 7, horizon: int = 7):
    """
    Very simple moving-average forecast to keep code light.
    """
    df = get_daily_sales(store_id, product_id)
    if df is None or df.empty:
        return None, None

    df["ma"] = df["qty"].rolling(window=window, min_periods=1).mean()
    last_date = df["sale_date"].max()
    last_ma = df["ma"].iloc[-1]

    future_dates = [last_date + timedelta(days=i) for i in range(1, horizon + 1)]
    future_qty = [round(last_ma, 2)] * horizon

    forecast_df = pd.DataFrame({
        "sale_date": future_dates,
        "forecast_qty": future_qty
    })
    return df, forecast_df
