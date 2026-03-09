# StockQuant Pro - 技术文档

欢迎使用 StockQuant Pro 技术文档！本文档集包含项目的完整技术说明和开发指南。

---

## 📚 文档目录

### 1. [产品文档](../PRODUCT_MVP.md)
**面向：** 产品经理、运营人员、开发者

**内容：**
- 产品定位和核心价值
- 目标用户画像
- 功能矩阵和定价策略
- ��规改造方案
- 上线计划和推广策略

**快速链接：**
- [核心功能](../PRODUCT_MVP.md#3-核心功能)
- [定价策略](../PRODUCT_MVP.md#4-定价策略)
- [合规改造](../PRODUCT_MVP.md#5-合规改造方案)

---

### 2. [后端API文档](./API_DOCUMENTATION.md)
**面向：** 后端开发者、前端开发者、测试人员

**内容：**
- 完整的API接口说明
- 请求/响应示例
- 错误码说明
- 权限控制逻辑
- 合规改造规范

**快速链接：**
- [认证相关](./API_DOCUMENTATION.md#1-认证相关)
- [策略回测](./API_DOCUMENTATION.md#3-策略回测)
- [每日筛选](./API_DOCUMENTATION.md#5-每日筛选)
- [错误码说明](./API_DOCUMENTATION.md#7-错误码说明)

**API Base URL：** `http://localhost:5001/api`

---

### 3. [前端组件文档](./FRONTEND_DOCUMENTATION.md)
**面向：** 前端开发者、UI设计师

**内容：**
- 技术架构和项目结构
- 核心组件说明
- 页面模块详解
- 状态管理
- 路由配置
- 权限控制
- 合规改造

**快速链接：**
- [技术架构](./FRONTEND_DOCUMENTATION.md#1-技术架构)
- [核心组件](./FRONTEND_DOCUMENTATION.md#3-核心组件)
- [页面模块](./FRONTEND_DOCUMENTATION.md#4-页面模块)
- [合规改造](./FRONTEND_DOCUMENTATION.md#9-合规改造)

**技术栈：** Vue 3 + TypeScript + Element Plus

---

### 4. [开发指南](./DEVELOPMENT_GUIDE.md)
**面向：** 全栈开发者、运维人员

**内容：**
- 快速开始
- 开发环境配置
- 数据库设计
- 核心业务逻辑
- 合规开发规范
- 常见问题
- 部署指南

**快速链接：**
- [快速开始](./DEVELOPMENT_GUIDE.md#1-快速开始)
- [数据库设计](./DEVELOPMENT_GUIDE.md#3-数据库设计)
- [核心业务逻辑](./DEVELOPMENT_GUIDE.md#4-核心业务逻辑)
- [常见问题](./DEVELOPMENT_GUIDE.md#6-常见问题)

---

## 🚀 快速开始

### 安装和启动

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/vnpy.git
cd vnpy

# 2. 启动后端
cd backend
source venv_backend/bin/activate
pip install -r requirements.txt
python init_db.py
python app.py

# 3. 启动前端（新终端）
cd frontend
npm install
npm run dev
```

**访问地址：**
- 前端：http://localhost:3000
- 后端：http://localhost:5001

详细说明请参考 [开发指南 - 快速开始](./DEVELOPMENT_GUIDE.md#1-快速开始)

---

## 📖 核心概念

### 产品定位

**StockQuant Pro** 是面向个人投资者的量化回测工具，核心特点：

- ✅ **简单易用**：无需编程，界面操作
- ✅ **价格亲民**：99元/年，比竞品便宜60倍
- ✅ **垂直A股**：专注A股市场
- ✅ **合规改造**：不构成投资建议

### 套餐体系

| 套餐 | 价格 | 回测次数 | 因子数量 | 每日筛选 | 导出报告 |
|-----|------|---------|---------|---------|---------|
| 免费版 | ¥0 | 3次/月 | 10个 | ❌ | ❌ |
| 专业版 | ¥99/年 | 无限 | 52个 | ✅ | ✅ |

### 技术架构

```
┌─────────────────────────────────────┐
│       前端 (Vue 3 + TypeScript)      │
│  - Element Plus UI                   │
│  - ECharts 图表                      │
│  - Pinia 状态管理                    │
└──────────────┬──────────────────────┘
               │ HTTP API
┌──────────────┴──────────────────────┐
│       后端 (Flask + Python)          │
│  - JWT 认证                          │
│  - SQLAlchemy ORM                    │
│  - 回测引擎                          │
└──────────────┬──────────────────────┘
               │
┌──────────────┴──────────────────────┐
│       数据库 (MySQL 8.0)             │
│  - 用户数据                          │
│  - 策略数据                          │
│  - 因子数据                          │
│  - K线数据                           │
└─────────────────────────────────────┘
```

---

## 🔐 合规要点

### 文案改造

| 原文案 | 改造后 |
|-------|--------|
| 买入信号 | 筛选结果 |
| 建议买入 | 符合筛选条件 |
| 预期收益 | 历史表现 |

### 数据脱敏

**不输出字段：**
- ❌ 价格（price）
- ❌ 金额（amount）
- ❌ 数量（volume）
- ❌ 买入建议

**必须包含：**
- ✅ 免责声明
- ✅ 风险提示

详细规范请参考：
- [后端API - 合规改造](./API_DOCUMENTATION.md#8-开发注意事项)
- [前端组件 - 合规改造](./FRONTEND_DOCUMENTATION.md#9-合规改造)
- [开发指南 - 合规开发规范](./DEVELOPMENT_GUIDE.md#5-合规开发规范)

---

## 📊 核心接口

### 认证相关

```bash
# 登录
POST /api/auth/login
Body: {"username": "test", "password": "123456"}

# 获取用户信息
GET /api/auth/me
Header: Authorization: Bearer {token}
```

### 回测相关

```bash
# 创建回测
POST /api/backtest/tasks
Header: Authorization: Bearer {token}

# 获取回测列表
GET /api/backtest/tasks?page=1&page_size=20

# 获取回测详情
GET /api/backtest/tasks/{task_id}
```

### 筛选相关（专业版）

```bash
# 获取每日筛选结果
GET /api/daily-observer/strategies/{strategy_id}/recommendations
Header: Authorization: Bearer {token}
```

更多接口请参考 [后端API文档](./API_DOCUMENTATION.md)

---

## 🛠️ 开发工具

### 推荐IDE

- **后端：** PyCharm / VSCode
- **前端：** VSCode / WebStorm

### 必备插件

**VSCode：**
```json
{
  "recommendations": [
    "vue.volar",
    "ms-python.python",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode"
  ]
}
```

### API测试

- **Postman：** 导入API文档中的示例
- **curl：** 命令行测试
- **浏览器：** 直接访问前端页面

---

## 🔍 故障排查

### 常见问题

1. **数据库连接失败**
   - 检查MySQL服务是否启动
   - 检查 `.env` 配置
   - 解决方案：[常见问题 #6.1](./DEVELOPMENT_GUIDE.md#61-数据库连接失败)

2. **API请求失败**
   - 检查后端服务是否启动
   - 检查CORS配置
   - 解决方案：[常见问题 #6.2](./DEVELOPMENT_GUIDE.md#62-前端api请求失败)

3. **回测任务卡住**
   - 检查任务日志
   - 重试任务
   - 解决方案：[常见问题 #6.4](./DEVELOPMENT_GUIDE.md#64-回测任务卡住)

更多问题请参考 [开发指南 - 常见问题](./DEVELOPMENT_GUIDE.md#6-常见问题)

---

## 📝 更新日志

### v2.1 MVP (2026-03-09)

**新增：**
- ✅ 完整的SaaS订阅系统
- ✅ 套餐权限控制
- ✅ 每日筛选功能（改造后合规版）
- ✅ 技术文档体系

**改进：**
- 🔒 合规改造（文案和数据）
- 🔒 权限控制优化
- 🔒 错误提示优化

---

## 👥 联系方式

**产品负责人：** 王志豪
**技术支持：** 知夏
**更新时间：** 2026-03-09

---

## 📄 许可证

MIT License

---

## 🙏 致谢

感谢所有为 StockQuant Pro 项目做出贡献的开发者和用户！

---

**下一步：**

- 📖 阅读产品文档：[PRODUCT_MVP.md](../PRODUCT_MVP.md)
- 🔧 开始开发：[开发指南](./DEVELOPMENT_GUIDE.md)
- 🔌 查看API：[API文档](./API_DOCUMENTATION.md)
- 🎨 前端开发：[前端文档](./FRONTEND_DOCUMENTATION.md)
