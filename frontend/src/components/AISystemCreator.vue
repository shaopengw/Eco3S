<template>
  <div class="ai-system-creator">
    <div class="creator-header">
      <h2>AI辅助模拟系统创建器</h2>
      <el-button @click="$emit('back')" text>返回</el-button>
    </div>

    <!-- 步骤指示器 -->
    <el-steps :active="currentStep" finish-status="success" align-center class="steps-container">
      <el-step title="需求输入" />
      <el-step title="需求解析" />
      <el-step title="系统设计" />
      <el-step title="代码生成" />
      <el-step title="运行测试" />
    </el-steps>

    <!-- 步骤1: 需求输入 -->
    <div v-if="currentStep === 0" class="step-content">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>输入模拟需求</span>
          </div>
        </template>
        
        <div class="requirement-input">
          <el-alert
            title="使用说明"
            type="info"
            :closable="false"
            show-icon
          >
            <p>请用自然语言描述您想要创建的模拟实验。系统将自动：</p>
            <ul>
              <li>分析需求并选择合适的模块</li>
              <li>生成设计文档和配置文件</li>
              <li>自动编写模拟器代码和入口文件</li>
              <li>运行模拟并评估结果</li>
            </ul>
          </el-alert>

          <div class="mode-selection">
            <el-radio-group v-model="mode">
              <el-radio value="auto">自动模式 - 一次性完成所有步骤</el-radio>
              <el-radio value="interactive">交互模式 - 每个阶段等待确认</el-radio>
            </el-radio-group>
          </div>

          <el-input
            v-model="requirement"
            type="textarea"
            :rows="8"
            placeholder="例如：我想研究气候变化对居民迁移的影响，需要模拟100个居民在不同气候条件下的行为，观察他们在极端天气下的决策..."
          />

          <div class="example-requirements">
            <span>示例需求：</span>
            <el-tag
              v-for="example in exampleRequirements"
              :key="example"
              @click="requirement = example"
              style="cursor: pointer; margin: 4px;"
            >
              {{ example.substring(0, 30) }}...
            </el-tag>
          </div>

          <div class="actions">
            <el-button type="primary" @click="startCreation" :loading="loading">
              开始创建
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 步骤2-5: 进度显示 -->
    <div v-else class="step-content">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>{{ currentPhaseTitle }}</span>
            <el-tag :type="statusType">{{ statusText }}</el-tag>
          </div>
        </template>

        <!-- 实时输出 -->
        <div class="output-container">
          <el-scrollbar height="400px">
            <pre class="output-text">{{ output }}</pre>
          </el-scrollbar>
        </div>

        <!-- 阶段结果展示 -->
        <div v-if="phaseResults" class="phase-results">
          <el-divider>阶段结果</el-divider>
          
          <!-- 解析结果 -->
          <div v-if="phaseResults.requirement_dict" class="result-section">
            <h4>📋 需求解析结果</h4>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="模拟名称">
                {{ phaseResults.simulation_name }}
              </el-descriptions-item>
              <el-descriptions-item label="模拟类型">
                {{ phaseResults.requirement_dict.simulation_type }}
              </el-descriptions-item>
              <el-descriptions-item label="项目目录" :span="2">
                {{ phaseResults.project_dir }}
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- 设计结果 -->
          <div v-if="phaseResults.design_results" class="result-section">
            <h4>🎨 设计阶段成果</h4>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="设计文档">
                已生成 description.md
              </el-descriptions-item>
              <el-descriptions-item label="模块配置">
                已生成 modules_config.yaml
              </el-descriptions-item>
            </el-descriptions>
            <el-button @click="viewDesignDoc" size="small" style="margin-top: 8px;">
              查看设计文档
            </el-button>
          </div>

          <!-- 编码结果 -->
          <div v-if="phaseResults.coding_results" class="result-section">
            <h4>💻 编码阶段成果</h4>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="模拟器代码" v-if="phaseResults.coding_results.simulator_files">
                {{ phaseResults.coding_results.simulator_files[0] }}
              </el-descriptions-item>
              <el-descriptions-item label="入口文件" v-if="phaseResults.coding_results.main_files">
                {{ phaseResults.coding_results.main_files[0] }}
              </el-descriptions-item>
              <el-descriptions-item label="配置文件" v-if="phaseResults.coding_results.config_files">
                {{ phaseResults.coding_results.config_files.length }} 个配置文件
              </el-descriptions-item>
              <el-descriptions-item label="提示词文件" v-if="phaseResults.coding_results.prompt_files">
                {{ phaseResults.coding_results.prompt_files.length }} 个提示词文件
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- 模拟结果 -->
          <div v-if="phaseResults.simulation_results" class="result-section">
            <h4>🎯 模拟运行结果</h4>
            <el-alert type="success" :closable="false">
              模拟成功运行！结果已保存到实验数据目录。
            </el-alert>
          </div>
        </div>

        <!-- 交互模式的操作按钮 -->
        <div v-if="mode === 'interactive' && showInteractiveActions" class="actions">
          <el-input
            v-if="waitingForFeedback"
            v-model="userFeedback"
            type="textarea"
            :rows="3"
            placeholder="输入您的反馈意见（可选）"
            style="margin-bottom: 12px;"
          />
          <el-button-group>
            <el-button type="primary" @click="continueToNextPhase" :loading="loading">
              继续下一步
            </el-button>
            <el-button @click="regeneratePhase" :loading="loading">
              重新生成
            </el-button>
            <el-button @click="cancelCreation">
              取消
            </el-button>
          </el-button-group>
        </div>

        <!-- 完成状态的操作 -->
        <div v-if="isCompleted" class="actions">
          <el-alert type="success" :closable="false" style="margin-bottom: 12px;">
            🎉 AI系统创建完成！您可以在模拟列表中找到新创建的项目。
          </el-alert>
          <el-button-group>
            <el-button type="primary" @click="goToSimulation">
              前往模拟
            </el-button>
            <el-button @click="resetCreator">
              创建新项目
            </el-button>
            <el-button @click="$emit('back')">
              返回首页
            </el-button>
          </el-button-group>
        </div>

        <!-- 错误状态 -->
        <div v-if="hasError" class="actions">
          <el-alert type="error" :closable="false" style="margin-bottom: 12px;">
            ❌ 创建过程出现错误，请查看输出日志了解详情。
          </el-alert>
          <el-button-group>
            <el-button @click="retryCurrentPhase" :loading="loading">
              重试当前步骤
            </el-button>
            <el-button @click="resetCreator">
              重新开始
            </el-button>
          </el-button-group>
        </div>
      </el-card>
    </div>

    <!-- 设计文档查看对话框 -->
    <el-dialog v-model="showDesignDialog" title="设计文档" width="80%">
      <div v-html="renderedDesignDoc" class="design-doc-content"></div>
    </el-dialog>

    <!-- 用户确认对话框 -->
    <el-dialog v-model="showConfirmDialog" :title="confirmMessage" width="50%" :close-on-click-modal="false" :close-on-press-escape="false">
      <div v-if="confirmType === 'input'" style="margin-bottom: 20px;">
        <el-input v-model="confirmInput" :placeholder="confirmMessage" />
      </div>
      
      <div v-else-if="confirmType === 'choice'" style="margin-bottom: 20px;">
        <el-radio-group v-model="confirmInput">
          <el-radio v-for="option in confirmOptions" :key="option" :label="option">
            {{ option }}
          </el-radio>
        </el-radio-group>
      </div>

      <div v-else-if="confirmType === 'yes_no'">
        <el-alert type="info" :closable="false">
          {{ confirmMessage }}
        </el-alert>
      </div>

      <template #footer>
        <div v-if="confirmType === 'yes_no'">
          <el-button @click="handleConfirm(false)">取消</el-button>
          <el-button type="primary" @click="handleConfirm(true)">确认</el-button>
        </div>
        <div v-else>
          <el-button type="primary" @click="handleConfirm(true)">提交</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'

const emit = defineEmits(['back', 'simulation-created'])

// 状态变量
const currentStep = ref(0)
const mode = ref('auto')
const requirement = ref('')
const sessionId = ref(null)
const status = ref('')
const phase = ref('')
const output = ref('')
const phaseResults = ref(null)
const loading = ref(false)
const userFeedback = ref('')
const showDesignDialog = ref(false)
const designDoc = ref('')
const showConfirmDialog = ref(false)
const confirmMessage = ref('')
const confirmType = ref('')
const confirmOptions = ref([])
const confirmInput = ref('')

let statusCheckTimer = null

// 示例需求
const exampleRequirements = [
  '我希望研究在一个有极端气候的世界中，政府如何通过调整税收和运河维护投资来平衡财政并抑制叛乱。模拟中应包含政府、居民和叛军三种角色，极端气候会随机发生并对运河造成破坏。',
  '我想研究气候变化对居民迁移的影响，需要模拟100个居民在不同气候条件下的行为，观察他们在极端天气下的决策',
  '我想创建一个信息传播模拟，研究不同的信息传播策略如何影响公众对政策的接受度'
]

// 计算属性
const currentPhaseTitle = computed(() => {
  const titles = {
    parse: '需求解析中',
    design: '系统设计中',
    coding: '代码生成中',
    simulation: '运行模拟中'
  }
  return titles[phase.value] || '处理中'
})

const statusType = computed(() => {
  if (status.value === 'error') return 'danger'
  if (status.value === 'completed') return 'success'
  return 'primary'
})

const statusText = computed(() => {
  const texts = {
    parsing: '解析中...',
    parsed: '解析完成',
    designing: '设计中...',
    design_completed: '设计完成',
    coding: '编码中...',
    coding_completed: '编码完成',
    running_simulation: '模拟运行中...',
    completed: '全部完成',
    error: '出错'
  }
  return texts[status.value] || status.value
})

const showInteractiveActions = computed(() => {
  const shouldShow = mode.value === 'interactive' && ['parsed', 'design_completed', 'coding_completed'].includes(status.value)
  console.log(`🔍 交互按钮显示检查: mode=${mode.value}, status=${status.value}, loading=${loading.value}, shouldShow=${shouldShow}`)
  return shouldShow
})

const waitingForFeedback = computed(() => {
  return showInteractiveActions.value
})

const isCompleted = computed(() => {
  return status.value === 'completed'
})

const hasError = computed(() => {
  return status.value === 'error'
})

const renderedDesignDoc = computed(() => {
  return marked(designDoc.value)
})

// 方法
const startCreation = async () => {
  if (!requirement.value.trim()) {
    ElMessage.warning('请输入模拟需求')
    return
  }

  loading.value = true
  currentStep.value = 1

  try {
    // 1. 解析需求
    const response = await fetch('/api/ai_system/parse_requirement', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirement_text: requirement.value })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '解析需求失败')
    }

    sessionId.value = data.session_id
    status.value = data.status
    output.value = data.message + '\n'

    // 开始轮询状态
    startStatusPolling()

  } catch (error) {
    ElMessage.error(error.message)
    loading.value = false
    currentStep.value = 0
  }
}

const startStatusPolling = () => {
  // 清除现有定时器
  if (statusCheckTimer) {
    clearInterval(statusCheckTimer)
  }

  // 每2秒检查一次状态
  statusCheckTimer = setInterval(async () => {
    await checkStatus()
  }, 2000)
}

const stopStatusPolling = () => {
  if (statusCheckTimer) {
    clearInterval(statusCheckTimer)
    statusCheckTimer = null
  }
}

const checkStatus = async () => {
  if (!sessionId.value) return

  try {
    const response = await fetch(`/api/ai_system/status/${sessionId.value}`)
    const data = await response.json()

    const prevStatus = status.value
    const prevPhase = phase.value
    
    status.value = data.status
    phase.value = data.phase

    // 追加新的输出
    if (data.output) {
      output.value += data.output + '\n'
    }

    // 更新结果
    if (data.results) {
      phaseResults.value = data.results
    }

    // 处理用户确认请求
    if (data.waiting_confirmation && !showConfirmDialog.value) {
      confirmMessage.value = data.confirmation_message
      confirmType.value = data.confirmation_type
      confirmOptions.value = data.confirmation_options || []
      confirmInput.value = ''
      showConfirmDialog.value = true
      console.log('显示确认对话框:', data.confirmation_message)
    }

    // 打印状态信息用于调试
    if (prevStatus !== data.status || prevPhase !== data.phase) {
      console.log(`状态变化: [${prevPhase}/${prevStatus}] -> [${data.phase}/${data.status}]`)
      console.log('当前模式:', mode.value)
    }

    // 更新步骤
    updateCurrentStep(data.phase, data.status)

    // 在阶段完成时重置 loading 状态
    if ((data.status === 'parsed' || data.status.includes('completed')) && loading.value) {
      console.log(`🔄 重置加载状态前: loading=${loading.value}, status=${data.status}`)
      loading.value = false
      console.log(`✅ 重置加载状态后: loading=${loading.value}`)
    }

    // 处理状态变化 - 只在状态改变时触发自动模式
    if (mode.value === 'auto' && prevStatus !== data.status) {
      if (data.status === 'parsed') {
        // 自动模式：继续设计阶段
        console.log('✓ 自动触发设计阶段')
        setTimeout(() => runDesignPhase(), 1000)
      } else if (data.status === 'design_completed') {
        // 自动模式：继续编码阶段
        console.log('✓ 自动触发编码阶段')
        setTimeout(() => runCodingPhase(), 1000)
      } else if (data.status === 'coding_completed') {
        // 自动模式：运行模拟
        console.log('✓ 自动触发模拟运行')
        setTimeout(() => runSimulation(), 1000)
      }
    }
    
    if (data.status === 'completed' || data.status === 'error') {
      // 停止轮询
      console.log('✓ 流程结束，停止轮询')
      stopStatusPolling()
      loading.value = false
    }

  } catch (error) {
    console.error('检查状态失败:', error)
  }
}

const updateCurrentStep = (currentPhase, currentStatus) => {
  const stepMap = {
    parse: 1,
    design: 2,
    coding: 3,
    simulation: 4
  }

  const step = stepMap[currentPhase] || 1
  
  // 如果阶段完成，前进到下一步
  if (currentStatus.includes('completed')) {
    currentStep.value = step + 1
  } else {
    currentStep.value = step
  }
}

const runDesignPhase = async () => {
  console.log('🚀 开始调用设计阶段API...')
  loading.value = true
  
  try {
    const response = await fetch('/api/ai_system/run_design', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        user_feedback: userFeedback.value || null
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '运行设计阶段失败')
    }

    console.log('✓ 设计阶段API调用成功')
    userFeedback.value = ''
    // loading 会在状态变化为 design_completed 或 error 时重置

  } catch (error) {
    console.error('❌ 设计阶段API调用失败:', error)
    ElMessage.error(error.message)
    loading.value = false
  }
}

const runCodingPhase = async () => {
  console.log('🚀 开始调用编码阶段API...')
  loading.value = true
  
  try {
    const response = await fetch('/api/ai_system/run_coding', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        user_feedback: userFeedback.value || null
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '运行编码阶段失败')
    }

    console.log('✓ 编码阶段API调用成功')
    userFeedback.value = ''

  } catch (error) {
    console.error('❌ 编码阶段API调用失败:', error)
    ElMessage.error(error.message)
    loading.value = false
  }
}

const runSimulation = async () => {
  console.log('🚀 开始调用模拟运行API...')
  loading.value = true
  
  try {
    const response = await fetch('/api/ai_system/run_simulation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '运行模拟失败')
    }

    console.log('✓ 模拟运行API调用成功')

  } catch (error) {
    console.error('❌ 模拟运行API调用失败:', error)
    ElMessage.error(error.message)
    loading.value = false
  }
}

const continueToNextPhase = () => {
  if (status.value === 'parsed') {
    runDesignPhase()
  } else if (status.value === 'design_completed') {
    runCodingPhase()
  } else if (status.value === 'coding_completed') {
    runSimulation()
  }
}

const regeneratePhase = () => {
  if (!userFeedback.value.trim()) {
    ElMessage.warning('请输入反馈意见以重新生成')
    return
  }
  continueToNextPhase()
}

const retryCurrentPhase = () => {
  if (phase.value === 'parse') {
    startCreation()
  } else {
    continueToNextPhase()
  }
}

const cancelCreation = () => {
  stopStatusPolling()
  resetCreator()
}

const resetCreator = () => {
  stopStatusPolling()
  currentStep.value = 0
  requirement.value = ''
  sessionId.value = null
  status.value = ''
  phase.value = ''
  output.value = ''
  phaseResults.value = null
  loading.value = false
  userFeedback.value = ''
}

const viewDesignDoc = async () => {
  if (!phaseResults.value?.config_dir) return

  try {
    const configDir = phaseResults.value.config_dir
    const simulationName = phaseResults.value.simulation_name
    
    // 从后端获取设计文档
    const response = await fetch(`/api/description/${simulationName}`)
    const data = await response.json()
    
    designDoc.value = data.description || '无法加载设计文档'
    showDesignDialog.value = true

  } catch (error) {
    ElMessage.error('加载设计文档失败')
  }
}

const goToSimulation = () => {
  if (phaseResults.value?.simulation_name) {
    emit('simulation-created', phaseResults.value.simulation_name)
  }
}

const handleConfirm = async (confirmed) => {
  try {
    const response = await fetch(`/api/ai_system/confirm/${sessionId.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        confirmed: confirmed,
        input: confirmInput.value
      })
    })

    if (!response.ok) {
      throw new Error('发送确认失败')
    }

    showConfirmDialog.value = false
    confirmInput.value = ''

  } catch (error) {
    ElMessage.error(error.message)
  }
}

// 清理
onUnmounted(() => {
  stopStatusPolling()
})
</script>

<style scoped>
.ai-system-creator {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.creator-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.steps-container {
  margin-bottom: 30px;
}

.step-content {
  flex: 1;
  overflow-y: auto;
}

.requirement-input {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.mode-selection {
  margin: 16px 0;
}

.example-requirements {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.output-container {
  margin: 16px 0;
  background-color: #1e1e1e;
  border-radius: 4px;
  padding: 12px;
}

.output-text {
  color: #d4d4d4;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.phase-results {
  margin-top: 20px;
}

.result-section {
  margin-bottom: 20px;
}

.result-section h4 {
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
}

.actions {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.design-doc-content {
  line-height: 1.6;
  max-height: 600px;
  overflow-y: auto;
}

.design-doc-content :deep(h1) {
  font-size: 24px;
  margin-bottom: 16px;
}

.design-doc-content :deep(h2) {
  font-size: 20px;
  margin: 16px 0;
}

.design-doc-content :deep(p) {
  margin: 12px 0;
}

.design-doc-content :deep(ul),
.design-doc-content :deep(ol) {
  padding-left: 24px;
  margin: 12px 0;
}

.design-doc-content :deep(code) {
  background-color: var(--el-fill-color-light);
  padding: 2px 4px;
  border-radius: 4px;
}

.design-doc-content :deep(pre) {
  background-color: var(--el-fill-color);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 16px 0;
}
</style>
