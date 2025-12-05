<template>
  <div class="app-container" :class="{ 'dark': isDark }">
    <header class="app-header">
      <h1 class="app-title">AgentWorld</h1>
      <div class="header-controls">
        <el-button-group>
          <el-button
            :icon="isDark ? 'Sunny' : 'Moon'"
            @click="toggleTheme"
            text
          >
            {{ isDark ? '浅色' : '深色' }}
          </el-button>
          <el-button
            :icon="isDark ? 'Sunny' : 'Moon'"
            @click="toggleLanguage"
            text
          >
            {{ language === 'zh' ? 'English' : '中文' }}
          </el-button>
        </el-button-group>
      </div>
    </header>

    <div class="main-container">
      <el-menu
        class="sidebar"
        :default-active="activeSimulation"
        @select="handleSelect"
      >
        <el-menu-item-group title="创建新模拟">
          <el-menu-item index="ai_creator">
            <el-icon><Plus /></el-icon>
            <span>{{ t('AI辅助创建') }}</span>
          </el-menu-item>
        </el-menu-item-group>
        
        <el-menu-item-group title="已有模拟">
          <el-menu-item 
            v-for="sim in availableSimulations" 
            :key="sim" 
            :index="sim"
          >
            <span>{{ t(getSimulationName(sim)) }}</span>
          </el-menu-item>
        </el-menu-item-group>
      </el-menu>

      <div class="main-content">
        <template v-if="showAICreator">
          <AISystemCreator
            @back="showAICreator = false"
            @simulation-created="handleSimulationCreated"
          />
        </template>
        <template v-else-if="!showSimulation && !showHistory && !showAnalyzer">
          <SimulationDescription
            :config-type="activeSimulation"
            @start-simulation="startSimulation"
            @view-history="viewHistory"
            @analyze-data="showAnalyzer = true"
          />
        </template>
        <template v-else-if="showHistory">
          <SimulationHistory
            :config-type="activeSimulation"
            @back-to-description="showHistory = false"
          />
        </template>
        <template v-else-if="showAnalyzer">
          <DataAnalyzer
            :config-type="activeSimulation"
            @back-to-description="showAnalyzer = false"
          />
        </template>
        <template v-else>
          <div class="simulation-container">
            <div class="simulation-runner-wrapper">
              <SimulationRunner
                :config-type="activeSimulation"
                @back-to-description="showSimulation = false"
              />
            </div>
            <div class="config-editor-wrapper">
              <ConfigEditor
                :config-type="activeSimulation"
                @config-saved="handleConfigSaved"
              />
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue';
import { Sunny, Moon, Plus } from '@element-plus/icons-vue';
import './style.css';
import ConfigEditor from './components/ConfigEditor.vue'
import SimulationRunner from './components/SimulationRunner.vue'
import SimulationDescription from './components/SimulationDescription.vue'
import SimulationHistory from './components/SimulationHistory.vue'
import DataAnalyzer from './components/DataAnalyzer.vue'
import AISystemCreator from './components/AISystemCreator.vue'

const activeSimulation = ref('default')
const showSimulation = ref(false)
const showHistory = ref(false)
const showAnalyzer = ref(false)
const showAICreator = ref(false) // 新增AI创建器状态
const isDark = ref(false)
const language = ref('zh')
const availableSimulations = ref(['default', 'TEOG', 'info_propagation']) // 可用的模拟列表

// 简单的翻译函数
const translations = {
  zh: {
    'AI辅助创建': 'AI辅助创建',
    '默认模拟': '默认模拟',
    'TEOG模拟': 'TEOG模拟',
    '信息传播模拟': '信息传播模拟',
    'default': '默认模拟',
    'TEOG': 'TEOG模拟',
    'info_propagation': '信息传播模拟'
  },
  en: {
    'AI辅助创建': 'AI-Assisted Creation',
    '默认模拟': 'Default Simulation',
    'TEOG模拟': 'TEOG Simulation',
    '信息传播模拟': 'Information Propagation',
    'default': 'Default Simulation',
    'TEOG': 'TEOG Simulation',
    'info_propagation': 'Information Propagation'
  }
}

const t = (key) => {
  return translations[language.value][key] || key
}

const getSimulationName = (simId) => {
  // 返回模拟的显示名称
  return translations[language.value][simId] || simId
}

const handleSelect = (index) => {
  if (index === 'ai_creator') {
    showAICreator.value = true
    showSimulation.value = false
    showHistory.value = false
    showAnalyzer.value = false
  } else {
    activeSimulation.value = index
    showAICreator.value = false
    showSimulation.value = false
    showHistory.value = false
    showAnalyzer.value = false
  }
}

const startSimulation = () => {
  showSimulation.value = true
  showHistory.value = false
  showAnalyzer.value = false
  showAICreator.value = false
}

const viewHistory = () => {
  showHistory.value = true
  showSimulation.value = false
  showAnalyzer.value = false
  showAICreator.value = false
}

const handleConfigSaved = () => {
  // 配置保存后的处理逻辑
}

const handleSimulationCreated = (simulationName) => {
  // AI创建完成后的处理
  if (!availableSimulations.value.includes(simulationName)) {
    availableSimulations.value.push(simulationName)
  }
  activeSimulation.value = simulationName
  showAICreator.value = false
  showSimulation.value = false
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  document.documentElement.className = isDark.value ? 'dark' : ''
}

const toggleLanguage = () => {
  language.value = language.value === 'zh' ? 'en' : 'zh'
}

// 加载可用的模拟列表
const loadAvailableSimulations = async () => {
  try {
    const response = await fetch('/api/ai_system/list_projects')
    const data = await response.json()
    
    if (data.projects) {
      const projectNames = data.projects.map(p => p.name)
      // 合并默认模拟和AI生成的模拟
      const defaultSims = ['default', 'TEOG', 'info_propagation']
      availableSimulations.value = [...new Set([...defaultSims, ...projectNames])]
    }
  } catch (error) {
    console.error('加载模拟列表失败:', error)
  }
}

onMounted(() => {
  loadAvailableSimulations()
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--el-bg-color);
  color: var(--el-text-color-primary);
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
}

.main-container {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.sidebar {
  width: 200px;
  border-right: 1px solid var(--el-border-color-light);
}

.main-content {
  flex: 1;
  overflow: auto;
  padding: 1rem;
}

.simulation-container {
  display: flex;
  height: 100%;
  gap: 1rem;
}

.simulation-runner-wrapper {
  flex: 3;
  overflow-y: auto;
  border: 1px solid var(--el-border-color-light);
  border-radius: 4px;
  padding: 1rem;
}

.config-editor-wrapper {
  flex: 1;
  overflow-y: auto;
  border: 1px solid var(--el-border-color-light);
  border-radius: 4px;
  padding: 1rem;
}

.dark {
  --el-bg-color: #1a1a1a;
  --el-text-color-primary: #ffffff;
  --el-border-color-light: #333333;
}
</style>
