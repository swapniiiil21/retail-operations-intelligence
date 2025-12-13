# backend/api/customer_api.py
from ..ml.customer_segmentation import compute_rfm

def run_customer_segmentation(k=4):
    rfm_df, cluster_summary, sil = compute_rfm(k=k)
    return rfm_df, cluster_summary, sil
