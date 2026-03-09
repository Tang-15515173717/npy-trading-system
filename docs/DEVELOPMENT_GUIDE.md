# StockQuant Pro - 开发指南

**版本：** v2.1 MVP
**更新时间：** 2026-03-09

---

## 📋 目录

1. [快速开始](#1-快速开始)
2. [开发环境配置](#2-开发环境配置)
3. [数据库设计](#3-数据库设计)
4. [核心业务逻辑](#4-核心业务逻辑)
5. [合规开发规范](#5-合规开发规范)
6. [常见问题](#6-常见问题)

---

## 1. 快速开始

### 1.1 项目克隆

```bash
git clone https://github.com/your-repo/vnpy.git
cd vnpy
```

### 1.2 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（如果还没有）
python3 -m venv venv_backend

# 激活虚拟环境
source venv_backend/bin/activate  # Linux/Mac
# 或
venv_backend\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python init_db.py

# 启动后端服务
python app.py
```

后端将运行在 `http://localhost:5001`

### 1.3 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将运行在 `http://localhost:3000`

---

## 2. 开发环境配置

### 2.1 环境变量

**后端环境变量（`backend/.env`）：**

```bash
# Flask配置
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-change-in-production

# 数据库配置
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/stockquant

# TuShare配置
TUSHARE_TOKEN=your-tushare-token

# Redis配置（可选）
REDIS_URL=redis://localhost:6379/0
```

**前端环境变量（`frontend/.env.development`）：**

```bash
# API地址
VITE_API_BASE_URL=http://localhost:5001/api

# 应用配置
VITE_APP_TITLE=StockQuant Pro
```

**前端环境变量（`frontend/.env.production`）：**

```bash
# API地址（生产环境）
VITE_API_BASE_URL=https://api.stockquant.pro/api

# 应用配置
VITE_APP_TITLE=StockQuant Pro
```

### 2.2 数据库初始化

```bash
# 进入backend目录
cd backend

# 运行初始化脚本
python init_db.py

# 这将创建所有表并插入初始数据
```

**手动创建数据库（如果需要）：**

```sql
CREATE DATABASE stockquant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2.3 开发工具推荐

- **IDE：** VSCode / PyCharm
- **API测试：** Postman / Insomnia
- **数据库管理：** Navicat / DBeaver
- **Git工具：** SourceTree / GitKraken

**VSCode插件推荐：**

```json
{
  "recommendations": [
    "vue.volar",
    "vue.vscode-typescript-vue-plugin",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "ms-python.python",
    "ms-python.vscode-pylance"
  ]
}
```

---

## 3. 数据库设计

### 3.1 核心表结构

#### 3.1.1 用户表（users）

```sql
CREATE TABLE users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(100) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  phone VARCHAR(20),
  plan VARCHAR(20) DEFAULT 'free',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_email (email),
  INDEX idx_plan (plan)
);
```

#### 3.1.2 订阅表（subscriptions）

```sql
CREATE TABLE subscriptions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  plan VARCHAR(20) NOT NULL,
  status VARCHAR(20) DEFAULT 'active',
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP NULL,
  auto_renew BOOLEAN DEFAULT FALSE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_user_id (user_id),
  INDEX idx_status (status)
);
```

#### 3.1.3 策略表（strategies）

```sql
CREATE TABLE strategies (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  description TEXT,
  engine VARCHAR(50) NOT NULL,
  config JSON NOT NULL,
  status VARCHAR(20) DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_user_id (user_id),
  INDEX idx_status (status)
);
```

#### 3.1.4 回测任务表（backtest_tasks）

```sql
CREATE TABLE backtest_tasks (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  strategy_id INT,
  name VARCHAR(100) NOT NULL,
  status VARCHAR(20) DEFAULT 'pending',
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  initial_capital DECIMAL(15,2) DEFAULT 100000,
  config JSON NOT NULL,
  result JSON,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE SET NULL,
  INDEX idx_user_id (user_id),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at)
);
```

#### 3.1.5 回测交易记录表（backtest_trades）

```sql
CREATE TABLE backtest_trades (
  id INT PRIMARY KEY AUTO_INCREMENT,
  task_id INT NOT NULL,
  trade_date DATE NOT NULL,
  symbol VARCHAR(20) NOT NULL,
  name VARCHAR(50),
  action ENUM('buy', 'sell') NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  shares INT NOT NULL,
  amount DECIMAL(15,2) NOT NULL,
  profit_loss DECIMAL(15,2),
  return_rate DECIMAL(10,4),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (task_id) REFERENCES backtest_tasks(id) ON DELETE CASCADE,
  INDEX idx_task_id (task_id),
  INDEX idx_trade_date (trade_date),
  INDEX idx_symbol (symbol)
);
```

#### 3.1.6 因子数据表（factor_data）

```sql
CREATE TABLE factor_data (
  id INT PRIMARY KEY AUTO_INCREMENT,
  trade_date DATE NOT NULL,
  symbol VARCHAR(20) NOT NULL,
  factor_name VARCHAR(50) NOT NULL,
  factor_value DECIMAL(15,6) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_date_symbol_factor (trade_date, symbol, factor_name),
  INDEX idx_trade_date (trade_date),
  INDEX idx_symbol (symbol),
  INDEX idx_factor_name (factor_name)
);
```

#### 3.1.7 K线数据表（bar_data）

```sql
CREATE TABLE bar_data (
  id INT PRIMARY KEY AUTO_INCREMENT,
  symbol VARCHAR(20) NOT NULL,
  trade_date DATE NOT NULL,
  open DECIMAL(10,2) NOT NULL,
  high DECIMAL(10,2) NOT NULL,
  low DECIMAL(10,2) NOT NULL,
  close DECIMAL(10,2) NOT NULL,
  volume BIGINT NOT NULL,
  amount DECIMAL(20,2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_symbol_date (symbol, trade_date),
  INDEX idx_trade_date (trade_date),
  INDEX idx_symbol (symbol)
);
```

### 3.2 数据库模型（SQLAlchemy）

**文件位置：** `backend/models/user.py`

```python
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    plan = db.Column(db.String(20), default='free')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(),
                          onupdate=db.func.current_timestamp())

    # 关系
    subscriptions = db.relationship('Subscription', back_populates='user',
                                    cascade='all, delete-orphan')
    strategies = db.relationship('Strategy', back_populates='user',
                                cascade='all, delete-orphan')
    backtest_tasks = db.relationship('BacktestTask', back_populates='user',
                                    cascade='all, delete-orphan')

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
```

---

## 4. 核心业务逻辑

### 4.1 用户认证流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as 前端
    participant B as 后端
    participant D as 数据库

    U->>F: 输入用户名密码
    F->>B: POST /api/auth/login
    B->>D: 查询用户
    D-->>B: 返回用户信息
    B->>B: 验证密码
    B->>B: 生成JWT Token
    B-->>F: 返回Token和用户信息
    F->>F: 存储Token到localStorage
    F-->>U: 跳转到首页
```

**实现代码：**

```python
# backend/api/auth_api.py
from flask import request, g
from models.user import User
from utils.jwt import generate_token

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # 查询用户
    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()

    if not user or not user.check_password(password):
        return error(message='用户名或密码错误')

    # 生成Token
    token = generate_token(user.id)

    # 返回用户信息
    return success(data={
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'plan': user.plan
        }
    })
```

### 4.2 回测流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as 前端
    participant B as 后端
    participant E as 回测引擎
    participant D as 数据库

    U->>F: 创建回测任务
    F->>B: POST /api/backtest/tasks
    B->>B: 验证套餐权限
    B->>B: 创建任务记录
    B-->>F: 返回任务ID
    F->>U: 显示任务列表

    B->>E: 异步执行回测
    E->>D: 读取K线数据
    E->>D: 读取因子数据
    E->>E: 执行回测逻辑
    E->>D: 保存交易记录
    E->>D: 更新任务状态
    E-->>B: 回测完成
```

**实现代码：**

```python
# backend/api/backtest_api.py
from flask import request
from models.backtest_task import BacktestTask
from services.backtest_service import BacktestService
from utils.subscription_limits import check_subscription_limit

@backtest_bp.route('/tasks', methods=['POST'])
@login_required
@check_subscription_limit('backtest')
def create_backtest_task():
    """创建回测任务"""
    data = request.get_json()

    # 创建任务
    task = BacktestTask(
        user_id=g.current_user.id,
        name=data['name'],
        start_date=data['backtest_config']['start_date'],
        end_date=data['backtest_config']['end_date'],
        config=data
    )
    db.session.add(task)
    db.session.commit()

    # 异步执行回测
    from utils.task_manager import task_manager
    task_manager.add_task(
        func=run_backtest,
        args=(task.id,)
    )

    return success(data={
        'task_id': task.id,
        'status': 'running'
    })

def run_backtest(task_id):
    """执行回测"""
    task = BacktestTask.query.get(task_id)

    try:
        # 执行回测
        service = BacktestService(task)
        result = service.run()

        # 保存结果
        task.result = result
        task.status = 'completed'
        db.session.commit()

    except Exception as e:
        task.status = 'failed'
        task.error_message = str(e)
        db.session.commit()
```

### 4.3 权限控制流程

```mermaid
graph TD
    A[用户请求] --> B{是否登录?}
    B -->|否| C[返回401]
    B -->|是| D{检查权限}

    D --> E{用户套餐}
    E --> F[免费版]
    E --> G[专业版]

    F --> H{检查次数限制}
    H -->|未超限| I[允许访问]
    H -->|超限| J[返回403 + 升级提示]

    G --> I

    I --> K[执行业务逻辑]
    J --> L[显示升级页面]
```

**实现代码：**

```python
# backend/utils/subscription_limits.py
from functools import wraps
from flask import g, jsonify
from models.user import User
from models.backtest_task import BacktestTask

def check_subscription_limit(feature):
    """检查订阅限制"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = g.current_user
            plan = user.plan or 'free'

            # 专业版无限制
            if plan == 'professional':
                return f(*args, **kwargs)

            # 免费版检查
            if feature == 'backtest':
                # 检查当月回测次数
                from datetime import datetime, timedelta
                this_month = datetime.now().replace(day=1)
                count = BacktestTask.query.filter(
                    BacktestTask.user_id == user.id,
                    BacktestTask.created_at >= this_month
                ).count()

                if count >= 3:
                    return jsonify({
                        'code': 3003,
                        'message': '您的免费回测次数已用完，请升级专业版',
                        'data': {
                            'upgrade_url': '/subscription',
                            'current_plan': 'free',
                            'limit': 3,
                            'used': count
                        }
                    }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_feature_access(feature):
    """检查功能权限"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = g.current_user
            plan = user.plan or 'free'

            # 检查功能权限
            if feature == 'observer' and plan == 'free':
                return jsonify({
                    'code': 3002,
                    'message': '此功能仅限专业版用户使用',
                    'data': {
                        'feature': feature,
                        'upgrade_url': '/subscription'
                    }
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

### 4.4 每日筛选流程（改造后）

```mermaid
graph TD
    A[用户请求筛选结果] --> B{检查权限}
    B -->|免费版| C[返回403]
    B -->|专业版| D[执行筛选逻辑]

    D --> E[读取策略配置]
    E --> F[读取因子数据]
    F --> G[计算股票得分]
    G --> H[生成筛选结果]

    H --> I[合规改造]
    I --> J[去除敏感字段]
    J --> K[修改文案]
    K --> L[添加免责声明]

    L --> M[返回结果]
```

**实现代码：**

```python
# backend/services/daily_observer_service.py
def _simplify_signals(signals):
    """
    简化信号（合规改造）
    去除价格、数量、买入建议
    """
    simplified = []

    for signal in signals:
        # 只保留必要字段
        item = {
            'ts_code': signal['ts_code'],
            'name': signal['name'],
            'score': signal['score'],
            'rank': signal['rank'],
            'factors': [],
            'summary': '因子得分较高，符合筛选条件'
        }

        # 添加因子分析（不包含价格）
        for factor in signal['factors']:
            item['factors'].append({
                'name': factor['name'],
                'value': factor['value'],
                'signal': factor['signal'],
                'description': factor.get('description', '')
            })

        # ❌ 不包含：price, amount, volume, buy_price
        # ❌ 不包含：建议买入、推荐买入

        simplified.append(item)

    return simplified

def get_recommendations(strategy_id, date=None):
    """获取筛选结果（改造后）"""
    # 检查权限
    user = g.current_user
    if user.plan != 'professional':
        return error(message='此功能仅限专业版用户使用')

    # 执行筛选
    strategy = Strategy.query.get(strategy_id)
    signals = run_filter_strategy(strategy, date)

    # 合规改造
    simplified_signals = _simplify_signals(signals)

    # 添加免责声明
    disclaimer = """
    ⚠️ 重要声明

    本系统提供的所有数据和分析结果，仅供研究学习使用，不构成任何投资建议。

    1. 历史表现不代表未来收益
    2. 因子筛选结果基于历史数据计算
    3. 投资有风险，决策需谨慎
    4. 用户应根据自身情况独立判断
    """

    return success(data={
        'date': date or get_latest_date(),
        'strategy_name': strategy.name,
        'disclaimer': disclaimer,
        'filter_results': simplified_signals,
        'statistics': {
            'total_pool': len(signals) + 100,
            'qualified': len(simplified_signals),
            'avg_score': sum(s['score'] for s in simplified_signals) / len(simplified_signals)
        },
        'generated_at': datetime.now().isoformat()
    })
```

---

## 5. 合规开发规范

### 5.1 文案规范

所有面向用户的文案必须符合以下规范：

| 原文案 | 改造后 | 场景 |
|-------|--------|------|
| 买入信号 | 筛选结果 | 每日筛选 |
| 卖出信号 | 不再符合条件 | 每日筛选 |
| 建议买入 | 符合筛选条件 | 每日筛选 |
| 推荐买入 | 因子得分较高 | 每日筛选 |
| 预期收益 | 历史表现 | 回测报告 |
| 目标价格 | 参考点位 | 筛选结果 |
| 止损价格 | 风险参考 | 筛选结果 |

### 5.2 数据字段规范

**敏感字段（不输出）：**

```python
SENSITIVE_FIELDS = [
    'price',           # 价格
    'amount',          # 金额
    'volume',          # 数量
    'buy_price',       # 买入价
    'sell_price',      # 卖出价
    'target_price',    # 目标价
    'stop_loss',       # 止损价
    'position',        # 仓位
    'shares',          # 股数
]
```

**允许字段（可输出）：**

```python
ALLOWED_FIELDS = [
    'ts_code',         # 股票代码
    'name',            # 股票名称
    'score',           # 得分
    'rank',            # 排名
    'factors',         # 因子分析
    'summary',         # 摘要
]
```

### 5.3 免责声明规范

所有涉及筛选结果的页面必须包含免责声明：

```vue
<!-- 页面顶部 -->
<el-alert type="warning" :closable="false">
  <template #title>
    ⚠️ 重要声明
  </template>
  <div>
    本系统提供的所有数据和分析结果，仅供研究学习使用，不构成任何投资建议。
    <br>1. 历史表现不代表未来收益
    <br>2. 因子筛选结果基于历史数据计算
    <br>3. 投资有风险，决策需谨慎
    <br>4. 用户应根据自身情况独立判断
  </div>
</el-alert>

<!-- 页面底部 -->
<el-text type="info" size="small">
  使用本系统即表示您已阅读并同意以上声明
</el-text>
```

### 5.4 代码检查清单

在提交代码前，请检查以下项：

**后端检查清单：**

- [ ] 接口不返回敏感字段（price、amount、volume）
- [ ] 文案不出现"推荐"、"建议买入"
- [ ] 筛选结果接口包含免责声明
- [ ] 权限检查正确实现
- [ ] 错误提示友好且符合规范

**前端检查清单：**

- [ ] 不显示价格、数量、金额字段
- [ ] 使用改造后的文案
- [ ] 所有筛选页面都有免责声明
- [ ] 权限控制正确实现
- [ ] 升级提示清晰明确

---

## 6. 常见问题

### 6.1 数据库连接失败

**问题：** `sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError)`

**解决方案：**

1. 检查MySQL服务是否启动
```bash
# Linux/Mac
sudo systemctl start mysql
# 或
sudo service mysql start

# Windows
net start mysql
```

2. 检查数据库配置（`.env`文件）
```bash
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/stockquant
```

3. 创建数据库
```sql
CREATE DATABASE stockquant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 6.2 前端API请求失败

**问题：** `Network Error` 或 `CORS Error`

**解决方案：**

1. 检查后端服务是否启动
```bash
# 访问健康检查接口
curl http://localhost:5001/health
```

2. 检查前端API配置（`frontend/.env.development`）
```bash
VITE_API_BASE_URL=http://localhost:5001/api
```

3. 确保后端CORS配置正确
```python
# backend/app.py
CORS(app, origins=["*"])
```

### 6.3 Token过期

**问题：** `401 Unauthorized`

**解决方案：**

```typescript
// 前端：request拦截器
request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 清除Token
      userStore.logout();
      // 跳转到登录页
      router.push('/login');
    }
    return Promise.reject(error);
  }
);
```

### 6.4 回测任务卡住

**问题：** 回测任务一直是 `running` 状态

**解决方案：**

1. 检查任务管理器
```bash
# 查看任务日志
tail -f /tmp/claude-*/tasks/*.output
```

2. 手动重试任务
```python
# backend/utils/task_manager.py
task_manager.retry_task(task_id)
```

3. 检查数据完整性
```bash
# 检查K线数据
python backend/check_data_count.py
```

### 6.5 因子数据缺失

**问题：** 因子分析页面显示无数据

**解决方案：**

1. 下载因子数据
```bash
python backend/download_all_stocks.py
python backend/calculate_all_factors.py
```

2. 检查数据日期
```bash
python backend/check_data_dates.py
```

3. 补充缺失数据
```bash
python backend/calculate_missing_factors.py
```

### 6.6 性能优化

**问题：** 回测速度慢

**解决方案：**

1. 使用数据库索引
```sql
-- 添加索引
CREATE INDEX idx_trade_date ON factor_data(trade_date);
CREATE INDEX idx_symbol ON factor_data(symbol);
```

2. 使用缓存
```python
from flask_caching import Cache

cache = Cache()

@cache.memoize(timeout=300)
def get_factor_data(symbol, date):
    # 查询逻辑
    pass
```

3. 异步处理
```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

def run_backtest_async(task_id):
    executor.submit(run_backtest, task_id)
```

---

## 7. 部署指南

### 7.1 生产环境配置

**后端配置（`production.env`）：**

```bash
# Flask配置
FLASK_ENV=production
SECRET_KEY=your-production-secret-key

# 数据库配置
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/stockquant

# 其他配置
LOG_LEVEL=INFO
DEBUG=False
```

**前端配置（`frontend/.env.production`）：**

```bash
VITE_API_BASE_URL=https://api.stockquant.pro/api
```

### 7.2 部署步骤

**1. 后端部署**

```bash
# 使用Gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 app:create_app()

# 或使用uWSGI
uwsgi --http 0.0.0.0:5001 --wsgi-file app.py --callable app --processes 4
```

**2. 前端部署**

```bash
# 构建前端
cd frontend
npm run build

# 使用Nginx托管
# 将dist目录内容复制到Nginx静态目录
```

**3. Nginx配置**

```nginx
server {
    listen 80;
    server_name stockquant.pro;

    # 前端
    location / {
        root /var/www/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端API
    location /api {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 8. 测试

### 8.1 单元测试

**后端测试（pytest）：**

```python
# tests/test_auth.py
def test_login(client):
    response = client.post('/api/auth/login', json={
        'username': 'test',
        'password': '123456'
    })
    assert response.status_code == 200
    assert 'token' in response.json['data']
```

**前端测试（vitest）：**

```typescript
// tests/components/BacktestList.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import BacktestList from '@/components/backtest/BacktestList.vue';

describe('BacktestList', () => {
  it('renders tasks', () => {
    const wrapper = mount(BacktestList, {
      props: {
        tasks: [
          { id: 1, name: '测试回测', status: 'completed' }
        ]
      }
    });
    expect(wrapper.text()).toContain('测试回测');
  });
});
```

### 8.2 API测试

```bash
# 使用curl测试
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"123456"}'

# 使用Postman测试
# 导入API文档中的示例请求
```

---

## 9. 贡献指南

### 9.1 代码规范

**Python代码规范：**

```bash
# 使用ruff检查
ruff check backend/

# 使用black格式化
black backend/

# 使用mypy类型检查
mypy backend/
```

**TypeScript代码规范：**

```bash
# ESLint检查
npm run lint

# Prettier格式化
npm run format

# 类型检查
npm run type-check
```

### 9.2 提交规范

```bash
# 提交格式
git commit -m "feat: 添加每日筛选功能"
git commit -m "fix: 修复回测任务卡住问题"
git commit -m "docs: 更新API文档"
git commit -m "style: 格式化代码"
git commit -m "refactor: 重构权限控制逻辑"
git commit -m "test: 添加单元测试"
git commit -m "chore: 更新依赖"
```

---

**文档更新时间：** 2026-03-09
**技术支持：** 知夏
