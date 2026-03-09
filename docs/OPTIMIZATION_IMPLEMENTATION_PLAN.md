# 策略优化实施计划

**版本：** v1.0
**日期：** 2026-03-09
**状态：** 待执行
**原则：** 不影响现有观测

---

## 📋 目录

1. [核心原则](#1-核心原则)
2. [架构设计](#2-架构设计)
3. [实验流程](#3-实验流程)
4. [时间计划](#4-时间计划)
5. [检验清单](#5-检验清单)
6. [应急方案](#6-应急方案)

---

## 1. 核心原则

### 1.1 不影响现有观测

```
现有系统 (v1.0)
├── 策略ID: 51 (daily_observer)
├── 状态: 🏃 运行中
├── 持仓: 8只股票
└── 数据: 正常记录

新系统 (v2.0)
├── 策略ID: 52 (daily_observer_v2)
├── 状态: 📋 待启动
├── 持仓: 暂无
└── 数据: 独立记录
```

**隔离原则：**
- ✅ v1.0 和 v2.0 完全独立
- ✅ v1.0 继续运行，不受影响
- ✅ v2.0 新建策略，独立记录
- ✅ 两份数据可以对比分析

### 1.2 实验原则

| 原则 | 说明 |
|------|------|
| **小步快跑** | 每次只改一个参数 |
| **独立验证** | 每步都要单独验证效果 |
| **随时回退** | 效果不好立即停止 |
| **数据驱动** | 用数据说话，不凭感觉 |

### 1.3 检验标准

| 指标 | v1.0 基线 | v2.0 目标 | 检验方式 |
|------|----------|-----------|---------|
| 年化收益 | 15% | ≥ 15% | 回测 |
| 最大回撤 | 15% | ≤ 15% | 回测 |
| 夏普比率 | 1.0 | ≥ 1.0 | 回测 |
| 统计显著性 | - | p < 0.05 | t检验 |
| 稳定性 | - | 标准差 < 5% | 按年份 |
| 换手率 | - | ≤ 5倍/年 | 回测 |

---

## 2. 架构设计

### 2.1 策略隔离

```python
# backend/services/scoring_engines/
├── daily_observer.py          # v1.0 现有策略
├── daily_observer_v2.py       # v2.0 新策略 (新建)
└── base_engine.py             # 基础引擎 (共享)

# database
├── daily_observer_strategies  # 策略表
│   ├── id: 51  (v1.0, 运行中)
│   └── id: 52  (v2.0, 新建)
│
├── daily_observer_records_51  # v1.0 观测记录
└── daily_observer_records_52  # v2.0 观测记录 (独立)
```

### 2.2 创建 v2.0 策略

```sql
-- 1. 在现有数据库中创建新策略
INSERT INTO daily_observer_strategies (
    name,
    description,
    engine,
    scoring_engine_id,
    factor_combo_id,
    top_n,
    max_positions,
    take_profit_ratio,
    stop_loss_ratio,
    trailing_stop_ratio,
    sell_rank_out,
    signal_confirm_days,
    blacklist_cooldown,
    status
) VALUES (
    '观测策略 v2.0',
    '风控参数优化版：止盈18%，止损6%，移动止损8%',
    'daily_observer_v2',
    'daily_observer_v2',  -- 新引擎ID
    1,  -- factor_combo_id (使用现有因子组合)
    10, -- top_n
    10, -- max_positions
    0.18,  -- ⚠️ 修改：止盈从25%降到18%
    -0.06,  -- 保持：止损6%
    0.08,  -- ⚠️ 修改：移动止损8%
    15,  -- 保持：排名15卖出
    3,   -- 保持：确认3天
    30,  -- 保持：冷却30天
    'paused'  -- ⚠️ 新策略默认暂停
);

-- 2. 获取新策略ID (假设是52)
SELECT LAST_INSERT_ID();

-- 3. 创建独立的观测记录表（可选，也可以用现有表加 strategy_id 区分）
-- daily_observer_records 会自动通过 strategy_id 区分
```

### 2.3 创建 v2.0 引擎

```python
# backend/services/scoring_engines/daily_observer_v2.py

from .daily_observer import DailyObserverEngine
from dataclasses import dataclass


@dataclass
class V2Config:
    """v2.0 配置"""
    take_profit_ratio: float = 0.18   # 修改点1：止盈18%
    stop_loss_ratio: float = -0.06    # 保持不变
    trailing_stop_ratio: float = 0.08  # 修改点2：移动止损8%

    # 其他参数保持和 v1.0 一致
    top_n: int = 10
    max_positions: int = 10
    sell_rank_out: int = 15
    signal_confirm_days: int = 3
    blacklist_cooldown: int = 30


class DailyObserverEngineV2(DailyObserverEngine):
    """v2.0 观测引擎

    改动点：
    1. 止盈从 25% 降到 18%
    2. 移动止损从 10% 改到 8%
    3. 其他逻辑保持不变
    """

    VERSION = "v2.0"

    def __init__(self, config: V2Config = None):
        super().__init__()
        self.config = config or V2Config()

    def get_take_profit_ratio(self) -> float:
        """获取止盈比例（v2.0: 18%）"""
        return self.config.take_profit_ratio

    def get_trailing_stop_ratio(self) -> float:
        """获取移动止损比例（v2.0: 8%）"""
        return self.config.trailing_stop_ratio

    def get_stop_loss_ratio(self) -> float:
        """获取止损比例（保持 6%）"""
        return self.config.stop_loss_ratio

    # 其他方法继承自 DailyObserverEngine，不需要修改


# 注册到引擎注册表
from .registry import register_engine

register_engine("daily_observer_v2", DailyObserverEngineV2)
```

---

## 3. 实验流程

### 3.1 Phase 1: 回测验证 (Week 1-2)

#### Step 1.1: 准备数据

```python
# backend/scripts/prepare_backtest_data.py

import pandas as pd
from datetime import datetime

# 数据分割（样本外验证）
TRAIN_START = "2024-01-01"
TRAIN_END = "2025-06-30"

VAL_START = "2025-07-01"
VAL_END = "2025-12-31"

TEST_START = "2026-01-01"
TEST_END = "2026-03-09"

# 交易成本（双边）
COST_PER_SIDE = 0.0028  # 0.28%
TOTAL_COST = 0.0056     # 0.56% 完整来回

# 确保数据完整
def check_data_completeness():
    """检查数据完整性"""
    # 1. K线数据
    # 2. 因子数据
    # 3. 停牌数据
    # 4. ST/退市数据
    pass
```

#### Step 1.2: 运行回测

```python
# backend/scripts/run_backtest_comparison.py

import sys
sys.path.insert(0, '.' )

from services.backtest_service import BacktestService
from services.scoring_engines.daily_observer import DailyObserverEngine
from services.scoring_engines.daily_observer_v2 import DailyObserverEngineV2
from utils.database import db


def run_backtest(
    engine,
    start_date,
    end_date,
    strategy_name
):
    """运行单次回测"""

    print(f"\n{'='*60}")
    print(f"运行回测: {strategy_name}")
    print(f"时间范围: {start_date} ~ {end_date}")
    print(f"{'='*60}\n")

    # 创建回测服务
    service = BacktestService(
        engine=engine,
        initial_capital=100000,
        commission=0.0003,      # 万三佣金
        slippage=0.002,         # 0.2% 滑点
        stamp_duty=0.001        # 千一印花税（卖出）
    )

    # 运行回测
    result = service.run(
        start_date=start_date,
        end_date=end_date,
        stock_pool_type="key",  # 关键股票池
        top_n=10,
        max_positions=10
    )

    # 分析结果
    metrics = analyze_result(result, strategy_name)

    return result, metrics


def analyze_result(result, strategy_name):
    """分析回测结果"""

    metrics = {
        "策略名称": strategy_name,
        "总收益率": result.total_return,
        "年化收益率": result.annual_return,
        "最大回撤": result.max_drawdown,
        "夏普比率": result.sharpe_ratio,
        "胜率": result.win_rate,
        "盈亏比": result.profit_loss_ratio,
        "交易次数": len(result.trades),
        "平均持仓天数": result.avg_hold_days,
    }

    # 计算额外指标
    metrics["换手率"] = calculate_turnover(result)
    metrics["持仓天数分布"] = analyze_hold_days(result)

    return metrics


def compare_v1_v2():
    """对比 v1.0 和 v2.0"""

    # 运行 v1.0 回测
    v1_engine = DailyObserverEngine()
    v1_train, v1_train_metrics = run_backtest(
        v1_engine,
        TRAIN_START,
        TRAIN_END,
        "v1.0 (训练集)"
    )

    # 运行 v2.0 回测
    v2_engine = DailyObserverEngineV2()
    v2_train, v2_train_metrics = run_backtest(
        v2_engine,
        TRAIN_START,
        TRAIN_END,
        "v2.0 (训练集)"
    )

    # 对比结果
    print("\n" + "="*60)
    print("训练集对比结果")
    print("="*60)
    print_comparison(v1_train_metrics, v2_train_metrics)

    # 样本外验证
    v1_val, v1_val_metrics = run_backtest(
        v1_engine,
        VAL_START,
        VAL_END,
        "v1.0 (验证集)"
    )

    v2_val, v2_val_metrics = run_backtest(
        v2_engine,
        VAL_START,
        VAL_END,
        "v2.0 (验证集)"
    )

    print("\n" + "="*60)
    print("验证集对比结果")
    print("="*60)
    print_comparison(v1_val_metrics, v2_val_metrics)

    # 统计显著性检验
    significance = test_significance(v1_train, v2_train)
    print(f"\n统计显著性: p_value = {significance['p_value']:.4f}")
    if significance['p_value'] < 0.05:
        print("✅ 差异显著，v2.0 确实比 v1.0 好")
    else:
        print("❌ 差异不显著，可能只是随机波动")

    # 决策
    decision = make_decision(v1_val_metrics, v2_val_metrics, significance)
    print(f"\n📋 决策: {decision}")

    return {
        "v1_train": v1_train_metrics,
        "v2_train": v2_train_metrics,
        "v1_val": v1_val_metrics,
        "v2_val": v2_val_metrics,
        "significance": significance,
        "decision": decision
    }


def print_comparison(m1, m2):
    """打印对比结果"""

    print(f"\n{'指标':<20} {'v1.0':>12} {'v2.0':>12} {'差异':>12}")
    print("-" * 60)

    for key in ["年化收益率", "最大回撤", "夏普比率", "胜率", "换手率"]:
        v1_val = m1.get(key, 0)
        v2_val = m2.get(key, 0)

        # 计算差异
        if isinstance(v1_val, float) and isinstance(v2_val, float):
            diff = v2_val - v1_val
            diff_str = f"{diff:+.2%}" if key == "换手率" else f"{diff:+.2f}"

            # 判断
            if "回撤" in key:
                status = "✅" if diff > 0 else "❌"
            else:
                status = "✅" if diff > 0 else "❌"
        else:
            diff_str = "N/A"
            status = "•"

        print(f"{key:<20} {v1_val:>12.2f} {v2_val:>12.2f} {status}{diff_str:>11}")


def calculate_turnover(result):
    """计算换手率"""
    # TODO: 实现换手率计算
    return 3.5  # 示例值


def analyze_hold_days(result):
    """分析持仓天数分布"""
    # TODO: 实现持仓天数分析
    return {
        "平均": 25,
        "中位数": 20,
        "<10天": "15%",
        ">60天": "10%",
    }


def test_significance(result1, result2):
    """统计显著性检验"""
    import scipy.stats as stats

    # 提取日收益率
    returns1 = extract_daily_returns(result1)
    returns2 = extract_daily_returns(result2)

    # t检验
    t_stat, p_value = stats.ttest_ind(returns1, returns2)

    return {
        "t_stat": t_stat,
        "p_value": p_value
    }


def extract_daily_returns(result):
    """提取日收益率序列"""
    # TODO: 从回测结果中提取日收益率
    import numpy as np
    return np.random.normal(0.001, 0.02, 500)  # 示例


def make_decision(m1, m2, significance):
    """决策"""

    # 检查标准
    checks = [
        m2["年化收益率"] >= m1["年化收益率"],
        abs(m2["最大回撤"]) <= abs(m1["最大回撤"]),
        m2["夏普比率"] >= m1["夏普比率"],
        significance["p_value"] < 0.05,
        m2["换手率"] <= 5.0,
    ]

    if all(checks):
        return "✅ v2.0 优于 v1.0，继续验证"
    elif sum(checks) >= 3:
        return "🟡 v2.0 有一定优势，谨慎推进"
    else:
        return "❌ v2.0 不如 v1.0，停止实验"


if __name__ == "__main__":
    result = compare_v1_v2()
```

#### Step 1.3: 检查清单

```markdown
## Phase 1 检验清单

### 回测验证
- [ ] 训练集回测完成 (2024-01-01 ~ 2025-06-30)
- [ ] 验证集回测完成 (2025-07-01 ~ 2025-12-31)
- [ ] 加上交易成本 (0.56% 双边)
- [ ] 计算换手率
- [ ] 分析持仓天数分布

### 指标对比
- [ ] 年化收益率: v2.0 ≥ v1.0
- [ ] 最大回撤: v2.0 ≤ v1.0
- [ ] 夏普比率: v2.0 ≥ v1.0
- [ ] 胜率: v2.0 ≥ v1.0

### 统计检验
- [ ] t检验完成
- [ ] p_value < 0.05
- [ ] 差异显著

### 稳定性检验
- [ ] 按年份统计收益
- [ ] 标准差 < 5%
- [ ] 每年都保持正收益

### 相关性检验
- [ ] 计算交易重合度
- [ ] 重合度 < 80%
- [ ] 确保优化是真实的

### 决策
- [ ] 通过所有检验 → 继续 Phase 2
- [ ] 未通过检验 → 停止实验，保持 v1.0
```

---

### 3.2 Phase 2: 模拟观测 (Week 3)

**如果 Phase 1 通过，进入模拟观测**

#### Step 2.1: 启动 v2.0 策略

```sql
-- 启动 v2.0 策略（模拟模式）
UPDATE daily_observer_strategies
SET status = 'active'
WHERE id = 52;
```

```python
# backend/scripts/start_v2_observer.py

from services.daily_observer_service import DailyObserverService
from models.daily_observer import DailyObserverStrategy

def start_v2_observer():
    """启动 v2.0 观测策略"""

    # 获取 v2.0 策略
    strategy = DailyObserverStrategy.query.get(52)

    if not strategy:
        print("❌ v2.0 策略不存在，请先创建")
        return

    # 启动模拟观测
    service = DailyObserverService(strategy_id=52)
    service.run_simulation()  # 模拟模式，不实际交易

    print(f"✅ v2.0 策略已启动（模拟模式）")
    print(f"   策略ID: {strategy.id}")
    print(f"   配置: 止盈{strategy.take_profit_ratio:.0%}, 止损{abs(strategy.stop_loss_ratio):.0%}")
```

#### Step 2.2: 模拟观测 2 周

```markdown
## 模拟观测期 (Week 3)

### 每日任务
- [ ] 记录 v1.0 的持仓
- [ ] 记录 v2.0 的持仓
- [ ] 对比两个策略的差异
- [ ] 记录每日收益率

### 每周任务
- [ ] 统计周收益
- [ ] 统计胜率
- [ ] 统计换手率
- [ ] 检查是否有异常

### 观测期结束
- [ ] 对比 2 周累计收益
- [ ] 对比最大回撤
- [ ] v2.0 优于 v1.0 → 继续 Phase 3
- [ ] v2.0 不如 v1.0 → 停止实验
```

---

### 3.3 Phase 3: 小资金实盘 (Week 4-5)

**如果 Phase 2 通过，进入小资金实盘**

#### Step 3.1: 1% 资金实盘

```python
# 当前总资金：1万
# 实盘资金：100元 (1%)
# 期限：2 周

# 股票选择：
# - 从 v2.0 的筛选结果中选
# - 只选 1-2 只股票
# - 单只股票最多 50 元

# 记录：
# - 每日记录实盘持仓
# - 对比模拟和实盘的差异
```

#### Step 3.2: 5% 资金实盘

```python
# 如果 1% 资金实盘效果好，增加到 5%
# 当前总资金：1万
# 实盘资金：500 元 (5%)
# 期限：2 周

# 记录：
# - 每日记录实盘持仓
# - 计算实际收益率
# - 对比模拟盘的收益率
```

---

### 3.4 Phase 4: 逐步加仓 (Week 6-8)

**如果小资金实盘效果好，逐步加仓**

```
Week 6: 10% 资金实盘
Week 7: 20% 资金实盘
Week 8: 50% 资金实盘

# 如果效果好 → 100% 资金切换到 v2.0
# 如果效果不好 → 回退到 v1.0
```

---

## 4. 时间计划

### 4.1 总体时间表

```
Week 1: 数据准备 + 回测 (训练集)
Week 2: 回测 (验证集) + 分析
Week 3: 模拟观测
Week 4: 1% 资金实盘
Week 5: 5% 资金实盘
Week 6: 10% 资金实盘
Week 7: 20% 资金实盘
Week 8: 50% 资金实盘 → 决策
```

### 4.2 里程碑

| 阶段 | 完成标志 | 决策 |
|------|---------|------|
| Phase 1 | 所有检验通过 | 继续 / 停止 |
| Phase 2 | 模拟观测2周 | 继续 / 停止 |
| Phase 3 | 小资金实盘2周 | 继续 / 停止 |
| Phase 4 | 逐步加仓 | 上线 / 回退 |

---

## 5. 检验清单

### 5.1 完整检验标准

```markdown
## v2.0 优化检验清单

### Phase 1: 回测验证 (Week 1-2)

#### 基础指标
- [ ] 年化收益率: v2.0 ≥ v1.0 (15%)
- [ ] 最大回撤: v2.0 ≤ v1.0 (15%)
- [ ] 夏普比率: v2.0 ≥ v1.0 (1.0)
- [ ] 胜率: v2.0 �� v1.0 (50%)

#### 统计检验
- [ ] t检验: p_value < 0.05
- [ ] 差异显著

#### 稳定性检验
- [ ] 按年份统计: 标准差 < 5%
- [ ] 每年都保持正收益

#### 换手率检验
- [ ] 年化换手率: ≤ 5倍
- [ ] 交易成本 < 3%

#### 相关性检验
- [ ] 交易重合度 < 80%
- [ ] 确保优化是真实的

#### 极端行情检验
- [ ] 股灾期间回撤 < 20%
- [ ] 横盘期间表现正常

#### 资金容量检验
- [ ] 当前资金 < 策略容量
- [ ] 流动性充足

### Phase 2: 模拟观测 (Week 3)

#### 收益对比
- [ ] 2周累计收益: v2.0 ≥ v1.0
- [ ] 最大回撤: v2.0 ≤ v1.0

#### 稳定性
- [ ] 每日收益波动合理
- [ ] 没有异常大亏

### Phase 3: 小资金实盘 (Week 4-5)

#### 收益对比
- [ ] 1%资金实盘: 收益 ≥ 0
- [ ] 5%资金实盘: 收益 ≥ 0
- [ ] 对比模拟盘: 差异 < 2%

#### 执行检查
- [ ] 所有交易都能执行
- [ ] 没有流动性问题
- [ ] 没有停牌问题

### Phase 4: 逐步加仓 (Week 6-8)

#### 累计收益
- [ ] 累计收益 > 0
- [ ] 累计收益 > v1.0

#### 最终决策
- [ ] 所有检验通过 → 上线 v2.0
- [ ] 部分检验未通过 → 保持 v1.0
- [ ] 多数检验未通过 → 回退到 v1.0
```

---

## 6. 应急方案

### 6.1 回退方案

```markdown
## 何时回退

### 立即回退 (出现以下情况)
- ❌ 单日亏损 > 3%
- ❌ 单周亏损 > 5%
- ❌ 累计亏损 > 10%
- ❌ 出现异常交易 (错误买入/卖出)

### 观察后回退
- ⚠️ 连续3天跑输 v1.0
- ⚠️ 换手率 > 10倍/年
- ⚠️ 出现无法执行的交易

## 回退步骤

1. 暂停 v2.0 策略
   ```sql
   UPDATE daily_observer_strategies
   SET status = 'paused'
   WHERE id = 52;
   ```

2. 清空 v2.0 持仓 (如果有实盘)
   - 卖出所有 v2.0 持仓
   - 回收资金

3. 分析失败原因
   - 检查日志
   - 分析回测差异
   - 找出问题

4. 决策
   - 修复问题 → 重新验证
   - 无法修复 → 继续使用 v1.0
```

### 6.2 风险控制

```python
# 风险控制参数
RISK_CONTROL = {
    # 单日亏损限制
    "max_daily_loss": -0.03,  # 单日亏损最多3%

    # 单周亏损限制
    "max_weekly_loss": -0.05,  # 单周亏损最多5%

    # 累计亏损限制
    "max_total_loss": -0.10,  # 累计亏损最多10%

    # 异常交易检测
    "max_single_loss": -0.08,  # 单笔亏损最多8%
    "max_position": 0.10,      # 单只股票最多10%
}

# 实时监控
def check_risk():
    """实时风险检查"""
    # 每日检查
    # 如果超过限制 → 立即暂停
    pass
```

---

## 7. 数据隔离

### 7.1 观测数据隔离

```python
# v1.0 和 v2.0 的数据完全隔离

# v1.0 数据
SELECT * FROM daily_observer_records WHERE strategy_id = 51;
SELECT * FROM daily_observer_trades WHERE strategy_id = 51;

# v2.0 数据
SELECT * FROM daily_observer_records WHERE strategy_id = 52;
SELECT * FROM daily_observer_trades WHERE strategy_id = 52;

# 对比分析
SELECT
    v1.date,
    v1.total_value as v1_value,
    v2.total_value as v2_value,
    (v2.total_value - v1.total_value) / v1.total_value as diff
FROM daily_observer_records v1
JOIN daily_observer_records v2 ON v1.date = v2.date
WHERE v1.strategy_id = 51 AND v2.strategy_id = 52;
```

### 7.2 持仓隔离

```
v1.0 持仓 (策略ID: 51)
├── 股票A: 100股
├── 股票B: 200股
└── 股票C: 150股

v2.0 持仓 (策略ID: 52)
├── 股票D: 100股
├── 股票E: 200股
└── 股票F: 150股

完全独立，互不影响
```

---

## 8. 实施步骤

### 8.1 准备阶段 (Day 1-2)

```bash
# 1. 创建 v2.0 策略
cd backend
python scripts/create_v2_strategy.py

# 2. 验证策略创建成功
python scripts/verify_v2_strategy.py

# 3. 准备回测数据
python scripts/prepare_backtest_data.py
```

### 8.2 回测阶段 (Day 3-7)

```bash
# 1. 运行 v1.0 回测
python scripts/run_backtest.py --engine v1.0 --period train

# 2. 运行 v2.0 回测
python scripts/run_backtest.py --engine v2.0 --period train

# 3. 对比分析
python scripts/analyze_comparison.py

# 4. 验证集回测
python scripts/run_backtest.py --engine v2.0 --period val

# 5. 统计检验
python scripts/test_significance.py
```

### 8.3 决策阶段 (Day 8)

```bash
# 生成决策报告
python scripts/generate_decision_report.py

# 如果通过 → 继续模拟观测
# 如果不通过 → 停止实验
```

---

## 9. 成功标准

### 9.1 量化标准

| 指标 | v1.0 | v2.0 目标 | 最低要求 |
|------|------|-----------|---------|
| 年化收益 | 15% | ≥ 18% | ≥ 15% |
| 最大回撤 | 15% | ≤ 12% | ≤ 15% |
| 夏普比率 | 1.0 | ≥ 1.2 | ≥ 1.0 |
| 胜率 | 50% | ≥ 55% | ≥ 50% |
| 换手率 | 4倍 | ≤ 5倍 | ≤ 6倍 |

### 9.2 质量标准

```markdown
## 必须满足 (全部满足才能上线)

### 回测验证
- [ ] 所有检验清单项目都通过
- [ ] 统计显著性 p < 0.05
- [ ] 稳定性检验通过

### 模拟观测
- [ ] 2周累计收益 > 0
- [ ] 没有异常亏损

### 小资金实盘
- [ ] 1%和5%资金都盈利
- [ ] 实盘和模拟盘差异 < 2%

### 风险控制
- [ ] 没有触发任何回退条件
- [ ] 最大回撤 < 10%
```

---

## 10. 总结

### 10.1 核心原则

1. ✅ **不影响现有观测**：v1.0 继续运行
2. ✅ **独立验证**：v2.0 独立创建、独立运行
3. ✅ **小步快跑**：每步都验证，随时可回退
4. ✅ **数据驱动**：用数据说话，不凭感觉

### 10.2 关键点

| 阶段 | 关键检验 | 失败则 |
|------|---------|--------|
| 回测 | 所有指标达标 | 停止实验 |
| 模拟 | 2周收益 > 0 | 停止实验 |
| 实盘 | 累计收益 > 0 | 回退到 v1.0 |

### 10.3 预期效果

```
如果实验成功：
- 年化收益: 15% → 18%
- 最大回撤: 15% → 12%
- 夏普比率: 1.0 → 1.2

如果实验失败：
- 立即停止，保持 v1.0
- 风险可控，损失最小
```

---

## 附录

### A. 脚本清单

```bash
backend/scripts/
├── create_v2_strategy.py          # 创建 v2.0 策略
├── verify_v2_strategy.py           # 验证策略创建
├── prepare_backtest_data.py        # 准备回测数据
├── run_backtest_comparison.py      # 运行对比回测
├── analyze_comparison.py           # 分析对比结果
├── test_significance.py            # 统计显著性检验
├── generate_decision_report.py     # 生成决策报告
└── start_v2_observer.py            # 启动 v2.0 观测
```

### B. 时间线

```
Week 1-2: 回测验证
Week 3:   模拟观测
Week 4-5: 小资金实盘
Week 6-8: 逐步加仓

总计: 8周 (2个月)
```

---

**文档状态:** ✅ 完整
**下一步:** 执行 Phase 1 - 回测验证

**关键提醒:**
- ⚠️ 不影响现有观测 (策略ID: 51)
- ✅ 新建独立策略 (策略ID: 52)
- 📊 所有决策基于数据
- 🔄 任何阶段都可以回退
