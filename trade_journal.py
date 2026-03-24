# -*- coding: utf-8 -*-
"""
交易日志助手
自动记录每日市场变化、操作决策、原因分析
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import datetime, date
import os

# ============== 日志记录器 ==============

class TradeJournal:
    """交易日志记录器"""

    def __init__(self, log_dir="C:\\Users\\Administrator\\my_finance_agent"):
        self.log_dir = log_dir
        self.today = datetime.now().strftime("%Y%m%d")
        self.log_file = os.path.join(log_dir, f"trade_log_{self.today}.md")

    def record_daily_change(self, market_data, positions_data):
        """
        记录每日市场变化

        Parameters:
        - market_data: 市场数据 dict
        - positions_data: 持仓数据 dict
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = f"""
## 📅 {timestamp} - 市场变化记录

### 指数涨跌幅
"""

        for etf_code, data in market_data.items():
            symbol = "📈" if data['change_pct'] > 0 else "📉" if data['change_pct'] < 0 else "➡️"
            entry += f"- {data['name']}（{etf_code}）：{symbol} {data['change_pct']:+.2f}%\n"

        entry += "\n### 持仓变化\n"

        for pos in positions_data:
            symbol = "🟢" if pos['profit'] > 0 else "🔴" if pos['profit'] < 0 else "⚪"
            entry += f"- {pos['name']}：{symbol} {pos['profit']:+.2f}元 ({pos['profit_pct']:+.2f}%)，今日{pos['change_pct']:+.2f}%\n"

        self._append_to_log(entry)

    def record_operation(self, operation_type, fund_code, fund_name, amount, reason, score=None):
        """
        记录操作决策

        Parameters:
        - operation_type: 操作类型（买入/卖出/观望）
        - fund_code: 基金代码
        - fund_name: 基金名称
        - amount: 金额/份额
        - reason: 原因
        - score: V5评分（可选）
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = f"""
## 💡 {timestamp} - 操作决策

### 操作：{operation_type}
**标的**：{fund_name}（{fund_code}）
**金额**：{amount}
**V5评分**：{score if score else 'N/A'}

### 原因分析
{reason}

### 判断依据
- 技术面：
- 基本面：
- 算法评分：
- 风险评估：
"""

        self._append_to_log(entry)

    def record_change_analysis(self, fund_code, fund_name, change_pct, reasons, judgment):
        """
        记录涨跌幅原因分析

        Parameters:
        - fund_code: 基金代码
        - fund_name: 基金名称
        - change_pct: 涨跌幅
        - reasons: 原因列表
        - judgment: 判断（正常/关注/操作）
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        symbol = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"

        entry = f"""
## 🔍 {timestamp} - {fund_name}涨跌分析

**涨跌幅**：{symbol} {change_pct:+.2f}%

### 原因分析
"""

        for i, reason in enumerate(reasons, 1):
            entry += f"{i}. {reason}\n"

        entry += f"""
### 判断
**状态**：{judgment}

**后续策略**：
- 短期（1-3天）：
- 中期（1-2周）：

**关注指标**：
"""

        self._append_to_log(entry)

    def record_technical_adjustment(self, adj_type, duration, amplitude, reasons, action):
        """
        记录技术调整

        Parameters:
        - adj_type: 调整类型（正常回踩/中度调整/深度调整/风格切换/板块轮动）
        - duration: 持续时间
        - amplitude: 调整幅度
        - reasons: 原因列表
        - action: 应对措施
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = f"""
## 📉 {timestamp} - 技术调整记录

**调整类型**：{adj_type}
**持续时间**：{duration}
**调整幅度**：{amplitude}

### 调整原因
"""

        for i, reason in enumerate(reasons, 1):
            entry += f"{i}. {reason}\n"

        entry += f"""
### 应对措施
{action}

### 后续观察
- 观察指标1：
- 观察指标2：
"""

        self._append_to_log(entry)

    def record_decision_evaluation(self, prediction, actual, accuracy, operation_quality, comments=""):
        """
        记录决策质量评估

        Parameters:
        - prediction: 昨日预测
        - actual: 今日实际
        - accuracy: 准确度（准确/偏差/错误）
        - operation_quality: 操作合理性评价
        - comments: 备注
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = f"""
## 📊 {timestamp} - 决策质量评估

### 预测 vs 实际
**昨日预测**：{prediction}
**今日实际**：{actual}
**准确度**：{accuracy}

### 操作合理性
{operation_quality}

### 经验总结
{comments}
"""

        self._append_to_log(entry)

    def _append_to_log(self, content):
        """追加内容到日志文件"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(content + "\n")
            print(f"✅ 已记录到日志：{self.log_file}")
        except Exception as e:
            print(f"❌ 记录失败：{e}")

    def create_daily_log(self):
        """创建当日日志文件（从模板）"""
        template_file = os.path.join(self.log_dir, "TRADE_LOG_TEMPLATE.md")

        if not os.path.exists(template_file):
            print("❌ 模板文件不存在")
            return False

        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                template = f.read()

            # 替换日期
            today_str = datetime.now().strftime("%Y-%m-%d")
            weekdays = ['一', '二', '三', '四', '五', '六', '日']
            weekday = weekdays[datetime.now().weekday()]

            template = template.replace("YYYY-MM-DD", today_str)
            template = template.replace("星期X", f"星期{weekday}")

            # 写入日志文件
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(template)

            print(f"✅ 已创建今日日志：{self.log_file}")
            return True

        except Exception as e:
            print(f"❌ 创建日志失败：{e}")
            return False


# ============== 快捷记录函数 ==============

journal = TradeJournal()

def quick_record_change(market_data, positions_data):
    """快速记录市场变化"""
    journal.record_daily_change(market_data, positions_data)

def quick_record_operation(op_type, code, name, amount, reason, score=None):
    """快速记录操作"""
    journal.record_operation(op_type, code, name, amount, reason, score)

def quick_record_analysis(code, name, change_pct, reasons, judgment):
    """快速记录涨跌分析"""
    journal.record_change_analysis(code, name, change_pct, reasons, judgment)

def quick_record_adjustment(adj_type, duration, amplitude, reasons, action):
    """快速记录技术调整"""
    journal.record_technical_adjustment(adj_type, duration, amplitude, reasons, action)


# ============== 使用示例 ==============

if __name__ == "__main__":
    print("=" * 60)
    print("📝 交易日志助手")
    print("=" * 60)

    # 创建今日日志
    journal.create_daily_log()

    print("\n使用示例：")
    print("1. quick_record_change() - 记录市场变化")
    print("2. quick_record_operation() - 记录操作决策")
    print("3. quick_record_analysis() - 记录涨跌分析")
    print("4. quick_record_adjustment() - 记录技术调整")
