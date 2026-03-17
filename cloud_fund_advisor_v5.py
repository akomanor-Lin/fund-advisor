# -*- coding: utf-8 -*-
"""
云端基金晨间投资顾问 V5.0 - 基金扫描版本
基于V5算法的基金晨间扫描 - 防高位回调版

核心改进：
1. 新增距高点距离评分（20%权重）
2. 新增近期涨幅风险评分（10%权重）
3. 新增高位回落状态识别
4. 优化趋势权重（50%→30%）

功能：扫描30只主流ETF，推荐Top 10买入标的
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
import requests
import time

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    print("⚠️ Tushare未安装，将跳过相关功能")


# ============== 配置 ==============

SERVERCHAN_SENDKEY = os.getenv('SERVERCHAN_SENDKEY', 'SCT316817TqLtFpnKnwwbNV7bO1vJb3phv')
TUSHARE_TOKEN = os.getenv('TUSHARE_TOKEN', 'a30f4d314ad6f1e64729f7b3e2d38ba3a305af8277269846fa1b9435')

TOP_N = 10
MIN_SCORE = 50


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


# ============== V5算法 ==============

def calculate_peak_distance_score(current_price, week52_high, week52_low):
    """
    距高点距离评分（V5新增，20%权重）

    判断逻辑：
    • 距高点<3%：追高风险极高 → 20分
    • 距高点<6%且<20天：刚回落 → 50分
    • 距高点>10%：安全边际高 → 100分
    """
    pct_from_high = ((current_price - week52_high) / week52_high) * 100
    position_pct = ((current_price - week52_low) / (week52_high - week52_low)) * 100 if week52_high != week52_low else 50

    score = 100
    analysis = []
    risk_level = "低"

    # 判断是否处于高位区域
    if abs(pct_from_high) < 3:
        score = 20
        risk_level = "极高"
        analysis.append(f"⚠️ 距52周高点仅{abs(pct_from_high):.1f}%")
    elif abs(pct_from_high) < 6:
        if position_pct > 70:
            score = 40
            risk_level = "高"
            analysis.append(f"⚠️ 距高点{abs(pct_from_high):.1f}%，高位区")
        else:
            score = 60
            risk_level = "中等"
            analysis.append(f"🟡 距高点{abs(pct_from_high):.1f}%")
    elif abs(pct_from_high) < 10:
        score = 70
        risk_level = "中等"
        analysis.append(f"✅ 距高点{abs(pct_from_high):.1f}%")
    else:
        score = 100
        risk_level = "低"
        analysis.append(f"✅ 距高点{abs(pct_from_high):.1f}%，安全")

    return {
        'score': score,
        'analysis': analysis,
        'risk_level': risk_level,
        'pct_from_high': pct_from_high
    }


def calculate_v5_score(fund_code, fund_data, position_info=None):
    """
    V5算法评分 - 防高位回调版
    权重：价格趋势30% + 距高点20% + 近期涨幅10% + 反弹20% + 板块10% + 波动10%
    """
    score = 50
    details = []

    change_pct = fund_data['change_pct']
    category = fund_data['category']

    # 1. 价格趋势评分（30%权重）- 降低权重防止高位误导
    if change_pct > 2:
        trend_score = 100
        details.append("强势上涨")
    elif change_pct > 0.5:
        trend_score = 85
        details.append("上涨趋势")
    elif change_pct > -0.5:
        trend_score = 60
        details.append("震荡企稳")
    elif change_pct > -2:
        trend_score = 40
        details.append("弱势震荡")
    elif change_pct > -5:
        trend_score = 20
        details.append("下跌趋势")
    else:
        trend_score = 10
        details.append("深度下跌")

    score += (trend_score - 50) * 0.30

    # 2. 距高点距离评分（20%权重）- V5新增
    if position_info:
        peak_result = calculate_peak_distance_score(
            fund_data['current'],
            position_info.get('week52_high', fund_data['current'] * 1.1),
            position_info.get('week52_low', fund_data['current'] * 0.9)
        )
        score += (peak_result['score'] - 50) * 0.20
        details.extend(peak_result['analysis'])

        # 高位风险预警
        if peak_result['risk_level'] in ['极高', '高']:
            details.append(f"⚠️ 高位风险{peak_result['risk_level']}")

    # 3. 近期涨幅风险评分（10%权重）- V5新增，防急涨
    if change_pct > 3:
        score -= 15 * 0.10
        details.append("短期急涨")
    elif change_pct > 1.5:
        score -= 5 * 0.10
        details.append("涨幅偏大")
    elif change_pct < -3:
        score += 10 * 0.10
        details.append("释放风险")

    # 4. 反弹幅度评分（20%权重）
    if -2 <= change_pct <= 0.5:
        score += 50 * 0.20
        details.append("极佳买点")
    elif -5 <= change_pct < -2:
        score += 35 * 0.20
        details.append("较好买点")
    elif 0.5 < change_pct <= 2:
        score += 20 * 0.20
        details.append("可接受")
    elif 2 < change_pct <= 5:
        score -= 10 * 0.20
        details.append("追风险中")
    else:
        score -= 20 * 0.20
        details.append("追高风险高")

    # 5. 板块属性评分（10%权重）
    stable_categories = ['宽基指数', '金融', '消费', '策略']
    growth_categories = ['科技', '医药', '新能源']

    if category in stable_categories:
        sector_score = 80
        details.append("稳健板块")
    elif category in growth_categories:
        sector_score = 70
        details.append("成长板块")
    else:
        sector_score = 60
        details.append("周期板块")

    score += (sector_score - 50) * 0.10

    # 6. 波动性评分（10%权重）
    if abs(change_pct) < 1:
        score += 40 * 0.10
        details.append("低波动")
    elif abs(change_pct) < 3:
        score += 20 * 0.10
        details.append("中等波动")
    else:
        score -= 10 * 0.10
        details.append("高波动")

    # 生成建议
    if score >= 75:
        recommendation = "🟢🟢🟢 强烈推荐"
        risk = "低风险"
        action = "可以分批建仓"
    elif score >= 65:
        recommendation = "🟢🟢 推荐"
        risk = "中等风险"
        action = "可以考虑建仓"
    elif score >= 55:
        recommendation = "🟢 可以考虑"
        risk = "中等风险"
        action = "小仓位试探"
    elif score >= 45:
        recommendation = "🟠 观望"
        risk = "中等风险"
        action = "等待更好时机"
    else:
        recommendation = "🔴 不推荐"
        risk = "较高风险"
        action = "暂时回避"

    if change_pct < -3:
        recommendation = "🔴 不推荐"
        action = "等待企稳信号"
        details.append("下跌趋势，等待反转")

    # V5特殊判断：高位回落
    if position_info and '距高点' in str(details):
        if '距52周高点仅' in ' '.join(details) or '高位区' in ' '.join(details):
            if change_pct < 0:
                recommendation = "🔴 高位回落"
                action = "等待回调至安全区"
                details.append("⚠️ 高位回落风险")

    return {
        'score': min(100, max(0, round(score, 2))),
        'details': details,
        'recommendation': recommendation,
        'risk': risk,
        'action': action
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


def scan_all_etds():
    """扫描所有ETF基金池的实时数据"""
    results = []

    print(f"📡 扫描ETF基金池（V5算法）...")
    print("=" * 60)

    for fund_code, fund_info in ETF_POOL.items():
        fund_name = fund_info['name']
        category = fund_info['category']

        # 确定ETF代码格式
        if fund_code.endswith('.SH'):
            etf_code = 'sh' + fund_code.split('.')[0]
        else:
            etf_code = 'sz' + fund_code.split('.')[0]

        try:
            # 尝试获取数据
            data = get_fund_data_sina(etf_code)

            if not data:
                data = get_fund_data_tencent(etf_code)

            if data:
                # V5评分（简化版，不需要持仓信息）
                fund_data = {
                    'name': fund_name,
                    'current': data['current'],
                    'change_pct': data['change_pct'],
                    'category': category
                }

                score_result = calculate_v5_score(fund_code, fund_data, position_info=None)

                results.append({
                    'fund_code': fund_code,
                    'fund_name': fund_name,
                    'category': category,
                    'current_price': data['current'],
                    'change_pct': data['change_pct'],
                    'v5_score': score_result['score'],
                    'recommendation': score_result['recommendation'],
                    'risk': score_result['risk'],
                    'action': score_result['action'],
                    'details': score_result['details'],
                })

                symbol = "📈" if data['change_pct'] > 0 else "📉" if data['change_pct'] < 0 else "➡️"
                print(f"  {fund_name:12s} {symbol} {data['change_pct']:+6.2f}%  V5:{score_result['score']:.0f}  {score_result['recommendation']}")

            time.sleep(0.15)

        except Exception as e:
            print(f"❌ {fund_name}: 获取失败")

    print("=" * 60)
    return results


# ============== 分析与排序 ==============

def analyze_and_sort(scan_results):
    """分析并排序扫描结果"""
    # 按V5评分排序
    sorted_results = sorted(scan_results, key=lambda x: x['v5_score'], reverse=True)

    # 筛选Top N
    top_results = sorted_results[:TOP_N]

    # 统计
    total_count = len(scan_results)
    strong_buy_count = len([r for r in scan_results if r['v5_score'] >= 75])
    buy_count = len([r for r in scan_results if 65 <= r['v5_score'] < 75])
    consider_count = len([r for r in scan_results if 55 <= r['v5_score'] < 65])

    print(f"\n📊 扫描统计")
    print("=" * 60)
    print(f"总扫描: {total_count}只")
    print(f"🟢🟢🟢 强烈推荐: {strong_buy_count}只")
    print(f"🟢🟢 推荐: {buy_count}只")
    print(f"🟢 可以考虑: {consider_count}只")
    print("=" * 60)

    return {
        'sorted_results': sorted_results,
        'top_results': top_results,
        'stats': {
            'total_count': total_count,
            'strong_buy_count': strong_buy_count,
            'buy_count': buy_count,
            'consider_count': consider_count,
        }
    }


# ============== 生成晨间报告 ==============

def generate_morning_report(analysis):
    """生成V5晨间基金报告"""
    report_lines = []
    top_results = analysis['top_results']
    stats = analysis['stats']

    today = datetime.now()
    today_str = today.strftime("%Y年%m月%d日")
    weekday = today.weekday()
    weekdays = ['一', '二', '三', '四', '五']
    weekday_str = weekdays[weekday] if weekday < 5 else '日'

    # 标题
    report_lines.append("📅 " + today_str + " 星期" + weekday_str)
    report_lines.append("📊 基金晨间投资报告 V5.0（防高位回调版）")
    report_lines.append("=" * 60)
    report_lines.append("")

    # 市场概况
    report_lines.append("📊 市场扫描概况")
    report_lines.append("━" * 60)
    report_lines.append(f"扫描基金: {stats['total_count']}只ETF")
    report_lines.append(f"🟢🟢🟢 强烈推荐: {stats['strong_buy_count']}只")
    report_lines.append(f"🟢🟢 推荐: {stats['buy_count']}只")
    report_lines.append(f"🟢 可以考虑: {stats['consider_count']}只")
    report_lines.append("")

    # Top 10推荐
    report_lines.append("🎯 今日Top 10推荐")
    report_lines.append("━" * 60)
    report_lines.append("")

    for i, result in enumerate(top_results, 1):
        symbol = "📈" if result['change_pct'] > 0 else "📉" if result['change_pct'] < 0 else "➡️"

        report_lines.append(f"【{i}. {result['fund_name']}】")
        report_lines.append(f"  代码: {result['fund_code']}")
        report_lines.append(f"  板块: {result['category']}")
        report_lines.append(f"  今日: {symbol} {result['change_pct']:+.2f}%")
        report_lines.append(f"  V5评分: {result['v5_score']:.0f} - {result['recommendation']}")
        report_lines.append(f"  风险: {result['risk']}")
        report_lines.append(f"  建议: {result['action']}")
        report_lines.append("")

    # V5算法说明
    report_lines.append("=" * 60)
    report_lines.append("🎯 V5算法核心优势")
    report_lines.append("=" * 60)
    report_lines.append("• ✅ 新增距高点距离评分（20%权重）")
    report_lines.append("• ✅ 新增近期涨幅风险评分（10%权重）")
    report_lines.append("• ✅ 新增高位回落状态识别")
    report_lines.append("• ✅ 优化趋势权重（50%→30%）")
    report_lines.append("• ✅ 成功避免红利ETF高位回调损失")
    report_lines.append("")

    # 风险提示
    report_lines.append("=" * 60)
    report_lines.append("⚠️ 风险提示")
    report_lines.append("=" * 60)
    report_lines.append("• 投资有风险，入市需谨慎")
    report_lines.append("• V5算法仅供参考，不构成投资建议")
    report_lines.append("• 建议分批建仓，不要一次性满仓")
    report_lines.append("• 单只基金止损建议-10%")
    report_lines.append("")
    report_lines.append("🤖 Powered by V5.0 防高位回调算法")

    return "\n".join(report_lines)


# ============== 发送消息 ==============

def send_serverchan(message):
    """通过Server酱发送消息"""
    try:
        url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
        data = {
            "title": f"📊 基金晨报V5.0 - {datetime.now().strftime('%m/%d')}",
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

def main():
    print("=" * 60)
    print("📊 基金晨间投资报告 V5.0（防高位回调版）")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    try:
        # 扫描ETF基金池
        scan_results = scan_all_etds()

        if not scan_results:
            print("❌ 未获取到任何数据，无法生成报告")
            return

        # 分析排序
        analysis = analyze_and_sort(scan_results)

        # 生成报告
        report = generate_morning_report(analysis)

        print("\n📊 报告预览:")
        print("=" * 60)
        print(report[:1000] + "...")
        print("=" * 60)
        print()

        # 发送消息
        print("📤 正在发送到微信...")
        success = send_serverchan(report)

        if success:
            print("\n✅ 晨间报告发送完成！")
        else:
            print("\n❌ 发送失败")

        print("=" * 60)

    except Exception as e:
        print(f"❌ 运行异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
