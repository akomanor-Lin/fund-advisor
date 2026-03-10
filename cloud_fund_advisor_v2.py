# -*- coding: utf-8 -*-
"""
云端基金晨间投资顾问 V2.0
基于2026-03-10科创50暴力反转经验优化

核心升级：
1. 异常波动检测（暴力反转、暴涨、暴跌）
2. 集成Tushare数据
3. V4算法基金筛选（价格趋势优先50%）
4. 用户持仓智能分析
5. 动态操作策略

运行在GitHub Actions上，每天早晨8:30自动推送
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

# 尝试导入tushare（可选）
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    print("⚠️ Tushare未安装，将跳过相关功能")


# ============== 配置 ==============

# Server酱SendKey
SERVERCHAN_SENDKEY = os.getenv('SERVERCHAN_SENDKEY', 'SCT316817TqLtFpnKnwwbNV7bO1vJb3phv')

# Tushare Token
TUSHARE_TOKEN = os.getenv('TUSHARE_TOKEN', 'a30f4d314ad6f1e64729f7b3e2d38ba3a305af8277269846fa1b9435')

# 自动筛选配置
TOP_N = 10
MIN_SCORE = 50

# 用户持仓配置（V2.0新增）
USER_POSITION = {
    'fund_code': '011612',
    'fund_name': '华夏科创50ETF联接A',
    'index': '科创50',
    'cost_nav': 1.111,
    'principal': 1000,
    'yesterday_nav': None,
    'yesterday_change_pct': None,
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


# ============== 异常波动检测（V2.0新增）=============

class AnomalyDetector:
    """异常波动检测器 - 基于2026-03-10暴力反转经验"""

    @staticmethod
    def detect_violent_reversal(yesterday_change, today_open_change):
        """
        检测暴力反转
        参数: yesterday_change, today_open_change (涨跌幅%)
        """
        if yesterday_change is None or today_open_change is None:
            return None

        total_change = today_open_change - yesterday_change

        # 条件1：昨日下跌且今日大涨
        if yesterday_change < -1.5 and today_open_change > 1.5:
            return {
                'is_anomaly': True,
                'type': '暴力反转',
                'severity': '高',
                'description': f'昨日{yesterday_change:+.2f}%, 今日高开{today_open_change:+.2f}%（总变化{total_change:+.2f}%）',
                'implication': '可能是行情反转的信号，注意观察持续性',
                'action': '不要急于止盈，观察上午走势，让利润奔跑',
            }

        # 条件2：两日总变化超过3.5%
        elif total_change > 3.5:
            return {
                'is_anomaly': True,
                'type': '剧烈波动',
                'severity': '中',
                'description': f'两日总变化{total_change:+.2f}%（昨日{yesterday_change:+.2f}% → 今日{today_open_change:+.2f}%）',
                'implication': '市场波动加剧，情绪化交易增多',
                'action': '保持冷静，严格执行止盈止损',
            }

        return None

    @staticmethod
    def detect_all(yesterday_change, today_open_change):
        """检测所有异常，返回异常列表"""
        anomalies = []

        # 1. 暴力反转检测
        reversal = AnomalyDetector.detect_violent_reversal(yesterday_change, today_open_change)
        if reversal:
            anomalies.append(reversal)

        # 2. 暴涨检测
        if today_open_change and today_open_change > 3.0:
            anomalies.append({
                'is_anomaly': True,
                'type': '暴涨',
                'severity': '中',
                'description': f'单日涨幅{today_open_change:+.2f}%',
                'implication': '短期涨幅过大，可能有回调风险',
                'action': '设置动态止盈，保护利润',
            })

        # 3. 暴跌检测
        if yesterday_change and yesterday_change < -3.0:
            anomalies.append({
                'is_anomaly': True,
                'type': '暴跌',
                'severity': '高',
                'description': f'单日跌幅{yesterday_change:+.2f}%',
                'implication': '市场恐慌情绪蔓延',
                'action': '严格执行止损，不要抄底',
            })

        return anomalies


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


def get_tushare_index_data(index_code):
    """使用Tushare获取指数数据（V2.0新增）"""
    if not TUSHARE_AVAILABLE:
        return None

    try:
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")

        df = pro.index_daily(ts_code=index_code, start_date=start_date, end_date=end_date)

        if df is not None and len(df) > 0:
            df = df.sort_values('trade_date')
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest

            return {
                'trade_date': latest['trade_date'],
                'close': latest['close'],
                'change_pct': ((latest['close'] - prev['close']) / prev['close']) * 100
            }

    except Exception as e:
        print(f"Tushare获取失败: {e}")

    return None


def scan_all_etfs():
    """扫描所有ETF，获取实时数据"""
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


# ============== 用户持仓分析（V2.0新增）=============

def analyze_user_position(yesterday_nav, yesterday_change_pct, today_open_change=None):
    """分析用户持仓情况"""
    principal = USER_POSITION['principal']
    cost_nav = USER_POSITION['cost_nav']

    # 计算昨日市值和盈亏
    yesterday_value = principal * yesterday_nav / cost_nav
    yesterday_profit = yesterday_value - principal
    yesterday_profit_pct = (yesterday_profit / principal) * 100

    # 计算今日预估
    if today_open_change:
        today_nav = yesterday_nav * (1 + today_open_change / 100)
        today_value = principal * today_nav / cost_nav
        today_profit = today_value - principal
        today_profit_pct = (today_profit / principal) * 100
    else:
        today_nav = yesterday_nav
        today_value = yesterday_value
        today_profit = yesterday_profit
        today_profit_pct = yesterday_profit_pct

    # 止损位
    stop_loss_nav = cost_nav * 0.97
    stop_loss_value = principal * 0.97
    distance_to_stop = ((today_nav - stop_loss_nav) / stop_loss_nav) * 100

    # 风险等级
    if distance_to_stop < 2:
        risk_level = '高'
        risk_icon = '🔴'
    elif distance_to_stop < 5:
        risk_level = '中'
        risk_icon = '🟡'
    else:
        risk_level = '低'
        risk_icon = '🟢'

    # 操作建议
    if today_profit_pct > 10:
        action = "建议分批止盈"
        detail = "盈利+20%: 止盈30%; 盈利+30%: 止盈40%; 盈利+50%: 全部止盈"
    elif today_profit_pct > 0:
        action = "建议继续持有"
        detail = f"设置止盈位: +10%（{principal * 1.1:.0f}元）；止损: 成本价"
    elif today_profit_pct > -3:
        action = "建议谨慎持有"
        detail = f"严格执行止损: -3%（{stop_loss_value:.0f}元）；不要加仓"
    else:
        action = "建议止损"
        detail = "已触发止损条件，建议立即止损"

    return {
        'yesterday_nav': yesterday_nav,
        'yesterday_value': yesterday_value,
        'yesterday_profit': yesterday_profit,
        'yesterday_profit_pct': yesterday_profit_pct,
        'today_nav': today_nav,
        'today_value': today_value,
        'today_profit': today_profit,
        'today_profit_pct': today_profit_pct,
        'stop_loss_nav': stop_loss_nav,
        'stop_loss_value': stop_loss_value,
        'distance_to_stop': distance_to_stop,
        'risk_level': risk_level,
        'risk_icon': risk_icon,
        'action': action,
        'detail': detail
    }


# ============== V4算法评分（V2.0核心）=============

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

    # 价格趋势权重50%
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

    # 特殊判断：深度下跌不推荐
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


def screen_and_rank(all_fund_data):
    """使用V4算法筛选并排名ETF"""
    scored_funds = []

    for fund_code, fund_data in all_fund_data.items():
        score_result = calculate_v4_score(fund_code, fund_data)

        scored_funds.append({
            'code': fund_code,
            'name': fund_data['name'],
            'current': fund_data['current'],
            'change_pct': fund_data['change_pct'],
            'category': fund_data['category'],
            **score_result
        })

    # 按V4评分排序
    scored_funds.sort(key=lambda x: x['score'], reverse=True)

    # 筛选Top N
    top_funds = [f for f in scored_funds if f['score'] >= MIN_SCORE][:TOP_N]

    return top_funds, scored_funds[:20]


# ============== 生成报告V2.0 ==============

def generate_morning_report_v2(top_funds, all_top_funds, position_analysis=None, anomalies=None):
    """生成晨间投资报告 V2.0"""
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
    report_lines.append("🌅 基金晨间投资报告 V2.0")
    report_lines.append("=" * 50)
    report_lines.append("")
    report_lines.append("⏰ 今日开盘时间: 9:30")
    report_lines.append(f"📊 扫描基金池: {len(ETF_POOL)}只主流ETF")
    report_lines.append(f"🎯 推荐范围: 前{TOP_N}名 (V4评分≥{MIN_SCORE})")
    report_lines.append("🔥 算法升级: 价格趋势优先（50%权重）")
    report_lines.append("")

    # 异常波动预警
    if anomalies and len(anomalies) > 0:
        report_lines.append("🚨 异常波动预警")
        report_lines.append("━" * 50)
        report_lines.append("")

        for anomaly in anomalies:
            severity_icon = {'高': '🔴', '中': '🟡', '低': '🟢'}.get(anomaly['severity'], '⚪')
            report_lines.append(f"{severity_icon} {anomaly['type']}（{anomaly['severity']}风险）")
            report_lines.append(f"   描述: {anomaly['description']}")
            report_lines.append(f"   含义: {anomaly['implication']}")
            report_lines.append(f"   建议: {anomaly['action']}")
            report_lines.append("")

        report_lines.append("")

    # 用户持仓分析
    if position_analysis:
        report_lines.append("💼 您的持仓分析")
        report_lines.append("━" * 50)
        report_lines.append("")

        pos = position_analysis
        report_lines.append(f"基金: {USER_POSITION['fund_name']} ({USER_POSITION['fund_code']})")
        report_lines.append(f"成本: {USER_POSITION['cost_nav']} | 本金: {USER_POSITION['principal']}元")
        report_lines.append("")
        report_lines.append("【昨日收盘】")
        report_lines.append(f"净值: {pos['yesterday_nav']:.4f}")
        report_lines.append(f"市值: {pos['yesterday_value']:.2f}元")
        report_lines.append(f"盈亏: {pos['yesterday_profit']:+.2f}元 ({pos['yesterday_profit_pct']:+.2f}%)")
        report_lines.append("")
        report_lines.append("【今日预估】")
        report_lines.append(f"净值: {pos['today_nav']:.4f}")
        report_lines.append(f"市值: {pos['today_value']:.2f}元")
        report_lines.append(f"盈亏: {pos['today_profit']:+.2f}元 ({pos['today_profit_pct']:+.2f}%)")
        report_lines.append("")
        report_lines.append("【止损管理】")
        report_lines.append(f"止损位: {pos['stop_loss_nav']:.4f} ({pos['stop_loss_value']:.2f}元)")
        report_lines.append(f"距离止损: {pos['distance_to_stop']:+.2f}% {pos['risk_icon']}{pos['risk_level']}风险")
        report_lines.append("")
        report_lines.append("【操作建议】")
        report_lines.append(f"{pos['action']}")
        report_lines.append(f"详情: {pos['detail']}")
        report_lines.append("")

    # 今日推荐（V4算法）
    if top_funds:
        report_lines.append("🏆 今日推荐（V4算法）")
        report_lines.append("━" * 50)
        report_lines.append("")

        for i, fund in enumerate(top_funds, 1):
            change_symbol = "📈" if fund['change_pct'] > 0 else "📉" if fund['change_pct'] < 0 else "➡️"
            report_lines.append(f"【#{i}】{fund['name']} ({fund['code']})")
            report_lines.append(f"  V4评分: {fund['score']}/100  {fund['risk']}")
            report_lines.append(f"  最新价: {fund['current']:.3f}  {change_symbol} {fund['change_pct']:+.2f}%")
            report_lines.append(f"  板块: {fund['category']}")
            report_lines.append(f"  建议: {fund['recommendation']}")
            report_lines.append(f"  操作: {fund['action']}")
            report_lines.append("")

    # Top 20 排行
    if all_top_funds:
        report_lines.append("=" * 50)
        report_lines.append("📊 Top 20 排行榜（V4算法）")
        report_lines.append("━" * 50)
        report_lines.append("")

        for i, fund in enumerate(all_top_funds, 1):
            change_symbol = "📈" if fund['change_pct'] > 0 else "📉" if fund['change_pct'] < 0 else "➡️"
            recommend_short = fund['recommendation'].replace('🟢🟢🟢', '★★★').replace('🟢🟢', '★★').replace('🟢', '★').replace('🔴', '×')

            report_lines.append(
                f"#{i:2d} {fund['name']:10s} {int(fund['score']):3d}分 "
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

    if anomalies and len(anomalies) > 0:
        high_severity = [a for a in anomalies if a['severity'] == '高']
        if high_severity:
            report_lines.append("⚠️ 检测到高风险异常，需要特别关注：")
            for anomaly in high_severity:
                report_lines.append(f"• {anomaly['type']}: {anomaly['action']}")
            report_lines.append("")
            report_lines.append("其他建议：")
        else:
            report_lines.append("检测到异常波动，建议谨慎操作：")
    else:
        report_lines.append("市场正常，按常规策略操作：")

    if avg_change > 1:
        report_lines.append("• 市场强势，可适当参与")
        report_lines.append("• 关注V4评分≥65的ETF")
        report_lines.append("• 不要追高，注意回调风险")
    elif avg_change < -1:
        report_lines.append("• 市场调整，谨慎为主")
        report_lines.append("• 等待企稳信号")
        report_lines.append("• 不要急于抄底")
    else:
        report_lines.append("• 市场震荡，稳健操作")
        report_lines.append("• 可小仓位试探")
        report_lines.append("• 严格止损")

    report_lines.append("")

    # 关键时间点
    report_lines.append("⏰ 关键时间点提醒:")
    report_lines.append("• 9:30 开盘观察")
    report_lines.append("• 10:00 第一次检查")
    report_lines.append("• 14:30 🔑 关键决策点")
    report_lines.append("• 14:50 最后检查")
    report_lines.append("• 15:00 收盘决策")
    report_lines.append("")

    # 免责声明
    report_lines.append("=" * 50)
    report_lines.append("📌 风险提示")
    report_lines.append("=" * 50)
    report_lines.append("• 本报告仅供参考，不构成投资建议")
    report_lines.append("• ETF有风险，投资需谨慎")
    report_lines.append("• 建议结合自身风险承受能力")
    report_lines.append("• V4算法优先价格趋势，避免下跌品种")
    report_lines.append("")
    report_lines.append("🤖 Powered by GitHub Actions | V2.0升级版")

    return "\n".join(report_lines)


# ============== 发送消息 ==============

def send_serverchan(message):
    """通过Server酱发送消息"""
    try:
        url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
        data = {
            "title": f"🌅 基金晨报V2.0 - {datetime.now().strftime('%m/%d')}",
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


# ============== 主程序 ==============

def main():
    print("=" * 50)
    print("🌅 基金晨间投资顾问 V2.0 启动")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔥 V4算法: 价格趋势优先（50%权重）")
    print(f"🚨 异常检测: 暴力反转、暴涨、暴跌")
    print("=" * 50)
    print()

    try:
        # ========== V2.0新增：获取用户持仓数据 ==========
        print("📊 获取用户持仓数据...")

        # 尝试从Tushare获取科创50数据
        index_data = get_tushare_index_data('000688.SH')

        if index_data:
            USER_POSITION['yesterday_nav'] = 1.1295
            USER_POSITION['yesterday_change_pct'] = index_data['change_pct']
            print(f"✅ 昨日科创50涨跌: {index_data['change_pct']:+.2f}%")
        else:
            # 使用示例数据（需要手工输入）
            USER_POSITION['yesterday_nav'] = 1.1295
            USER_POSITION['yesterday_change_pct'] = -1.61
            print("⚠️ 使用示例数据（-1.61%）")

        print()

        # ========== V2.0新增：异常波动检测 ==========
        print("🚨 检测异常波动...")

        # 今日开盘涨幅（暂时使用昨日数据）
        today_open_change = USER_POSITION['yesterday_change_pct']

        anomalies = AnomalyDetector.detect_all(
            USER_POSITION['yesterday_change_pct'],
            today_open_change
        )

        if anomalies:
            print(f"⚠️ 检测到 {len(anomalies)} 个异常波动")
            for anomaly in anomalies:
                print(f"   - {anomaly['type']}: {anomaly['description']}")
        else:
            print("✅ 未检测到异常波动")

        print()

        # ========== V2.0新增：持仓分析 ==========
        print("💼 分析用户持仓...")
        position_analysis = analyze_user_position(
            USER_POSITION['yesterday_nav'],
            USER_POSITION['yesterday_change_pct'],
            today_open_change
        )

        print(f"当前市值: {position_analysis['today_value']:.2f}元")
        print(f"浮动盈亏: {position_analysis['today_profit']:+.2f}元 ({position_analysis['today_profit_pct']:+.2f}%)")
        print(f"操作建议: {position_analysis['action']}")
        print()

        # ========== 扫描所有ETF ==========
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

获取数据量：{len(all_data) if all_data else 0} / {len(ETF_POOL)}
"""
            print("❌ 获取数据不足，无法生成报告")
            send_error_notification(error_msg)
            return

        # ========== V4算法评分筛选 ==========
        print("📊 使用V4算法分析评分...")
        top_funds, all_top_funds = screen_and_rank(all_data)

        if not top_funds:
            error_msg = f"""没有符合条件的推荐

分析完成，但没有筛选出符合条件的ETF
• 当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
• 分析基金数：{len(all_data)}
• 评分标准：V4评分≥{MIN_SCORE}

这可能是市场整体行情导致的正常现象
"""
            print("⚠️ 没有符合条件的推荐")
            send_error_notification(error_msg)
            return

        print(f"✅ 筛选出 {len(top_funds)} 只推荐ETF\n")

        # ========== 生成V2.0晨报 ==========
        report = generate_morning_report_v2(
            top_funds,
            all_top_funds,
            position_analysis,
            anomalies
        )

        if not report:
            print("❌ 生成报告失败")
            return

        print("📊 报告预览:")
        print("=" * 50)
        print(report[:800] + "...")
        print("=" * 50)
        print()

        # ========== 发送消息 ==========
        print("📤 正在发送到微信...")
        success = send_serverchan(report)

        if success:
            print("\n✅ 晨间报告V2.0发送完成！")
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
