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
        <el-menu-item index="default">
          <span>{{ t('默认模拟') }}</span>
        </el-menu-item>
        <el-menu-item index="TEOG">
          <span>{{ t('TEOG模拟') }}</span>
        </el-menu-item>
        <el-menu-item index="info_propagation">
          <span>{{ t('信息传播模拟') }}</span>
        </el-menu-item>
      </el-menu>

      <div class="main-content">
        <template v-if="!showSimulation">
          <SimulationDescription
            :config-type="activeSimulation"
            @start-simulation="startSimulation"
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
import { Sunny, Moon } from '@element-plus/icons-vue';
import './style.css';
import ConfigEditor from './components/ConfigEditor.vue'
import SimulationRunner from './components/SimulationRunner.vue'
import SimulationDescription from './components/SimulationDescription.vue'

const activeSimulation = ref('default')
const showSimulation = ref(false)
const isDark = ref(false)
const language = ref('zh')

// 简单的翻译函数
const translations = {
  zh: {
    '默认模拟': '默认模拟',
    'TEOG模拟': 'TEOG模拟',
    '信息传播模拟': '信息传播模拟'
  },
  en: {
    '默认模拟': 'Default Simulation',
    'TEOG模拟': 'TEOG Simulation',
    '信息传播模拟': 'Information Propagation'
  }
}

const t = (key) => {
  return translations[language.value][key] || key
}

const handleSelect = (index) => {
  activeSimulation.value = index
  showSimulation.value = false
}

const startSimulation = () => {
  showSimulation.value = true
}

const handleConfigSaved = () => {
  // 配置保存后的处理逻辑
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  document.documentElement.className = isDark.value ? 'dark' : ''
}

const toggleLanguage = () => {
  language.value = language.value === 'zh' ? 'en' : 'zh'
}
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
