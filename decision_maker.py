import sqlite3
import json
import urllib.request
import re
import os

DB_PATH = 'reviews.db'
POS_KEYWORDS_PATH = 'positive_keywords.txt'
NEG_KEYWORDS_PATH = 'negative_keywords.txt'

def load_keywords_file(filepath, default_content):
    """讀取外部字典檔，若無則自動建立預設值"""
    if not os.path.exists(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(default_content)
            
    categories = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ':' in line:
                cat, words = line.split(':', 1)
                categories[cat.strip()] = [w.strip() for w in words.split(',')]
    return categories

def extract_data_id(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req)
        final_url = res.geturl()
        match = re.search(r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', final_url)
        return match.group(1) if match else None
    except:
        return None

def generate_decision_report(data_id):
    if not os.path.exists(DB_PATH):
        print("❌ 找不到資料庫。")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT reviews, analysis_result FROM review_history
        WHERE data_id = ? ORDER BY created_at DESC LIMIT 1
    ''', (data_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[1]:
        print("❌ 沒有找到分析紀錄，請先執行 review_fetcher.py 與 review_processor.py。")
        return

    raw_reviews = json.loads(row[0])
    analysis_result = json.loads(row[1])

    # 1. 基礎數據
    total_count = analysis_result.get("total_reviews", 0)
    fake_count = analysis_result.get("fake_count", 0)
    fake_ratio = analysis_result.get("fake_ratio", 0)
    real_reviews = [r for r in analysis_result.get("processed_reviews", []) if not r.get("is_fake", False)]
    
    # 計算表面分數 (未過濾前)
    original_sum = sum([r.get("rating", 0) for r in raw_reviews])
    original_avg = round(original_sum / total_count, 1) if total_count > 0 else 0.0
    real_avg = analysis_result.get("real_average_rating", 0.0)

    # 2. 擷取正向與負向特徵 (針對所有真實評論)
    default_pos = "環境與衛生: 乾淨, 舒適, 裝潢好, 氣氛佳, 明亮, 寬敞, 網美\n服務與態度: 親切, 熱情, 貼心, 服務好, 笑容, 招待\n餐點與食物: 好吃, 美味, 新鮮, 驚艷, 推薦, 必點, 豐富, Q彈, 入味\n價格與CP值: 便宜, 划算, 高CP, 物超所值, 份量多, 平價\n"
    default_neg = "環境與衛生: 蟑螂, 蟲, 髒, 臭, 油膩, 蒼蠅, 老鼠, 冷氣不冷, 擁擠, 吵\n服務與態度: 態度差, 臉臭, 等很久, 漏單, 生氣, 不理, 惡劣, 催, 無視\n餐點與食物: 難吃, 沒熟, 酸掉, 冷掉, 少, 太鹹, 太淡, 不新鮮, 雷, 腥味\n價格與CP值: 貴, 不值, 坑, 黑店, 盤子, 低消, 料少\n"
    
    POS_CATEGORIES = load_keywords_file(POS_KEYWORDS_PATH, default_pos)
    NEG_CATEGORIES = load_keywords_file(NEG_KEYWORDS_PATH, default_neg)
    
    pos_counts = {k: 0 for k in POS_CATEGORIES.keys()}
    neg_counts = {k: 0 for k in NEG_CATEGORIES.keys()}
    hit_pos_keywords = {k: set() for k in POS_CATEGORIES.keys()}
    hit_neg_keywords = {k: set() for k in NEG_CATEGORIES.keys()}
    evaluated_reviews_count = 0

    for rv in real_reviews:
        snippet = rv.get("snippet", "")
        # 分析對象為所有剩下的真實評論
        if snippet:
            evaluated_reviews_count += 1
            
            # 計算正向
            for category, keywords in POS_CATEGORIES.items():
                for kw in keywords:
                    if kw in snippet:
                        pos_counts[category] += 1
                        hit_pos_keywords[category].add(kw)
                        
            # 計算負向
            for category, keywords in NEG_CATEGORIES.items():
                for kw in keywords:
                    if kw in snippet:
                        neg_counts[category] += 1
                        hit_neg_keywords[category].add(kw)

    # 尋找最大的優點與雷點
    top_pos_cat = max(pos_counts, key=pos_counts.get) if pos_counts else None
    top_neg_cat = max(neg_counts, key=neg_counts.get) if neg_counts else None

    print("\n" + "="*58)
    print("🍔 可解釋性 AI 決策支援報告 (XAI Decision Report)")
    print("="*58)
    
    # 產出：白話解釋生成 (動態字串模板組合，不使用 LLM)
    print("\n📝 [星等真實度解析]")
    if fake_count > 0:
        diff = round(original_avg - real_avg, 1)
        action = f"下修了 {diff} 顆星" if diff > 0 else (f"上調了 {abs(diff)} 顆星" if diff < 0 else "維持原星等")
            
        print(f"系統將這間店的評分從面上的 {original_avg} 顆星{action}，得出真實評分為 {real_avg} 顆星。")
        print(f"主因是在這 {total_count} 則評論中，偵測到 {fake_ratio}%（共 {fake_count} 則）包含「打卡送禮」等潛在誘因。")
        print(f"排除這些干擾後，我們對剩下的 {evaluated_reviews_count} 則純淨評論進行了文本深度解析。")
    else:
        print(f"系統評鑑這間店的結構相當健康！在 {total_count} 則留言中並無明顯被操作的打卡評論。")
        print(f"其真實星等與表面星等一致，為穩定的 {real_avg} 顆星，由此為您展開細節解析：")

    # 產出：優劣勢特徵提取
    print("\n✨ [正負評價特徵提取]")
    has_pos = top_pos_cat and pos_counts[top_pos_cat] > 0
    has_neg = top_neg_cat and neg_counts[top_neg_cat] > 0
    
    if has_pos:
        print(f"✅ 【最大亮點】集中在「{top_pos_cat}」。")
        print(f"   這群消費者最常提到的好評字眼是：{', '.join(list(hit_pos_keywords[top_pos_cat])[:7])}。")
    else:
        print("✅ 【最大亮點】：真實評論中並無特別突出的好評項目。")
        
    if has_neg:
        print(f"⚠️ 【最大隱憂】出現在「{top_neg_cat}」。")
        print(f"   遭到抱怨最多次的災情字眼為：{', '.join(list(hit_neg_keywords[top_neg_cat])[:7])}。")
    else:
        print("⚠️ 【最大隱憂】：目前的真實消費者中，並未反應出任何嚴重的客訴雷區。")

    # 產出：情境導向行動建議
    print("\n💡 [情境導向行動建議]")
    if has_neg and top_neg_cat == "環境與衛生":
        print(f"▶ 避坑提示：若您此次聚餐對「環境品質、約會氛圍」要求極高，由於出現了衛生疑慮，強烈建議更換聚餐地點。")
        print("▶ 適合情境：這間店較適合只尋求外帶、或是根本不在意內用環境只求果腹的客人。")
    elif has_neg and top_neg_cat == "服務與態度":
        print(f"▶ 避坑提示：這家店在「服務品質」上累積了較多客怨。若您不喜歡看店員臉色或排隊受氣，最好三思。")
        print("▶ 適合情境：對服務態度容忍度高、不太在意店員反應的人。")
    elif has_pos and top_pos_cat == "餐點與食物":
        print("▶ 適合情境：這間店的本體就是老饕最愛的享受！對於「追求純粹美味」的食客，非常推薦親自鑑定。")
    elif has_pos and top_pos_cat == "價格與CP值":
        print("▶ 適合情境：這是一家以「CP值」取勝的好去處！極力推薦給月底想省錢、食量大的學生或小資族群。")
    else:
        if real_avg >= 4.0:
            print("▶ 綜合建議：就我們的資料解析，這是一間各項表現相對均衡、安分守己的好店，適合多數您的日常用餐情境。")
        else:
            print("▶ 綜合建議：本店表現較為平庸落於俗套。雖無致命缺點，但也無特別突出的優勢，建議您同時搜尋周邊其他名單比較。")
        
    print("="*58 + "\n")

if __name__ == '__main__':
    while True:
        try:
            url = input("👉 請輸入 Google Maps 分享網址 (或輸入 q 離開): ").strip()
        except EOFError:
            break
        if url.lower() == 'q':
            break
        if not url: continue
        
        data_id = extract_data_id(url)
        if data_id:
            generate_decision_report(data_id)
        else:
            print("❌ 無法解析該網址的 data_id。")
