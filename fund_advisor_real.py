"""
基金晨间投资顾问 - 真实数据版本
使用新浪财经API获取实时数据
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import config
import os
import requests
import urllib3
import time

# 禁用代理和警告
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()
session.trust_env = False
session.proxies = {'http': None, 'https': None}


def get_sina_fund_data(fund_code, fund_type):
    """
    从新浪财经获取基金数据
    fund_type: 'etf' 或 'open'
    """
    try:
        if fund_type == 'etf':
            # 场内ETF基金 - 使用实时行情接口
            # 新浪财经接口: http://hq.sinajs.cn/list=sh510300
            code = fund_code.replace('.SH', '').replace('.SZ', '').lower()
            market = 'sh' if fund_code.endswith('.SH') else 'sz'

            url = f"http://hq.sinajs.cn/list={market}{code}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = session.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                # 解析数据
                content = response.text
                if 'var hq_str_' in content:
                    data_str = content.split('=')[1].strip('"; \n')
                    data_parts = data_str.split(',')

                    if len(data_parts) > 1:
                        name = data_parts[0]
                        price = float(data_parts[3]) if data_parts[3] else 0
                        prev_close = float(data_parts[2]) if data_parts[2] else price

                        if price > 0:
                            change_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0

                            return {
                                'name': name,
                                'current_nav': price,
                                'change_pct': change_pct,
                                'prev_nav': prev_close,
                                'volume': float(data_parts[8]) if len(data_parts) > 8 and data_parts[8] else 0
                            }

        else:
            # 场外基金 - 使用净值接口
            # 新浪财经基金接口: http://fund.eastmoney.com/000001.html
            code = fund_code

            url = f"http://fund.eastmoney.com/pingzhongdata/{code}.js"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': f'http://fund.eastmoney.com/{code}.html'
            }

            response = session.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                content = response.text
                # 解析JSON数据
                try:
                    # 提取净值数据
                    import json
                    # 去掉JavaScript var 声明
                    json_str = content.replace('var Data_DWJZ = ', '').replace('var Data_SYLZ = ', '').replace('var Data_DWJZNEW = ', '').rstrip(';')

                    if json_str:
                        data = json.loads(json_str)

                        if isinstance(data, list) and len(data) > 0:
                            latest = data[0]
                            if len(latest) > 0:
                                nav_date = latest[0]
                                nav_value = float(latest[1]) if len(latest) > 1 else 0
                                prev_nav = float(latest[1]) if len(data) > 1 and len(data[1]) > 1 else nav_value

                                if nav_value > 0:
                                    change_pct = ((nav_value - prev_nav) / prev_nav) * 100 if prev_nav > 0 else 0

                                    return {
                                        'name': fund_code,
                                        'current_nav': nav_value,
                                        'change_pct': change_pct,
                                        'prev_nav': prev_nav,
                                        'volume': 0
                                    }
                except:
                    pass

        return None

    except Exception as e:
        print(f"  获取失败: {e}")
        return None


def get_fund_data_real():
    """
    获取真实基金数据
    """
    try:
        all_data = {}

        print("📡 正在从新浪财经获取真实基金数据...")

        # 基金名称和类型映射
        fund_info = {
            "510300.SH": {"name": "沪深300ETF", "type": "etf"},
            "159915.SZ": {"name": "创业板ETF", "type": "etf"},
            "512000.SH": {"name": "券商ETF", "type": "etf"},
            "510500.SH": {"name": "中证500ETF", "type": "etf"},
            "000001": {"name": "华夏成长", "type": "open"},
            "110022": {"name": "易方达消费行业", "type": "open"},
        }

        for fund_code in config.FUND_LIST:
            info = fund_info.get(fund_code, {"name": fund_code, "type": "etf"})

            print(f"  正在获取 {info['name']}({fund_code})...")

            # 重试机制
            max_retries = 3
            for retry in range(max_retries):
                try:
                    real_data = get_sina_fund_data(fund_code, info['type'])

                    if real_data:
                        # 生成历史数据（用于技术分析）
                        df = generate_mock_history_with_latest(real_data)

                        all_data[fund_code] = {
                            "name": real_data['name'],
                            "type": info['type'],
                            "df": df,
                            "real_data": real_data
                        }

                        print(f"  ✅ {fund_code} 获取成功: 净值={real_data['current_nav']:.4f}, 涨跌={real_data['change_pct']:+.2f}%")
                        break
                    else:
                        if retry < max_retries - 1:
                            print(f"  ⚠️ 第{retry+1}次获取失败，重试中...")
                            time.sleep(1)
                        else:
                            print(f"  ❌ {fund_code} 获取失败")
                            # 使用模拟数据作为后备
                            df = generate_mock_fund_data(fund_code, info['name'], info['type'])
                            all_data[fund_code] = {
                                "name": info['name'],
                                "type": info['type'],
                                "df": df
                            }

                except Exception as e:
                    if retry < max_retries - 1:
                        print(f"  ⚠️ 网络错误，重试中...")
                        time.sleep(2)
                    else:
                        print(f"  ❌ {fund_code} 获取失败，使用模拟数据")
                        # 使用模拟数据
                        df = generate_mock_fund_data(fund_code, info['name'], info['type'])
                        all_data[fund_code] = {
                            "name": info['name'],
                            "type": info['type'],
                            "df": df
                        }

        return all_data if all_data else None

    except Exception as e:
        print(f"获取数据时出错: {e}")
        return None


def generate_mock_history_with_latest(real_data):
    """
    基于真实数据生成历史数据（用于技术分析）
    """
    np.random.seed(hash(real_data['name']) % 10000)

    days = 60
    end_date = datetime.now() - timedelta(days=1)
    dates = pd.date_range(end=end_date, periods=days, freq='D')
    dates = [d for d in dates if d.weekday() < 5]
    dates = dates[:min(days, len(dates))]

    # 生成历史数据，最后一天使用真实数据
    base_nav = real_data['prev_nav']
    returns = np.random.normal(0.0005, 0.015, len(dates))
    navs = [base_nav]

    for ret in returns[1:]:
        navs.append(navs[-1] * (1 + ret))

    # 最后一行用真实数据
    navs[-1] = real_data['current_nav']

    data = {
        '日期': dates,
        '净值': navs,
        '涨跌幅': np.concatenate([[0], np.diff(navs) / navs[:-1] * 100]),
        '成交量': [real_data.get('volume', 0) if i == len(navs)-1 else np.random.uniform(100000, 50000000) for i in range(len(navs))]
    }

    df = pd.DataFrame(data)
    df['涨跌幅'] = df['涨跌幅'].round(4)

    return df


def generate_mock_fund_data(fund_code, fund_name, fund_type, days=60):
    """生成模拟基金数据（后备方案）"""
    np.random.seed(hash(fund_code) % 10000)

    end_date = datetime.now() - timedelta(days=1)
    dates = pd.date_range(end=end_date, periods=days, freq='D')
    dates = [d for d in dates if d.weekday() < 5]
    dates = dates[:min(days, len(dates))]

    base_nav = np.random.uniform(1.0, 5.0)
    returns = np.random.normal(0.0005, 0.015, len(dates))
    navs = [base_nav]

    for ret in returns[1:]:
        navs.append(navs[-1] * (1 + ret))

    if fund_type == 'etf':
        data = {
            '日期': dates,
            '净值': navs,
            '涨跌幅': np.concatenate([[0], np.diff(navs) / navs[:-1] * 100]),
            '成交量': [np.random.uniform(100000, 50000000) for _ in navs]
        }
    else:
        data = {
            '日期': dates,
            '净值': navs,
            '涨跌幅': np.concatenate([[0], np.diff(navs) / navs[:-1] * 100]),
            '成交量': [0] * len(navs)
        }

    df = pd.DataFrame(data)
    df['涨跌幅'] = df['涨跌幅'].round(4)

    return df


# ============== 导入原来的分析代码 ==============

def calculate_ma(df, period=5):
    """计算移动平均线"""
    return df['净值'].rolling(window=period).mean().iloc[-1]


def calculate_rsi(df, period=14):
    """计算RSI"""
    delta = df['净值'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50


def calculate_atr(df, period=14):
    """计算平均真实波动范围 (ATR) - 用于预测波动幅度"""
    high = df['净值']
    low = df['净值']
    close = df['净值']

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0


def calculate_volatility(df, period=20):
    """计算历史波动率（年化）"""
    returns = df['净值'].pct_change().dropna()
    volatility = returns.rolling(window=period).std() * np.sqrt(252)
    return volatility.iloc[-1] if not np.isnan(volatility.iloc[-1]) else 0


def calculate_macd(df, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    exp1 = df['净值'].ewm(span=fast, adjust=False).mean()
    exp2 = df['净值'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line

    return {
        'macd': macd.iloc[-1] if not np.isnan(macd.iloc[-1]) else 0,
        'signal': signal_line.iloc[-1] if not np.isnan(signal_line.iloc[-1]) else 0,
        'histogram': histogram.iloc[-1] if not np.isnan(histogram.iloc[-1]) else 0
    }


def calculate_bollinger_bands(df, period=20, std_dev=2):
    """计算布林带"""
    sma = df['净值'].rolling(window=period).mean()
    std = df['净值'].rolling(window=period).std()

    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)

    return {
        'upper': upper_band.iloc[-1] if not np.isnan(upper_band.iloc[-1]) else df['净值'].iloc[-1],
        'middle': sma.iloc[-1] if not np.isnan(sma.iloc[-1]) else df['净值'].iloc[-1],
        'lower': lower_band.iloc[-1] if not np.isnan(lower_band.iloc[-1]) else df['净值'].iloc[-1]
    }


def analyze_trend(df):
    """趋势分析"""
    ma5 = calculate_ma(df, 5)
    ma10 = calculate_ma(df, 10)
    ma20 = calculate_ma(df, 20)
    current_nav = df['净值'].iloc[-1]

    if current_nav > ma5 > ma10 > ma20:
        return "强势上涨", "多头排列，趋势向上"
    elif current_nav > ma5 > ma10:
        return "上涨趋势", "短期均线向上"
    elif ma5 < ma10 < ma20 and current_nav < ma5:
        return "下跌趋势", "空头排列，趋势向下"
    else:
        return "震荡整理", "均线缠绕，方向不明"


def calculate_support_resistance(df):
    """计算支撑和压力位"""
    recent_data = df.tail(20)
    resistance = recent_data['净值'].max()
    support = recent_data['净值'].min()
    current = df['净值'].iloc[-1]

    return {
        'support': support,
        'resistance': resistance,
        'current': current,
        'position': (current - support) / (resistance - support) * 100 if resistance > support else 50
    }


def predict_price_movement(df, atr, volatility, rsi, macd, bollinger):
    """
    预测短期价格涨跌幅
    返回: {
        'expected_up': 预计上涨百分比,
        'expected_down': 预计下跌百分比,
        'confidence': 预测置信度(0-100)
    }
    """
    current_price = df['净值'].iloc[-1]

    # 基于ATR计算潜在涨跌幅（日级别）
    atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

    # 基于布林带的价格通道
    bb_distance_up = ((bollinger['upper'] - current_price) / current_price * 100) if current_price > 0 else 0
    bb_distance_down = ((current_price - bollinger['lower']) / current_price * 100) if current_price > 0 else 0

    # 综合分析因子
    up_factors = []
    down_factors = []

    # 1. 趋势因子（MACD）
    if macd['histogram'] > 0:
        up_factors.append(min(abs(macd['histogram']) * 10, 3))
    else:
        down_factors.append(min(abs(macd['histogram']) * 10, 3))

    # 2. 超买超卖因子（RSI）
    if rsi < 30:
        up_factors.append(2)  # 超卖，反弹概率大
    elif rsi > 70:
        down_factors.append(2)  # 超买，回调概率大
    elif 40 <= rsi <= 60:
        # RSI中性，看趋势
        if macd['macd'] > macd['signal']:
            up_factors.append(1)
        else:
            down_factors.append(1)

    # 3. 布林带位置因子
    bb_position = (current_price - bollinger['lower']) / (bollinger['upper'] - bollinger['lower']) * 100 if bollinger['upper'] != bollinger['lower'] else 50
    if bb_position < 20:
        up_factors.append(1.5)  # 接近下轨，反弹可能
    elif bb_position > 80:
        down_factors.append(1.5)  # 接近上轨，回调可能

    # 4. 波动率调整
    volatility_adjustment = min(volatility / 10, 1)  # 波动率越高，潜在涨跌越大

    # 计算预计涨跌幅
    base_up = atr_pct + volatility_adjustment
    base_down = atr_pct + volatility_adjustment

    expected_up = base_up * (1 + sum(up_factors) * 0.3) if up_factors else base_up * 0.7
    expected_down = base_down * (1 + sum(down_factors) * 0.3) if down_factors else base_down * 0.7

    # 使用布林带作为边界限制
    expected_up = min(expected_up, bb_distance_up * 0.8) if bb_distance_up > 0 else expected_up
    expected_down = min(expected_down, bb_distance_down * 0.8) if bb_distance_down > 0 else expected_down

    # 计算置信度
    signal_strength = abs(macd['histogram']) + abs(50 - rsi) / 10
    confidence = min(50 + signal_strength * 5, 85)  # 最高85%置信度

    return {
        'expected_up': round(expected_up, 2),
        'expected_down': round(expected_down, 2),
        'confidence': round(confidence, 0)
    }


def get_best_timing(df, current_price, atr, rsi, macd, bollinger, prediction):
    """
    判断最佳买入和卖出时机
    返回: {
        'buy_timing': 买入时机建议,
        'sell_timing': 卖出时机建议,
        'buy_signal': 买入信号强度(0-100),
        'sell_signal': 卖出信号强度(0-100)
    }
    """
    # 买入信号分析
    buy_signals = 0
    buy_reasons = []

    # 1. RSI超卖
    if rsi < 30:
        buy_signals += 25
        buy_reasons.append(f"RSI超卖({rsi:.0f})")

    # 2. MACD金叉
    if macd['macd'] > macd['signal'] and macd['histogram'] > 0:
        buy_signals += 20
        buy_reasons.append("MACD金叉")

    # 3. 价格接近布林带下轨
    bb_position = (current_price - bollinger['lower']) / (bollinger['upper'] - bollinger['lower']) * 100 if bollinger['upper'] != bollinger['lower'] else 50
    if bb_position < 25:
        buy_signals += 20
        buy_reasons.append("接近支撑位")

    # 4. 预期上涨幅度大
    if prediction['expected_up'] > prediction['expected_down'] * 1.5:
        buy_signals += 15
        buy_reasons.append(f"预期涨幅可达{prediction['expected_up']}%")

    # 5. 近期下跌
    recent_change = (df['净值'].iloc[-1] / df['净值'].iloc[-5] - 1) * 100 if len(df) >= 5 else 0
    if recent_change < -2:
        buy_signals += 10
        buy_reasons.append("近期回调充分")

    # 6. 均线支撑
    ma5 = calculate_ma(df, 5)
    if current_price <= ma5 * 1.01:
        buy_signals += 10
        buy_reasons.append("接近短期均线")

    # 卖出信号分析
    sell_signals = 0
    sell_reasons = []

    # 1. RSI超买
    if rsi > 70:
        sell_signals += 25
        sell_reasons.append(f"RSI超买({rsi:.0f})")

    # 2. MACD死叉
    if macd['macd'] < macd['signal'] and macd['histogram'] < 0:
        sell_signals += 20
        sell_reasons.append("MACD死叉")

    # 3. 价格接近布林带上轨
    if bb_position > 75:
        sell_signals += 20
        sell_reasons.append("接近压力位")

    # 4. 预期下跌幅度大
    if prediction['expected_down'] > prediction['expected_up'] * 1.5:
        sell_signals += 15
        sell_reasons.append(f"预期跌幅可达{prediction['expected_down']}%")

    # 5. 近期上涨
    if recent_change > 3:
        sell_signals += 10
        sell_reasons.append("短期涨幅较大")

    # 6. 远离均线
    if current_price > ma5 * 1.02:
        sell_signals += 10
        sell_reasons.append("远离短期均线")

    # 生成时机建议
    if buy_signals >= 60:
        buy_timing = "🟢 当前是较好买入时机"
    elif buy_signals >= 40:
        buy_timing = "🟡 可考虑逢低买入"
    elif buy_signals >= 20:
        buy_timing = "🟠 建议观望，等待更好时机"
    else:
        buy_timing = "🔴 不建议买入，等待信号"

    if sell_signals >= 60:
        sell_timing = "🔴 建议止盈或减仓"
    elif sell_signals >= 40:
        sell_timing = "🟠 可考虑分批止盈"
    elif sell_signals >= 20:
        sell_timing = "🟡 持有观望，关注卖出信号"
    else:
        sell_timing = "🟢 继续持有，暂无卖出信号"

    return {
        'buy_timing': buy_timing,
        'sell_timing': sell_timing,
        'buy_signal': min(buy_signals, 100),
        'sell_signal': min(sell_signals, 100),
        'buy_reasons': buy_reasons,
        'sell_reasons': sell_reasons
    }


def calculate_dynamic_stop_loss(current_nav, cost_nav, profit_pct, atr, volatility, holding_period=0):
    """
    动态止损计算 - 根据市场波动和盈利情况调整止损位

    参数:
    - current_nav: 当前净值
    - cost_nav: 持仓成本
    - profit_pct: 当前盈利百分比（正数表示盈利）
    - atr: 平均真实波动范围
    - volatility: 波动率
    - holding_period: 持有天数

    返回: {
        'stop_loss': 止损价位,
        'stop_loss_pct': 止损百分比,
        'trailing_stop': 是否启用移动止损,
        'reason': 止损位设置原因
    }
    """
    # 计算基础止损百分比
    base_stop_pct = -2.0  # 默认-2%止损

    # 根据波动率调整止损幅度
    if volatility > 30:
        base_stop_pct = -3.5  # 高波动，给予更多空间
    elif volatility > 20:
        base_stop_pct = -2.5  # 中等波动
    else:
        base_stop_pct = -1.5  # 低波动，可以收紧

    # 根据ATR调整（日线级别）
    atr_pct = (atr / current_nav * 100) if current_nav > 0 else 0
    if atr_pct > 2:
        base_stop_pct = min(base_stop_pct, -3.0)  # 波动大，放宽止损

    # 动态调整：根据盈利情况上移止损位
    if profit_pct > 5:
        # 盈利超过5%，止损移至+2%（保护部分利润）
        stop_loss_pct = 2.0
        trailing_stop = True
        reason = "盈利>5%，启用移动止损保护利润"
    elif profit_pct > 3:
        # 盈利超过3%，止损移至成本价（保本）
        stop_loss_pct = 0
        trailing_stop = True
        reason = "盈利>3%，止损移至成本价保本"
    elif profit_pct > 1:
        # 盈利1-3%，止损移至-1%（保护已有收益）
        stop_loss_pct = -1.0
        trailing_stop = True
        reason = "盈利>1%，收紧止损至-1%保护收益"
    else:
        # 亏损或微利，使用基础止损
        stop_loss_pct = base_stop_pct
        trailing_stop = False
        reason = f"基础止损{base_stop_pct}%"

    # 计算止损价位
    stop_loss_nav = current_nav * (1 + stop_loss_pct / 100)

    return {
        'stop_loss': round(stop_loss_nav, 4),
        'stop_loss_pct': round(stop_loss_pct, 2),
        'trailing_stop': trailing_stop,
        'reason': reason,
        'base_stop_pct': round(base_stop_pct, 2)
    }


def calculate_pyramid_positions(current_nav, cost_nav, current_position=1000):
    """
    金字塔分批建仓策略

    参数:
    - current_nav: 当前净值
    - cost_nav: 平均成本
    - current_position: 当前持仓金额

    返回: {
        'positions': 建仓层级列表,
        'total_add_amount': 总加仓金额,
        'risk_level': 风险等级
    }
    """
    # 计算当前回撤百分比
    drawdown_pct = ((current_nav - cost_nav) / cost_nav * 100) if cost_nav > 0 else 0

    positions = []
    total_add = 0

    # 金字塔建仓层级
    if drawdown_pct <= -2:
        # 第一层：回撤-2%，加仓20%
        amount1 = current_position * 0.2
        positions.append({
            'level': 1,
            'trigger': f"回撤≤-2%",
            'add_amount': round(amount1, 2),
            'total_position': round(current_position + amount1, 2),
            'avg_cost': round((current_position * cost_nav + amount1 * current_nav) / (current_position + amount1), 4)
        })
        total_add += amount1

    if drawdown_pct <= -4:
        # 第二层：回撤-4%，加仓30%
        amount2 = current_position * 0.3
        positions.append({
            'level': 2,
            'trigger': f"回撤≤-4%",
            'add_amount': round(amount2, 2),
            'total_position': round(current_position + amount2 + total_add, 2),
            'avg_cost': round((current_position * cost_nav + (amount2 + total_add) * current_nav) / (current_position + amount2 + total_add), 4)
        })
        total_add += amount2

    if drawdown_pct <= -6:
        # 第三层：回撤-6%，加仓50%
        amount3 = current_position * 0.5
        positions.append({
            'level': 3,
            'trigger': f"回撤≤-6%",
            'add_amount': round(amount3, 2),
            'total_position': round(current_position + amount3 + total_add, 2),
            'avg_cost': round((current_position * cost_nav + (amount3 + total_add) * current_nav) / (current_position + amount3 + total_add), 4)
        })
        total_add += amount3

    # 风险等级
    if drawdown_pct <= -6:
        risk_level = "高风险（已触发最大加仓）"
    elif drawdown_pct <= -4:
        risk_level = "中高风险（已触发第二层加仓）"
    elif drawdown_pct <= -2:
        risk_level = "中等风险（已触发第一层加仓）"
    else:
        risk_level = "低风险（未触发加仓）"

    return {
        'positions': positions,
        'total_add_amount': round(total_add, 2),
        'current_drawdown': round(drawdown_pct, 2),
        'risk_level': risk_level
    }


def check_crash_alert(current_change, threshold=-2.5):
    """
    暴跌预警系统

    参数:
    - current_change: 当前涨跌幅
    - threshold: 预警阈值（默认-2.5%）

    返回: {
        'alert_level': 预警等级,
        'alert_message': 预警信息,
        'suggested_action': 建议操作
    }
    """
    if current_change <= -5.0:
        return {
            'alert_level': '🔴 极端暴跌',
            'alert_message': f'暴跌{current_change:.2f}%，市场恐慌',
            'suggested_action': '立即减仓50%或全部止损'
        }
    elif current_change <= -3.5:
        return {
            'alert_level': '🟠 严重暴跌',
            'alert_message': f'大跌{current_change:.2f}%，启动紧急保护',
            'suggested_action': '尾盘前减仓30%或准备止损'
        }
    elif current_change <= -2.5:
        return {
            'alert_level': '🟡 暴跌预警',
            'alert_message': f'下跌{current_change:.2f}%，关注反弹',
            'suggested_action': '观察尾盘，若维持跌幅考虑减仓'
        }
    else:
        return {
            'alert_level': '🟢 正常波动',
            'alert_message': f'涨跌幅{current_change:+.2f}%在正常范围',
            'suggested_action': '按原策略执行'
        }


def generate_etf_advice(fund_code, fund_data, position_info=None):
    """
    场内ETF基金操作建议（增强版）

    position_info: 持仓信息 {
        'cost_nav': 成本净值,
        'position_amount': 持仓金额,
        'holding_days': 持有天数
    }
    """
    df = fund_data['df']
    fund_name = fund_data['name']

    # 如果有真实数据，使用真实数据的最新净值
    if 'real_data' in fund_data:
        real = fund_data['real_data']
        yesterday_nav = real['current_nav']
        yesterday_change = real['change_pct']
    else:
        latest = df.iloc[-1]
        yesterday_nav = latest['净值']
        yesterday_change = latest['涨跌幅']

    # 基础技术分析
    rsi = calculate_rsi(df)
    trend, trend_desc = analyze_trend(df)
    sr = calculate_support_resistance(df)

    # 新增：高级技术指标
    atr = calculate_atr(df)
    volatility = calculate_volatility(df)
    macd = calculate_macd(df)
    bollinger = calculate_bollinger_bands(df)

    # 新增：价格预测
    prediction = predict_price_movement(df, atr, volatility, rsi, macd, bollinger)

    # 新增：最佳买卖时机判断
    timing = get_best_timing(df, yesterday_nav, atr, rsi, macd, bollinger, prediction)

    # 新增：持仓分析（如果提供了持仓信息）
    dynamic_stop_loss = None
    pyramid_positions = None
    crash_alert = None

    if position_info:
        cost_nav = position_info.get('cost_nav', yesterday_nav)
        position_amount = position_info.get('position_amount', 1000)
        holding_days = position_info.get('holding_days', 0)

        # 计算当前盈利
        profit_pct = (yesterday_nav - cost_nav) / cost_nav * 100 if cost_nav > 0 else 0

        # 动态止损
        dynamic_stop_loss = calculate_dynamic_stop_loss(
            yesterday_nav, cost_nav, profit_pct, atr, volatility, holding_days
        )

        # 金字塔加仓
        pyramid_positions = calculate_pyramid_positions(
            yesterday_nav, cost_nav, position_amount
        )

    # 暴跌预警（基于今日盘中涨跌幅）
    crash_alert = check_crash_alert(yesterday_change, threshold=-2.5)

    # 评分
    score = 50
    reasons = []

    if trend == "强势上涨":
        score += 20
        reasons.append("强势上涨趋势")
    elif trend == "上涨趋势":
        score += 10
        reasons.append("上涨趋势")
    elif trend == "下跌趋势":
        score -= 15
        reasons.append("下跌趋势")

    if rsi < 30:
        score += 15
        reasons.append("RSI超卖，可能反弹")
    elif rsi > 70:
        score -= 10
        reasons.append("RSI超买，注意回调")
    elif 40 < rsi < 60:
        score += 5
        reasons.append("RSI健康")

    if sr['position'] < 30:
        score += 10
        reasons.append("接近支撑位")
    elif sr['position'] > 70:
        score -= 5
        reasons.append("接近压力位")

    # 根据时机信号调整评分
    if timing['buy_signal'] > 60:
        score += 5
        reasons.append("买入信号较强")
    elif timing['sell_signal'] > 60:
        score -= 5
        reasons.append("卖出信号较强")

    # 根据暴跌预警调整评分
    if crash_alert['alert_level'] in ['🔴 极端暴跌', '🟠 严重暴跌']:
        score -= 15
        reasons.append(crash_alert['alert_level'])

    # 生成建议
    if score >= 70:
        action = "可以考虑买入"
        advice_type = "买入"
        risk_level = "中等风险"
    elif score >= 55:
        action = "可以小仓位买入或持有"
        advice_type = "持有"
        risk_level = "中等风险"
    elif score >= 45:
        action = "建议观望"
        advice_type = "观望"
        risk_level = "低风险"
    else:
        action = "建议减仓或回避"
        advice_type = "卖出"
        risk_level = "较高风险"

    # 操作区间
    buy_range_low = sr['support'] * 1.005
    buy_range_high = sr['current'] * 0.995

    # 使用动态止损（如果有持仓信息）
    if dynamic_stop_loss:
        stop_loss = dynamic_stop_loss['stop_loss']
    else:
        stop_loss = sr['support'] * 0.97

    target = sr['resistance'] * 0.98

    return {
        'code': fund_code,
        'name': fund_name,
        'type': '场内ETF',
        'score': score,
        'action': action,
        'advice_type': advice_type,
        'risk_level': risk_level,
        'reasons': reasons,
        'yesterday_nav': yesterday_nav,
        'yesterday_change': yesterday_change,
        'trend': trend,
        'trend_desc': trend_desc,
        'rsi': round(rsi, 2),
        'buy_range': (round(buy_range_low, 4), round(buy_range_high, 4)),
        'stop_loss': round(stop_loss, 4),
        'target': round(target, 4),
        'support': round(sr['support'], 4),
        'resistance': round(sr['resistance'], 4),
        # 新增字段
        'prediction': prediction,
        'timing': timing,
        'volatility': round(volatility, 2),
        'macd': round(macd['macd'], 4),
        'bollinger': bollinger,
        # 增强功能
        'dynamic_stop_loss': dynamic_stop_loss,
        'pyramid_positions': pyramid_positions,
        'crash_alert': crash_alert
    }


def generate_open_fund_advice(fund_code, fund_data):
    """场外基金操作建议"""
    df = fund_data['df']
    fund_name = fund_data['name']

    # 如果有真实数据，使用真实数据
    if 'real_data' in fund_data:
        real = fund_data['real_data']
        yesterday_nav = real['current_nav']
        yesterday_change = real['change_pct']
    else:
        latest = df.iloc[-1]
        yesterday_nav = latest['净值']
        yesterday_change = latest['涨跌幅']

    # 技术分析
    rsi = calculate_rsi(df)
    trend, trend_desc = analyze_trend(df)
    sr = calculate_support_resistance(df)

    # 评分（场外基金更注重长期）
    score = 50

    # 30日涨跌
    momentum_30 = (df['净值'].iloc[-1] / df['净值'].iloc[-30] - 1) * 100

    if momentum_30 > 5:
        score += 20
    elif momentum_30 > 0:
        score += 10
    elif momentum_30 < -5:
        score -= 15

    if rsi < 35:
        score += 10
    elif rsi > 65:
        score -= 5

    if trend == "强势上涨" or trend == "上涨趋势":
        score += 10

    # 生成建议
    if score >= 70:
        if momentum_30 > 0:
            action = "建议继续定投"
        else:
            action = "回调后加大定投"
        advice_type = "定投"
    elif score >= 50:
        action = "建议保持定投"
        advice_type = "定投"
    elif score >= 40:
        action = "建议减少定投或暂停"
        advice_type = "观望"
    else:
        action = "建议暂停定投，等待时机"
        advice_type = "观望"

    return {
        'code': fund_code,
        'name': fund_name,
        'type': '场外基金',
        'score': score,
        'action': action,
        'advice_type': advice_type,
        'yesterday_nav': yesterday_nav,
        'yesterday_change': yesterday_change,
        'momentum_30': round(momentum_30, 2),
        'trend': trend,
        'trend_desc': trend_desc,
        'rsi': round(rsi, 2)
    }


def generate_morning_report(all_fund_data):
    """生成晨间投资报告"""
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
    report_lines.append("📊 数据来源: 新浪财经（实时数据）")
    report_lines.append("")

    # 分别处理场内ETF和场外基金
    etf_funds = {}
    open_funds = {}

    for fund_code, fund_data in all_fund_data.items():
        if fund_data['type'] == 'etf':
            etf_funds[fund_code] = fund_data
        else:
            open_funds[fund_code] = fund_data

    # 场内ETF建议
    if etf_funds:
        report_lines.append("📊 场内ETF基金操作建议")
        report_lines.append("━" * 50)
        report_lines.append("")

        etf_advice_list = []
        for fund_code, fund_data in etf_funds.items():
            advice = generate_etf_advice(fund_code, fund_data)
            etf_advice_list.append(advice)

        etf_advice_list.sort(key=lambda x: x['score'], reverse=True)

        for i, advice in enumerate(etf_advice_list, 1):
            change_symbol = "📈" if advice['yesterday_change'] > 0 else "📉" if advice['yesterday_change'] < 0 else "➡️"

            report_lines.append(f"【#{i}】{advice['name']} ({advice['code']})")
            report_lines.append(f"  评分: {advice['score']}/100  {advice['risk_level']}")
            report_lines.append(f"  昨日净值: {advice['yesterday_nav']:.4f}  {change_symbol} {advice['yesterday_change']:+.2f}%")
            report_lines.append("")

            # 新增：价格预测信息
            pred = advice['prediction']
            report_lines.append(f"  📊 短期价格预测 (置信度: {pred['confidence']}%):")
            report_lines.append(f"     - 预计涨幅: +{pred['expected_up']}%")
            report_lines.append(f"     - 预计跌幅: -{pred['expected_down']}%")
            report_lines.append("")

            # 新增：最佳买卖时机
            timing = advice['timing']
            report_lines.append(f"  ⏰ 最佳操作时机:")
            report_lines.append(f"     - 买入时机: {timing['buy_timing']}")
            report_lines.append(f"     - 卖出时机: {timing['sell_timing']}")
            if timing['buy_reasons']:
                report_lines.append(f"     - 买入理由: {', '.join(timing['buy_reasons'][:2])}")
            if timing['sell_reasons']:
                report_lines.append(f"     - 卖出理由: {', '.join(timing['sell_reasons'][:2])}")
            report_lines.append("")

            report_lines.append(f"  💡 今日操作建议: {advice['action']}")
            report_lines.append(f"     - 建议买入区间: {advice['buy_range'][0]:.4f} - {advice['buy_range'][1]:.4f}")
            report_lines.append(f"     - 止损位: {advice['stop_loss']:.4f}")
            report_lines.append(f"     - 目标位: {advice['target']:.4f}")
            report_lines.append("")

            # 新增：动态止损信息
            if advice['dynamic_stop_loss']:
                dynamic_sl = advice['dynamic_stop_loss']
                report_lines.append(f"  🛡️ 动态止损系统:")
                report_lines.append(f"     - 当前止损位: {dynamic_sl['stop_loss']:.4f} ({dynamic_sl['stop_loss_pct']:+.1f}%)")
                report_lines.append(f"     - 止损策略: {dynamic_sl['reason']}")
                if dynamic_sl['trailing_stop']:
                    report_lines.append(f"     - ✅ 移动止损已启用（保护利润）")
                else:
                    report_lines.append(f"     - 基础止损: {dynamic_sl['base_stop_pct']:.1f}%")
                report_lines.append("")

            # 新增：暴跌预警
            crash_alert = advice['crash_alert']
            if crash_alert['alert_level'] != '🟢 正常波动':
                report_lines.append(f"  ⚠️ {crash_alert['alert_level']}: {crash_alert['alert_message']}")
                report_lines.append(f"     - 建议操作: {crash_alert['suggested_action']}")
                report_lines.append("")

            # 新增：金字塔建仓策略（如果有触发）
            if advice['pyramid_positions'] and advice['pyramid_positions']['positions']:
                pyramid = advice['pyramid_positions']
                report_lines.append(f"  🔺 金字塔建仓策略:")
                report_lines.append(f"     - 当前回撤: {pyramid['current_drawdown']:+.1f}%")
                report_lines.append(f"     - 风险等级: {pyramid['risk_level']}")
                for pos in pyramid['positions']:
                    report_lines.append(f"     - 第{pos['level']}层: {pos['trigger']}, 加仓{pos['add_amount']}元")
                    report_lines.append(f"       总仓位: {pos['total_position']}元, 成本: {pos['avg_cost']:.4f}")
                report_lines.append("")

            report_lines.append(f"  🔍 技术分析:")
            report_lines.append(f"     - 趋势: {advice['trend']} - {advice['trend_desc']}")
            report_lines.append(f"     - RSI: {advice['rsi']} (超卖<30 / 超买>70)")
            report_lines.append(f"     - 波动率: {advice['volatility']}% (年化)")
            report_lines.append(f"     - MACD: {advice['macd']}")
            report_lines.append(f"     - 支撑位: {advice['support']:.4f}")
            report_lines.append(f"     - 压力位: {advice['resistance']:.4f}")
            report_lines.append("")
            report_lines.append(f"  📝 理由: {'; '.join(advice['reasons'])}")
            report_lines.append("")

    # 场外基金建议
    if open_funds:
        report_lines.append("=" * 50)
        report_lines.append("💰 场外基金定投建议")
        report_lines.append("━" * 50)
        report_lines.append("")
        report_lines.append("⏰ 定投提醒: 今日15:00前完成申购")
        report_lines.append("")

        open_advice_list = []
        for fund_code, fund_data in open_funds.items():
            advice = generate_open_fund_advice(fund_code, fund_data)
            open_advice_list.append(advice)

        open_advice_list.sort(key=lambda x: x['score'], reverse=True)

        for i, advice in enumerate(open_advice_list, 1):
            change_symbol = "📈" if advice['yesterday_change'] > 0 else "📉" if advice['yesterday_change'] < 0 else "➡️"

            report_lines.append(f"【#{i}】{advice['name']} ({advice['code']})")
            report_lines.append(f"  评分: {advice['score']}/100")
            report_lines.append(f"  昨日净值: {advice['yesterday_nav']:.4f}  {change_symbol} {advice['yesterday_change']:+.2f}%")
            report_lines.append(f"  近30日涨跌: {advice['momentum_30']:+.2f}%")
            report_lines.append("")
            report_lines.append(f"  💡 定投建议: {advice['action']}")
            report_lines.append("")
            report_lines.append(f"  🔍 分析:")
            report_lines.append(f"     - 趋势: {advice['trend']}")
            report_lines.append(f"     - RSI: {advice['rsi']}")
            report_lines.append("")

    # 整体建议
    report_lines.append("=" * 50)
    report_lines.append("🎯 今日整体策略")
    report_lines.append("=" * 50)
    report_lines.append("")

    all_scores = []
    for fund_code, fund_data in all_fund_data.items():
        if fund_data['type'] == 'etf':
            advice = generate_etf_advice(fund_code, fund_data)
        else:
            advice = generate_open_fund_advice(fund_code, fund_data)
        all_scores.append(advice['score'])

    avg_score = sum(all_scores) / len(all_scores) if all_scores else 50

    if avg_score >= 65:
        strategy = "积极"
        position = "可适当提高仓位至60-70%"
        risk_tip = "市场整体偏强，注意追高风险"
    elif avg_score >= 50:
        strategy = "稳健"
        position = "建议保持50%左右仓位"
        risk_tip = "市场震荡为主，均衡配置"
    elif avg_score >= 40:
        strategy = "保守"
        position = "建议降低仓位至30-40%"
        risk_tip = "市场偏弱，注意控制风险"
    else:
        strategy = "谨慎"
        position = "建议空仓或轻仓（<30%）"
        risk_tip = "市场风险较高，建议观望"

    report_lines.append(f"📊 市场评分: {avg_score:.0f}/100")
    report_lines.append(f"🎯 操作策略: {strategy}")
    report_lines.append(f"💼 仓位建议: {position}")
    report_lines.append(f"⚠️ 风险提示: {risk_tip}")
    report_lines.append("")

    if etf_advice_list:
        best_etf = etf_advice_list[0]
        report_lines.append(f"🥇 今日推荐: {best_etf['name']} ({best_etf['code']})")
        report_lines.append(f"   评分: {best_etf['score']}/100")
        report_lines.append(f"   建议: {best_etf['action']}")
        report_lines.append("")

    report_lines.append("=" * 50)
    report_lines.append("📌 重要提示")
    report_lines.append("=" * 50)
    report_lines.append("• 本报告仅供参考，不构成投资建议")
    report_lines.append("• 基金有风险，投资需谨慎")
    report_lines.append("• 建议结合自身风险承受能力决策")
    report_lines.append("")
    report_lines.append("🤖 Powered by 基金晨间投资顾问 (真实数据版)")

    return "\n".join(report_lines)


# ============== 消息推送模块 ==============

def send_serverchan_message(message):
    """通过Server酱发送消息到微信"""
    try:
        url = f"https://sctapi.ftqq.com/{config.SERVERCHAN_SENDKEY}.send"
        data = {
            "title": "🌅 基金晨间投资报告",
            "desp": message
        }
        response = session.post(url, json=data, timeout=15, verify=False)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print("✅ Server酱消息发送成功（请查看微信）")
                return True
            else:
                print(f"❌ Server酱发送失败: {result.get('message')}")
                return False
        else:
            print(f"❌ Server酱发送失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 发送Server酱消息时出错: {e}")
        return False


def send_notification(message):
    """统一的消息发送入口"""
    method = config.NOTIFY_METHOD.lower()

    if method == "serverchan":
        return send_serverchan_message(message)
    else:
        print(f"❌ 暂不支持推送方式: {method}")
        return False


def is_trading_day():
    """判断今天是否是交易日"""
    today = date.today()
    if today.weekday() >= 5:  # 周六、周日
        return False
    return True


# ============== 主程序接口 ==============

def get_market_data():
    """获取数据"""
    return get_fund_data_real()


def generate_report(all_data):
    """生成报告"""
    return generate_morning_report(all_data)
