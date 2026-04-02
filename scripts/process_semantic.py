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

from core.db import DB_NAME, CHAT_DB_NAME
from core.gemini_client import get_embeddings, summarize_cluster

def update_embeddings_batch(batch_size=50):
    """Fetch missing embeddings from Gemini and store them. Batch size set to 50."""
    
    # Check Reviews DB first
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, content FROM reviews WHERE embedding IS NULL AND content IS NOT NULL AND content != '' LIMIT ?", (batch_size,))
    rows = c.fetchall()
    table_name = "reviews"
    db_conn = conn
    
    if not rows:
        conn.close()
        # Fallback to check Chats DB
        conn_c = sqlite3.connect(CHAT_DB_NAME)
        c_c = conn_c.cursor()
        c_c.execute("SELECT id, content FROM chat_messages WHERE embedding IS NULL AND content IS NOT NULL AND content != '' LIMIT ?", (batch_size,))
        rows = c_c.fetchall()
        table_name = "chat_messages"
        db_conn = conn_c
        c = c_c

        if not rows:
            print("No new data to embed in either database.")
            conn_c.close()
            return 0
    
    ids = [r[0] for r in rows]
    texts = [r[1][:500] for r in rows] # Limit text length for embedding
    
    print(f"Fetching embeddings for {len(texts)} {table_name}...")
    embeddings = get_embeddings(texts)
    
    if embeddings:
        for rid, emb in zip(ids, embeddings):
            # Store as binary pickle for SQLite
            emb_blob = pickle.dumps(np.array(emb, dtype=np.float32))
            c.execute(f"UPDATE {table_name} SET embedding = ? WHERE id = ?", (emb_blob, rid))
        db_conn.commit()
        print(f"Successfully updated {len(ids)} embeddings in {table_name}.")
        db_conn.close()
        return len(ids)
    else:
        print("Failed to get embeddings. Check API Key or limits.")
        db_conn.close()
        return 0

def run_semantic_clustering(n_clusters=40):
    """Perform T-SNE reduction and Clustering. Increased clusters for better granularity."""
    
    # Fetch from both DBs
    conn_r = sqlite3.connect(DB_NAME)
    df_r = pd.read_sql_query("SELECT id, content, embedding FROM reviews WHERE embedding IS NOT NULL", conn_r)
    if not df_r.empty: df_r['is_review'] = True
    
    conn_c = sqlite3.connect(CHAT_DB_NAME)
    df_c = pd.read_sql_query("SELECT id, content, embedding FROM chat_messages WHERE embedding IS NOT NULL", conn_c)
    if not df_c.empty: df_c['is_review'] = False
    
    if df_r.empty and df_c.empty:
        df = pd.DataFrame()
    elif df_r.empty:
        df = df_c
    elif df_c.empty:
        df = df_r
    else:
        df = pd.concat([df_r, df_c], ignore_index=True)
    
    if len(df) < n_clusters:
        print(f"Not enough data for clustering (need at least {n_clusters} records).")
        conn_r.close()
        conn_c.close()
        return

    print(f"Processing clustering for {len(df)} records across both databases...")
    
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
        
        if label:
            cluster_labels[i] = label
            time.sleep(2) 
        else:
            print(f"Skipping Cluster {i} due to API failure/limit. Will retry later.")
    
    # 5. Update Database
    for _, row in df.iterrows():
        is_rev = row.get('is_review', True)
        c = conn_r.cursor() if is_rev else conn_c.cursor()
        t_name = "reviews" if is_rev else "chat_messages"
        
        # Only update cluster_label if we actually generated a new one
        if row['cluster'] in cluster_labels:
            c.execute(
                f"UPDATE {t_name} SET x = ?, y = ?, cluster_label = ? WHERE id = ?",
                (float(row['x']), float(row['y']), cluster_labels[row['cluster']], row['id'])
            )
        else:
            c.execute(
                f"UPDATE {t_name} SET x = ?, y = ? WHERE id = ?",
                (float(row['x']), float(row['y']), row['id'])
            )
    
    conn_r.commit()
    conn_c.commit()
    conn_r.close()
    conn_c.close()
    print("Semantic map updated successfully for both databases!")

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
    
    # 2. Run clustering with all available data (increased granularity to 40)
    run_semantic_clustering(n_clusters=40)
