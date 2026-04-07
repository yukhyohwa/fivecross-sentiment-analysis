import os
import re
import datetime
import hashlib
import json
import itertools
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'backups', 'cluster_cache.jsonl')

# --- Multi-Key Support ---
api_keys_raw = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY")
if api_keys_raw:
    API_KEYS = [k.strip() for k in api_keys_raw.split(",") if k.strip()]
else:
    API_KEYS = []

# Create a cyclic iterator for the keys
key_pool = itertools.cycle(API_KEYS) if API_KEYS else None
current_key = next(key_pool) if key_pool else None

# --- Active Client ---
client = genai.Client(api_key=current_key) if current_key else None

# --- Model Selection State ---
last_successful_model = 'gemini-2.0-flash'
last_model_failure_time = 0
FAILURE_COOLDOWN = 300 # 5 minutes cooldown for a failing model

def rotate_key():
    """Switch to the next available API key and rebuild client."""
    global current_key, client
    if key_pool:
        current_key = next(key_pool)
        client = genai.Client(api_key=current_key)
        print(f"--- Switched to API Key: {current_key[:8]}... ---")
        return True
    return False

def get_embeddings(texts):
    """Fetch vector embeddings using the new google.genai SDK with auto-key rotation."""
    if not client or not texts: return None
    
    # Filter out empty or non-string texts
    texts = [str(t) for t in texts if t and len(str(t).strip()) > 0]
    if not texts: return None

    max_cycles = 4
    for cycle in range(max_cycles):
        attempts = len(API_KEYS) if API_KEYS else 1
        for _ in range(attempts):
            try:
                result = client.models.embed_content(
                    model='gemini-embedding-001',
                    contents=texts,
                    config=types.EmbedContentConfig(task_type="CLUSTERING")
                )
                # New SDK returns a list of ContentEmbedding objects
                return [emb.values for emb in result.embeddings]
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    print(f"Rate limited on get_embeddings. Rotating key...")
                    if rotate_key():
                        time.sleep(2)
                        continue
                else:
                    print(f"Gemini Embedding Error: {err_msg}")
                    if rotate_key(): continue
                    return None
                    
        # All keys exhausted, sleep and try the next cycle
        wait_m = [1, 2, 3][min(cycle, 2)]
        print(f"--- All keys exhausted for embeddings. Waiting {wait_m}m... ---")
        time.sleep(wait_m * 60)
        
    return None

def summarize_cluster(reviews):
    """Use Gemini to summarize reviews with local cache and persistent multi-key rotation."""
    if not client or not reviews or len(reviews.strip()) < 5: 
        return None
    
    content_hash = hashlib.md5(reviews.encode('utf-8')).hexdigest()
    
    # 1. Local Cache Check
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    cached = json.loads(line)
                    if cached.get('hash') == content_hash and cached.get('label'):
                        return cached['label']
                except: continue

    # 2. API Call with persistent retries
    global last_successful_model, last_model_failure_time
    
    max_cycles = 4
    for cycle in range(max_cycles):
        # Determine which model to try
        if cycle == 0:
            if last_successful_model == 'gemini-2.0-flash':
                model_name = 'gemini-2.0-flash'
            else:
                if time.time() - last_model_failure_time > FAILURE_COOLDOWN:
                     model_name = 'gemini-2.0-flash'
                else:
                     model_name = 'gemini-2.0-flash-lite'
        else:
            model_name = 'gemini-2.0-flash-lite'
            
        attempts = len(API_KEYS) if API_KEYS else 1
        
        for _ in range(attempts):
            try:
                print(f"--- Cycle {cycle+1}, Attempting summary with {model_name} (Key: {current_key[:8]}...) ---")
                
                # Refined prompt for standardized labels
                prompt = (
                    "你是一个游戏社区分析员。请从以下【标准标签集】中为这组公开评论提取一个最准确的**单一分类标签**：\n"
                    "【标准标签集】：氪金机制、版本更新、角色建议、玩法模式、系统BUG、优化反馈、运营策略、新手引导、社区讨论、游戏评价、竞技公平\n"
                    "要求：\n"
                    "1. **严禁输出列表或解释**。仅输出标准集里的一个名称，不要加任何标点、拼音或多余字符。\n"
                    "2. 如果内容极其复杂无法归纳，请返回'其他'。\n\n"
                    f"评论内容：\n{reviews[:2000]}"
                )
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                
                if not response or not response.text:
                    raise Exception("Empty response from Gemini")
                    
                label = response.text.strip().replace('"', '').replace("'", "")
                
                if label:
                    last_successful_model = model_name
                    # Save to cache
                    cache_entry = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "hash": content_hash,
                        "label": label,
                        "review_count": len(reviews.split('\n---\n'))
                    }
                    with open(CACHE_FILE, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(cache_entry, ensure_ascii=False) + "\n")
                    return label
                    
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    print(f"Rate limited (429) on {model_name}. Rotating...")
                    if model_name == 'gemini-2.0-flash':
                        last_successful_model = 'gemini-2.0-flash-lite'
                        last_model_failure_time = time.time()
                        
                    if rotate_key():
                        time.sleep(2) 
                        continue 
                else:
                    print(f"Gemini API Error ({model_name}): {err_msg}")
                    if rotate_key(): continue
        
        # If we finished a full cycle of all keys and still have 429s
        if cycle < max_cycles - 1:
            wait_minutes = [1, 3, 5][min(cycle, 2)]
            print(f"--- All keys exhausted for {model_name}. Waiting {wait_minutes} minutes before cycle {cycle + 2}/{max_cycles}... ---")
            time.sleep(wait_minutes * 60)
            
    return None
