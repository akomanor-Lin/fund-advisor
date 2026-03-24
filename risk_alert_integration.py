# -*- coding: utf-8 -*-
"""
将风险预警系统集成到主程序中
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from risk_alert_system import RiskAlertEngine, RiskLevel, RiskIndicators

# ============== 集成到主程序的函数 ==============

def add_risk_monitor_to_main():
    """
    在主程序中添加风险监控

    使用方法：
    1. 在main()函数开始时创建引擎
    2. 每日更新市场数据
    3. 评估风险并发出预警
    4. 根据风险等级调整操作建议
    """

    integration_code = '''
# 在主程序开头添加
from risk_alert_system import RiskAlertEngine, RiskLevel

# 在main()函数中创建风险引擎
def main():
    # ... 原有代码 ...

    # 创建风险预警引擎
    risk_engine = RiskAlertEngine()

    # 每日更新市场数据
    try:
        # 获取今日涨跌幅
        today_changes = {}
        for position in MULTI_POSITIONS['positions']:
            etf_code = position['etf_code']
            data = get_fund_data_sina(etf_code)
            if data:
                today_changes[etf_code] = data['change_pct']

        # 更新风险引擎
        risk_engine.update_market_data(today_changes)

        # 评估风险
        risk_report = risk_engine.assess_risk(today_changes)

        # 显示风险预警
        print("\\n" + "=" * 60)
        print("🚨 风险预警")
        print("=" * 60)
        print(f"风险等级：{risk_report['risk_level']}")
        print(f"风险评分：{risk_report['risk_score']}")

        if risk_report['signals']:
            print("\\n风险信号：")
            for signal in risk_report['signals']:
                level_icon = {
                    'CRITICAL': '🔴',
                    'HIGH': '⚠️',
                    'MEDIUM': '🟡',
                    'LOW': '🟢',
                }.get(signal['level'], '➡️')
                print(f"  {level_icon} {signal['message']}")

        # 根据风险等级调整操作建议
        if risk_report['risk_level'] in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            print("\\n⚠️ 高风险预警！建议：")
            for step in risk_report['recommendation']['steps']:
                print(f"  {step}")

            # 发送预警消息
            alert_message = f"🚨 风险预警\\n等级：{risk_report['risk_level']}\\n评分：{risk_report['score']}"
            send_serverchan(alert_message)

        print("=" * 60)

    except Exception as e:
        print(f"⚠️ 风险评估失败：{e}")

    # ... 原有代码 ...
'''

    return integration_code


def generate_risk_monitoring_guide():
    """生成风险监控指南"""

    guide = """
# 风险预警系统使用指南

## 🎯 核心功能

### 1. 实时风险监控
- 每日更新市场数据
- 自动计算风险指标
- 实时评估风险等级

### 2. 提前预警
- 检测趋势反转
- 识别虚假反弹
- 预警全盘下跌

### 3. 操作建议
- 根据风险等级给出建议
- 参考历史案例
- 提供具体步骤

---

## 📊 风险等级定义

| 等级 | 评分 | 颜色 | 操作 |
|------|------|------|------|
| CRITICAL | ≥80 | 🔴 | 立即减仓或止损 |
| HIGH | 60-79 | ⚠️ | 准备减仓 |
| MEDIUM | 40-59 | 🟡 | 密切关注 |
| LOW | 20-39 | 🟢 | 正常持有 |
| MINIMAL | <20 | ✅ | 安全 |

---

## 🔍 风险信号类型

### 1. 动量急剧恶化 (HIGH)
- 从昨日+X%到今日-Y%
- 变化幅度>3%
- 参考案例：2026-03-19（+1.08%→-2.66%）

### 2. 虚假反弹/死猫跳 (HIGH)
- 下降趋势中的小幅反弹
- 反弹<2%，次日立即下跌
- 参考案例：2026-03-18→19

### 3. 趋势反转 (CRITICAL)
- 连续上涨后转为连续下跌
- 3日均线下穿
- 参考案例：多次市场转折

### 4. 市场普跌 (MEDIUM)
- 多数指数下跌
- 广度指标<-50
- 市场情绪转弱

### 5. 单日大幅下跌 (HIGH)
- 单日跌幅>2%
- 可能是趋势开始
- 需要高度警惕

---

## 💡 使用建议

### 每日必做：
1. ✅ 更新市场数据
2. ✅ 查看风险等级
3. ✅ 阅读风险信号
4. ✅ 执行相应操作

### 风险等级对应操作：

#### 🔴 CRITICAL（严重）
- [ ] 立即评估持仓
- [ ] 减仓50%或更多
- [ ] 高风险品种优先减
- [ ] 转向稳健品种
- [ ] 触及止损立即执行

#### ⚠️ HIGH（高）
- [ ] 密切关注明日表现
- [ ] 如继续下跌，立即减仓
- [ ] 考虑调仓（成长→稳健）
- [ ] 设置明日预警线

#### 🟡 MEDIUM（中）
- [ ] 每日收盘后评估
- [ ] 风险上升准备行动
- [ ] 不要加仓高风险
- [ ] 检查止损线

#### 🟢 LOW（低）
- [ ] 继续持有
- [ ] 定期检查
- [ ] 不要放松警惕

---

## 📚 历史案例库

### 案例1：2026-03-19 中证500跳水
- **事件**：+1.08% → -2.66%（24小时）
- **信号**：虚假反弹、趋势反转
- **教训**：下降趋势中的反弹是陷阱
- **应对**：减仓50%转入银行ETF

### 案例2：（待补充）
- **事件**：
- **信号**：
- **教训**：
- **应对**：

---

## 🔧 集成步骤

### 步骤1：导入模块
```python
from risk_alert_system import RiskAlertEngine, RiskLevel
```

### 步骤2：创建引擎
```python
risk_engine = RiskAlertEngine()
```

### 步骤3：更新数据
```python
risk_engine.update_market_data(today_changes)
```

### 步骤4：评估风险
```python
risk_report = risk_engine.assess_risk(current_changes)
```

### 步骤5：执行建议
```python
if risk_report['risk_level'] == RiskLevel.CRITICAL:
    # 执行紧急减仓
    pass
```

---

## ⚠️ 重要提醒

1. **信任系统**：不要心存侥幸
2. **及时行动**：不要等待确认
3. **严格执行**：不要犹豫不决
4. **持续监控**：不要放松警惕
5. **记录总结**：每次事件都要复盘

---

**记住：系统不会每次都准确，但它可以帮你避免重大损失！**
"""

    return guide


# ============== 生成示例输出 ==============

if __name__ == "__main__":
    print("=" * 70)
    print("📋 风险预警系统集成指南")
    print("=" * 70)
    print()

    print("1️⃣ 集成代码示例")
    print("-" * 70)
    print(add_risk_monitor_to_main()[:500])
    print("...")
    print()

    print("2️⃣ 使用指南")
    print("-" * 70)
    print(generate_risk_monitoring_guide()[:500])
    print("...")
    print()

    print("3️⃣ 测试系统")
    print("-" * 70)
    from risk_alert_system import example_usage
    example_usage()
