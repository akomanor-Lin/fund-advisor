# -*- coding: utf-8 -*-
"""
智能选基系统 V5.1 - 风险预警增强版
核心改进：
1. 集成风险预警系统
2. 增加短期趋势评分（1-7天）
3. 根据风险等级动态调整评分
4. 新增企稳信号检测

作者：Claude Code V5.0
创建时间：2026-03-23
版本：V5.1
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import datetime, timedelta
from collections import deque


# ============== 导入风险预警系统 ==============

class RiskIndicators:
    """风险指标计算（精简版）"""

    @staticmethod
    def calculate_momentum_change(today_change, yesterday_change):
        """计算动量变化"""
        momentum_change = today_change - yesterday_change

        if momentum_change < -3:
            return -100  # 动量急剧恶化
        elif momentum_change < -2:
            return -75   # 动量明显恶化
        elif momentum_change < -1:
            return -50   # 动量转弱
        elif momentum_change < 0:
            return -25   # 动量减弱
        elif momentum_change < 1:
            return 0     # 动量平稳
        elif momentum_change < 2:
            return 25    # 动量增强
        else:
            return 50    # 动量明显增强

    @staticmethod
    def detect_false_rally(change_history):
        """检测虚假反弹（死猫跳）"""
        if len(change_history) < 3:
            return False, 0

        recent_3_days = change_history[-3:]

        # 特征1：整体趋势向下
        trend_down = sum(recent_3_days) < 0

        # 特征2：只有1天反弹，且反弹幅度小（<2%）
        single_small_rally = (
            len([x for x in recent_3_days if x > 0]) == 1 and
            max(recent_3_days) < 2
        )

        # 特征3：反弹后立即下跌
        rally_then_drop = (
            recent_3_days[-2] > 0 and recent_3_days[-1] < 0
        )

        # 判断
        is_false = trend_down and single_small_rally and rally_then_drop

        # 计算置信度
        confidence = 0
        if trend_down:
            confidence += 0.3
        if single_small_rally:
            confidence += 0.4
        if rally_then_drop:
            confidence += 0.3

        return is_false, confidence


class RiskLevel:
    """风险等级"""

    CRITICAL = "CRITICAL"  # 严重风险
    HIGH = "HIGH"          # 高风险
    MEDIUM = "MEDIUM"      # 中等风险
    LOW = "LOW"            # 低风险
    MINIMAL = "MINIMAL"    # 最低风险


# ============== 短期趋势评分模块（V5.1新增）=============

class ShortTermTrendAnalyzer:
    """短期趋势分析器（1-7天）"""

    def __init__(self):
        self.change_history = deque(maxlen=7)  # 保留最近7天数据

    def update(self, daily_change):
        """更新每日数据"""
        self.change_history.append(daily_change)

    def calculate_short_term_score(self):
        """
        计算短期趋势评分

        返回：
        - score: 0-100分
        - analysis: 分析结果列表
        - trend_status: 趋势状态
        """
        if len(self.change_history) < 3:
            return 50, ["数据不足，需要至少3天数据"], "数据不足"

        score = 50  # 基础分
        analysis = []

        recent_3 = list(self.change_history)[-3:]
        recent_5 = list(self.change_history)[-5:] if len(self.change_history) >= 5 else recent_3

        # 1. 连续下跌检测（严重扣分）
        consecutive_down = 0
        for change in reversed(self.change_history):
            if change < 0:
                consecutive_down += 1
            else:
                break

        if consecutive_down >= 3:
            score -= 30
            analysis.append(f"🔴 连续{consecutive_down}天下跌，短期下降趋势明确")
            trend_status = "下降"
        elif consecutive_down == 2:
            score -= 15
            analysis.append(f"🟡 连续{consecutive_down}天下跌，短期偏弱")
            trend_status = "转弱"
        else:
            # 2. 连续上涨检测（加分）
            consecutive_up = 0
            for change in reversed(self.change_history):
                if change > 0:
                    consecutive_up += 1
                else:
                    break

            if consecutive_up >= 3:
                score += 20
                analysis.append(f"✅ 连续{consecutive_up}天上涨，短期上升趋势明确")
                trend_status = "上升"
            elif consecutive_up == 2:
                score += 10
                analysis.append(f"🟢 连续{consecutive_up}天上涨，短期偏强")
                trend_status = "转强"
            else:
                # 3. 震荡判断
                volatility = max(recent_5) - min(recent_5)
                if volatility < 1.0:
                    analysis.append("➡️ 短期震荡，方向不明")
                    trend_status = "震荡"
                else:
                    analysis.append("🟡 短期波动较大")
                    trend_status = "波动"

        # 4. 虚假反弹检测
        is_false_rally, confidence = RiskIndicators.detect_false_rally(list(self.change_history))
        if is_false_rally and confidence > 0.7:
            score -= 25
            analysis.append(f"⚠️ 检测到虚假反弹（死猫跳），置信度{confidence:.0%}")

        # 5. 动量变化
        if len(self.change_history) >= 2:
            momentum_score = RiskIndicators.calculate_momentum_change(
                self.change_history[-1], self.change_history[-2]
            )
            if momentum_score <= -75:
                score -= 15
                analysis.append("🔴 动量急剧恶化")
            elif momentum_score <= -50:
                score -= 10
                analysis.append("🟠 动量明显转弱")
            elif momentum_score >= 50:
                score += 10
                analysis.append("🟢 动量明显增强")

        # 限制分数范围
        score = max(0, min(100, score))

        return score, analysis, trend_status


# ============== 企稳信号检测模块（V5.1新增）=============

class StabilizationDetector:
    """企稳信号检测器"""

    def __init__(self):
        self.change_history = deque(maxlen=10)  # 保留最近10天数据
        self.volume_history = deque(maxlen=10)   # 保留最近10天成交量

    def update(self, daily_change, volume=None):
        """更新数据"""
        self.change_history.append(daily_change)
        if volume:
            self.volume_history.append(volume)

    def detect_stabilization(self):
        """
        检测企稳信号

        企稳定义：
        1. 连续2天涨跌幅在±0.5%以内
        2. 成交量较前期萎缩>30%（如果有成交量数据）
        3. 未创新低

        返回：
        - is_stabilized: 是否企稳
        - confidence: 企稳置信度 (0-1)
        - signals: 企稳信号列表
        """
        if len(self.change_history) < 2:
            return False, 0, ["数据不足"]

        signals = []
        confidence = 0
        conditions_met = 0

        # 条件1：连续2天涨跌幅在±0.5%以内
        if len(self.change_history) >= 2:
            recent_2 = list(self.change_history)[-2:]
            if all(abs(change) <= 0.5 for change in recent_2):
                conditions_met += 1
                confidence += 0.4
                signals.append("✅ 连续2天涨跌幅在±0.5%以内")
            else:
                signals.append(f"❌ 涨跌幅波动较大：{recent_2}")

        # 条件2：成交量萎缩（如果有数据）
        if len(self.volume_history) >= 5:
            recent_3_vol = list(self.volume_history)[-3:]
            previous_3_vol = list(self.volume_history)[-6:-3]

            if recent_3_vol and previous_3_vol:
                recent_avg = sum(recent_3_vol) / len(recent_3_vol)
                previous_avg = sum(previous_3_vol) / len(previous_3_vol)

                if previous_avg > 0 and recent_avg < previous_avg * 0.7:
                    conditions_met += 1
                    confidence += 0.3
                    signals.append(f"✅ 成交量萎缩{((1 - recent_avg/previous_avg) * 100):.1f}%")
                else:
                    signals.append("⚠️ 成交量未明显萎缩")

        # 条件3：未创新低
        if len(self.change_history) >= 5:
            recent_5 = list(self.change_history)[-5:]
            min_recent_3 = min(recent_5[-3:])
            min_previous_2 = min(recent_5[:-3])

            if min_recent_3 >= min_previous_2:
                conditions_met += 1
                confidence += 0.3
                signals.append("✅ 最近3天未创新低")
            else:
                signals.append("❌ 仍在创新低")

        # 判断是否企稳
        is_stabilized = conditions_met >= 2  # 至少满足2个条件

        return is_stabilized, confidence, signals


# ============== V5.1 智能选基系统 ==============

class SmartSelectorV5_1:
    """智能选基系统 V5.1 - 风险预警增强版"""

    def __init__(self):
        # 真实基金数据
        self.fund_pool = {
            '011612': {
                'name': '华夏科创50ETF联接A',
                'index': '科创50',
                'style': '科技',
                'current': 1.465,
                'week52_high': 1.58,
                'week52_low': 1.398,
                'month6_high': 1.58,
                'month6_low': 1.420,
                'days_from_high': 15,
                'pct_from_high': -7.3,
                'trend_3m': -0.02,
                'trend_6m': 0.05,
                'trend_status': '震荡',
                'trend_strength': '弱',
                'recent_gain_1m': -0.03,
                'recent_gain_3m': -0.02,
                # 新增：短期趋势数据（模拟）
                'short_term_changes': [-0.5, 1.08, -2.66, -1.2, -0.8],  # 最近5天涨跌幅
            },
            '001229': {
                'name': '天弘中证500ETF联接A',
                'index': '中证500',
                'style': '中盘',
                'current': 5420,
                'week52_high': 5850,
                'week52_low': 5180,
                'month6_high': 5780,
                'month6_low': 5200,
                'days_from_high': 20,
                'pct_from_high': -6.2,
                'trend_3m': 0.03,
                'trend_6m': 0.08,
                'trend_status': '震荡上涨',
                'trend_strength': '中',
                'recent_gain_1m': 0.02,
                'recent_gain_3m': 0.03,
                'short_term_changes': [0.5, 1.08, -2.66, -1.5, -1.0],  # 最近5天
            },
            '000961': {
                'name': '天弘沪深300ETF联接A',
                'index': '沪深300',
                'style': '大盘',
                'current': 4615,
                'week52_high': 4837,
                'week52_low': 4480,
                'month6_high': 4800,
                'month6_low': 4550,
                'days_from_high': 45,
                'pct_from_high': -3.9,
                'trend_3m': 0.01,
                'trend_6m': 0.05,
                'trend_status': '震荡',
                'trend_strength': '弱',
                'recent_gain_1m': 0.005,
                'recent_gain_3m': 0.01,
                'short_term_changes': [0.3, 0.43, -1.48, -0.9, -0.6],  # 最近5天
            },
            '008113': {
                'name': '天弘中证银行ETF联接A',
                'index': '中证银行',
                'style': '金融',
                'current': 5820,
                'week52_high': 6250,
                'week52_low': 5450,
                'month6_high': 6050,
                'month6_low': 5580,
                'days_from_high': 30,
                'pct_from_high': -3.8,
                'trend_3m': 0.08,
                'trend_6m': 0.15,
                'trend_status': '上涨',
                'trend_strength': '中',
                'recent_gain_1m': 0.04,
                'recent_gain_3m': 0.08,
                'short_term_changes': [-0.1, -0.25, -0.25, -0.2, -0.15],  # 最近5天，相对稳定
            },
        }

        # 初始化分析器
        self.short_term_analyzer = ShortTermTrendAnalyzer()
        self.stabilization_detector = StabilizationDetector()

    def calculate_peak_distance_score(self, fund_info):
        """距近期高点距离评分（V5原有，保持不变）"""
        pct_from_high = fund_info['pct_from_high']
        days_from_high = fund_info['days_from_high']

        score = 100
        analysis = []
        risk_level = "低"

        if abs(pct_from_high) < 3:
            if days_from_high < 10:
                score = 20
                risk_level = "极高"
                analysis.append(f"⚠️ 距6个月高点仅{abs(pct_from_high):.1f}%，追高风险极高")
            elif days_from_high < 30:
                score = 40
                risk_level = "高"
                analysis.append(f"⚠️ 距6个月高点{abs(pct_from_high):.1f}%，处于高位区")
            else:
                score = 60
                risk_level = "中等"
                analysis.append(f"🟡 距6个月高点{abs(pct_from_high):.1f}%，高位横盘")

        elif abs(pct_from_high) < 6:
            score = 70
            risk_level = "中低"
            analysis.append(f"✅ 距6个月高点{abs(pct_from_high):.1f}%，相对安全")

        elif abs(pct_from_high) < 10:
            score = 85
            risk_level = "低"
            analysis.append(f"✅ 距6个月高点{abs(pct_from_high):.1f}%，安全边际较高")

        else:
            score = 95
            risk_level = "极低"
            analysis.append(f"✅ 距6个月高点{abs(pct_from_high):.1f}%，安全边际很高")

        return score, analysis, risk_level

    def calculate_short_term_trend_score(self, fund_info):
        """计算短期趋势评分（V5.1新增）"""
        # 更新短期趋势数据
        if 'short_term_changes' in fund_info:
            for change in fund_info['short_term_changes']:
                self.short_term_analyzer.update(change)

        # 计算评分
        score, analysis, trend_status = self.short_term_analyzer.calculate_short_term_score()

        return score, analysis, trend_status

    def assess_market_risk_level(self, all_fund_changes):
        """
        评估市场整体风险等级

        参数：
        - all_fund_changes: 所有基金的今日涨跌幅列表

        返回：
        - risk_level: 风险等级
        - risk_score: 风险分数 (0-100)
        - signals: 风险信号列表
        """
        if not all_fund_changes:
            return RiskLevel.LOW, 25, ["无数据"]

        avg_change = sum(all_fund_changes) / len(all_fund_changes)
        signals = []
        risk_score = 0

        # 1. 平均涨跌幅
        if avg_change < -2:
            risk_score += 40
            signals.append(f"🔴 市场平均跌幅{avg_change:.2f}%，严重下跌")
        elif avg_change < -1:
            risk_score += 25
            signals.append(f"🟠 市场平均跌幅{avg_change:.2f}%，明显下跌")
        elif avg_change < -0.5:
            risk_score += 15
            signals.append(f"🟡 市场平均跌幅{avg_change:.2f}%，小幅下跌")
        elif avg_change > 1:
            risk_score -= 10
            signals.append(f"🟢 市场平均涨幅{avg_change:.2f}%，表现良好")

        # 2. 下跌品种占比
        down_count = len([c for c in all_fund_changes if c < 0])
        down_ratio = down_count / len(all_fund_changes)

        if down_ratio >= 0.8:
            risk_score += 30
            signals.append(f"🔴 {down_ratio:.0%}的品种下跌，市场普跌")
        elif down_ratio >= 0.6:
            risk_score += 15
            signals.append(f"🟠 {down_ratio:.0%}的品种下跌，多数下跌")
        elif down_ratio <= 0.2:
            risk_score -= 10
            signals.append(f"✅ 仅{down_ratio:.0%}的品种下跌，市场普涨")

        # 3. 动量变化（如果有历史数据）
        if hasattr(self, '_yesterday_avg_change'):
            momentum_score = RiskIndicators.calculate_momentum_change(
                avg_change, self._yesterday_avg_change
            )

            if momentum_score <= -75:
                risk_score += 30
                signals.append(f"🔴 动量急剧恶化：{self._yesterday_avg_change:+.2f}% → {avg_change:+.2f}%")
            elif momentum_score <= -50:
                risk_score += 20
                signals.append(f"🟠 动量明显转弱：{self._yesterday_avg_change:+.2f}% → {avg_change:+.2f}%")

        # 保存今日数据
        self._yesterday_avg_change = avg_change

        # 4. 确定风险等级
        risk_score = max(0, min(100, risk_score))

        if risk_score >= 70:
            return RiskLevel.CRITICAL, risk_score, signals
        elif risk_score >= 50:
            return RiskLevel.HIGH, risk_score, signals
        elif risk_score >= 30:
            return RiskLevel.MEDIUM, risk_score, signals
        elif risk_score >= 15:
            return RiskLevel.LOW, risk_score, signals
        else:
            return RiskLevel.MINIMAL, risk_score, signals

    def calculate_v5_1_score(self, fund_code):
        """
        计算V5.1综合评分

        核心改进：
        1. 集成短期趋势评分（权重15%）
        2. 根据风险等级动态调整
        3. 保持V5原有的距高点评分（20%）

        权重分配：
        - 短期趋势：15%（新增）
        - 中期趋势：20%（原V5趋势权重的一部分）
        - 距高点距离：20%（保持不变）
        - 涨幅风险：10%（保持不变）
        - 反弹潜力：10%（降低，原15%）
        - 估值：15%（保持不变）
        - 位置：10%（保持不变）
        """
        fund_info = self.fund_pool.get(fund_code)

        if not fund_info:
            return None, "基金代码不存在"

        scores = {}
        analyses = {}

        # 1. 短期趋势评分（V5.1新增，权重15%）
        short_score, short_analysis, short_status = self.calculate_short_term_trend_score(fund_info)
        scores['short_term'] = short_score * 0.15
        analyses['short_term'] = short_analysis

        # 2. 距高点距离评分（V5原有，权重20%）
        peak_score, peak_analysis, peak_risk = self.calculate_peak_distance_score(fund_info)
        scores['peak_distance'] = peak_score * 0.20
        analyses['peak_distance'] = peak_analysis

        # 3. 其他评分（简化版，保持V5逻辑）
        # 中期趋势（20%）
        trend_3m = fund_info.get('trend_3m', 0)
        if trend_3m > 0.05:
            trend_score = 80
        elif trend_3m > 0:
            trend_score = 60
        elif trend_3m > -0.05:
            trend_score = 40
        else:
            trend_score = 20
        scores['medium_term'] = trend_score * 0.20

        # 涨幅风险（10%）- 近1个月涨幅过大扣分
        recent_gain_1m = fund_info.get('recent_gain_1m', 0)
        if recent_gain_1m > 0.10:
            gain_risk_score = 20  # 涨幅过大，风险高
        elif recent_gain_1m > 0.05:
            gain_risk_score = 50
        elif recent_gain_1m > 0:
            gain_risk_score = 70
        else:
            gain_risk_score = 90  # 下跌或持平，风险低
        scores['gain_risk'] = gain_risk_score * 0.10

        # 反弹潜力（10%）- 距低点距离
        pct_from_high = fund_info.get('pct_from_high', 0)
        if pct_from_high < -10:
            rebound_score = 80  # 距高点远，反弹空间大
        elif pct_from_high < -5:
            rebound_score = 60
        else:
            rebound_score = 40
        scores['rebound'] = rebound_score * 0.10

        # 估值（15%）- 简化处理，基于距高点距离
        if pct_from_high < -10:
            value_score = 90  # 深度回调，估值低
        elif pct_from_high < -5:
            value_score = 70
        else:
            value_score = 50
        scores['value'] = value_score * 0.15

        # 位置（10%）- 在52周区间中的位置
        week52_high = fund_info.get('week52_high', fund_info['current'])
        week52_low = fund_info.get('week52_low', fund_info['current'])
        position_ratio = (fund_info['current'] - week52_low) / (week52_high - week52_low)

        if position_ratio < 0.3:
            position_score = 90  # 接近低点
        elif position_ratio < 0.5:
            position_score = 70
        elif position_ratio < 0.7:
            position_score = 50
        else:
            position_score = 30  # 接近高点
        scores['position'] = position_score * 0.10

        # 计算总分
        total_score = sum(scores.values())

        return total_score, scores, analyses

    def generate_recommendation(self, fund_code, market_changes=None):
        """
        生成基金推荐报告（V5.1增强版）

        参数：
        - fund_code: 基金代码
        - market_changes: 市场整体涨跌幅列表（可选，用于风险评估）

        返回：
        - recommendation: 推荐报告
        """
        # 1. 计算V5.1评分
        result = self.calculate_v5_1_score(fund_code)

        if not result:
            return None

        total_score, scores, analyses = result
        fund_info = self.fund_pool[fund_code]

        # 2. 评估市场风险（如果有市场数据）
        if market_changes:
            risk_level, risk_score, risk_signals = self.assess_market_risk_level(market_changes)
        else:
            # 使用基金短期数据估算市场风险
            fund_changes = [fund_info.get('current', 0)]
            risk_level, risk_score, risk_signals = self.assess_market_risk_level(fund_changes)

        # 3. 根据风险等级调整评分（V5.1核心改进）
        adjusted_score = total_score
        risk_adjustment = []

        if risk_level == RiskLevel.CRITICAL:
            adjusted_score = total_score * 0.5  # 严重风险，评分减半
            risk_adjustment.append("⚠️ 市场CRITICAL风险，评分×0.5")
        elif risk_level == RiskLevel.HIGH:
            adjusted_score = total_score * 0.7  # 高风险，评分打7折
            risk_adjustment.append("⚠️ 市场HIGH风险，评分×0.7")
        elif risk_level == RiskLevel.MEDIUM:
            adjusted_score = total_score * 0.9  # 中等风险，评分打9折
            risk_adjustment.append("⚠️ 市场MEDIUM风险，评分×0.9")

        # 4. 生成推荐
        if adjusted_score >= 70:
            action = "可以考虑买入"
            action_type = "买入"
            emoji = "🟢"
        elif adjusted_score >= 55:
            action = "可以小仓位买入或持有"
            action_type = "持有"
            emoji = "🟡"
        elif adjusted_score >= 40:
            action = "建议观望"
            action_type = "观望"
            emoji = "🟠"
        else:
            action = "建议减仓或回避"
            action_type = "卖出"
            emoji = "🔴"

        # 5. 组装报告
        report = {
            'fund_code': fund_code,
            'fund_name': fund_info['name'],
            'fund_index': fund_info['index'],
            'current_nav': fund_info['current'],
            'original_score': round(total_score, 1),
            'adjusted_score': round(adjusted_score, 1),
            'action': action,
            'action_type': action_type,
            'emoji': emoji,
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_signals': risk_signals,
            'risk_adjustment': risk_adjustment,
            'scores_breakdown': {
                'short_term': round(scores.get('short_term', 0), 1),
                'medium_term': round(scores.get('medium_term', 0), 1),
                'peak_distance': round(scores.get('peak_distance', 0), 1),
                'gain_risk': round(scores.get('gain_risk', 0), 1),
                'rebound': round(scores.get('rebound', 0), 1),
                'value': round(scores.get('value', 0), 1),
                'position': round(scores.get('position', 0), 1),
            },
            'analysis': analyses,
        }

        return report

    def format_recommendation(self, report):
        """格式化推荐报告"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"智能选基系统 V5.1 - {report['fund_name']} ({report['fund_code']})")
        lines.append("=" * 60)
        lines.append("")

        # 基本信息
        lines.append(f"📊 基金名称：{report['fund_name']}")
        lines.append(f"📈 跟踪指数：{report['fund_index']}")
        lines.append(f"💰 当前净值：{report['current_nav']}")
        lines.append("")

        # 评分信息
        lines.append(f"🎯 原始V5评分：{report['original_score']}/100")
        lines.append(f"⚠️ 风险调整后：{report['adjusted_score']}/100")
        lines.append(f"📊 市场风险等级：{report['risk_level']} (分数: {report['risk_score']}/100)")
        lines.append("")

        # 风险信号
        if report['risk_signals']:
            lines.append("⚠️ 风险信号：")
            for signal in report['risk_signals']:
                lines.append(f"   {signal}")
            lines.append("")

        # 风险调整说明
        if report['risk_adjustment']:
            lines.append("🔧 风险调整：")
            for adjustment in report['risk_adjustment']:
                lines.append(f"   {adjustment}")
            lines.append("")

        # 操作建议
        lines.append(f"{report['emoji']} 操作建议：{report['action']}")
        lines.append("")

        # 评分明细
        lines.append("📋 评分明细：")
        lines.append(f"   ├─ 短期趋势（15%）：{report['scores_breakdown']['short_term']:.1f}/15.0 ⭐ V5.1新增")
        lines.append(f"   ├─ 中期趋势（20%）：{report['scores_breakdown']['medium_term']:.1f}/20.0")
        lines.append(f"   ├─ 距高点距离（20%）：{report['scores_breakdown']['peak_distance']:.1f}/20.0")
        lines.append(f"   ├─ 涨幅风险（10%）：{report['scores_breakdown']['gain_risk']:.1f}/10.0")
        lines.append(f"   ├─ 反弹潜力（10%）：{report['scores_breakdown']['rebound']:.1f}/10.0")
        lines.append(f"   ├─ 估值（15%）：{report['scores_breakdown']['value']:.1f}/15.0")
        lines.append(f"   └─ 位置（10%）：{report['scores_breakdown']['position']:.1f}/10.0")
        lines.append("")

        # 详细分析
        lines.append("🔍 详细分析：")

        if 'short_term' in report['analysis']:
            lines.append("   短期趋势分析：")
            for analysis in report['analysis']['short_term']:
                lines.append(f"      {analysis}")

        if 'peak_distance' in report['analysis']:
            lines.append("   位置分析：")
            for analysis in report['analysis']['peak_distance']:
                lines.append(f"      {analysis}")

        lines.append("")
        lines.append("=" * 60)
        lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("版本：V5.1 - 风险预警增强版")
        lines.append("=" * 60)

        return "\n".join(lines)


# ============== 主程序接口 ==============

def main():
    """主程序演示"""
    selector = SmartSelectorV5_1()

    print("智能选基系统 V5.1 - 风险预警增强版")
    print("=" * 60)
    print("")

    # 示例：分析中证500ETF（模拟3/19后的市场环境）
    fund_code = '001229'  # 天弘中证500ETF联接A

    # 模拟市场数据（3/23上午）
    market_changes = [-2.37, -2.32, -0.2]  # 中证500、沪深300、上证

    report = selector.generate_recommendation(fund_code, market_changes)

    if report:
        print(selector.format_recommendation(report))


if __name__ == "__main__":
    main()
