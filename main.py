import requests
import re
import datetime
import os

# ================= 配置区域 =================
# 读取 GitHub 的保密配置
# 从环境变量获取 Key 字符串 (SCT_A,SCT_B,SCT_C)
KEYS_STR = os.getenv("SERVERCHAN_KEY", "")

TARGETS = {
    "美股纳指": {"code": "gb_ixic", "type": "us"},
    "标普500":  {"code": "gb_inx",  "type": "us"},
    "港股恒指": {"code": "rt_hkHSI", "type": "hk"},
    "美元/人民币": {"code": "fx_susdcny", "type": "fx"},
    "黄金期货": {"code": "hf_GC", "type": "future"},
    "白银期货": {"code": "hf_SI", "type": "future"},
    "铜期货":   {"code": "hf_HG", "type": "future"},
}

# ================= 热点政策新闻配置 =================
# 使用新浪财经滚动新闻接口（无需额外 key），做一个简单的关键词过滤
SINA_POLICY_NEWS_API = (
    "https://feed.mix.sina.com.cn/api/roll/get"
    "?pageid=155&lid=2516&num=30&page=1&callback="
)

# 这里是一些粗略筛选“可能影响股市的政策/宏观”新闻的关键词
POLICY_KEYWORDS = [
    "政策", "央行", "美联储", "加息", "降息", "利率",
    "关税", "制裁", "减税", "财政刺激", "货币政策",
    "通胀", "通缩", "就业", "失业", "贸易协定", "贸易战",
    "经济数据", "GDP", "PMI"
]

def get_sina_data(targets):
    codes = [item['code'] for item in targets.values()]
    url = f"http://hq.sinajs.cn/list={','.join(codes)}"
    headers = {"Referer": "https://finance.sina.com.cn/"}

    try:
        resp = requests.get(url, headers=headers, timeout=5)
        text = resp.text
    except Exception as e:
        return "获取失败", str(e)

    results = []
    main_title_info = ""

    for name, config in targets.items():
        pattern = f'var hq_str_{config["code"]}="(.*?)";'
        match = re.search(pattern, text)
        
        if match:
            data_str = match.group(1)
            parts = data_str.split(',')
            try:
                price, change_pct = 0.0, 0.0
                
                # --- 解析逻辑 ---
                if config['type'] == 'us':
                    price = float(parts[1])
                    change_pct = float(parts[2])
                elif config['type'] == 'hk':
                    price = float(parts[6])
                    change_pct = float(parts[8])
                elif config['type'] == 'future':
                    price = float(parts[0])
                    prev_close = float(parts[7])
                    if prev_close > 0:
                        change_pct = ((price - prev_close) / prev_close) * 100
                elif config['type'] == 'fx':
                    price = float(parts[1])
                    change_pct = 0.0 

                # --- 图标逻辑 ---
                if change_pct > 0:
                    icon, sign = "🔴", "+"
                elif change_pct < 0:
                    icon, sign = "🟢", ""
                else:
                    icon, sign = "⚪", ""

                # --- 【排版优化】改为清单格式 ---
                # 汇率不需要显示涨跌幅，其他需要
                if name == "美元/人民币":
                     line = f"{icon} **{name}**: {price:.4f}"
                else:
                     line = f"{icon} **{name}**: {price:,.2f} ({sign}{change_pct:.2f}%)"
                
                # 收集标题信息
                if name == "美股纳指":
                    main_title_info += f"纳指 {sign}{change_pct:.2f}%"
                if name == "美元/人民币":
                    main_title_info += f" | 汇率 {price:.2f}"
                    
            except:
                line = f"⚪ **{name}**: 解析出错"
        else:
            line = f"⚪ **{name}**: 无数据"
            
        results.append(line)

    time_str = datetime.datetime.now().strftime("%m-%d %H:%M")
    title = f"盘前: {main_title_info}"
    
    # 使用 \n\n 强制换行，让手机显示更舒服
    content = f"📅 {time_str}\n\n" + "\n\n".join(results)
    
    return title, content


def get_policy_news(max_items=5):
    """
    获取前一晚及近期的国内外政策/宏观类热点新闻（简单版本）。
    - 使用新浪财经滚动新闻接口；
    - 通过标题关键词做一个大致过滤。
    """
    try:
        resp = requests.get(SINA_POLICY_NEWS_API, timeout=5)
        data = resp.json()
    except Exception as e:
        return [f"⚪ 热点政策新闻获取失败: {e}"]

    items = data.get("result", {}).get("data", []) or []
    news_lines = []

    # 先按关键词过滤一轮
    for item in items:
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()
        if not title:
            continue
        if any(k in title for k in POLICY_KEYWORDS):
            line = f"• {title}\n  {url}" if url else f"• {title}"
            news_lines.append(line)
        if len(news_lines) >= max_items:
            break

    # 如果关键词过滤结果太少，就退而求其次，直接拿最新几条
    if not news_lines:
        for item in items[:max_items]:
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            if not title:
                continue
            line = f"• {title}\n  {url}" if url else f"• {title}"
            news_lines.append(line)

    return news_lines

def push_to_wechat(title, content):
    if not KEYS_STR:
        print("⚠️ 未配置 Key")
        return
    
    # 【核心修改】分割 Key 并循环发送
    keys = KEYS_STR.split(",")
    for key in keys:
        key = key.strip() # 去除可能误填的空格
        if not key: continue
        
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = {"title": title, "desp": content}
        try:
            requests.post(url, data=data)
            print(f"✅ 已推送给: ...{key[-4:]}")
        except Exception as e:
            print(f"❌ 推送失败 ({key[-4:]}): {e}")

if __name__ == "__main__":
    title, content = get_sina_data(TARGETS)

    # 追加热点政策新闻区块
    policy_news_lines = get_policy_news(max_items=5)
    if policy_news_lines:
        content = (
            content
            + "\n\n"
            + "📰 热点政策 / 宏观新闻（昨晚及近期）\n\n"
            + "\n\n".join(policy_news_lines)
        )
    print("--- 预览 ---")
    print(title)
    print(content)
    print("-----------")
    push_to_wechat(title, content)
