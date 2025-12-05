# AgentWorld 前端

基于 Vue 3 + Vite 的多智能体模拟系统前端界面。

## 功能特性

### 🎯 核心功能

1. **模拟管理**
   - 浏览和选择不同的模拟实验
   - 查看模拟描述和配置
   - 运行和监控模拟进度

2. **配置编辑**
   - 在线编辑模拟配置文件
   - 实时保存和验证
   - 支持YAML和JSON格式

3. **数据分析**
   - 实时查看模拟数据图表
   - 历史模拟记录查询
   - 数据分析和报告生成

4. **AI辅助创建** ⭐ 新功能
   - 自然语言描述需求
   - 自动生成模拟代码和配置
   - 支持自动和交互两种模式
   - 实时进度跟踪和结果展示

## 快速开始

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

服务将运行在 `http://localhost:5173`

### 构建生产版本

```bash
npm run build
```

### 预览生产构建

```bash
npm run preview
```

## 技术栈

- **Vue 3**: 渐进式JavaScript框架
- **Vite**: 下一代前端构建工具
- **Element Plus**: Vue 3 UI组件库
- **Chart.js**: 数据可视化
- **Marked**: Markdown渲染

## 项目结构

```
frontend/
├── public/              # 静态资源
├── src/
│   ├── components/      # Vue组件
│   │   ├── AISystemCreator.vue      # AI创建器 ⭐
│   │   ├── ConfigEditor.vue         # 配置编辑器
│   │   ├── DataAnalyzer.vue         # 数据分析器
│   │   ├── SimulationDescription.vue # 模拟描述
│   │   ├── SimulationHistory.vue    # 历史记录
│   │   └── SimulationRunner.vue     # 模拟运行器
│   ├── App.vue          # 主应用组件
│   ├── main.js          # 应用入口
│   └── style.css        # 全局样式
├── index.html
├── package.json
├── vite.config.js
└── AI_INTEGRATION_GUIDE.md  # AI集成详细指南 ⭐
```

## 使用AI创建器

### 基本流程

1. 在侧边栏点击 **"AI辅助创建"**
2. 选择运行模式（自动/交互）
3. 输入模拟需求描述
4. 点击 **"开始创建"**
5. 等待系统自动完成各阶段
6. 查看生成的项目并开始模拟

### 详细说明

请参阅 [AI集成指南](./AI_INTEGRATION_GUIDE.md) 获取完整的使用说明和示例。

## 组件说明

### AISystemCreator.vue ⭐

AI辅助创建器组件，支持：
- 需求输入和解析
- 5步骤进度跟踪
- 实时输出日志显示
- 阶段结果展示
- 交互式反馈和重新生成

主要功能：
```javascript
// 启动创建流程
startCreation()

// 检查执行状态
checkStatus()

// 运行各阶段
runDesignPhase()
runCodingPhase()
runSimulation()
```

### SimulationRunner.vue

模拟运行器，负责：
- 启动和停止模拟
- 显示运行日志
- 展示实时数据图表
- 显示模拟结果

### ConfigEditor.vue

配置编辑器，支持：
- 加载和显示配置文件
- 在线编辑YAML/JSON
- 保存配置更改
- 语法验证

### DataAnalyzer.vue

数据分析工具，提供：
- 数据统计和聚合
- 图表生成和展示
- 分析报告导出

### SimulationHistory.vue

历史记录查看器：
- 列出所有历史运行
- 查看日志文件
- 显示历史图表
- 比较不同运行结果

### SimulationDescription.vue

模拟描述展示：
- Markdown格式渲染
- 模拟介绍和说明
- 快速操作按钮

## API通信

前端通过以下API与后端通信：

### 模拟管理
- `GET /api/config/<type>` - 获取配置
- `POST /api/config/<type>` - 更新配置
- `GET /api/run/<type>` - 运行模拟
- `GET /api/simulation_status/<id>` - 获取状态

### AI系统
- `POST /api/ai_system/parse_requirement` - 解析需求
- `POST /api/ai_system/run_design` - 运行设计
- `POST /api/ai_system/run_coding` - 运行编码
- `POST /api/ai_system/run_simulation` - 运行模拟
- `GET /api/ai_system/status/<id>` - 获取状态
- `GET /api/ai_system/list_projects` - 列出项目

### 数据分析
- `POST /api/analyze` - 运行分析
- `GET /api/description/<type>` - 获取描述
- `GET /api/history/<type>` - 获取历史

## 开发指南

### 添加新组件

1. 在 `src/components/` 创建新的 `.vue` 文件
2. 在 `App.vue` 中导入组件
3. 添加路由或条件渲染逻辑
4. 实现组件功能和样式

### 调用后端API

```javascript
// 示例：调用API
const response = await fetch('/api/endpoint', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
})
const result = await response.json()
```

### 状态管理

使用 Vue 3 Composition API 的 `ref` 和 `computed`:

```javascript
import { ref, computed } from 'vue'

const state = ref('initial')
const derivedState = computed(() => state.value.toUpperCase())
```

### 样式定制

在组件中使用 scoped 样式：

```vue
<style scoped>
.my-component {
  /* 样式只作用于当前组件 */
}
</style>
```

## 常见问题

### Q: 如何修改API基础URL？

A: 在 `vite.config.js` 中配置代理：

```javascript
export default {
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
}
```

### Q: 如何添加新的模拟类型？

A: 
1. 后端添加相应的配置和命令
2. 前端在 `availableSimulations` 中添加
3. 更新翻译映射

### Q: 如何调试组件？

A: 使用 Vue DevTools 浏览器扩展，或在代码中使用 `console.log`。

## IDE支持

推荐使用 VS Code 配合以下插件：
- Volar (Vue 3语言支持)
- ESLint
- Prettier

## 了解更多

- [Vue 3 文档](https://v3.vuejs.org/)
- [Vite 文档](https://vitejs.dev/)
- [Element Plus 文档](https://element-plus.org/)
- [Chart.js 文档](https://www.chartjs.org/)

## 许可证

与主项目保持一致
