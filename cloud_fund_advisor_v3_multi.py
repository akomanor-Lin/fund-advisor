# -*- coding: utf-8 -*-
"""
云端基金晨间投资顾问 V3.0 - 多持仓版本
基于V4算法的多持仓策略测试

核心升级：
1. 支持多持仓配置（5只基金）
2. 每只基金独立的盈亏分析
3. 组合整体收益统计
4. 分批建仓建议
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

# V3.0: 多持仓配置
MULTI_POSITIONS = {
    'positions': [
        {
            'fund_code': '510300.SH',
            'fund_name': '沪深300ETF',
            'etf_code': 'sh510300',
            'category': '宽基指数',
            'cost_nav': None,  # 建仓时填写
            'shares': None,    # 建仓时填写
            'principal': 250,  # 计划本金
            'target_nav': None,  # 目标买入价
        },
        {
            'fund_code': '512800.SH',
            'fund_name': '银行ETF',
            'etf_code': 'sh512800',
            'category': '金融',
            'cost_nav': None,
            'shares': None,
            'principal': 200,
            'target_nav': None,
        },
        {
            'fund_code': '510880.SH',
            'fund_name': '红利ETF',
            'etf_code': 'sh510880',
            'category': '策略',
            'cost_nav': None,
            'shares': None,
            'principal': 200,
            'target_nav': None,
        },
        {
            'fund_code': '510150.SH',
            'fund_name': '消费ETF',
            'etf_code': 'sh510150',
            'category': '消费',
            'cost_nav': None,
            'shares': None,
            'principal': 200,
            'target_nav': None,
        },
        {
            'fund_code': '159915.SZ',
            'fund_name': '创业板ETF',
            'etf_code': 'sz159915',
            'category': '宽基指数',
            'cost_nav': None,
            'shares': None,
            'principal': 150,
            'target_nav': None,
        },
    ],
    'total_principal': 1000,  # 总本金
    'build_strategy': 'batch',  # 建仓策略：batch(分批) / once(一次性)
}


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


# ============== V4算法（保持不变）=============

def calculate_v4_score(fund_code, fund_data):
    """
    V4算法评分 - 价格趋势优先
    权重：价格趋势50% + 反弹幅度20% + 板块属性15% + 波动性15%
    """
    score = 50
    details = []

    change_pct = fund_data['change_pct']
    category = fund_data['category']

    # 1. 价格趋势评分（50%权重）- 最重要
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

    score += (trend_score - 50) * 0.5

    # 2. 反弹幅度评分（20%权重）
    if -2 <= change_pct <= 0.5:
        score += 50 * 0.2
        details.append("极佳买点")
    elif -5 <= change_pct < -2:
        score += 35 * 0.2
        details.append("较好买点")
    elif 0.5 < change_pct <= 2:
        score += 20 * 0.2
        details.append("可接受")
    elif 2 < change_pct <= 5:
        score -= 10 * 0.2
        details.append("追高风险中等")
    else:
        score -= 20 * 0.2
        details.append("追高风险高")

    # 3. 板块属性评分（15%权重）
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

    score += (sector_score - 50) * 0.15

    # 4. 波动性评分（15%权重）
    if abs(change_pct) < 1:
        score += 40 * 0.15
        details.append("低波动")
    elif abs(change_pct) < 3:
        score += 20 * 0.15
        details.append("中等波动")
    else:
        score -= 10 * 0.15
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
        recommendation = "🟡 观望"
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


def scan_target_etds(target_list):
    """扫描目标ETF的实时数据"""
    results = []

    print(f"📡 扫描 {len(target_list)} 只目标ETF...")
    print("=" * 60)

    for position in target_list:
        etf_code = position['etf_code']
        fund_code = position['fund_code']
        fund_name = position['fund_name']
        category = position['category']

        try:
            # 尝试获取数据
            data = get_fund_data_sina(etf_code)

            if not data:
                data = get_fund_data_tencent(etf_code)

            if data:
                # V4评分
                fund_data = {
                    'name': fund_name,
                    'current': data['current'],
                    'change_pct': data['change_pct'],
                    'category': category
                }

                score_result = calculate_v4_score(fund_code, fund_data)

                results.append({
                    'fund_code': fund_code,
                    'fund_name': fund_name,
                    'category': category,
                    'current_price': data['current'],
                    'change_pct': data['change_pct'],
                    'v4_score': score_result['score'],
                    'recommendation': score_result['recommendation'],
                    'risk': score_result['risk'],
                    'action': score_result['action'],
                    'details': score_result['details'],
                })

                symbol = "📈" if data['change_pct'] > 0 else "📉" if data['change_pct'] < 0 else "➡️"
                print(f"✅ {fund_name:12s} {symbol} {data['change_pct']:+6.2f}%  V4评分:{score_result['score']:.0f}  {score_result['recommendation']}")

            time.sleep(0.15)

        except Exception as e:
            print(f"❌ {fund_name}: 获取失败")

    print("=" * 60)
    return results


# ============== 多持仓分析 ==============

def analyze_multi_positions(scan_results, positions_config):
    """分析多持仓情况"""
    total_principal = positions_config['total_principal']
    positions = positions_config['positions']

    analysis = {
        'total_principal': total_principal,
        'positions_analysis': [],
        'batch_plan': {
            'batch_1': [],
            'batch_2': []
        }
    }

    print("\n📊 多持仓分析")
    print("=" * 60)

    for i, position in enumerate(positions):
        fund_code = position['fund_code']

        # 查找扫描结果
        scan_data = next((r for r in scan_results if r['fund_code'] == fund_code), None)

        if scan_data:
            principal = position['principal']
            current_price = scan_data['current_price']
            v4_score = scan_data['v4_score']
            recommendation = scan_data['recommendation']

            # 计算预估份额
            estimated_shares = int(principal / current_price / 100) * 100  # ETF按手买

            # 分批建议
            if v4_score >= 65:
                batch = 'batch_1'
                batch_reason = 'V4评分高，第一批建仓'
            elif v4_score >= 55:
                batch = 'batch_2'
                batch_reason = 'V4评分中等，第二批建仓'
            else:
                batch = 'wait'
                batch_reason = 'V4评分低，暂缓建仓'

            pos_analysis = {
                'fund_name': position['fund_name'],
                'fund_code': fund_code,
                'principal': principal,
                'current_price': current_price,
                'estimated_shares': estimated_shares,
                'v4_score': v4_score,
                'recommendation': recommendation,
                'batch': batch,
                'batch_reason': batch_reason
            }

            analysis['positions_analysis'].append(pos_analysis)

            if batch in ['batch_1', 'batch_2']:
                analysis['batch_plan'][batch].append(pos_analysis)

            print(f"\n【{i+1}】{position['fund_name']} ({position['category']})")
            print(f"  计划金额: {principal}元")
            print(f"  当前价格: {current_price:.3f}")
            print(f"  预估份额: {estimated_shares}份")
            print(f"  V4评分: {v4_score:.0f} - {recommendation}")
            print(f"  建仓批次: {batch_reason}")

    return analysis


# ============== 生成V3报告 ==============

def generate_v3_report(scan_results, analysis):
    """生成V3多持仓报告"""
    report_lines = []

    today = datetime.now()
    today_str = today.strftime("%Y年%m月%d日")
    weekday = today.weekday()
    weekdays = ['一', '二', '三', '四', '五']
    weekday_str = weekdays[weekday] if weekday < 5 else '日'

    # 标题
    report_lines.append("📅 " + today_str + " 星期" + weekday_str)
    report_lines.append("🎯 基金多持仓策略报告 V3.0")
    report_lines.append("=" * 60)
    report_lines.append("")

    # 策略说明
    report_lines.append("🎲 测试策略：多持仓 + V4算法")
    report_lines.append(f"  持仓数量: {len(scan_results)}只")
    report_lines.append(f"  总本金: {analysis['total_principal']}元")
    report_lines.append(f"  建仓方式: 分批建仓")
    report_lines.append("")

    # 第一批建仓
    batch_1 = analysis['batch_plan']['batch_1']
    if batch_1:
        report_lines.append("🚀 第一批建仓（今天）")
        report_lines.append("━" * 60)
        report_lines.append("")

        for pos in batch_1:
            report_lines.append(f"【{pos['fund_name']}】")
            report_lines.append(f"  代码: {pos['fund_code']}")
            report_lines.append(f"  当前价: {pos['current_price']:.3f}")
            report_lines.append(f"  建仓金额: {pos['principal']}元")
            report_lines.append(f"  预估份额: {pos['estimated_shares']}份")
            report_lines.append(f"  V4评分: {pos['v4_score']:.0f} - {pos['recommendation']}")
            report_lines.append("")

        batch_1_total = sum(p['principal'] for p in batch_1)
        report_lines.append(f"第一批合计: {batch_1_total}元")
        report_lines.append("")

    # 第二批建仓
    batch_2 = analysis['batch_plan']['batch_2']
    if batch_2:
        report_lines.append("⏳ 第二批建仓（明天/后天）")
        report_lines.append("━" * 60)
        report_lines.append("")

        for pos in batch_2:
            report_lines.append(f"【{pos['fund_name']}】")
            report_lines.append(f"  代码: {pos['fund_code']}")
            report_lines.append(f"  当前价: {pos['current_price']:.3f}")
            report_lines.append(f"  建仓金额: {pos['principal']}元")
            report_lines.append(f"  V4评分: {pos['v4_score']:.0f} - {pos['recommendation']}")
            report_lines.append("")

        batch_2_total = sum(p['principal'] for p in batch_2)
        report_lines.append(f"第二批合计: {batch_2_total}元")
        report_lines.append("")

    # V4算法说明
    report_lines.append("=" * 60)
    report_lines.append("📊 V4算法说明")
    report_lines.append("━" * 60)
    report_lines.append("权重分配：")
    report_lines.append("  • 价格趋势: 50%（最重要）")
    report_lines.append("  • 反弹幅度: 20%（避免追高）")
    report_lines.append("  • 板块属性: 15%（稳健板块加分）")
    report_lines.append("  • 波动性: 15%（低波动加分）")
    report_lines.append("")
    report_lines.append("最佳买点：")
    report_lines.append("  • 涨跌幅: -2% ~ +0.5%（极佳买点）")
    report_lines.append("  • 板块: 宽基/金融/消费（稳健板块）")
    report_lines.append("  • 波动: <1%（低波动）")
    report_lines.append("")

    # 风险提示
    report_lines.append("=" * 60)
    report_lines.append("⚠️ 风险提示")
    report_lines.append("=" * 60)
    report_lines.append("• 本策略仅供参考，不构成投资建议")
    report_lines.append("• ETF有风险，投资需谨慎")
    report_lines.append("• 建议设置止损：单只基金-10%，组合整体-8%")
    report_lines.append("• V4算法优先价格趋势，避免下跌品种")
    report_lines.append("")
    report_lines.append("🤖 Powered by V3.0 多持仓策略 | 测试V4算法稳定性")

    return "\n".join(report_lines)


# ============== 发送消息 ==============

def send_serverchan(message):
    """通过Server酱发送消息"""
    try:
        url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
        data = {
            "title": f"🎯 多持仓策略V3.0 - {datetime.now().strftime('%m/%d')}",
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
    print("🎯 基金多持仓策略 V3.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 测试多持仓 + V4算法")
    print("=" * 60)
    print()

    try:
        # 扫描目标ETF
        scan_results = scan_target_etds(MULTI_POSITIONS['positions'])

        if not scan_results:
            print("❌ 未获取到任何数据，无法生成报告")
            return

        # 分析多持仓
        analysis = analyze_multi_positions(scan_results, MULTI_POSITIONS)

        # 生成报告
        report = generate_v3_report(scan_results, analysis)

        print("\n📊 报告预览:")
        print("=" * 60)
        print(report[:1000] + "...")
        print("=" * 60)
        print()

        # 发送消息
        print("📤 正在发送到微信...")
        success = send_serverchan(report)

        if success:
            print("\n✅ 多持仓策略报告发送完成！")
        else:
            print("\n❌ 发送失败")

        print("=" * 60)

    except Exception as e:
        print(f"❌ 运行异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
