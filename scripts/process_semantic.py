import os
import sys
import sqlite3
import numpy as np
import pandas as pd
import json
import pickle
import time
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db import DB_NAME
from core.gemini_client import get_embeddings, summarize_cluster

def update_embeddings_batch(batch_size=50):
    """Fetch missing embeddings from Gemini and store them. Batch size set to 50."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get reviews without embeddings but having content (not empty)
    c.execute("SELECT id, content FROM reviews WHERE embedding IS NULL AND content IS NOT NULL AND content != '' LIMIT ?", (batch_size,))
    rows = c.fetchall()
    
    if not rows:
        print("No new reviews to embed.")
        conn.close()
        return 0
    
    ids = [r[0] for r in rows]
    texts = [r[1][:500] for r in rows] # Limit text length for embedding
    
    print(f"Fetching embeddings for {len(texts)} reviews...")
    embeddings = get_embeddings(texts)
    
    if embeddings:
        for rid, emb in zip(ids, embeddings):
            # Store as binary pickle for SQLite
            emb_blob = pickle.dumps(np.array(emb, dtype=np.float32))
            c.execute("UPDATE reviews SET embedding = ? WHERE id = ?", (emb_blob, rid))
        conn.commit()
        print(f"Successfully updated {len(ids)} embeddings.")
        conn.close()
        return len(ids)
    else:
        print("Failed to get embeddings. Check API Key or limits.")
        conn.close()
        return 0

def run_semantic_clustering(n_clusters=20):
    """Perform T-SNE reduction and Clustering. Increased clusters for better granularity."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT id, content, embedding FROM reviews WHERE embedding IS NOT NULL", conn)
    
    if len(df) < n_clusters:
        print(f"Not enough data for clustering (need at least {n_clusters} reviews).")
        conn.close()
        return

    print(f"Processing clustering for {len(df)} reviews...")
    
    # 1. Unpickle embeddings
    X = np.array([pickle.loads(e) for e in df['embedding'].values])
    
    # 2. T-SNE Reductions
    # Using small perplexity for small datasets
    tsne = TSNE(n_components=2, perplexity=min(30, len(df)-1), random_state=42, init='pca', learning_rate='auto')
    coords = tsne.fit_transform(X)
    
    # 3. K-Means Clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X)
    
    df['x'] = coords[:, 0]
    df['y'] = coords[:, 1]
    df['cluster'] = clusters
    
    # 4. Generate Topic Labels for each cluster (using Gemini)
    cluster_labels = {}
    for i in range(n_clusters):
        # Filter out empty or very short reviews to avoid API errors
        sample_reviews = [r for r in df[df['cluster'] == i]['content'].head(10).tolist() if r and len(r.strip()) > 2]
        
        if not sample_reviews:
            print(f"Skipping Cluster {i} - no valid content for summarization.")
            continue
            
        text_for_ai = "\n---\n".join(sample_reviews)
        print(f"Summarizing Cluster {i} ({i+1}/{n_clusters})...")
        label = summarize_cluster(text_for_ai)
        
        # Only update if we got a valid label (avoids overwriting with None/Unlabeled)
        if label:
            cluster_labels[i] = label
            # Reduced delay as gemini_client now handles robust retry and fallback
            time.sleep(2) 
        else:
            print(f"Skipping Cluster {i} due to API failure/limit. Will retry later.")
    
    # 5. Update Database
    for _, row in df.iterrows():
        c = conn.cursor()
        # Only update cluster_label if we actually generated a new one
        if row['cluster'] in cluster_labels:
            c.execute(
                "UPDATE reviews SET x = ?, y = ?, cluster_label = ? WHERE id = ?",
                (float(row['x']), float(row['y']), cluster_labels[row['cluster']], row['id'])
            )
        else:
            # Still update coordinates even if label failed, but keep old label
            c.execute(
                "UPDATE reviews SET x = ?, y = ? WHERE id = ?",
                (float(row['x']), float(row['y']), row['id'])
            )
    
    conn.commit()
    conn.close()
    print("Semantic map updated successfully!")

if __name__ == "__main__":
    # 1. Update missing embeddings (in batches until done)
    print("Starting embedding update...")
    total_updated = 0
    while True:
        count = update_embeddings_batch(100)
        if count == 0:
            break
        total_updated += count
        print(f"Total embeddings updated so far: {total_updated}")
        time.sleep(2) # Small gap between batches
    
    # 2. Run clustering with all available data
    run_semantic_clustering()
