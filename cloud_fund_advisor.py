"""
云端基金晨间投资顾问 - 自动筛选版本
每天从主流ETF池中自动筛选推荐
运行在GitHub Actions上，每天早晨8:30自动推送
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
import requests
import akshare as ak
import time


# ============== 配置 ==============

# Server酱SendKey
SERVERCHAN_SENDKEY = os.getenv('SERVERCHAN_SENDKEY', '')

# 自动筛选配置
TOP_N = 10  # 推荐前N名
MIN_SCORE = 50  # 最低评分要求


# ============== 主流ETF基金池 ==============

ETF_POOL = {
    # 宽基指数ETF
    "510300.SH": {"name": "沪深300ETF", "category": "宽基指数"},
    "510500.SH": {"name": "中证500ETF", "category": "宽基指数"},
    "159915.SZ": {"name": "创业板ETF", "category": "宽基指数"},
    "588000.SH": {"name": "科创50ETF", "category": "宽基指数"},
    "159949.SZ": {"name": "创业板50ETF", "category": "宽基指数"},
    "512100.SH": {"name": "中证1000ETF", "category": "宽基指数"},
    "159531.SZ": {"name": "中证2000ETF", "category": "宽基指数"},
    "510210.SH": {"name": "上证180ETF", "category": "宽基指数"},

    # 金融板块
    "512000.SH": {"name": "券商ETF", "category": "金融"},
    "512800.SH": {"name": "银行ETF", "category": "金融"},
    "512880.SH": {"name": "证券保险ETF", "category": "金融"},

    # 科技板块
    "515000.SH": {"name": "5G ETF", "category": "科技"},
    "512480.SH": {"name": "半导体ETF", "category": "科技"},
    "159913.SZ": {"name": "科技ETF", "category": "科技"},

    # 新能源
    "516160.SH": {"name": "新能源ETF", "category": "新能源"},
    "159806.SZ": {"name": "新能源车ETF", "category": "新能源"},
    "515790.SH": {"name": "光伏ETF", "category": "新能源"},
    "159745.SZ": {"name": "电池ETF", "category": "新能源"},

    # 医药健康
    "512010.SH": {"name": "医药ETF", "category": "医药"},
    "512290.SH": {"name": "生物医药ETF", "category": "医药"},
    "159938.SZ": {"name": "医药卫生ETF", "category": "医药"},

    # 消费
    "510150.SH": {"name": "消费ETF", "category": "消费"},
    "512690.SH": {"name": "酒ETF", "category": "消费"},

    # 资源周期
    "512400.SH": {"name": "有色金属ETF", "category": "资源"},
    "515220.SH": {"name": "煤炭ETF", "category": "资源"},
    "515210.SH": {"name": "钢铁ETF", "category": "资源"},
    "159870.SZ": {"name": "化工ETF", "category": "资源"},

    # 军工
    "512660.SH": {"name": "军工ETF", "category": "军工"},

    # 红利价值
    "510880.SH": {"name": "红利ETF", "category": "策略"},
    "512080.SH": {"name": "价值ETF", "category": "策略"},

    # 房地产
    "512200.SH": {"name": "房地产ETF", "category": "地产"},
}


# ============== 数据获取 ==============

def get_fund_data_sina(code):
    """使用新浪财经API获取ETF数据"""
    try:
        url = f"http://hq.sinajs.cn/list={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}

        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            data_str = response.text
            if 'var hq_str_' in data_str and '=' in data_str:
                data_part = data_str.split('"')[1]
                parts = data_part.split(',')

                if len(parts) > 5 and parts[0]:
                    try:
                        price_current = float(parts[3]) if parts[3] else 0
                        price_prev_close = float(parts[2]) if parts[2] else 0

                        if price_current > 0 and price_prev_close > 0:
                            return {
                                'name': parts[0],
                                'current': price_current,
                                'change_pct': ((price_current - price_prev_close) / price_prev_close) * 100
                            }
                    except (ValueError, IndexError):
                        pass
        return None
    except Exception as e:
        return None


def get_fund_data_tencent(code):
    """使用腾讯财经API获取ETF数据"""
    try:
        url = f"http://qt.gtimg.cn/q={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}

        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            data_str = response.text
            if '~' in data_str and data_str.count('~') > 10:
                parts = data_str.split('~')
                if len(parts) > 5:
                    try:
                        price_current = float(parts[3]) if parts[3] else 0
                        price_prev_close = float(parts[4]) if parts[4] else 0
                        if price_current > 0 and price_prev_close > 0:
                            return {
                                'name': parts[1],
                                'current': price_current,
                                'change_pct': ((price_current - price_prev_close) / price_prev_close) * 100
                            }
                    except (ValueError, IndexError):
                        pass
        return None
    except Exception:
        return None


def scan_all_etfs():
    """
    扫描所有ETF，获取实时数据
    返回: dict[基金代码] = {name, current, change_pct, category}
    """
    all_data = {}
    success_count = 0

    print(f"📡 开始扫描 {len(ETF_POOL)} 只主流ETF...")
    print("=" * 50)

    for fund_code, info in ETF_POOL.items():
        try:
            # 生成代码格式
            if 'SH' in fund_code:
                sina_code = f"sh{fund_code.split('.')[0]}"
            else:
                sina_code = f"sz{fund_code.split('.')[0]}"

            # 尝试获取数据
            data = get_fund_data_sina(sina_code)

            if not data:
                data = get_fund_data_tencent(sina_code)

            if data:
                all_data[fund_code] = {
                    'name': data['name'],
                    'current': data['current'],
                    'change_pct': data['change_pct'],
                    'category': info['category']
                }
                success_count += 1

                symbol = "📈" if data['change_pct'] > 0 else "📉" if data['change_pct'] < 0 else "➡️"
                print(f"✅ {info['category']:8s} {data['name']:12s} {symbol} {data['change_pct']:+6.2f}%")

            # 避免请求过快
            time.sleep(0.15)

        except Exception as e:
            continue

    print("=" * 50)
    print(f"✅ 成功获取 {success_count}/{len(ETF_POOL)} 只基金数据\n")

    return all_data if all_data else None


# ============== 技术分析与评分 ==============

def calculate_etf_score(fund_code, fund_data):
    """
    ETF综合评分系统
    返回: {score, details, recommendation}
    """
    score = 50  # 基础分
    details = []

    # 1. 涨跌幅评分 (-15 ~ +15)
    change_pct = fund_data['change_pct']
    if -2 <= change_pct <= 0.5:
        score += 15
        details.append("微跌企稳")
    elif -5 <= change_pct < -2:
        score += 10
        details.append("小幅回调")
    elif 0.5 < change_pct <= 2:
        score += 5
        details.append("小幅上涨")
    elif change_pct > 5:
        score -= 10
        details.append("涨幅过大")
    elif change_pct < -5:
        score -= 5
        details.append("跌幅较大")

    # 2. 类别权重调整
    category = fund_data['category']
    if category in ['宽基指数', '医药', '消费', '策略', '金融']:
        score += 5
        details.append("稳健板块")
    elif category in ['军工', '资源', '新能源']:
        score -= 5
        details.append("高波动板块")

    # 3. 价格位置评分 (基于涨跌幅估算)
    if -3 <= change_pct <= 0:
        score += 10
        details.append("相对低位")

    # 4. 趋势评分
    if change_pct > 0:
        score += 5
        details.append("上涨趋势")
    elif change_pct < -1:
        score -= 5
        details.append("下跌趋势")

    # 5. 波动率惩罚
    if abs(change_pct) > 4:
        score -= 5
        details.append("高波动")

    # 生成建议
    if score >= 70:
        recommendation = "⭐⭐⭐ 强烈推荐"
        risk = "低风险"
    elif score >= 60:
        recommendation = "⭐⭐ 推荐"
        risk = "中等风险"
    elif score >= 50:
        recommendation = "⭐ 观望"
        risk = "中等风险"
    else:
        recommendation = "❌ 回避"
        risk = "较高风险"

    return {
        'score': min(100, max(0, score)),
        'details': details,
        'recommendation': recommendation,
        'risk': risk
    }


def screen_and_rank(all_fund_data):
    """
    筛选并排名ETF
    返回: Top N 推荐
    """
    scored_funds = []

    for fund_code, fund_data in all_fund_data.items():
        score_result = calculate_etf_score(fund_code, fund_data)

        scored_funds.append({
            'code': fund_code,
            'name': fund_data['name'],
            'current': fund_data['current'],
            'change_pct': fund_data['change_pct'],
            'category': fund_data['category'],
            **score_result
        })

    # 按评分排序
    scored_funds.sort(key=lambda x: x['score'], reverse=True)

    # 筛选Top N
    top_funds = [f for f in scored_funds if f['score'] >= MIN_SCORE][:TOP_N]

    return top_funds, scored_funds[:20]  # 返回推荐和前20名


# ============== 生成报告 ==============

def generate_morning_report(top_funds, all_top_funds):
    """生成晨间投资报告"""
    if not top_funds:
        return None

    report_lines = []

    today = datetime.now()
    today_str = today.strftime("%Y年%m月%d日")
    weekday = today.weekday()
    weekdays = ['一', '二', '三', '四', '五']
    weekday_str = weekdays[weekday] if weekday < 5 else '日'

    # 标题
    report_lines.append("📅 " + today_str + " 星期" + weekday_str)
    report_lines.append("🌅 基金晨间投资报告")
    report_lines.append("=" * 50)
    report_lines.append("")
    report_lines.append("⏰ 今日开盘时间: 9:30")
    report_lines.append(f"📊 扫描基金池: {len(ETF_POOL)}只主流ETF")
    report_lines.append(f"🎯 推荐范围: 前{TOP_N}名 (评分≥{MIN_SCORE})")
    report_lines.append("")

    # 今日推荐
    if top_funds:
        report_lines.append("🏆 今日重点关注推荐")
        report_lines.append("━" * 50)
        report_lines.append("")

        for i, fund in enumerate(top_funds, 1):
            change_symbol = "📈" if fund['change_pct'] > 0 else "📉" if fund['change_pct'] < 0 else "➡️"

            report_lines.append(f"【#{i}】{fund['name']} ({fund['code']})")
            report_lines.append(f"  评分: {fund['score']}/100  {fund['risk']}")
            report_lines.append(f"  最新价: {fund['current']:.3f}  {change_symbol} {fund['change_pct']:+.2f}%")
            report_lines.append(f"  板块: {fund['category']}")
            report_lines.append(f"  💡 {fund['recommendation']}")
            report_lines.append(f"  🔍 理由: {' | '.join(fund['details'][:3])}")
            report_lines.append("")

    # Top 20 排行
    if all_top_funds:
        report_lines.append("=" * 50)
        report_lines.append("📊 Top 20 排行榜")
        report_lines.append("━" * 50)
        report_lines.append("")

        for i, fund in enumerate(all_top_funds, 1):
            change_symbol = "📈" if fund['change_pct'] > 0 else "📉" if fund['change_pct'] < 0 else "➡️"
            recommend_short = fund['recommendation'].replace('⭐⭐⭐', '★★★').replace('⭐⭐', '★★').replace('⭐', '★').replace('❌', '×')

            report_lines.append(
                f"#{i:2d} {fund['name']:10s} {fund['score']:3d}分 "
                f"{change_symbol} {fund['change_pct']:+6.2f}% "
                f"{recommend_short}"
            )

        report_lines.append("")

    # 市场分析
    all_changes = [f['change_pct'] for f in all_top_funds]
    avg_change = sum(all_changes) / len(all_changes) if all_changes else 0
    up_count = sum(1 for c in all_changes if c > 0)
    down_count = sum(1 for c in all_changes if c < 0)

    report_lines.append("=" * 50)
    report_lines.append("📈 市场情绪")
    report_lines.append("=" * 50)
    report_lines.append(f"平均涨跌: {avg_change:+.2f}%")
    report_lines.append(f"上涨/下跌: {up_count}/{down_count}")

    if avg_change > 1:
        sentiment = "🟢 市场偏强"
    elif avg_change < -1:
        sentiment = "🔴 市场偏弱"
    else:
        sentiment = "🟡 市场中性"

    report_lines.append(f"整体情绪: {sentiment}")
    report_lines.append("")

    # 操作建议
    report_lines.append("=" * 50)
    report_lines.append("💡 今日操作建议")
    report_lines.append("=" * 50)
    report_lines.append("")

    if avg_change > 1:
        report_lines.append("• 市场强势，可适当参与")
        report_lines.append("• 关注评分≥60的ETF")
    elif avg_change < -1:
        report_lines.append("• 市场调整，谨慎为主")
        report_lines.append("• 等待企稳信号")
    else:
        report_lines.append("• 市场震荡，稳健操作")
        report_lines.append("• 可小仓位试探")

    report_lines.append("")

    # 免责声明
    report_lines.append("=" * 50)
    report_lines.append("📌 风险提示")
    report_lines.append("=" * 50)
    report_lines.append("• 本报告仅供参考，不构成投资建议")
    report_lines.append("• ETF有风险，投资需谨慎")
    report_lines.append("• 建议结合自身风险承受能力")
    report_lines.append("")
    report_lines.append("🤖 Powered by GitHub Actions | 自动筛选")

    return "\n".join(report_lines)


# ============== 发送消息 ==============

def send_serverchan(message):
    """通过Server酱发送消息"""
    try:
        url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
        data = {
            "title": f"🌅 基金晨间报告 - {datetime.now().strftime('%m/%d')}",
            "desp": message
        }
        response = requests.post(url, json=data, timeout=15)

        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print("✅ 消息发送成功")
                return True

        print(f"❌ 发送失败: {response.text}")
        return False
    except Exception as e:
        print(f"❌ 发送错误: {e}")
        return False


# ============== 主程序 ==============

def send_error_notification(error_msg):
    """发送错误通知"""
    try:
        url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
        data = {
            "title": f"⚠️ 基金报告推送失败 - {datetime.now().strftime('%m/%d %H:%M')}",
            "desp": error_msg
        }
        requests.post(url, json=data, timeout=15)
    except:
        pass


def main():
    print("=" * 50)
    print("🌅 基金晨间投资顾问启动")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 自动筛选模式")
    print("=" * 50)
    print()

    try:
        # 1. 扫描所有ETF
        all_data = scan_all_etfs()

        if not all_data or len(all_data) < 5:
            error_msg = f"""获取数据不足，无法生成报告

可能原因：
• 当前时间：{datetime.now().strftime('%H:%M')}
• 市场状态：未开盘或非交易时间
• API问题：数据源可能暂时不可用

建议：
• 请在交易时间（9:30-15:00）手动触发测试
• 或将定时任务调整为9:30之后执行

获取数据量：{len(all_data) if all_data else 0} / 32
"""
            print("❌ 获取数据不足，无法生成报告")
            send_error_notification(error_msg)
            return

        # 2. 评分筛选
        print("📊 正在分析评分...")
        top_funds, all_top_funds = screen_and_rank(all_data)

        if not top_funds:
            error_msg = f"""没有符合条件的推荐

分析完成，但没有筛选出符合条件的ETF
• 当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
• 分析基金数：{len(all_data)}
• 评分标准：最低{MIN_SCORE}分

这可能是市场整体行情导致的正常现象
"""
            print("⚠️ 没有符合条件的推荐")
            send_error_notification(error_msg)
            return

        print(f"✅ 筛选出 {len(top_funds)} 只推荐ETF\n")

        # 3. 生成报告
        report = generate_morning_report(top_funds, all_top_funds)

        if not report:
            print("❌ 生成报告失败")
            return

        print("📊 报告预览:")
        print("=" * 50)
        print(report[:500] + "...")
        print("=" * 50)
        print()

        # 4. 发送消息
        print("📤 正在发送到微信...")
        success = send_serverchan(report)

        if success:
            print("\n✅ 晨间报告发送完成！")
        else:
            print("\n❌ 发送失败")

        print("=" * 50)

    except Exception as e:
        error_msg = f"""程序运行异常

错误信息：{str(e)}

请检查代码或联系管理员
"""
        print(f"❌ 运行异常: {e}")
        send_error_notification(error_msg)


if __name__ == "__main__":
    main()
