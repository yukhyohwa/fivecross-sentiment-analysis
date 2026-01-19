import os
import datetime
import hashlib
import json
import itertools
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cluster_cache.jsonl')

# --- Multi-Key Support ---
api_keys_raw = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY")
if api_keys_raw:
    API_KEYS = [k.strip() for k in api_keys_raw.split(",") if k.strip()]
else:
    API_KEYS = []

# Create a cyclic iterator for the keys
key_pool = itertools.cycle(API_KEYS) if API_KEYS else None
current_key = next(key_pool) if key_pool else None

# --- Model Selection State ---
last_successful_model = 'gemini-2.0-flash'
last_model_failure_time = 0
FAILURE_COOLDOWN = 300 # 5 minutes cooldown for a failing model

def rotate_key():
    """Switch to the next available API key."""
    global current_key
    if key_pool:
        current_key = next(key_pool)
        genai.configure(api_key=current_key)
        print(f"--- Switched to API Key: {current_key[:8]}... ---")
        return True
    return False

# Initial configuration
if current_key:
    genai.configure(api_key=current_key)

def get_embeddings(texts):
    """Fetch vector embeddings with auto-key rotation on failure."""
    if not current_key or not texts: return None
    
    # Filter out empty or non-string texts
    texts = [str(t) for t in texts if t and len(str(t).strip()) > 0]
    if not texts: return None

    attempts = len(API_KEYS) if API_KEYS else 1
    for _ in range(attempts):
        try:
            model = 'models/text-embedding-004'
            result = genai.embed_content(model=model, content=texts, task_type="clustering")
            return result['embedding']
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg and rotate_key():
                continue # Retry with new key
            print(f"Gemini Embedding Error: {err_msg}")
            return None
    return None

def summarize_cluster(reviews):
    """Use Gemini 2.0 to summarize reviews with local cache and persistent multi-key rotation."""
    if not current_key or not reviews or len(reviews.strip()) < 5: 
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
    
    # Cycles 1: Try gemini-2.0-flash (if not in cooldown)
    # Cycles 2-4: Try gemini-flash-latest (1.5 Flash stable)
    max_cycles = 4
    for cycle in range(max_cycles):
        # Determine which model to try
        if cycle == 0:
            if last_successful_model == 'gemini-2.0-flash':
                model_name = 'gemini-2.0-flash'
            else:
                # If 2.0 failed before, check if cooldown is over
                if time.time() - last_model_failure_time > FAILURE_COOLDOWN:
                     model_name = 'gemini-2.0-flash'
                else:
                     model_name = 'gemini-flash-latest' # Skip 2.0-flash
        else:
            model_name = 'gemini-flash-latest'
            
        attempts = len(API_KEYS) if API_KEYS else 1
        
        for _ in range(attempts):
            try:
                print(f"--- Cycle {cycle+1}, Attempting summary with {model_name} (Key: {current_key[:8]}...) ---")
                model = genai.GenerativeModel(model_name) 
                
                # Refined prompt for clean, symbolic labels without Pinyin
                prompt = (
                    f"请总结以下游戏评论的核心话题(5-8字)。\n"
                    f"要求：\n"
                    f"1. 仅输出核心话题，不要任何解释或修饰词。\n"
                    f"2. 绝对不要显示拼音、英文或注音。\n"
                    f"3. 话题前后必须加上四个星号，格式如：**** 话题名称 ****\n"
                    f"4. 不要包含字数说明(如'5字')或括号补充。\n\n"
                    f"评论内容：\n{reviews[:2000]}"
                )
                
                response = model.generate_content(prompt)
                
                if not response or not response.text:
                    raise Exception("Empty response from Gemini")
                    
                label = response.text.strip().replace('"', '').replace("'", "")
                
                # Post-process to ensure star injection if missing
                if label and not label.startswith("****"):
                    # Extra safety: Clean up any remaining Pinyin/Markdown if Gemini slips
                    label = re.sub(r'\(.*?\)', '', label) # Remove common (pinyin) or (6字)
                    label = f"**** {label.strip()} ****"
                
                if label:
                    # Success!
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
                if "429" in err_msg:
                    print(f"Rate limited (429) on {model_name}. Rotating...")
                    if model_name == 'gemini-2.0-flash':
                        last_successful_model = 'gemini-flash-latest'
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
