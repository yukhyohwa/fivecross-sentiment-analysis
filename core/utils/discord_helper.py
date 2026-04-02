
import os
import re
import datetime
import hashlib
from core.db import save_chat_message, init_db

def clean_discord_content(content):
    # Remove Discord Emojis/Stickers: <:name:id>
    content = re.sub(r'<:[a-zA-Z0-9_]+:[0-9]+>', '', content)
    # Remove URLs
    content = re.sub(r'https?://[^\s]+', '', content)
    return content.strip()

def import_discord_files(directory="data/discord", game_id="jump_assemble"):
    """Scans and imports all TXT files from the specified directory."""
    if not os.path.exists(directory):
        print(f"  [discord] Directory {directory} not found. Skipping.")
        return 0

    init_db()
    files = [f for f in os.listdir(directory) if f.endswith('.txt')]
    if not files:
        print(f"  [discord] No .txt files found in {directory}.")
        return 0

    total_imported = 0
    print(f"  [discord] Found {len(files)} files to process.")

    for filename in files:
        filepath = os.path.join(directory, filename)
        channel_name = filename.replace('.txt', '')
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_msg = None
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                if current_msg:
                    if "使用export" in current_msg['content'] or not current_msg['content']:
                        current_msg = None
                        continue
                        
                    # Create clean Hash ID (16 chars)
                    raw_id = f"{current_msg['author']}{current_msg['message_date']}{current_msg['content']}"
                    current_msg['id'] = hashlib.md5(raw_id.encode('utf-8')).hexdigest()[:16]
                    
                    save_chat_message(current_msg)
                    total_imported += 1
                    current_msg = None
                continue

            if '\t202' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    author, date_str = parts[0].strip(), parts[1].strip()
                    if "(🤖)系統信息" in author:
                        current_msg = None
                        continue
                    
                    current_msg = {
                        'id': None, # Set at end of block
                        'game_id': game_id,
                        'channel': channel_name,
                        'author': author,
                        'content': '',
                        'message_date': date_str,
                        'source': 'discord_chat'
                    }
            elif current_msg:
                cleaned = clean_discord_content(line)
                if cleaned:
                    if current_msg['content']:
                        current_msg['content'] += "\n" + cleaned
                    else:
                        current_msg['content'] = cleaned

        # Final check for last block
        if current_msg and "使用export" not in current_msg['content'] and current_msg['content']:
            raw_id = f"{current_msg['author']}{current_msg['message_date']}{current_msg['content']}"
            current_msg['id'] = hashlib.md5(raw_id.encode('utf-8')).hexdigest()[:16]
            save_chat_message(current_msg)
            total_imported += 1

    print(f"  [discord] Successfully imported {total_imported} messages.")
    return total_imported
