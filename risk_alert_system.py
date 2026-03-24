# -*- coding: utf-8 -*-
"""
风险预警系统 V1.0
基于2026-03-19市场跳水事件的风险预警算法

核心功能：
1. 实时监控市场风险信号
2. 预测潜在的全盘下跌风险
3. 提前发出风险预警
4. 建议应对措施
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import datetime, timedelta
from collections import deque

# ============== 风险事件案例库 ==============

RISK_CASES = {
    '2026-03-19': {
        'date': '2026-03-19',
        'event_name': '中证500大幅跳水',
        'event_type': 'trend_reversal',  # 趋势反转
        'description': '''
从中证500+1.08%（3/18 14:41）到-2.66%（3/19 13:50）
24小时内从反弹转为大跌，累计跌幅3.74%

关键特征：
1. 反弹失败：昨日+1.08%反弹未能延续
2. 快速跳水：短时间内从红盘翻绿
3. 全线下跌：三大指数全部翻绿
4. 趋势确认：从反弹转为明确下降趋势
        ''',
        'early_signals': [
            '反弹出现在下降趋势中',
            '反弹幅度小（+1.08%）',
            '反弹无成交量配合',
            '次日直接低开或冲高回落',
        ],
        'risk_level': 'HIGH',
        'impact': '004348两日累计亏损约-3.5%',
        'lesson': '下降趋势中的反弹往往是"死猫跳"，不可盲目追涨',
        'prevention': '在下降趋势中，即使反弹也不应加仓，反而应减仓',
    },
}

# ============== 风险指标定义 ==============

class RiskIndicators:
    """风险指标计算"""

    @staticmethod
    def calculate_momentum_change(today_change, yesterday_change):
        """
        计算动量变化

        参数：
        - today_change: 今日涨跌幅
        - yesterday_change: 昨日涨跌幅

        返回：
        - momentum_score: 动量评分 (-100 到 +100)
        """
        momentum_change = today_change - yesterday_change

        # 动量评分
        if momentum_change < -3:
            return -100  # 动量急剧恶化，高风险
        elif momentum_change < -2:
            return -75   # 动量明显恶化，中高风险
        elif momentum_change < -1:
            return -50   # 动量转弱，中等风险
        elif momentum_change < 0:
            return -25   # 动量减弱，低风险
        elif momentum_change < 1:
            return 0     # 动量平稳
        elif momentum_change < 2:
            return 25    # 动量增强
        else:
            return 50    # 动量明显增强

    @staticmethod
    def detect_false_rally(change_history):
        """
        检测虚假反弹（死猫跳）

        参数：
        - change_history: 最近N天的涨跌幅列表

        返回：
        - is_false_rally: 是否是虚假反弹
        - confidence: 置信度 (0-1)
        """
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

        # 判断是否是虚假反弹
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

    @staticmethod
    def calculate_breadth指数涨跌散度(up_count, down_count, flat_count):
        """
        计算市场涨跌散度（广度指标）

        参数：
        - up_count: 上涨指数数量
        - down_count: 下跌指数数量
        - flat_count: 平盘指数数量

        返回：
        - breadth_score: 广度评分 (-100 到 +100)
        """
        total = up_count + down_count + flat_count
        if total == 0:
            return 0

        # 上涨占比
        up_ratio = up_count / total

        # 广度评分
        if up_ratio >= 0.8:
            return 100  # 普涨，强势
        elif up_ratio >= 0.6:
            return 50   # 多数上涨，偏强
        elif up_ratio >= 0.4:
            return 0    # 涨跌参半，震荡
        elif up_ratio >= 0.2:
            return -50  # 多数下跌，偏弱
        else:
            return -100 # 普跌，弱势

    @staticmethod
    def detect_trend_reversal(change_history):
        """
        检测趋势反转

        参数：
        - change_history: 最近N天的涨跌幅列表

        返回：
        - is_reversal: 是否反转
        - reversal_type: 反转类型 ('bull_to_bear', 'bear_to_bull')
        """
        if len(change_history) < 5:
            return False, None

        recent_5 = change_history[-5:]
        first_3_avg = sum(recent_5[:3]) / 3
        last_2_avg = sum(recent_5[-2:]) / 2

        # 从上涨转为下跌
        if first_3_avg > 0.5 and last_2_avg < -0.5:
            return True, 'bull_to_bear'

        # 从下跌转为上涨
        if first_3_avg < -0.5 and last_2_avg > 0.5:
            return True, 'bear_to_bull'

        return False, None


# ============== 风险等级定义 ==============

class RiskLevel:
    """风险等级"""

    CRITICAL = "CRITICAL"  # 严重风险，立即操作
    HIGH = "HIGH"          # 高风险，准备操作
    MEDIUM = "MEDIUM"      # 中等风险，密切关注
    LOW = "LOW"            # 低风险，正常监控
    MINIMAL = "MINIMAL"    # 最低风险，安全

    @staticmethod
    def get_score(level):
        """将风险等级转换为数字分数"""
        scores = {
            'CRITICAL': 100,
            'HIGH': 75,
            'MEDIUM': 50,
            'LOW': 25,
            'MINIMAL': 0,
        }
        return scores.get(level, 0)

    @staticmethod
    def from_score(score):
        """将数字分数转换为风险等级"""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        elif score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL


# ============== 风险预警引擎 ==============

class RiskAlertEngine:
    """风险预警引擎"""

    def __init__(self):
        self.change_history = deque(maxlen=10)  # 保留最近10天的涨跌幅
        self.alerts = []

    def update_market_data(self, changes_dict):
        """
        更新市场数据

        参数：
        - changes_dict: {指数代码: 涨跌幅}
        """
        # 计算平均涨跌幅
        avg_change = sum(changes_dict.values()) / len(changes_dict)
        self.change_history.append(avg_change)

    def assess_risk(self, current_changes):
        """
        评估当前风险

        参数：
        - current_changes: {指数代码: 涨跌幅}

        返回：
        - risk_report: 风险报告
        """
        if len(self.change_history) < 2:
            return self._generate_report(RiskLevel.LOW, [], "数据不足，继续观察")

        risk_signals = []
        risk_score = 0

        # 1. 动量变化检测
        avg_change = sum(current_changes.values()) / len(current_changes)
        if len(self.change_history) >= 2:
            yesterday_avg = self.change_history[-2]
            momentum_score = RiskIndicators.calculate_momentum_change(
                avg_change, yesterday_avg
            )

            if momentum_score <= -75:
                risk_signals.append({
                    'type': 'momentum_deterioration',
                    'level': 'HIGH',
                    'message': f'动量急剧恶化：昨日{yesterday_avg:+.2f}% → 今日{avg_change:+.2f}%',
                    'score_impact': 30,
                })
                risk_score += 30
            elif momentum_score <= -50:
                risk_signals.append({
                    'type': 'momentum_weakening',
                    'level': 'MEDIUM',
                    'message': f'动量明显转弱：昨日{yesterday_avg:+.2f}% → 今日{avg_change:+.2f}%',
                    'score_impact': 20,
                })
                risk_score += 20

        # 2. 虚假反弹检测
        is_false_rally, confidence = RiskIndicators.detect_false_rally(
            list(self.change_history)
        )

        if is_false_rally and confidence > 0.7:
            risk_signals.append({
                'type': 'false_rally',
                'level': 'HIGH',
                'message': f'检测到虚假反弹（死猫跳），置信度{confidence:.0%}',
                'score_impact': 35,
                'lesson': '根据2026-03-19案例，下降趋势中的反弹往往是陷阱',
            })
            risk_score += 35

        # 3. 趋势反转检测
        is_reversal, reversal_type = RiskIndicators.detect_trend_reversal(
            list(self.change_history)
        )

        if is_reversal and reversal_type == 'bull_to_bear':
            risk_signals.append({
                'type': 'trend_reversal',
                'level': 'CRITICAL',
                'message': '趋势反转：从上涨转为下跌',
                'score_impact': 40,
                'lesson': '根据2026-03-19案例，趋势反转后往往持续下跌',
            })
            risk_score += 40

        # 4. 市场广度检测
        up_count = len([x for x in current_changes.values() if x > 0])
        down_count = len([x for x in current_changes.values() if x < 0])
        breadth_score = RiskIndicators.calculate_breadth指数涨跌散度(
            up_count, down_count, 0
        )

        if breadth_score <= -50:
            risk_signals.append({
                'type': 'weak_breadth',
                'level': 'MEDIUM',
                'message': f'市场普跌：{down_count}个指数下跌，{up_count}个指数上涨',
                'score_impact': 15,
            })
            risk_score += 15

        # 5. 单日大幅下跌检测
        min_change = min(current_changes.values())
        if min_change < -2:
            risk_signals.append({
                'type': 'sharp_decline',
                'level': 'HIGH',
                'message': f'单日大幅下跌：跌幅最大的指数达{min_change:.2f}%',
                'score_impact': 25,
            })
            risk_score += 25
        elif min_change < -1.5:
            risk_signals.append({
                'type': 'moderate_decline',
                'level': 'MEDIUM',
                'message': f'单日明显下跌：跌幅最大的指数达{min_change:.2f}%',
                'score_impact': 15,
            })
            risk_score += 15

        # 确定风险等级
        risk_level = RiskLevel.from_score(risk_score)

        return self._generate_report(risk_level, risk_signals, risk_score)

    def _generate_report(self, risk_level, signals, score):
        """生成风险报告"""
        report = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'risk_level': risk_level,
            'risk_score': score,
            'signals': signals,
            'recommendation': self._generate_recommendation(risk_level, signals),
        }

        return report

    def _generate_recommendation(self, risk_level, signals):
        """生成操作建议"""

        if risk_level == RiskLevel.CRITICAL:
            return {
                'action': '立即减仓或止损',
                'reason': '严重风险信号，趋势可能已反转',
                'steps': [
                    '1. 立即评估持仓，考虑减仓50%',
                    '2. 高风险品种（如成长ETF）优先减仓',
                    '3. 转向稳健品种（如银行ETF）',
                    '4. 如触及止损线，立即执行止损',
                ],
                'reference_case': '2026-03-19：趋势反转后连续下跌',
            }

        elif risk_level == RiskLevel.HIGH:
            return {
                'action': '准备减仓',
                'reason': '高风险信号，需要警惕',
                'steps': [
                    '1. 密切关注明日市场表现',
                    '2. 如继续下跌，立即减仓',
                    '3. 考虑将成长仓位转移到稳健仓位',
                    '4. 设置明日预警线（如再跌-1.5%）',
                ],
                'reference_case': '2026-03-19：动量恶化后继续大跌',
            }

        elif risk_level == RiskLevel.MEDIUM:
            return {
                'action': '密切关注',
                'reason': '中等风险，需要观察',
                'steps': [
                    '1. 每日收盘后评估风险',
                    '2. 如风险上升，准备行动',
                    '3. 不要加仓高风险品种',
                    '4. 检查止损线设置',
                ],
            }

        else:  # LOW or MINIMAL
            return {
                'action': '正常持有',
                'reason': '风险可控',
                'steps': [
                    '1. 继续持有',
                    '2. 定期检查',
                    '3. 不要放松警惕',
                ],
            }


# ============== 使用示例 ==============

def example_usage():
    """使用示例"""

    print("=" * 70)
    print("🚨 风险预警系统 V1.0")
    print("=" * 70)
    print()

    # 创建风险预警引擎
    engine = RiskAlertEngine()

    # 模拟2026-03-19的情况
    print("📊 模拟2026-03-19市场跳水")
    print("=" * 70)

    # 3/17数据
    engine.update_market_data({
        'sh510500': -1.97,
        'sh510300': -0.68,
        'sh512800': 0.79,
    })
    print("3/17: 中证500-1.97%, 沪深300-0.68%, 银行+0.79%")

    # 3/18数据（反弹）
    engine.update_market_data({
        'sh510500': 1.08,
        'sh510300': 0.43,
        'sh512800': -0.25,
    })
    print("3/18: 中证500+1.08%, 沪深300+0.43%, 银行-0.25%")

    # 3/19数据（跳水）
    engine.update_market_data({
        'sh510500': -2.66,
        'sh510300': -1.48,
        'sh512800': -0.25,
    })
    print("3/19: 中证500-2.66%, 沪深300-1.48%, 银行-0.25%")
    print()

    # 评估风险
    print("🔍 风险评估")
    print("=" * 70)

    current_changes = {
        'sh510500': -2.66,
        'sh510300': -1.48,
        'sh512800': -0.25,
    }

    report = engine.assess_risk(current_changes)

    print(f"风险等级：{report['risk_level']}")
    print(f"风险评分：{report['risk_score']}")
    print()

    if report['signals']:
        print("风险信号：")
        for signal in report['signals']:
            level_icon = {
                'CRITICAL': '🔴',
                'HIGH': '⚠️',
                'MEDIUM': '🟡',
                'LOW': '🟢',
            }.get(signal['level'], '➡️')

            print(f"  {level_icon} {signal['message']}")
            if 'lesson' in signal:
                print(f"     💡 {signal['lesson']}")
        print()

    print("操作建议：")
    print("-" * 70)
    print(f"行动：{report['recommendation']['action']}")
    print(f"理由：{report['recommendation']['reason']}")
    print()
    print("具体步骤：")
    for step in report['recommendation']['steps']:
        print(f"  {step}")
    print()

    if 'reference_case' in report['recommendation']:
        print(f"参考案例：{report['recommendation']['reference_case']}")
    print()


if __name__ == "__main__":
    example_usage()
