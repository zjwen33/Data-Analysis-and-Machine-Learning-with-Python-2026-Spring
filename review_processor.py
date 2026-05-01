import sqlite3
import json
import os
import urllib.request
import re

DB_PATH = 'reviews.db'
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
    """處理評論、分析假好評，並更新至 reviews.db 中對應的最新紀錄"""
    if not os.path.exists(DB_PATH):
        print(f"找不到 {DB_PATH}。請先使用 review_fetcher.py 獲取資料。")
        return None
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 查詢庫中該店家的最新紀錄 (依據搜集時間 created_at)
    cursor.execute('''
        SELECT id, reviews, analysis_result, created_at FROM review_history
        WHERE data_id = ? AND hl = ?
        ORDER BY created_at DESC LIMIT 1
    ''', (data_id, hl))
    row = cursor.fetchone()

    if not row:
        print("資料庫中沒有該店家的原始評論記錄，請先執行 review_fetcher.py。")
        conn.close()
        return None

    record_id, reviews_json, analysis_result_json, created_at_str = row
    
    # 2. 如果這筆紀錄身上已經有 analysis_result，代表處理過了
    if analysis_result_json:
        print(f"使用已處理快取資料 (隨原始資料於 {created_at_str} 一併更新)")
        analysis_result = json.loads(analysis_result_json)
        conn.close()
        return analysis_result

    # 3. 執行清洗與處理 (當最新紀錄尚未分析過時)
    print("最新原始資料尚未分析，開始進行評論處理與假評論過濾...")
    raw_reviews = json.loads(reviews_json)
    
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
            # 將 rating 轉為字串並四捨五入到整數，方便統計 (例如 4.5 -> 捨入為最接近的星等桶)
            # Google Review 星等通常是整數 (1.0, 2.0...)，但為確保安全轉為 int
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
    
    print("將過濾與分析結果合併回 reviews.db 中...")
    cursor.execute('''
        UPDATE review_history 
        SET analysis_result = ?
        WHERE id = ?
    ''', (json.dumps(analysis_result, ensure_ascii=False), record_id))
    conn.commit()
    conn.close()
    
    return analysis_result

if __name__ == '__main__':
    hl_lang = "zh-tw"
    
    while True:
        input_url = input("\n請輸入 Google Maps 分享網址 (例如 https://maps.app.goo.gl/... 或輸入 q 離開): ").strip()
        if input_url.lower() == 'q':
            break
        if not input_url:
            continue
            
        print("正在嘗試從網址提取 data_id...")
        extracted_data_id = extract_data_id(input_url)
        
        if not extracted_data_id:
            print("無法從網址中擷取到有效的 data_id，請確認網址格式是否正確。")
            continue
            
        print(f"對應的 data_id: {extracted_data_id}")
        
        print("-" * 40)
        result = analyze_and_get_results(extracted_data_id, hl_lang)
        
        if result:
            print("-" * 40)
            print("分析結果摘要：")
            print(f"總處理筆數：{result['total_reviews']}")
            print(f"誘因評論 (假五星) 筆數：{result['fake_count']}")
            print(f"誘因評論佔比：{result['fake_ratio']}%")
            if result['fake_time_range']:
                tr = result['fake_time_range']
                print(f"發生時間區段：從 {tr['first_occurrence']} 到 {tr['last_occurrence']}")            
            print("-" * 20)
            print(f"真實評論筆數：{result['real_reviews_count']}")
            print(f"扣除假五星後平均分數：{result['real_average_rating']} 顆星")
            print("真實評論星等分佈：")
            dist = result['real_rating_distribution']
            for star in ["5", "4", "3", "2", "1"]:
                count = dist.get(star, 0)
                # 視覺化長條圖
                bar = "█" * int(count)
                print(f"  {star} 星: {str(count).rjust(3)} 筆 | {bar}")
            print("-" * 40)
