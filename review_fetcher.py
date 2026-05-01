import os
import serpapi
import sqlite3
import json
import datetime
import urllib.request
import re
import random

DB_PATH = 'reviews.db'

def extract_data_id(url):
    """將網址展開並從中擷取 data_id"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req)
        final_url = res.geturl()
        match = re.search(r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', final_url)
        if match:
            return match.group(1)
        else:
            return None
    except Exception as e:
        print(f"解析網址時發生錯誤: {e}")
        return None

def extract_data_cid(data_id):
    """從 data_id 中轉換並擷取 data_cid (10進位)"""
    try:
        parts = data_id.split(':')
        if len(parts) == 2:
            return str(int(parts[1], 16))
    except Exception:
        pass
    return None

def init_db():
    """初始化資料庫與資料表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 建立評論與地標資訊的歷史資料表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS places_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place_id TEXT UNIQUE NOT NULL,
            data_id TEXT NOT NULL,
            data_cid TEXT NOT NULL,
            place_info TEXT NOT NULL,
            reviews TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def fetch_with_api_keys(api_keys, params, engine="google_maps_reviews"):
    """共用的 API 請求邏輯，自動切換 API Key"""
    random.shuffle(api_keys)
    current_key_idx = 0
    
    while current_key_idx < len(api_keys):
        try:
            active_key = api_keys[current_key_idx]
            client = serpapi.Client(api_key=active_key)
            results = client.search(params)
            
            if "error" in results:
                err_msg = str(results["error"]).lower()
                if "searches left" in err_msg or "plan" in err_msg or "quota" in err_msg or "maximum" in err_msg:
                    print(f"第 {current_key_idx + 1} 組 API Key 額度受限，切換下一組...")
                    current_key_idx += 1
                    continue
                else:
                    print(f"API 發生錯誤: {results['error']}")
                    return None
            return results
                
        except Exception as e:
            print(f"第 {current_key_idx + 1} 組 API Key 發生錯誤：{e}，切換下一組...")
            current_key_idx += 1
            
    print("警告：所有 API Keys 都已耗盡或無法使用！")
    return None

def get_place_and_reviews(url, hl, api_keys):
    """
    透過 data_id 檢查快取以節省額度。
    第一次 API：使用 data_cid 搜尋並獲得 place_info 及 place_id。
    第二次 API：使用 data_id 搜尋 google_maps_reviews 獲得評論。
    並將結果存入資料庫 places_cache 中。
    """
    extracted_data_id = extract_data_id(url)
    if not extracted_data_id:
        raise ValueError("無法從網址中擷取到有效的 data_id。")

    data_cid = extract_data_cid(extracted_data_id)
    if not data_cid:
        raise ValueError("無法從 data_id 轉換取得 data_cid。")

    print(f"成功擷取到 data_id: {extracted_data_id}, data_cid: {data_cid}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 檢查快取
    cursor.execute('''
        SELECT place_info, reviews, created_at FROM places_cache
        WHERE data_cid = ?
    ''', (data_cid,))
    row = cursor.fetchone()
    
    now = datetime.datetime.now()
    if row:
        cached_info_str, cached_reviews_str, created_at_str = row
        created_at = datetime.datetime.fromisoformat(created_at_str)
        # 30 天內的快取直接回傳
        if (now - created_at).days < 30:
            print(f"使用快取資料 (儲存時間: {created_at_str})")
            conn.close()
            return json.loads(cached_info_str), json.loads(cached_reviews_str)

    # ====== 1. 執行第一次 API 請求：取得地點詳細資訊 ======
    print("發送第一次請求 (google_maps) 獲取地點資訊...")
    place_params = {
        "engine": "google_maps",
        "data_cid": data_cid,
        "hl": hl
    }
    
    place_results = fetch_with_api_keys(api_keys, place_params, "google_maps")
    if not place_results:
        raise Exception("取得地點資訊失敗。")
        
    local = place_results.get("local_results", [])
    place_info = local[0] if local else place_results.get("place_results", {})
    
    if not place_info:
        raise Exception("無法從 API 返回結果中找到地點資訊。")

    place_id = place_info.get("place_id")
    data_id = extracted_data_id
    
    if not place_id:
        raise Exception("無法從 Google Maps 結果中獲取 place_id。")

    # ====== 2. 執行第二次 API 請求：取得評論 ======
    print("發送第二次請求 (google_maps_reviews) 獲取評論...")
    all_reviews = []
    next_page_token = None
    target_amount = 50
    api_call_count = 0
    max_api_calls = 4
    has_error = False
    
    while len(all_reviews) < target_amount and api_call_count < max_api_calls:
        api_call_count += 1
        reviews_params = {
            "engine": "google_maps_reviews",
            "data_id": data_id,
            "hl": hl,
            "sort_by": "qualityScore",
            "no_cache": False
        }
        if next_page_token:
            reviews_params["next_page_token"] = next_page_token
            reviews_params["num"] = 20
            
        print(f"正在獲取評論 (目前累積 {len(all_reviews)} 筆)...")
        reviews_result = fetch_with_api_keys(api_keys, reviews_params, "google_maps_reviews")
        
        if not reviews_result:
            has_error = True
            break
            
        page_reviews = reviews_result.get("reviews", [])
        if not page_reviews:
            break
            
        all_reviews.extend(page_reviews)
        pagination = reviews_result.get("serpapi_pagination", {})
        next_page_token = pagination.get("next_page_token")
        
        if not next_page_token:
            break
            
    # 沒有遇到中斷錯誤才能存快取
    if not (has_error and len(all_reviews) == 0):
        print(f"將新資料儲存至 places_cache (地標: {place_id} | 評論 {len(all_reviews)} 筆)...")
        now_str = now.isoformat()
        
        # 使用 REPLACE INTO 來更新舊快取 (因 place_id 為 UNIQUE)
        cursor.execute('''
            REPLACE INTO places_cache (place_id, data_id, data_cid, place_info, reviews, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (place_id, data_id, data_cid, json.dumps(place_info, ensure_ascii=False), json.dumps(all_reviews, ensure_ascii=False), now_str))
        conn.commit()
    conn.close()
    return place_info, all_reviews


def load_api_keys():
    """從 .env 讀取所有 SERPAPI_KEY 開頭的環境變數"""
    keys = []
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip().startswith('SERPAPI_KEY'):
                        keys.append(v.strip())
    # 去除重複，確保按順序排列
    return list(dict.fromkeys(keys)) if keys else []


if __name__ == '__main__':
    init_db()
    
    API_KEYS = load_api_keys()
    if not API_KEYS:
        print("錯誤：未在 .env 檔案中找到 API Key！請建立 .env 檔案並設定 SERPAPI_KEY... 變數。")
        exit(1)
        
    hl_lang = "zh-tw"
    
    while True:
        input_url = input("\n請輸入 Google Maps 分享網址或輸入 q 離開): ").strip()
        if input_url.lower() == 'q':
            break
        if not input_url:
            continue
            
        try:
            place_info, reviews_data = get_place_and_reviews(input_url, hl_lang, API_KEYS)
            print(f"地標名稱: {place_info.get('title')}")
            print(f"總共取得 {len(reviews_data)} 筆評論")
        except Exception as e:
            print(f"寫入或獲取資料失敗: {e}")