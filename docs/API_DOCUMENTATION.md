# StockQuant Pro - 后端 API 文档

**版本：** v2.1 MVP
**更新时间：** 2026-03-09
**Base URL：** `http://localhost:5001/api`

---

## 📋 目录

1. [认证相关](#1-认证相关)
2. [订阅相关](#2-订阅相关)
3. [策略回测](#3-策略回测)
4. [因子分析](#4-因子分析)
5. [每日筛选](#5-每日筛选)
6. [数据管理](#6-数据管理)
7. [错误码说明](#7-错误码说明)

---

## 1. 认证相关

### 1.1 用户注册

**接口地址：** `POST /auth/register`

**请求参数：**

```json
{
  "username": "string",     // 用户名（必填，3-20字符）
  "email": "string",        // 邮箱（必填，唯一）
  "password": "string",     // 密码（必填，6-20字符）
  "phone": "string"         // 手机号（可选）
}
```

**响应示例：**

```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "user_id": 1,
    "username": "test_user",
    "email": "test@example.com",
    "plan": "free",
    "created_at": "2026-03-09T10:00:00Z"
  }
}
```

---

### 1.2 用户登录

**接口地址：** `POST /auth/login`

**请求参数：**

```json
{
  "username": "string",     // 用户名或邮箱
  "password": "string"      // 密码
}
```

**响应示例：**

```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": 1,
      "username": "test_user",
      "email": "test@example.com",
      "plan": "free",
      "expires_at": null
    }
  }
}
```

---

### 1.3 获取当前用户信息

**接口地址：** `GET /auth/me`

**请求头：**

```
Authorization: Bearer {token}
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "username": "test_user",
    "email": "test@example.com",
    "plan": "free",              // free | professional
    "subscription": {
      "plan": "free",
      "status": "active",        // active | expired | cancelled
      "started_at": "2026-03-01T00:00:00Z",
      "expires_at": null,
      "auto_renew": false
    },
    "usage": {
      "backtest_count": 2,       // 当月回测次数
      "backtest_limit": 3        // 回测次数限制
    }
  }
}
```

---

## 2. 订阅相关

### 2.1 获取套餐列表

**接口地址：** `GET /subscription/plans`

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "plans": [
      {
        "id": "free",
        "name": "免费版",
        "price": 0,
        "duration": null,
        "features": [
          "每月3次回测",
          "最多1年回测周期",
          "10个基础因子",
          "基础统计报告"
        ],
        "limits": {
          "backtest_per_month": 3,
          "backtest_max_years": 1,
          "factors_count": 10,
          "can_export": false,
          "can_observer": false
        }
      },
      {
        "id": "professional",
        "name": "专业版",
        "price": 99,
        "duration": "365",
        "features": [
          "无限次回测",
          "无限回测周期",
          "52个全部因子",
          "详细分析报告",
          "导出PDF/Excel",
          "每日筛选结果"
        ],
        "limits": {
          "backtest_per_month": -1,     // -1表示无限制
          "backtest_max_years": -1,
          "factors_count": 52,
          "can_export": true,
          "can_observer": true
        }
      }
    ]
  }
}
```

---

### 2.2 创建订阅订单

**接口地址：** `POST /subscription/create-order`

**请求头：**

```
Authorization: Bearer {token}
```

**请求参数：**

```json
{
  "plan_id": "professional"    // 套餐ID
}
```

**响应示例：**

```json
{
  "code": 0,
  "message": "订单创建成功",
  "data": {
    "order_id": "ORD_20260309001",
    "plan_id": "professional",
    "amount": 99,
    "currency": "CNY",
    "payment_url": "https://pay.example.com/...",
    "expires_at": "2026-03-09T11:00:00Z"
  }
}
```

---

### 2.3 查询订阅使用情况

**接口地址：** `GET /subscription/usage`

**请求头：**

```
Authorization: Bearer {token}
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "plan": "free",
    "backtest": {
      "used": 2,
      "limit": 3,
      "remaining": 1,
      "reset_at": "2026-04-01T00:00:00Z"
    },
    "features": {
      "can_backtest": true,
      "can_export": false,
      "can_observer": false,
      "can_download": false
    }
  }
}
```

---

## 3. 策略回测

### 3.1 创建回测任务

**接口地址：** `POST /backtest/tasks`

**请求头：**

```
Authorization: Bearer {token}
```

**请求参数：**

```json
{
  "name": "动量策略回测",
  "strategy_config": {
    "engine": "daily_observer",           // 引擎类型
    "factors": ["momentum_5d", "rs_5d"],  // 因子列表
    "factor_combo_id": 1,                 // 因子组合ID（可选）
    "params": {                           // 策略参数
      "lookback_days": 5,
      "top_n": 10,
      "stop_loss": 0.08,
      "take_profit": 0.15
    }
  },
  "backtest_config": {
    "start_date": "2024-01-01",
    "end_date": "2025-01-01",            // 免费版最多1年
    "initial_capital": 100000,
    "commission": 0.0003,
    "slippage": 0.0
  },
  "stock_pool": {
    "type": "key",                       // key | all | custom
    "stocks": []                         // 自定义股票池（可选）
  }
}
```

**权限检查：**
- 免费版：检查当月回测次数是否超过3次
- 专业版：无限制

**响应示例：**

```json
{
  "code": 0,
  "message": "回测任务创建成功",
  "data": {
    "task_id": 123,
    "status": "running",                 // running | completed | failed
    "progress": 0,
    "created_at": "2026-03-09T10:00:00Z"
  }
}
```

---

### 3.2 获取回测任务列表

**接口地址：** `GET /backtest/tasks`

**请求头：**

```
Authorization: Bearer {token}
```

**查询参数：**

```
?page=1                  // 页码（默认1）
?page_size=20            // 每页数量（默认20）
&status=                 // 状态筛选（可选）
&sort_by=created_at      // 排序字段
&order=desc              // 排序方向
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 15,
    "page": 1,
    "page_size": 20,
    "tasks": [
      {
        "id": 123,
        "name": "动量策略回测",
        "status": "completed",
        "start_date": "2024-01-01",
        "end_date": "2025-01-01",
        "summary": {
          "total_return": 0.156,
          "annual_return": 0.145,
          "max_drawdown": -0.082,
          "sharpe_ratio": 1.23,
          "win_rate": 0.65
        },
        "created_at": "2026-03-09T10:00:00Z",
        "updated_at": "2026-03-09T10:05:00Z"
      }
    ]
  }
}
```

---

### 3.3 获取回测详情

**接口地址：** `GET /backtest/tasks/{task_id}`

**请求头：**

```
Authorization: Bearer {token}
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task": {
      "id": 123,
      "name": "动量策略回测",
      "status": "completed",
      "strategy_config": { /* ... */ },
      "backtest_config": { /* ... */ },
      "created_at": "2026-03-09T10:00:00Z"
    },
    "summary": {
      "total_return": 0.156,              // 总收益率
      "annual_return": 0.145,             // 年化收益
      "max_drawdown": -0.082,             // 最大回撤
      "sharpe_ratio": 1.23,               // 夏普比率
      "win_rate": 0.65,                   // 胜率
      "profit_loss_ratio": 2.1,           // 盈亏比
      "total_trades": 45,                 // 总交易次数
      "profitable_trades": 29,            // 盈利交易次数
      "average_hold_days": 12.5           // 平均持仓天数
    },
    "equity_curve": [
      {"date": "2024-01-01", "value": 100000},
      {"date": "2024-01-02", "value": 100150},
      // ...
    ],
    "trades": [
      {
        "date": "2024-01-05",
        "symbol": "601985",
        "name": "中国核电",
        "action": "buy",                  // buy | sell
        "price": 12.50,
        "shares": 800,
        "amount": 10000,
        "return": 0.08                    // 收益率
      },
      // ...
    ],
    "positions": [
      {
        "date": "2024-01-10",
        "symbol": "601985",
        "name": "中国核电",
        "shares": 800,
        "cost_price": 12.50,
        "current_price": 13.10,
        "market_value": 10480,
        "profit_loss": 480,
        "return": 0.048
      },
      // ...
    ]
  }
}
```

---

### 3.4 导出回测报告（专业版）

**接口地址：** `GET /backtest/tasks/{task_id}/export`

**请求头：**

```
Authorization: Bearer {token}
```

**查询参数：**

```
format=pdf             // pdf | excel
```

**权限检查：**
- 免费版：返回错误提示
- 专业版：返回文件

**响应示例（PDF）：**

```
Content-Type: application/pdf
Content-Disposition: attachment; filename="backtest_report_123.pdf"

[二进制文件内容]
```

**响应示例（Excel）：**

```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="backtest_report_123.xlsx"

[二进制文件内容]
```

---

## 4. 因子分析

### 4.1 获取因子列表

**接口地址：** `GET /factor/list`

**请求头：**

```
Authorization: Bearer {token}
```

**查询参数：**

```
?category=              // 因子分类（可选）
&has_data=true          // 是否有数据
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "factors": [
      {
        "id": 1,
        "name": "momentum_5d",
        "display_name": "5日动量",
        "category": "量价",              // 量价 | 基本面 | 反转 | 技术 | 其他
        "description": "过去5日的涨跌幅",
        "formula": "(close - close_5d) / close_5d",
        "ic": 0.045,                     // IC值（因子预测能力）
        "ir": 0.82,                      // IR值（IC稳定性）
        "rank_ic": 5,                    // IC排名
        "data_available": true,
        "latest_date": "2026-03-08"
      },
      {
        "id": 2,
        "name": "rs_5d",
        "display_name": "5日反转",
        "category": "反转",
        "description": "过去5日收益率取反",
        "formula": "-(close - close_5d) / close_5d",
        "ic": 0.038,
        "ir": 0.75,
        "rank_ic": 8,
        "data_available": true,
        "latest_date": "2026-03-08"
      }
      // ... 共52个因子（专业版）或10个因子（免费版）
    ]
  }
}
```

---

### 4.2 获取因子详情

**接口地址：** `GET /factor/{factor_id}`

**请求头：**

```
Authorization: Bearer {token}
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "factor": {
      "id": 1,
      "name": "momentum_5d",
      "display_name": "5日动量",
      "category": "量价",
      "description": "过去5日的涨跌幅",
      "formula": "(close - close_5d) / close_5d",
      "ic": 0.045,
      "ir": 0.82,
      "rank_ic": 5
    },
    "analysis": {
      "ic_series": [                      // IC时间序列
        {"date": "2024-01", "value": 0.042},
        {"date": "2024-02", "value": 0.048},
        // ...
      ],
      "ic_distribution": {
        "mean": 0.045,
        "std": 0.055,
        "min": -0.082,
        "max": 0.123,
        "skewness": -0.32,
        "kurtosis": 2.85
      },
      "group_returns": [                   // 分组收益
        {"group": 1, "return": -0.025},    // 最低组
        {"group": 2, "return": -0.008},
        {"group": 3, "return": 0.005},
        {"group": 4, "return": 0.018},
        {"group": 5, "return": 0.035}      // 最高组
      ],
      "correlation": {                     // 因子相关性
        "rs_5d": -0.75,                    // 与5日反转负相关
        "volatility_20d": 0.52,
        "turnover_20d": 0.48
      }
    }
  }
}
```

---

### 4.3 获取因子组合列表

**接口地址：** `GET /factor/combo`

**请求头：**

```
Authorization: Bearer {token}
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "combos": [
      {
        "id": 1,
        "name": "动量组合",
        "description": "多因子动量策略",
        "factors": [
          {"name": "momentum_5d", "weight": 0.4},
          {"name": "momentum_20d", "weight": 0.3},
          {"name": "rs_5d", "weight": 0.3}
        ],
        "backtest_count": 12,
        "created_at": "2026-02-01T10:00:00Z"
      }
    ]
  }
}
```

---

## 5. 每日筛选

### 5.1 获取每日筛选结果（改造后合规版）

**接口地址：** `GET /daily-observer/strategies/{strategy_id}/recommendations`

**请求头：**

```
Authorization: Bearer {token}
```

**查询参数：**

```
?date=20260309          // 筛选日期（可选，默认最新）
```

**权限检查：**
- 免费版：返回错误提示
- 专业版：返回筛选结果

**响应示例（改造后）：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "20260309",
    "strategy_name": "动量策略",
    "disclaimer": "⚠️ 重要声明\n\n本系统提供的所有数据和分析结果，仅供研究学习使用，不构成任何投资建议。\n\n1. 历史表现不代表未来收益\n2. 因子筛选结果基于历史数据计算\n3. 投资有风险，决策需谨慎\n4. 用户应根据自身情况独立判断",
    "filter_results": [
      {
        "ts_code": "601985",
        "name": "中国核电",
        "score": 8.5,
        "rank": 1,
        "factors": [
          {
            "name": "动量",
            "value": "9.2",
            "signal": "强势",
            "description": "过去5日涨幅较大"
          },
          {
            "name": "RSI",
            "value": "66",
            "signal": "中性偏强",
            "description": "处于合理区间"
          }
        ],
        "summary": "因子得分较高，符合筛选条件"
      },
      {
        "ts_code": "600519",
        "name": "贵州茅台",
        "score": 8.2,
        "rank": 2,
        "factors": [
          {
            "name": "动量",
            "value": "8.5",
            "signal": "强势"
          },
          {
            "name": "换手率",
            "value": "0.8%",
            "signal": "正常"
          }
        ],
        "summary": "因子得分较高，符合筛选条件"
      }
      // ... 更多筛选结果
    ],
    "statistics": {
      "total_pool": 50,
      "qualified": 10,
      "avg_score": 7.8
    },
    "generated_at": "2026-03-09T09:30:00Z"
  }
}
```

**改造要点：**
- ❌ 不输出：价格、数量、金额、买入建议
- ✅ 只输出：代码、名称、得分、排名、因子分析
- ✅ 必须加：免责声明

---

### 5.2 获取筛选策略列表

**接口地址：** `GET /daily-observer/strategies`

**请求头：**

```
Authorization: Bearer {token}
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "strategies": [
      {
        "id": 51,
        "name": "动量策略",
        "description": "基于动量因子的选股策略",
        "status": "active",               // active | paused | stopped
        "engine": "daily_observer",
        "last_run_date": "2026-03-09",
        "created_at": "2026-02-01T10:00:00Z"
      }
    ]
  }
}
```

---

## 6. 数据管理

### 6.1 获取股票列表

**接口地址：** `GET /data/stocks`

**请求头：**

```
Authorization: Bearer {token}
```

**查询参数：**

```
?stock_type=key         // 股票类型：key | all
&has_factor_data=true   // 是否有因子数据
&page=1
&page_size=100
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 50,
    "page": 1,
    "page_size": 100,
    "stocks": [
      {
        "ts_code": "601985",
        "name": "中国核电",
        "industry": "电力",
        "market": "主板",
        "has_factor_data": true,
        "latest_date": "2026-03-08"
      }
      // ... 更多股票
    ]
  }
}
```

---

### 6.2 获取K线数据

**接口地址：** `GET /data/bars`

**请求头：**

```
Authorization: Bearer {token}
```

**查询参数：**

```
?ts_code=601985
&start_date=2024-01-01
&end_date=2026-03-09
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "ts_code": "601985",
    "name": "中国核电",
    "bars": [
      {
        "date": "2024-01-01",
        "open": 12.30,
        "high": 12.50,
        "low": 12.20,
        "close": 12.45,
        "volume": 125000,
        "amount": 1550000
      }
      // ... 更多K线数据
    ]
  }
}
```

---

## 7. 错误码说明

### 7.1 错误响应格式

```json
{
  "code": 1001,
  "message": "错误描述",
  "data": null
}
```

### 7.2 常见错误码

| 错误码 | 说明 | HTTP状态码 |
|-------|------|-----------|
| 0 | 成功 | 200 |
| 1001 | 参数错误 | 400 |
| 1002 | 缺少必填参数 | 400 |
| 1003 | 参数格式错误 | 400 |
| 2001 | 未登录 | 401 |
| 2002 | Token过期 | 401 |
| 2003 | Token无效 | 401 |
| 3001 | 权限不足 | 403 |
| 3002 | 功能仅限专业版 | 403 |
| 3003 | 回测次数已用完 | 403 |
| 4001 | 资源不存在 | 404 |
| 4002 | 回测任务不存在 | 404 |
| 4003 | 策略不存在 | 404 |
| 5001 | 服务器内部错误 | 500 |
| 5002 | 数据库错误 | 500 |
| 5003 | 回测执行失败 | 500 |

### 7.3 错误示例

**示例1：未登录**

```json
{
  "code": 2001,
  "message": "请先登录",
  "data": null
}
```

**示例2：回测次数已用完**

```json
{
  "code": 3003,
  "message": "您的免费回测次数已用完，请升级专业版享受无限回测",
  "data": {
    "upgrade_url": "https://stockquant.pro/upgrade",
    "current_plan": "free",
    "limit": 3,
    "used": 3
  }
}
```

**示例3：功能仅限专业版**

```json
{
  "code": 3002,
  "message": "此功能仅限专业版用户使用",
  "data": {
    "feature": "daily_observer",
    "upgrade_url": "https://stockquant.pro/upgrade"
  }
}
```

---

## 8. 开发注意事项

### 8.1 权限控制

所有需要检查用户套餐的接口都必须使用装饰器：

```python
from utils.subscription_limits import check_subscription_limit, check_feature_access

# 示例：创建回测任务
@app.route('/api/backtest/tasks', methods=['POST'])
@check_subscription_limit('backtest')
def create_backtest_task():
    # 业务逻辑
    pass

# 示例：每日筛选
@app.route('/api/daily-observer/strategies/<int:strategy_id>/recommendations')
@check_feature_access('observer')
def get_recommendations(strategy_id):
    # 业务逻辑（包含合规改造）
    pass
```

### 8.2 合规改造

所有涉及筛选结果的接口都必须：

1. **使用简化函数**
```python
from services.daily_observer_service import _simplify_signals

def get_recommendations(strategy_id):
    # 原始信号
    raw_signals = get_raw_signals(strategy_id)

    # 简化信号（去除价格、数量、买入建议）
    simplified = _simplify_signals(raw_signals)

    # 添加免责声明
    simplified['disclaimer'] = get_disclaimer_template()

    return simplified
```

2. **添加免责声明**
```python
DISCLAIMER_TEMPLATE = """
⚠️ 重要声明

本系统提供的所有数据和分析结果，仅供研究学习使用，不构成任何投资建议。

1. 历史表现不代表未来收益
2. 因子筛选结果基于历史数据计算
3. 投资有风险，决策需谨慎
4. 用户应根据自身情况独立判断

使用本系统即表示您已阅读并同意以上声明。
"""
```

### 8.3 文案规范

| 原文案 | 改造后 |
|-------|--------|
| 买入信号 | 筛选结果 |
| 卖出信号 | 不再符合条件 |
| 建议买入 | 符合筛选条件 |
| 推荐买入 | 因子得分较高 |
| 预期收益 | 历史表现 |

---

## 9. 测试用例

### 9.1 认证测试

```bash
# 注册
curl -X POST http://localhost:5001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"123456"}'

# 登录
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"123456"}'

# 获取用户信息
curl -X GET http://localhost:5001/api/auth/me \
  -H "Authorization: Bearer {token}"
```

### 9.2 回测测试

```bash
# 创建回测任务（免费用户）
curl -X POST http://localhost:5001/api/backtest/tasks \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试回测",
    "strategy_config": {
      "engine": "daily_observer",
      "factors": ["momentum_5d"]
    },
    "backtest_config": {
      "start_date": "2024-01-01",
      "end_date": "2024-06-01",
      "initial_capital": 100000
    }
  }'

# 获取回测列表
curl -X GET http://localhost:5001/api/backtest/tasks \
  -H "Authorization: Bearer {token}"

# 获取回测详情
curl -X GET http://localhost:5001/api/backtest/tasks/123 \
  -H "Authorization: Bearer {token}"
```

### 9.3 权限测试

```bash
# 免费用户尝试访问每日筛选（应该返回错误）
curl -X GET http://localhost:5001/api/daily-observer/strategies/51/recommendations \
  -H "Authorization: Bearer {free_user_token}"

# 预期响应：
# {
#   "code": 3002,
#   "message": "此功能仅限专业版用户使用"
# }

# 免费用户尝试第4次回测（应该返回错误）
curl -X POST http://localhost:5001/api/backtest/tasks \
  -H "Authorization: Bearer {free_user_token}" \
  -H "Content-Type: application/json" \
  -d '{...}'

# 预期响应：
# {
#   "code": 3003,
#   "message": "您的免费回测次数已用完，请升级专业版"
# }
```

---

**文档更新时间：** 2026-03-09
**技术支持：** 知夏
