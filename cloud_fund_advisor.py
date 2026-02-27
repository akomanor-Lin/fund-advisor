"""
云端基金晨间投资顾问
运行在GitHub Actions上，每天早晨8:30自动推送
使用AkShare获取真实数据
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
import requests
import akshare as ak
import time


# ============== 配置 ==============

# 从环境变量读取配置
SERVERCHAN_SENDKEY = os.getenv('SERVERCHAN_SENDKEY', '')
FUND_LIST_STR = os.getenv('FUND_LIST', '510300.SH,159915.SZ')

# 解析基金列表
FUND_LIST = [f.strip() for f in FUND_LIST_STR.split(',') if f.strip()]

# 默认基金列表
if not FUND_LIST:
    FUND_LIST = ['510300.SH', '159915.SZ', '512000.SH']


# ============== 数据获取 ==============

def get_fund_data_cloud():
    """
    从云端获取基金数据
    使用AkShare获取真实数据
    """
    try:
        all_data = {}

        print(f"📡 正在获取 {len(FUND_LIST)} 只基金的数据...")

        # 基金信息
        fund_info = {
            "510300.SH": {"name": "沪深300ETF", "type": "etf"},
            "159915.SZ": {"name": "创业板ETF", "type": "etf"},
            "512000.SH": {"name": "券商ETF", "type": "etf"},
            "510500.SH": {"name": "中证500ETF", "type": "etf"},
            "159949.SZ": {"name": "创业板50ETF", "type": "etf"},
            "000001": {"name": "华夏成长", "type": "open"},
            "110022": {"name": "易方达消费行业", "type": "open"},
        }

        for fund_code in FUND_LIST:
            info = fund_info.get(fund_code, {"name": fund_code, "type": "etf"})

            try:
                print(f"  获取 {info['name']}({fund_code})...")

                if info['type'] == 'etf':
                    # 场内ETF - 使用股票接口
                    code = fund_code.split('.')[0]
                    df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")

                    if df is not None and not df.empty:
                        # 获取基金名称
                        try:
                            fund_info_detail = ak.stock_individual_info_em(symbol=code)
                            fund_name = fund_info_detail[fund_info_detail['item'] == '股票名称']['value'].values[0]
                        except:
                            fund_name = info['name']

                        # 取最新数据
                        latest = df.iloc[0]

                        all_data[fund_code] = {
                            "name": fund_name,
                            "type": "etf",
                            "df": df.head(60),
                            "latest_nav": latest['收盘'],
                            "change_pct": latest['涨跌幅']
                        }

                        print(f"  ✅ {fund_code}: 净值={latest['收盘']:.4f}, 涨跌={latest['涨跌幅']:+.2f}%")

                else:
                    # 场外基金 - 使用基金接口
                    try:
                        # 尝试获取开放式基金净值
                        df = ak.fund_open_fund_info_em(fund=fund_code, indicator="单位净值走势")

                        if df is not None and not df.empty:
                            latest = df.iloc[0]

                            all_data[fund_code] = {
                                "name": info['name'],
                                "type": "open",
                                "df": df.head(60),
                                "latest_nav": latest['单位净值'],
                                "change_pct": 0  # 需要计算
                            }

                            print(f"  ✅ {fund_code}: 净值={latest['单位净值']:.4f}")
                    except:
                        print(f"  ⚠️ {fund_code} 场外基金数据获取失败，跳过")

                # 避免请求过快
                time.sleep(0.5)

            except Exception as e:
                print(f"  ❌ {fund_code} 获取失败: {e}")
                continue

        return all_data if all_data else None

    except Exception as e:
        print(f"获取数据时出错: {e}")
        return None


# ============== 技术分析 ==============

def calculate_ma(df, period=5):
    return df['收盘'].rolling(window=period).mean().iloc[-1] if '收盘' in df.columns else df['净值'].rolling(window=period).mean().iloc[-1]


def calculate_rsi(df, period=14):
    price_col = '收盘' if '收盘' in df.columns else '净值'
    delta = df[price_col].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50


def analyze_trend(df):
    ma5 = calculate_ma(df, 5)
    ma10 = calculate_ma(df, 10)
    ma20 = calculate_ma(df, 20)
    price_col = '收盘' if '收盘' in df.columns else '净值'
    current_price = df[price_col].iloc[-1]

    if current_price > ma5 > ma10 > ma20:
        return "强势上涨", 8
    elif current_price > ma5 > ma10:
        return "上涨趋势", 6
    elif ma5 < ma10 < ma20 and current_price < ma5:
        return "下跌趋势", 3
    else:
        return "震荡整理", 5


def calculate_support_resistance(df):
    price_col = '收盘' if '收盘' in df.columns else '净值'
    recent_data = df.tail(20)
    resistance = recent_data[price_col].max()
    support = recent_data[price_col].min()
    current = df[price_col].iloc[-1]

    return {
        'support': support,
        'resistance': resistance,
        'current': current,
        'position': (current - support) / (resistance - support) * 100 if resistance > support else 50
    }


# ============== 生成建议 ==============

def generate_etf_advice(fund_code, fund_data):
    df = fund_data['df']
    fund_name = fund_data['name']
    latest_nav = fund_data['latest_nav']
    change_pct = fund_data['change_pct']

    # 技术分析
    rsi = calculate_rsi(df)
    trend, trend_score = analyze_trend(df)
    sr = calculate_support_resistance(df)

    # 评分
    score = 50
    reasons = []

    score += trend_score - 5
    reasons.append(trend)

    if rsi < 30:
        score += 10
        reasons.append("RSI超卖")
    elif rsi > 70:
        score -= 10
        reasons.append("RSI超买")

    if sr['position'] < 30:
        score += 10
        reasons.append("接近支撑")

    # 生成建议
    if score >= 65:
        action = "可考虑买入"
        risk = "中等风险"
    elif score >= 50:
        action = "可小仓位买入"
        risk = "中等风险"
    elif score >= 40:
        action = "建议观望"
        risk = "低风险"
    else:
        action = "建议回避"
        risk = "较高风险"

    return {
        'code': fund_code,
        'name': fund_name,
        'score': score,
        'action': action,
        'risk': risk,
        'nav': latest_nav,
        'change': change_pct,
        'trend': trend,
        'rsi': round(rsi, 2),
        'support': round(sr['support'], 4),
        'resistance': round(sr['resistance'], 4)
    }


def generate_open_fund_advice(fund_code, fund_data):
    df = fund_data['df']
    fund_name = fund_data['name']
    latest_nav = fund_data['latest_nav']

    # 简化分析
    score = 50
    action = "继续定投"

    # 30日涨跌
    price_col = '单位净值' if '单位净值' in df.columns else '净值'
    momentum_30 = (df[price_col].iloc[-1] / df[price_col].iloc[-30] - 1) * 100

    if momentum_30 > 5:
        score += 15
    elif momentum_30 < -5:
        score -= 15

    if score >= 60:
        action = "建议积极定投"
    elif score >= 45:
        action = "保持定投"
    else:
        action = "暂停定投，观望"

    return {
        'code': fund_code,
        'name': fund_name,
        'score': score,
        'action': action,
        'nav': latest_nav,
        'momentum_30': round(momentum_30, 2)
    }


# ============== 生成报告 ==============

def generate_morning_report(all_fund_data):
    if not all_fund_data:
        return None

    report_lines = []

    today = datetime.now()
    today_str = today.strftime("%Y年%m月%d日")
    weekday = today.weekday()
    weekdays = ['一', '二', '三', '四', '五']
    weekday_str = weekdays[weekday] if weekday < 5 else '日'

    report_lines.append(f"📅 {today_str} 星期{weekday_str}")
    report_lines.append(f"🌅 基金晨间投资报告")
    report_lines.append("=" * 50)
    report_lines.append("")
    report_lines.append("⏰ 今日开盘时间: 9:30")
    report_lines.append("📊 数据来源: AkShare (实时数据)")
    report_lines.append("🤖 云端自动生成")
    report_lines.append("")

    # 分类处理
    etf_list = []
    open_list = []

    for fund_code, fund_data in all_fund_data.items():
        if fund_data['type'] == 'etf':
            advice = generate_etf_advice(fund_code, fund_data)
            etf_list.append(advice)
        else:
            advice = generate_open_fund_advice(fund_code, fund_data)
            open_list.append(advice)

    # 场内ETF
    if etf_list:
        etf_list.sort(key=lambda x: x['score'], reverse=True)

        report_lines.append("📊 场内ETF基金操作建议")
        report_lines.append("━" * 50)
        report_lines.append("")

        for i, item in enumerate(etf_list, 1):
            change_symbol = "📈" if item['change'] > 0 else "📉" if item['change'] < 0 else "➡️"

            report_lines.append(f"【#{i}】{item['name']} ({item['code']})")
            report_lines.append(f"  评分: {item['score']}/100  {item['risk']}")
            report_lines.append(f"  昨日净值: {item['nav']:.4f}  {change_symbol} {item['change']:+.2f}%")
            report_lines.append(f"  💡 建议: {item['action']}")
            report_lines.append(f"  🔍 趋势: {item['trend']} | RSI: {item['rsi']}")
            report_lines.append(f"  📍 支撑: {item['support']:.4f} | 压力: {item['resistance']:.4f}")
            report_lines.append("")

    # 场外基金
    if open_list:
        open_list.sort(key=lambda x: x['score'], reverse=True)

        report_lines.append("=" * 50)
        report_lines.append("💰 场外基金定投建议")
        report_lines.append("━" * 50)
        report_lines.append("")

        for i, item in enumerate(open_list, 1):
            report_lines.append(f"【#{i}】{item['name']} ({item['code']})")
            report_lines.append(f"  评分: {item['score']}/100")
            report_lines.append(f"  最新净值: {item['nav']:.4f}")
            report_lines.append(f"  近30日: {item['momentum_30']:+.2f}%")
            report_lines.append(f"  💡 建议: {item['action']}")
            report_lines.append("")

    # 总结
    report_lines.append("=" * 50)
    report_lines.append("🎯 今日策略")
    report_lines.append("=" * 50)
    report_lines.append("")

    all_scores = [item['score'] for item in etf_list + open_list]
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 50

    if avg_score >= 60:
        strategy = "可适当积极"
    elif avg_score >= 45:
        strategy = "稳健为主"
    else:
        strategy = "谨慎观望"

    report_lines.append(f"市场评分: {avg_score:.0f}/100")
    report_lines.append(f"操作策略: {strategy}")
    report_lines.append("")

    if etf_list:
        best = etf_list[0]
        report_lines.append(f"🥇 今日推荐: {best['name']}")
        report_lines.append(f"   建议: {best['action']}")
        report_lines.append("")

    report_lines.append("=" * 50)
    report_lines.append("📌 提示")
    report_lines.append("=" * 50)
    report_lines.append("• 本报告仅供参考，不构成投资建议")
    report_lines.append("• 基金有风险，投资需谨慎")
    report_lines.append("")
    report_lines.append("🤖 Powered by GitHub Actions")

    return "\n".join(report_lines)


# ============== 发送消息 ==============

def send_serverchan(message):
    """通过Server酱发送消息"""
    try:
        url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
        data = {
            "title": "🌅 基金晨间投资报告",
            "desp": message
        }
        response = requests.post(url, json=data, timeout=15)

        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print("✅ 消息发送成功")
                return True
            else:
                print(f"❌ 发送失败: {result.get('message')}")
                return False
        else:
            print(f"❌ 发送失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 发送错误: {e}")
        return False


# ============== 主程序 ==============

def main():
    print("=" * 50)
    print("🌅 基金晨间投资顾问启动")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print()

    # 获取数据
    all_data = get_fund_data_cloud()

    if not all_data:
        print("❌ 无法获取数据")
        return

    print(f"\n✅ 成功获取 {len(all_data)} 只基金数据\n")

    # 生成报告
    report = generate_morning_report(all_data)

    if not report:
        print("❌ 生成报告失败")
        return

    print("📊 报告内容:")
    print("=" * 50)
    print(report)
    print("=" * 50)
    print()

    # 发送消息
    print("📤 正在发送到微信...")
    success = send_serverchan(report)

    if success:
        print("\n✅ 晨间报告发送完成！")
    else:
        print("\n❌ 发送失败")

    print("=" * 50)


if __name__ == "__main__":
    main()
