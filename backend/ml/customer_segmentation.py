# backend/ml/customer_segmentation.py
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import silhouette_score
from ..db.db_utils import get_connection
from datetime import datetime

def compute_rfm(k=4, reference_date=None):
    """
    Compute RFM features and apply KMeans clustering.
    Returns: rfm_df (with cluster labels), cluster_summary_df, silhouette (float)
    """
    conn = get_connection()
    if not conn:
        raise ConnectionError("DB connection failed")

    # Pull transactional data: customer_id, txn_timestamp, total_amount
    q = """
    SELECT customer_id, txn_timestamp, total_amount
    FROM sales_transactions
    WHERE customer_id IS NOT NULL;
    """
    df = pd.read_sql(q, conn)
    conn.close()

    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), None

    # Ensure datetime
    df["txn_timestamp"] = pd.to_datetime(df["txn_timestamp"])

    # reference_date: use max txn date + 1 day if not provided
    if reference_date is None:
        reference_date = df["txn_timestamp"].max() + pd.Timedelta(days=1)

    # RFM aggregation
    agg = df.groupby("customer_id").agg(
        recency = ("txn_timestamp", lambda x: (reference_date - x.max()).days),
        frequency = ("txn_timestamp", "count"),
        monetary = ("total_amount", "sum")
    ).reset_index()

    # Remove zero/negative monetary if any
    agg = agg[agg["monetary"] >= 0].copy()

    # log transform monetary to reduce skew
    agg["monetary_log"] = np.log1p(agg["monetary"])

    features = agg[["recency", "frequency", "monetary_log"]].copy()

    # Scale features with RobustScaler (robust to outliers)
    scaler = RobustScaler()
    X = scaler.fit_transform(features)

    # Determine KMeans
    model = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = model.fit_predict(X)

    agg["segment"] = labels

    # Compute silhouette if possible
    sil = None
    try:
        if len(set(labels)) > 1 and len(agg) > len(set(labels)):
            sil = silhouette_score(X, labels)
    except Exception:
        sil = None

    # Create readable segment names by sorting cluster by monetary median
    cluster_profile = agg.groupby("segment").agg(
        recency_med=("recency","median"),
        frequency_med=("frequency","median"),
        monetary_med=("monetary","median"),
        count=("customer_id","count")
    ).reset_index()

    # Rank clusters by monetary_med descending: best segment -> 0
    cluster_profile = cluster_profile.sort_values("monetary_med", ascending=False).reset_index(drop=True)
    cluster_profile["rank"] = cluster_profile.index + 1

    # Map segment -> human label e.g. "High Value", "Medium", "Low"
    # We'll create labels based on rank: 1 -> "Best", 2 -> "Good", else "Needs Attention"
    seg_map = {}
    for _, row in cluster_profile.iterrows():
        seg_id = int(row["segment"])
        rank = int(row["rank"])
        if rank == 1:
            seg_map[seg_id] = "High Value"
        elif rank == 2:
            seg_map[seg_id] = "Medium Value"
        else:
            seg_map[seg_id] = "Low Value"

    agg["segment_name"] = agg["segment"].map(seg_map)

    # Cluster summary DF for UI
    cluster_summary = cluster_profile.copy()
    cluster_summary["segment_name"] = cluster_summary["segment"].map(seg_map)
    cluster_summary = cluster_summary[["segment","segment_name","recency_med","frequency_med","monetary_med","count"]]

    # Return RFM + labels, cluster summary and silhouette
    return agg.sort_values("segment").reset_index(drop=True), cluster_summary, sil
