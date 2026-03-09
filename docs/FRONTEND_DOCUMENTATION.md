# StockQuant Pro - 前端组件文档

**版本：** v2.1 MVP
**更新时间：** 2026-03-09
**技术栈：** Vue 3 + TypeScript + Element Plus

---

## 📋 目录

1. [技术架构](#1-技术架构)
2. [目录结构](#2-目录结构)
3. [核心组件](#3-核心组件)
4. [页面模块](#4-页面模块)
5. [状态管理](#5-状态管理)
6. [路由配置](#6-路由配置)
7. [API调用](#7-api调用)
8. [权限控制](#8-权限控制)
9. [合规改造](#9-合规改造)

---

## 1. 技术架构

### 1.1 技术栈

| 类别 | 技术 | 版本 | 说明 |
|-----|------|------|------|
| **框架** | Vue | 3.4+ | 渐进式框架 |
| **语言** | TypeScript | 5.3+ | 类型安全 |
| **构建工具** | Vite | 5.0+ | 快速构建 |
| **UI组件** | Element Plus | 2.5+ | 组件库 |
| **状态管理** | Pinia | 2.1+ | 状态管理 |
| **路由** | Vue Router | 4.2+ | 路由管理 |
| **图表** | ECharts | 5.6+ | 数据可视化 |
| **HTTP** | Axios | 1.6+ | API请求 |
| **日期** | Day.js | 1.11+ | 日期处理 |

### 1.2 项目结构

```
frontend/
├── public/                 # 静态资源
├── src/
│   ├── api/               # API接口
│   │   ├── index.ts       # API配置
│   │   ├── auth.ts        # 认证API
│   │   ├── backtest.ts    # 回测API
│   │   ├── factor.ts      # 因子API
│   │   └── observer.ts    # 筛选API
│   ├── assets/            # 资源文件
│   │   ├── styles/        # 样式
│   │   └── images/        # 图片
│   ├── components/        # 公共组件
│   │   ├── common/        # 通用组件
│   │   ├── charts/        # 图表组件
│   │   └── backtest/      # 回测组件
│   ├── composables/       # 组合式函数
│   │   ├── useAuth.ts     # 认证
│   │   ├── useBacktest.ts # 回测
│   │   └── useObserver.ts # 筛选
│   ├── router/            # 路由
│   │   └── index.ts
│   ├── stores/            # 状态管理
│   │   ├── user.ts        # 用户状态
│   │   ├── subscription.ts # 订阅状态
│   │   └── backtest.ts    # 回测状态
│   ├── types/             # 类型定义
│   │   ├── api.ts         # API类型
│   │   ├── user.ts        # 用户类型
│   │   └── backtest.ts    # 回测类型
│   ├── utils/             # 工具函数
│   │   ├── request.ts     # 请求封装
│   │   ├── format.ts      # 格式化
│   │   └── permission.ts  # 权限控制
│   ├── views/             # 页面
│   │   ├── auth/          # 认证
│   │   ├── backtest/      # 回测
│   │   ├── factor/        # 因子
│   │   ├── observer/      # 筛选（付费）
│   │   └── subscription/  # 订阅
│   ├── App.vue            # 根组件
│   └── main.ts            # 入口
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## 2. 目录结构详解

### 2.1 核心目录

**src/api/** - API接口层
- 封装所有后端API调用
- 统一错误处理
- 请求/响应拦截

**src/components/** - 组件层
- 可复用的UI组件
- 按功能模块分类

**src/views/** - 页面层
- 完整的页面组件
- 对应路由

**src/stores/** - 状态管理
- Pinia stores
- 全局状态

**src/composables/** - 组合式函数
- 可复用的逻辑
- 按功能分类

---

## 3. 核心组件

### 3.1 通用组件

#### 3.1.1 PageHeader

**文件位置：** `src/components/common/PageHeader.vue`

**功能：** 页面头部组件

**Props：**

```typescript
interface Props {
  title: string;           // 页面标题
  subtitle?: string;       // 副标题
  showBack?: boolean;      // 是否显示返回按钮
}
```

**示例：**

```vue
<PageHeader
  title="策略回测"
  subtitle="创建和管理您的回测任务"
/>
```

---

#### 3.1.2 LoadingSpinner

**文件位置：** `src/components/common/LoadingSpinner.vue`

**功能：** 加载动画

**Props：**

```typescript
interface Props {
  text?: string;           // 加载文字
  size?: 'small' | 'medium' | 'large';
}
```

---

#### 3.1.3 EmptyState

**文件位置：** `src/components/common/EmptyState.vue`

**功能：** 空状态提示

**Props：**

```typescript
interface Props {
  type?: 'no-data' | 'no-result' | 'error' | 'no-permission';
  title?: string;
  description?: string;
  actionText?: string;
  showAction?: boolean;
}
```

**示例：**

```vue
<!-- 无数据 -->
<EmptyState type="no-data" />

<!-- 无权限 -->
<EmptyState
  type="no-permission"
  title="此功能仅限专业版用户"
  description="升级到专业版即可使用每日筛选功能"
  actionText="立即升级"
  :showAction="true"
  @action="handleUpgrade"
/>
```

---

#### 3.1.4 PermissionGuard

**文件位置：** `src/components/common/PermissionGuard.vue`

**功能：** 权限守卫组件

**Props：**

```typescript
interface Props {
  feature: 'backtest' | 'export' | 'observer' | 'download';
  plan?: 'free' | 'professional';
  hideContent?: boolean;    // 是否隐藏内容（默认显示升级提示）
}
```

**示例：**

```vue
<template>
  <PermissionGuard feature="observer">
    <!-- 只有专业版用户能看到 -->
    <DailyObserver />
  </PermissionGuard>
</template>
```

---

### 3.2 图表组件

#### 3.2.1 EquityCurveChart

**文件位置：** `src/components/charts/EquityCurveChart.vue`

**功能：** 资金曲线图

**Props：**

```typescript
interface Props {
  data: Array<{
    date: string;
    value: number;
  }>;
  height?: string;
}
```

---

#### 3.2.2 BacktestStatsCard

**文件位置：** `src/components/charts/BacktestStatsCard.vue`

**功能：** 回测统计卡片

**Props：**

```typescript
interface Props {
  stats: {
    total_return: number;
    annual_return: number;
    max_drawdown: number;
    sharpe_ratio: number;
    win_rate: number;
    profit_loss_ratio: number;
  };
}
```

---

#### 3.2.3 FactorDistributionChart

**文件位置：** `src/components/charts/FactorDistributionChart.vue`

**功能：** 因子分布图

**Props：**

```typescript
interface Props {
  data: Array<{
    group: number;
    return: number;
  }>;
  factorName: string;
}
```

---

### 3.3 回测组件

#### 3.3.1 BacktestForm

**文件位置：** `src/components/backtest/BacktestForm.vue`

**功能：** 回测表单

**Props：**

```typescript
interface Props {
  loading?: boolean;
}
```

**Events：**

```typescript
const emit = defineEmits<{
  submit: [config: BacktestConfig];
}>();
```

**示例：**

```vue
<BacktestForm
  :loading="isSubmitting"
  @submit="handleSubmit"
/>
```

---

#### 3.3.2 BacktestList

**文件位置：** `src/components/backtest/BacktestList.vue`

**功能：** 回测任务列表

**Props：**

```typescript
interface Props {
  tasks: BacktestTask[];
  loading?: boolean;
}
```

**Events：**

```typescript
const emit = defineEmits<{
  view: [taskId: number];
  delete: [taskId: number];
}>();
```

---

#### 3.3.3 BacktestReport

**文件位置：** `src/components/backtest/BacktestReport.vue`

**功能：** 回测报告

**Props：**

```typescript
interface Props {
  taskId: number;
  showExport?: boolean;    // 是否显示导出按钮
}
```

---

### 3.4 筛选组件（改造后）

#### 3.4.1 DailyObserver

**文件位置：** `src/components/observer/DailyObserver.vue`

**功能：** 每日筛选结果（改造后合规版）

**Props：**

```typescript
interface Props {
  strategyId: number;
  date?: string;
}
```

**数据格式（改造后）：**

```typescript
interface FilterResult {
  ts_code: string;         // 股票代码
  name: string;            // 股票名称
  score: number;           // 得分
  rank: number;            // 排名
  factors: Array<{
    name: string;          // 因子名称
    value: string;         // 因子值
    signal: string;        // 信号描述
    description?: string;  // 详细说明
  }>;
  summary: string;         // 摘要
}
```

**关键改造点：**

```vue
<template>
  <div class="daily-observer">
    <!-- 顶部免责声明 -->
    <el-alert
      type="warning"
      :closable="false"
      show-icon
    >
      <template #title>
        ⚠️ 重要声明
      </template>
      <div class="disclaimer-text">
        本系统提供的所有数据和分析结果，仅供研究学习使用，不构成任何投资建议。
        <br>1. 历史表现不代表未来收益
        <br>2. 因子筛选结果基于历史数据计算
        <br>3. 投资有风险，决策需谨慎
        <br>4. 用户应根据自身情况独立判断
      </div>
    </el-alert>

    <!-- 筛选结果列表 -->
    <el-table :data="filterResults">
      <el-table-column prop="ts_code" label="代码" width="100" />
      <el-table-column prop="name" label="名称" width="120" />
      <el-table-column prop="score" label="得分" width="80" />
      <el-table-column prop="rank" label="排名" width="80" />

      <!-- 因子分析 -->
      <el-table-column label="因子分析">
        <template #default="{ row }">
          <el-tag
            v-for="factor in row.factors"
            :key="factor.name"
            :type="getSignalType(factor.signal)"
            size="small"
          >
            {{ factor.name }}: {{ factor.value }} ({{ factor.signal }})
          </el-tag>
        </template>
      </el-table-column>

      <!-- 摘要（改造后） -->
      <el-table-column prop="summary" label="摘要" />

      <!-- ❌ 不显示：价格、数量、金额 -->
    </el-table>

    <!-- 底部免责声明 -->
    <div class="disclaimer-footer">
      使用本系统即表示您已阅读并同意以上声明
    </div>
  </div>
</template>
```

---

#### 3.4.2 FactorTag

**文件位置：** `src/components/observer/FactorTag.vue`

**功能：** 因子标签（改造后）

**Props：**

```typescript
interface Props {
  factor: {
    name: string;
    value: string;
    signal: string;
  };
}
```

**示例：**

```vue
<FactorTag
  :factor="{
    name: '动量',
    value: '9.2',
    signal: '强势'
  }"
/>
```

---

## 4. 页面模块

### 4.1 认证模块

#### 4.1.1 登录页

**文件位置：** `src/views/auth/Login.vue`

**路由：** `/login`

**功能：**
- 用户登录
- 表单验证
- 错误处理

**核心代码：**

```vue
<script setup lang="ts">
import { useAuthStore } from '@/stores/user';
import type { LoginForm } from '@/types/user';

const authStore = useAuthStore();
const router = useRouter();

const form = reactive<LoginForm>({
  username: '',
  password: ''
});

const loading = ref(false);

const handleLogin = async () => {
  loading.value = true;
  try {
    await authStore.login(form);
    router.push('/');
  } catch (error) {
    // 错误处理
  } finally {
    loading.value = false;
  }
};
</script>
```

---

#### 4.1.2 注册页

**文件位置：** `src/views/auth/Register.vue`

**路由：** `/register`

**功能：**
- 用户注册
- 表单验证
- 密码强度检查

---

### 4.2 回测模块

#### 4.2.1 回测列表页

**文件位置：** `src/views/backtest/BacktestList.vue`

**路由：** `/backtest`

**功能：**
- 显示回测任务列表
- 分页、筛选、排序
- 快速查看摘要
- 删除任务

**权限检查：**

```vue
<template>
  <div class="backtest-list">
    <PageHeader title="策略回测" />

    <!-- 套餐提示 -->
    <UsageCard
      :used="usage.backtest_count"
      :limit="usage.backtest_limit"
      feature="backtest"
    />

    <!-- 操作按钮 -->
    <el-button
      type="primary"
      :disabled="!canCreateBacktest"
      @click="handleCreate"
    >
      创建回测
    </el-button>

    <!-- 任务列表 -->
    <BacktestList
      :tasks="tasks"
      :loading="loading"
      @view="handleView"
      @delete="handleDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { useSubscriptionStore } from '@/stores/subscription';

const subscriptionStore = useSubscriptionStore();
const { usage, canCreateBacktest } = storeToRefs(subscriptionStore);
</script>
```

---

#### 4.2.2 创建回测页

**文件位置：** `src/views/backtest/CreateBacktest.vue`

**路由：** `/backtest/create`

**功能：**
- 配置回测参数
- 选择因子组合
- 设置止盈止损
- 提交任务

**权限检查：**

```vue
<script setup lang="ts">
import { useSubscriptionStore } from '@/stores/subscription';

const subscriptionStore = useSubscriptionStore();

// 检查是否可以创建回测
const checkPermission = () => {
  if (!subscriptionStore.canCreateBacktest) {
    ElMessageBox.alert(
      '您的免费回测次数已用完，请升级专业版',
      '提示',
      {
        confirmButtonText: '立即升级',
        callback: () => {
          router.push('/subscription');
        }
      }
    );
    return false;
  }
  return true;
};

const handleSubmit = async (config: BacktestConfig) => {
  if (!checkPermission()) return;

  // 创建回测
  await createBacktest(config);
};
</script>
```

---

#### 4.2.3 回测详情页

**文件位置：** `src/views/backtest/BacktestDetail.vue`

**路由：** `/backtest/:id`

**功能：**
- 显示回测报告
- 资金曲线图
- 交易明细
- 持仓分析
- 导出报告（专业版）

**导出权限检查：**

```vue
<template>
  <div class="backtest-detail">
    <!-- 报告内容 -->
    <BacktestReport :task-id="taskId" />

    <!-- 导出按钮（权限控制） -->
    <PermissionGuard feature="export">
      <el-button @click="handleExport('pdf')">
        导出PDF
      </el-button>
      <el-button @click="handleExport('excel')">
        导出Excel
      </el-button>
    </PermissionGuard>
  </div>
</template>
```

---

### 4.3 因子分析模块

#### 4.3.1 因子列表页

**文件位置：** `src/views/factor/FactorList.vue`

**路由：** `/factors`

**功能：**
- 显示所有因子
- 因子分类筛选
- 查看因子IC/IR
- 免费版只显示10个因子

**因子数量限制：**

```vue
<script setup lang="ts">
import { useSubscriptionStore } from '@/stores/subscription';

const subscriptionStore = useSubscriptionStore();
const { plan, factorLimit } = storeToRefs(subscriptionStore);

// 免费版只显示10个因子
const displayedFactors = computed(() => {
  if (plan.value === 'free') {
    return allFactors.value.slice(0, 10);
  }
  return allFactors.value;
});
</script>
```

---

#### 4.3.2 因子详情页

**文件位置：** `src/views/factor/FactorDetail.vue`

**路由：** `/factors/:id`

**功能：**
- 因子详细信息
- IC时间序列
- 分组收益
- 相关性分析

---

### 4.4 筛选模块（改造后）

#### 4.4.1 筛选中心

**文件位置：** `src/views/observer/ObserverCenter.vue`

**路由：** `/observer`

**权限：** 仅专业版

**功能：**
- 显示每日筛选结果
- 选择策略
- 查看历史筛选
- **改造后合规输出**

**关键改造：**

```vue
<template>
  <PermissionGuard feature="observer">
    <div class="observer-center">
      <!-- 顶部免责声明 -->
      <el-alert type="warning" :closable="false">
        <template #title>
          ⚠️ 重要声明
        </template>
        <div class="disclaimer-text">
          本系统提供的所有数据和分析结果，仅供研究学习使用，不构成任何投资建议。
        </div>
      </el-alert>

      <!-- 策略选择 -->
      <el-select v-model="selectedStrategy">
        <el-option
          v-for="strategy in strategies"
          :key="strategy.id"
          :label="strategy.name"
          :value="strategy.id"
        />
      </el-select>

      <!-- 筛选结果（改造后） -->
      <FilterResults
        :results="filterResults"
        :disclaimer="disclaimer"
      />
    </div>
  </PermissionGuard>
</template>

<script setup lang="ts">
import { getRecommendations } from '@/api/observer';

// 获取筛选结果（已改造）
const filterResults = ref<FilterResult[]>([]);

const loadResults = async () => {
  const data = await getRecommendations(selectedStrategy.value);

  // 后端已改造，不包含价格、数量、买入建议
  filterResults.value = data.filter_results;
};
</script>
```

---

#### 4.4.2 FilterResults组件

**文件位置：** `src/components/observer/FilterResults.vue`

**功能：** 筛选结果展示（改造后）

**关键改造点：**

```vue
<template>
  <el-table :data="results">
    <el-table-column prop="ts_code" label="股票代码" />
    <el-table-column prop="name" label="股票名称" />
    <el-table-column prop="score" label="得分">
      <template #default="{ row }">
        <el-tag :type="getScoreType(row.score)">
          {{ row.score.toFixed(1) }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="rank" label="排名" />

    <!-- 因子分析 -->
    <el-table-column label="因子分析">
      <template #default="{ row }">
        <div class="factors">
          <el-tag
            v-for="factor in row.factors"
            :key="factor.name"
            size="small"
            class="factor-tag"
          >
            {{ factor.name }}: {{ factor.value }}
            <span class="signal">({{ factor.signal }})</span>
          </el-tag>
        </div>
      </template>
    </el-table-column>

    <!-- 摘要 -->
    <el-table-column prop="summary" label="摘要" />

    <!-- ❌ 不显示：价格、数量、金额、建议买入 -->
  </el-table>
</template>

<script setup lang="ts">
interface Factor {
  name: string;
  value: string;
  signal: string;
  description?: string;
}

interface FilterResult {
  ts_code: string;
  name: string;
  score: number;
  rank: number;
  factors: Factor[];
  summary: string;
}

defineProps<{
  results: FilterResult[];
  disclaimer: string;
}>();
</script>
```

---

### 4.5 订阅模块

#### 4.5.1 套餐列表页

**文件位置：** `src/views/subscription/Plans.vue`

**路由：** `/subscription`

**功能：**
- 显示套餐对比
- 价格展示
- 功能对比
- 购买按钮

**示例：**

```vue
<template>
  <div class="plans">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card class="plan-card free">
          <template #header>
            <h2>免费版</h2>
            <div class="price">¥0</div>
          </template>
          <ul class="features">
            <li>✓ 每月3次回测</li>
            <li>✓ 最多1年回测周期</li>
            <li>✓ 10个基础因子</li>
            <li>✗ 每日筛选结果</li>
            <li>✗ 报告导出</li>
          </ul>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="plan-card professional">
          <template #header>
            <h2>专业版</h2>
            <div class="price">¥99/年</div>
          </template>
          <ul class="features">
            <li>✓ 无限次回测</li>
            <li>✓ 无限回测周期</li>
            <li>✓ 52个全部因子</li>
            <li>✓ 每日筛选结果</li>
            <li>✓ 报告导出</li>
          </ul>
          <el-button type="primary" @click="handleUpgrade">
            立即升级
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
```

---

#### 4.5.2 使用情况页

**文件位置：** `src/views/subscription/Usage.vue`

**路由：** `/usage`

**功能：**
- 显示当前套餐
- 使用情况统计
- 剩余次数
- 升级提示

---

## 5. 状态管理

### 5.1 User Store

**文件位置：** `src/stores/user.ts`

**功能：** 用户认证和状态

```typescript
import { defineStore } from 'pinia';
import type { User, LoginForm } from '@/types/user';

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null as User | null,
    token: localStorage.getItem('token') || '',
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    userId: (state) => state.user?.id,
    username: (state) => state.user?.username,
    plan: (state) => state.user?.plan || 'free',
  },

  actions: {
    async login(form: LoginForm) {
      const { data } = await authApi.login(form);
      this.token = data.token;
      this.user = data.user;
      localStorage.setItem('token', data.token);
    },

    async logout() {
      this.token = '';
      this.user = null;
      localStorage.removeItem('token');
    },

    async fetchUserInfo() {
      const { data } = await authApi.me();
      this.user = data;
    },
  },
});
```

---

### 5.2 Subscription Store

**文件位置：** `src/stores/subscription.ts`

**功能：** 订阅和权限

```typescript
import { defineStore } from 'pinia';

export const useSubscriptionStore = defineStore('subscription', {
  state: () => ({
    usage: {
      backtest_count: 0,
      backtest_limit: 3,
    },
    features: {
      can_backtest: true,
      can_export: false,
      can_observer: false,
      can_download: false,
    },
  }),

  getters: {
    plan: () => useUserStore().plan,

    canCreateBacktest: (state) => {
      if (state.plan === 'professional') return true;
      return state.usage.backtest_count < state.usage.backtest_limit;
    },

    canExport: (state) => state.features.can_export,
    canObserver: (state) => state.features.can_observer,
    canDownload: (state) => state.features.can_download,

    backtestRemaining: (state) => {
      if (state.plan === 'professional') return -1; // 无限制
      return Math.max(0, state.usage.backtest_limit - state.usage.backtest_count);
    },
  },

  actions: {
    async fetchUsage() {
      const { data } = await subscriptionApi.getUsage();
      this.usage = data.backtest;
      this.features = data.features;
    },
  },
});
```

---

### 5.3 Backtest Store

**文件位置：** `src/stores/backtest.ts`

**功能：** 回测状态管理

```typescript
import { defineStore } from 'pinia';
import type { BacktestTask, BacktestConfig } from '@/types/backtest';

export const useBacktestStore = defineStore('backtest', {
  state: () => ({
    tasks: [] as BacktestTask[],
    currentTask: null as BacktestTask | null,
    loading: false,
  }),

  actions: {
    async fetchTasks(params: {
      page?: number;
      page_size?: number;
    }) {
      this.loading = true;
      try {
        const { data } = await backtestApi.getTasks(params);
        this.tasks = data.tasks;
      } finally {
        this.loading = false;
      }
    },

    async createTask(config: BacktestConfig) {
      const { data } = await backtestApi.createTask(config);
      this.tasks.unshift(data);
      return data;
    },

    async fetchTaskDetail(taskId: number) {
      const { data } = await backtestApi.getTaskDetail(taskId);
      this.currentTask = data;
      return data;
    },
  },
});
```

---

## 6. 路由配置

### 6.1 路由定义

**文件位置：** `src/router/index.ts`

```typescript
import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '@/stores/user';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/backtest',
    name: 'BacktestList',
    component: () => import('@/views/backtest/BacktestList.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/backtest/create',
    name: 'CreateBacktest',
    component: () => import('@/views/backtest/CreateBacktest.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/backtest/:id',
    name: 'BacktestDetail',
    component: () => import('@/views/backtest/BacktestDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/factors',
    name: 'FactorList',
    component: () => import('@/views/factor/FactorList.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/factors/:id',
    name: 'FactorDetail',
    component: () => import('@/views/factor/FactorDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/observer',
    name: 'ObserverCenter',
    component: () => import('@/views/observer/ObserverCenter.vue'),
    meta: {
      requiresAuth: true,
      requiredPlan: 'professional',  // 仅专业版
    },
  },
  {
    path: '/subscription',
    name: 'Subscription',
    component: () => import('@/views/subscription/Plans.vue'),
    meta: { requiresAuth: false },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 路由守卫
router.beforeEach((to, from, next) => {
  const userStore = useUserStore();

  // 检查是否需要登录
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next('/login');
    return;
  }

  // 检查套餐权限
  if (to.meta.requiredPlan === 'professional' && userStore.plan !== 'professional') {
    next('/subscription?redirect=' + to.fullPath);
    return;
  }

  next();
});

export default router;
```

---

## 7. API调用

### 7.1 请求封装

**文件位置：** `src/utils/request.ts`

```typescript
import axios from 'axios';
import { useUserStore } from '@/stores/user';
import { ElMessage } from 'element-plus';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001/api',
  timeout: 30000,
});

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const userStore = useUserStore();
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const { code, message, data } = response.data;

    // 成功
    if (code === 0) {
      return response.data;
    }

    // 业务错误
    ElMessage.error(message);
    return Promise.reject(new Error(message));
  },
  (error) => {
    // HTTP错误
    if (error.response) {
      const { status, data } = error.response;

      switch (status) {
        case 401:
          ElMessage.error('请先登录');
          useUserStore().logout();
          window.location.href = '/login';
          break;
        case 403:
          ElMessage.error(data.message || '权限不足');
          break;
        case 404:
          ElMessage.error('请求的资源不存在');
          break;
        case 500:
          ElMessage.error('服务器错误，请稍后重试');
          break;
        default:
          ElMessage.error(data.message || '请求失败');
      }
    }

    return Promise.reject(error);
  }
);

export default request;
```

---

### 7.2 API模块

**文件位置：** `src/api/backtest.ts`

```typescript
import request from '@/utils/request';
import type { BacktestConfig, BacktestTask, BacktestDetail } from '@/types/backtest';

export const backtestApi = {
  // 获取回测列表
  getTasks(params: {
    page?: number;
    page_size?: number;
    status?: string;
  }) {
    return request.get<{ tasks: BacktestTask[]; total: number }>('/backtest/tasks', {
      params,
    });
  },

  // 创建回测
  createTask(config: BacktestConfig) {
    return request.post<{ task_id: number }>('/backtest/tasks', config);
  },

  // 获取回测详情
  getTaskDetail(taskId: number) {
    return request.get<BacktestDetail>(`/backtest/tasks/${taskId}`);
  },

  // 导出报告
  exportReport(taskId: number, format: 'pdf' | 'excel') {
    return request.get(`/backtest/tasks/${taskId}/export`, {
      params: { format },
      responseType: 'blob',
    });
  },
};
```

---

## 8. 权限控制

### 8.1 权限指令

**文件位置：** `src/directives/permission.ts`

```typescript
import type { Directive } from 'vue';
import { useSubscriptionStore } from '@/stores/subscription';

export const permission: Directive = {
  mounted(el, binding) {
    const { value } = binding;
    const subscriptionStore = useSubscriptionStore();

    if (value && !subscriptionStore[value]) {
      // 没有权限，移除元素
      el.parentNode?.removeChild(el);
    }
  },
};
```

**使用示例：**

```vue
<template>
  <!-- 只有专业版用户能看到 -->
  <button v-permission="'canObserver'">
    每日筛选
  </button>

  <!-- 只有能导出的用户能看到 -->
  <button v-permission="'canExport'">
    导出报告
  </button>
</template>
```

---

### 8.2 权限组合式函数

**文件位置：** `src/composables/usePermission.ts`

```typescript
import { computed } from 'vue';
import { useSubscriptionStore } from '@/stores/subscription';

export function usePermission() {
  const subscriptionStore = useSubscriptionStore();

  const canCreateBacktest = computed(() => subscriptionStore.canCreateBacktest);
  const canExport = computed(() => subscriptionStore.canExport);
  const canObserver = computed(() => subscriptionStore.canObserver);
  const canDownload = computed(() => subscriptionStore.canDownload);

  return {
    canCreateBacktest,
    canExport,
    canObserver,
    canDownload,
  };
}
```

**使用示例：**

```vue
<script setup lang="ts">
import { usePermission } from '@/composables/usePermission';

const { canExport, canObserver } = usePermission();
</script>

<template>
  <el-button v-if="canExport" @click="handleExport">
    导出报告
  </el-button>

  <el-button v-if="canObserver" @click="handleObserver">
    每日筛选
  </el-button>
</template>
```

---

## 9. 合规改造

### 9.1 文案改造

**文件位置：** `src/utils/textMapping.ts`

```typescript
// 文案映射表（改造后）
export const TEXT_MAPPING = {
  // 原文案 -> 改造后
  '买入信号': '筛选结果',
  '卖出信号': '不再符合条件',
  '建议买入': '符合筛选条件',
  '推荐买入': '因子得分较高',
  '预期收益': '历史表现',
  '目标价格': '参考点位',
  '止损价格': '风险参考',
} as const;

// 转换函数
export function transformText(text: string): string {
  return TEXT_MAPPING[text] || text;
}
```

---

### 9.2 免责声明组件

**文件位置：** `src/components/common/Disclaimer.vue`

```vue
<template>
  <el-alert type="warning" :closable="false" show-icon>
    <template #title>
      ⚠️ 重要声明
    </template>
    <div class="disclaimer-text">
      <p>本系统提供的所有数据和分析结果，仅供研究学习使用，不构成任何投资建议。</p>
      <p>1. 历史表现不代表未来收益</p>
      <p>2. 因子筛选结果基于历史数据计算</p>
      <p>3. 投资有风险，决策需谨慎</p>
      <p>4. 用户应根据自身情况独立判断</p>
    </div>
  </el-alert>
</template>

<style scoped>
.disclaimer-text {
  line-height: 1.8;
  color: #606266;
}

.disclaimer-text p {
  margin: 4px 0;
}
</style>
```

**使用示例：**

```vue
<template>
  <div class="observer-page">
    <!-- 页面顶部 -->
    <Disclaimer />

    <!-- 内容区域 -->
    <FilterResults :results="results" />

    <!-- 页面底部 -->
    <el-text type="info" size="small">
      使用本系统即表示您已阅读并同意以上声明
    </el-text>
  </div>
</template>
```

---

### 9.3 数据过滤（去除敏感字段）

**文件位置：** `src/utils/dataFilter.ts`

```typescript
// 敏感字段列表
const SENSITIVE_FIELDS = [
  'price',
  'amount',
  'volume',
  'buy_price',
  'sell_price',
  'target_price',
  'stop_loss',
  'position',
  'shares',
];

/**
 * 过滤敏感字段
 */
export function filterSensitiveData<T extends Record<string, any>>(data: T): T {
  const filtered = { ...data };

  SENSITIVE_FIELDS.forEach((field) => {
    delete filtered[field];
  });

  return filtered;
}

/**
 * 批量过滤
 */
export function filterSensitiveDataList<T extends Record<string, any>>(
  list: T[]
): T[] {
  return list.map(filterSensitiveData);
}
```

**使用示例：**

```vue
<script setup lang="ts">
import { filterSensitiveDataList } from '@/utils/dataFilter';
import { getRecommendations } from '@/api/observer';

const results = ref([]);

const loadResults = async () => {
  const { data } = await getRecommendations(strategyId);

  // 过滤敏感字段（双重保险）
  results.value = filterSensitiveDataList(data.filter_results);
};
</script>
```

---

## 10. 类型定义

### 10.1 用户类型

**文件位置：** `src/types/user.ts`

```typescript
export interface User {
  id: number;
  username: string;
  email: string;
  plan: 'free' | 'professional';
  created_at: string;
}

export interface LoginForm {
  username: string;
  password: string;
}

export interface RegisterForm {
  username: string;
  email: string;
  password: string;
  phone?: string;
}

export interface Subscription {
  plan: 'free' | 'professional';
  status: 'active' | 'expired' | 'cancelled';
  started_at: string;
  expires_at: string | null;
  auto_renew: boolean;
}
```

---

### 10.2 回测类型

**文件位置：** `src/types/backtest.ts`

```typescript
export interface BacktestConfig {
  name: string;
  strategy_config: {
    engine: string;
    factors: string[];
    factor_combo_id?: number;
    params: Record<string, any>;
  };
  backtest_config: {
    start_date: string;
    end_date: string;
    initial_capital: number;
    commission: number;
    slippage: number;
  };
  stock_pool: {
    type: 'key' | 'all' | 'custom';
    stocks?: string[];
  };
}

export interface BacktestTask {
  id: number;
  name: string;
  status: 'running' | 'completed' | 'failed';
  start_date: string;
  end_date: string;
  summary: {
    total_return: number;
    annual_return: number;
    max_drawdown: number;
    sharpe_ratio: number;
    win_rate: number;
  };
  created_at: string;
  updated_at: string;
}

export interface BacktestDetail {
  task: BacktestTask;
  summary: any;
  equity_curve: Array<{ date: string; value: number }>;
  trades: Array<{
    date: string;
    symbol: string;
    name: string;
    action: 'buy' | 'sell';
    price: number;
    shares: number;
    amount: number;
    return: number;
  }>;
  positions: Array<{
    date: string;
    symbol: string;
    name: string;
    shares: number;
    cost_price: number;
    current_price: number;
    market_value: number;
    profit_loss: number;
    return: number;
  }>;
}
```

---

### 10.3 因子类型

**文件位置：** `src/types/factor.ts`

```typescript
export interface Factor {
  id: number;
  name: string;
  display_name: string;
  category: '量价' | '基本面' | '反转' | '技术' | '其他';
  description: string;
  formula: string;
  ic: number;
  ir: number;
  rank_ic: number;
  data_available: boolean;
  latest_date: string;
}

export interface FactorDetail extends Factor {
  analysis: {
    ic_series: Array<{ date: string; value: number }>;
    ic_distribution: {
      mean: number;
      std: number;
      min: number;
      max: number;
      skewness: number;
      kurtosis: number;
    };
    group_returns: Array<{ group: number; return: number }>;
    correlation: Record<string, number>;
  };
}
```

---

### 10.4 筛选类型（改造后）

**文件位置：** `src/types/observer.ts`

```typescript
export interface FactorSignal {
  name: string;
  value: string;
  signal: string;
  description?: string;
}

export interface FilterResult {
  ts_code: string;
  name: string;
  score: number;
  rank: number;
  factors: FactorSignal[];
  summary: string;
  // ❌ 不包含：price, amount, volume, buy_price, sell_price
}

export interface FilterResults {
  date: string;
  strategy_name: string;
  disclaimer: string;
  filter_results: FilterResult[];
  statistics: {
    total_pool: number;
    qualified: number;
    avg_score: number;
  };
  generated_at: string;
}
```

---

## 11. 开发规范

### 11.1 命名规范

- **组件名：** PascalCase（如：`BacktestList.vue`）
- **文件名：** kebab-case（如：`use-backtest.ts`）
- **变量名：** camelCase（如：`backtestList`）
- **常量名：** UPPER_SNAKE_CASE（如：`API_BASE_URL`）

### 11.2 组件规范

```vue
<script setup lang="ts">
// 1. 导入
import { ref, computed } from 'vue';
import { useBacktestStore } from '@/stores/backtest';

// 2. 类型定义
interface Props {
  taskId: number;
}

// 3. Props和Emits
const props = defineProps<Props>();
const emit = defineEmits<{
  update: [taskId: number];
}>();

// 4. 响应式数据
const loading = ref(false);

// 5. 计算属性
const canEdit = computed(() => props.taskId > 0);

// 6. 方法
const handleSubmit = async () => {
  // ...
};

// 7. 生命周期
onMounted(() => {
  // ...
});
</script>

<template>
  <div class="component-name">
    <!-- 模板 -->
  </div>
</template>

<style scoped>
.component-name {
  /* 样式 */
}
</style>
```

### 11.3 API调用规范

```typescript
// ✅ 好的实践
const loadData = async () => {
  loading.value = true;
  try {
    const { data } = await backtestApi.getTasks({ page: 1 });
    tasks.value = data.tasks;
  } catch (error) {
    ElMessage.error('加载失败');
  } finally {
    loading.value = false;
  }
};

// ❌ 不好的实践
const loadData = async () => {
  const { data } = await axios.get('/api/backtest/tasks');
  tasks.value = data.tasks;
};
```

---

## 12. 测试

### 12.1 单元测试示例

```typescript
import { describe, it, expect } from 'vitest';
import { filterSensitiveData } from '@/utils/dataFilter';

describe('filterSensitiveData', () => {
  it('should remove sensitive fields', () => {
    const data = {
      ts_code: '601985',
      name: '中国核电',
      price: 12.5,        // 敏感字段
      amount: 10000,      // 敏感字段
    };

    const filtered = filterSensitiveData(data);

    expect(filtered).toHaveProperty('ts_code');
    expect(filtered).toHaveProperty('name');
    expect(filtered).not.toHaveProperty('price');
    expect(filtered).not.toHaveProperty('amount');
  });
});
```

---

**文档更新时间：** 2026-03-09
**技术支持：** 知夏
