import json
import os
import urllib.request
import re
from db_utils import get_reviews_collection

KEYWORDS_PATH = 'fake_keywords.txt'

def extract_data_id(url):
    """將短網址展開並從中擷取 data_id"""
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

def load_keywords():
    """讀取外部的非真實體驗字典檔"""
    if not os.path.exists(KEYWORDS_PATH):
        with open(KEYWORDS_PATH, 'w', encoding='utf-8') as f:
            f.write("打卡\n送肉盤\n招待\n好評\n送\n評分\n")
            
    with open(KEYWORDS_PATH, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def analyze_and_get_results(data_id, hl):
    """處理評論、分析假好評，並更新至 MongoDB 中對應的最新紀錄"""
    collection = get_reviews_collection()

    # 1. 查詢庫中該店家的最新紀錄
    row = collection.find_one({"data_id": data_id, "hl": hl})

    if not row:
        print("資料庫中沒有該店家的原始評論記錄，請先執行 review_fetcher.py。")
        return None

    '''（待程式邏輯都已確定後，可恢復此功能）
    # 2. 如果這筆紀錄身上已經有 analysis_result，代表處理過了
    analysis_result = row.get("analysis_result")
    if analysis_result:
        print(f"使用已處理快取資料 (隨原始資料於 {row.get('created_at')} 一併更新)")
        return analysis_result
    '''

    # 3. 執行清洗與處理 (當最新紀錄尚未分析過時)
    print("最新原始資料尚未分析，開始進行評論處理與假評論過濾...")
    raw_reviews = row.get("reviews", [])
    
    keywords = load_keywords()
    fake_count = 0
    fake_dates = []
    processed_reviews = []
    
    # 用於計算真實評論分數與分佈
    real_rating_sum = 0
    real_rating_counts = { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 }
    
    for rv in raw_reviews:
        snippet = rv.get('snippet') or ''
        rating = rv.get('rating', 0)
        iso_date = rv.get('iso_date')
        
        is_fake = False
        if rating == 5.0 and any(kw in snippet for kw in keywords):
            is_fake = True
            fake_count += 1
            if iso_date:
                fake_dates.append(iso_date)
        else:
            # 這是真實評論，納入計算
            real_rating_sum += rating
            # 將 rating 轉為字串並四捨五入到整數，方便統計
            rating_key = str(int(rating)) if int(rating) in range(1, 6) else "0"
            if rating_key in real_rating_counts:
                real_rating_counts[rating_key] += 1
                
        rv_processed = dict(rv)
        rv_processed['is_fake'] = is_fake
        processed_reviews.append(rv_processed)
        
    time_range = None
    if fake_dates:
        fake_dates.sort()
        time_range = {
            "first_occurrence": fake_dates[0],
            "last_occurrence": fake_dates[-1]
        }
        
    real_count = len(raw_reviews) - fake_count
    real_avg = round(real_rating_sum / real_count, 1) if real_count > 0 else 0.0
        
    analysis_result = {
        "total_reviews": len(raw_reviews),
        "fake_count": fake_count,
        "fake_ratio": round(fake_count / len(raw_reviews) * 100, 2) if raw_reviews else 0,
        "fake_time_range": time_range,
        "real_reviews_count": real_count,
        "real_average_rating": real_avg,
        "real_rating_distribution": real_rating_counts,
        "processed_reviews": processed_reviews
    }
    
    print("將過濾與分析結果合併回 MongoDB 中...")
    collection.update_one(
        {"_id": row["_id"]},
        {"$set": {"analysis_result": analysis_result}}
    )
    
    return analysis_result

# CLI 測試區塊已移除，本程式目前作為網頁 API 的模組使用。
