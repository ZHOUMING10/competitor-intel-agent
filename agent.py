import os
import json
import requests
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件中的环境变量

# ---- 配置 ----
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")  # 可选：飞书机器人 webhook 地址

# 要监控的竞品列表（URL 可换成真实的官网、微博、公众号等）
COMPETITORS = {
    "竞品A": "https://example-competitor-a.com/news",
    "竞品B": "https://example-competitor-b.com/blog",
}

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


# ---- Step 1: 数据抓取 Agent ----
def fetch_competitor_data(name, url):
    """抓取竞品网页内容"""
    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        # 简单提取文本（实际可用 BeautifulSoup 精确解析）
        text = resp.text[:2000]
        print(f"[采集] {name} 数据获取成功，长度: {len(text)} 字符")
        return text
    except Exception as e:
        print(f"[采集] {name} 抓取失败: {e}")
        return f"抓取失败，错误信息: {str(e)}"


# ---- Step 2: 分析 Agent ----
def analyze_competitor(name, raw_text):
    """调用 DeepSeek 生成摘要和情感倾向"""
    prompt = f"""
你是一个资深市场分析师。请根据以下竞品"{name}"的网页内容，执行三个任务：
1. 提取3个以内的关键更新点（产品发布、促销活动、高层变动等）
2. 判断整体情感倾向（积极/中性/消极）
3. 生成一段80字以内的简报，适合推送给运营团队。

内容如下：
{raw_text[:1500]}

请用 JSON 格式返回，包含字段：key_updates（列表）、sentiment（字符串）、brief（字符串）。
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        result = response.choices[0].message.content
        print(f"[分析] {name} 分析完成")
        return result
    except Exception as e:
        print(f"[分析] {name} 调用失败: {e}")
        return '{"error": "分析失败"}'


# ---- Step 3: 报告组装 & 推送 Agent ----
def push_report(report_text):
    """推送到飞书（如果有 webhook），否则保存到本地文件"""
    if FEISHU_WEBHOOK:
        try:
            requests.post(FEISHU_WEBHOOK, json={
                "msg_type": "text",
                "content": {"text": report_text}
            })
            print("[推送] 已发送至飞书群")
        except Exception as e:
            print(f"[推送] 飞书发送失败: {e}")
    else:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"[推送] 报告已保存至 {filename}")


# ---- 主工作流 ----
def run_intel_agent():
    print("=== 竞品舆情 Agent 启动 ===\n")
    full_report = f"# 竞品舆情日报 ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"

    for name, url in COMPETITORS.items():
        print(f"\n--- 处理 {name} ---")
        raw_text = fetch_competitor_data(name, url)
        json_analysis = analyze_competitor(name, raw_text)

        try:
            analysis = json.loads(json_analysis)
            if "error" not in analysis:
                key_updates = analysis.get("key_updates", [])
                sentiment = analysis.get("sentiment", "未知")
                brief = analysis.get("brief", "无")
            else:
                key_updates, sentiment, brief = [], "错误", "分析失败"
        except json.JSONDecodeError:
            key_updates, sentiment, brief = [], "错误", "JSON解析失败"

        report_section = (
            f"## {name}\n"
            f"**情感倾向**: {sentiment}\n"
            f"**关键更新**: {', '.join(key_updates) if key_updates else '无'}\n"
            f"> {brief}\n\n"
        )
        full_report += report_section

    print("\n" + "=" * 50)
    print(full_report)
    push_report(full_report)
    print("=== 任务结束 ===")


if __name__ == "__main__":
    run_intel_agent()