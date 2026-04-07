import os
import sys
import sqlite3
import numpy as np
import pandas as pd
import json
import pickle
import time
import urllib.request
import urllib.error
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.db import DB_NAME, CHAT_DB_NAME

# ─── Configuration ───
SERVER_URL = "http://127.0.0.1:8080"
EMBEDDINGS_ENDPOINT = f"{SERVER_URL}/v1/embeddings"
COMPLETIONS_ENDPOINT = f"{SERVER_URL}/v1/chat/completions"

def get_embeddings_local(texts):
    """Fetch vector embeddings via local llama-server."""
    if not texts: return None
    
    # Filter and truncate texts
    valid_texts = [str(t)[:500] for t in texts if t and len(str(t).strip()) > 0]
    if not valid_texts: return None

    # llama-server uses OpenAI format
    payload = json.dumps({
        "model": "gemma-4",
        "input": valid_texts
    }).encode("utf-8")

    req = urllib.request.Request(
        EMBEDDINGS_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
            # Result contains a list of objects with "embedding" field
            return [data["embedding"] for data in result["data"]]
    except Exception as e:
        print(f"❌ Failed to get local embeddings: {e}")
        print("💡 Hint: Ensure you started 'start_server.bat' with the '--embedding' flag.")
        return None

def summarize_cluster_local(content_text):
    """Use Local Gemma 4 to generate a summary tag for a cluster of messages."""
    if not content_text or len(content_text.strip()) < 5:
        return None

    prompt = (
        "你是一个游戏社区分析员。请从以下【标准标签集】中选择一个最准确的单一标签来描述这组评论的主题：\n"
        "【标准标签集】：氪金机制、版本更新、角色建议、玩法模式、系统BUG、优化反馈、运营策略、新手引导、社区讨论、游戏评价、竞技公平\n"
        "要求：\n"
        "1. 仅输出标签名称，不要有任何修饰词、解释、标点或引注。\n"
        "2. 严禁输出思考过程（thought process）。\n"
        "3. 必须从标准集中选择，若无法确定请返回'其他'。\n\n"
        f"评论内容预览：\n{content_text[:2000]}"
    )

    payload = json.dumps({
        "model": "gemma-4",
        "messages": [
            {"role": "system", "content": "你是一个专业的游戏分析助手。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 64
    }).encode("utf-8")

    req = urllib.request.Request(
        COMPLETIONS_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            label = result["choices"][0]["message"]["content"].strip()
            
            # Clean up 'thought' tokens or internal reasoning patterns
            import re
            label = re.sub(r'<\|.*?\|>', '', label)
            label = label.replace('thought', '').replace('|', '').strip()

            # Basic cleanup: take first line
            label = label.split('\n')[0].strip()
            return label if label else "其他"
    except Exception as e:
        print(f"❌ Failed to summarize cluster: {e}")
        return None

def update_embeddings_batch(batch_size=50):
    """Fetch rows without embeddings from both DBs and generate them locally."""
    # Check Reviews DB
    conn_r = sqlite3.connect(DB_NAME)
    c_r = conn_r.cursor()
    c_r.execute("SELECT id, content FROM reviews WHERE embedding IS NULL AND content IS NOT NULL AND content != '' LIMIT ?", (batch_size,))
    rows = c_r.fetchall()
    
    if rows:
        db_conn, table_name, cursor = conn_r, "reviews", c_r
    else:
        conn_r.close()
        # Fallback to Chats DB
        conn_c = sqlite3.connect(CHAT_DB_NAME)
        c_c = conn_c.cursor()
        c_c.execute("SELECT id, content FROM chat_messages WHERE embedding IS NULL AND content IS NOT NULL AND content != '' LIMIT ?", (batch_size,))
        rows = c_c.fetchall()
        if not rows:
            conn_c.close()
            return 0
        db_conn, table_name, cursor = conn_c, "chat_messages", c_c

    ids = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    
    print(f"Generating vectors for {len(texts)} {table_name} locally...")
    embeddings = get_embeddings_local(texts)
    
    if embeddings:
        for rid, emb in zip(ids, embeddings):
            # Same format as original: binary pickle of numpy array
            emb_blob = pickle.dumps(np.array(emb, dtype=np.float32))
            cursor.execute(f"UPDATE {table_name} SET embedding = ? WHERE id = ?", (emb_blob, rid))
        db_conn.commit()
        print(f"Successfully processed {len(ids)} embeddings.")
        db_conn.close()
        return len(ids)
    
    db_conn.close()
    return 0

def run_semantic_clustering(n_clusters=40):
    """Execute T-SNE and KMeans, then label clusters using Local Gemma."""
    # 1. Fetch data from both databases
    conn_r = sqlite3.connect(DB_NAME)
    df_r = pd.read_sql_query("SELECT id, content, embedding FROM reviews WHERE embedding IS NOT NULL", conn_r)
    df_r['is_review'] = True
    
    conn_c = sqlite3.connect(CHAT_DB_NAME)
    df_c = pd.read_sql_query("SELECT id, content, embedding FROM chat_messages WHERE embedding IS NOT NULL", conn_c)
    df_c['is_review'] = False
    
    if df_r.empty and df_c.empty:
        print("No embeddings found in either database.")
        conn_r.close(); conn_c.close()
        return

    df = pd.concat([df_r, df_c], ignore_index=True)
    if len(df) < n_clusters:
        print(f"Not enough data for clustering (need at least {n_clusters}).")
        conn_r.close(); conn_c.close()
        return

    print(f"Running clustering on {len(df)} records...")
    
    # 2. X, Y Calculation (T-SNE)
    X = np.array([pickle.loads(e) for e in df['embedding'].values])
    tsne = TSNE(n_components=2, perplexity=min(30, len(df)-1), random_state=42, init='pca', learning_rate='auto')
    coords = tsne.fit_transform(X)
    
    # 3. K-Means
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X)
    
    df['x'] = coords[:, 0]
    df['y'] = coords[:, 1]
    df['cluster'] = clusters
    
    # 4. Generate Topic Labels using Gemma
    cluster_labels = {}
    for i in range(n_clusters):
        sample_contents = df[df['cluster'] == i]['content'].head(15).tolist()
        text_for_ai = "\n---\n".join([s for s in sample_contents if s])
        
        if not text_for_ai.strip(): continue
        
        print(f"Labeling Cluster {i} using Local Gemma...")
        label = summarize_cluster_local(text_for_ai)
        if label:
            cluster_labels[i] = label
            
    # 5. Save back to DBs
    for _, row in df.iterrows():
        is_rev = row['is_review']
        conn = conn_r if is_rev else conn_c
        t_name = "reviews" if is_rev else "chat_messages"
        c = conn.cursor()
        
        # Consistent with process_semantic.py logic
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

    conn_r.commit(); conn_c.commit()
    conn_r.close(); conn_c.close()
    print("✅ Local semantic mapping update finished.")

if __name__ == "__main__":
    # 1. Update embeddings batch by batch
    print("Starting background embedding processing...")
    while update_embeddings_batch(100) > 0:
        time.sleep(1)
        
    # 2. Re-cluster and generate labels
    run_semantic_clustering(n_clusters=40)
