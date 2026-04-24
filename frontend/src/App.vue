<template>
  <div class="app-container" :class="{ 'dark': isDark }">
    <!-- Premium Header -->
    <header class="app-header premium-header">
      <div class="header-left">
        <!-- Logo or Title -->
        <div class="logo-area" @click="goHome">
          <div class="logo-icon">🌍</div>
          <h1 class="app-title">{{ t('header.title') }}</h1>
        </div>

        <!-- Subpage Navigation (Only visible when in subpages) -->
        <div v-if="isSubPage" class="subpage-nav fade-in">
          <el-divider direction="vertical" class="nav-divider" />
          <span class="current-sim-name">{{ showAICreator ? t('menu.aiAssisted') : formatSimulationName(activeSimulation) }}</span>
          
          <el-button-group class="nav-btn-group" v-if="!showAICreator">
            <el-button 
              :type="!showHistory && !showAnalyzer ? 'primary' : 'default'" 
              @click="startSimulation" 
              icon="VideoPlay"
              round
            >
              {{ t('header.nav.dashboard') }}
            </el-button>
            <el-button 
              :type="showHistory ? 'primary' : 'default'" 
              @click="viewHistory" 
              icon="List"
              round
            >
              {{ t('header.nav.history') }}
            </el-button>
            <el-button 
              :type="showAnalyzer ? 'primary' : 'default'" 
              @click="showAnalyzer = true; showHistory = false; showSimulation = false;" 
              icon="DataAnalysis"
              round
            >
              {{ t('header.nav.analysis') }}
            </el-button>
          </el-button-group>

          <el-button 
            class="back-btn" 
            icon="Back" 
            @click="goHome" 
            text 
            bg 
            round
          >
            {{ t('header.nav.backHome') }}
          </el-button>
        </div>
      </div>

      <div class="header-controls">
        <el-button-group class="theme-lang-group">
          <el-button
            :icon="isDark ? 'Sunny' : 'Moon'"
            @click="toggleTheme"
            circle
          />
          <el-button
            @click="toggleLanguage"
            circle
          >
            {{ t('header.language') === '中文' ? 'EN' : '中' }}
          </el-button>
        </el-button-group>
      </div>
    </header>

    <div class="main-container">
      <!-- Premium Sidebar (Hidden on subpages) -->
      <transition name="slide-left">
        <aside v-show="!isSubPage" class="premium-sidebar">
          <div class="sidebar-header">
            <span class="sidebar-title">{{ t('menu.projectList') }}</span>
          </div>
          <el-menu
            class="sidebar-menu"
            :default-active="activeSimulation"
            @select="handleSelect"
          >
            <el-menu-item-group :title="t('menu.createNew')">
              <el-menu-item index="ai_creator" class="creator-item">
                <el-icon><Plus /></el-icon>
                <span>{{ t('menu.aiAssisted') }}</span>
              </el-menu-item>
            </el-menu-item-group>
            
            <el-menu-item-group :title="t('menu.existingSimulations')">
              <el-menu-item 
                v-for="sim in availableSimulations" 
                :key="sim" 
                :index="sim"
                class="sim-item"
              >
                <el-icon><Folder /></el-icon>
                <el-tooltip :content="formatSimulationName(sim)" placement="right" :show-after="500">
                  <span class="menu-item-label">{{ formatSimulationName(sim) }}</span>
                </el-tooltip>
              </el-menu-item>
            </el-menu-item-group>
          </el-menu>
        </aside>
      </transition>

      <!-- Main Content Area -->
      <main class="main-content" :class="{ 'is-subpage': isSubPage }">
        <template v-if="showAICreator">
          <AISystemCreator
            @back="goHome"
            @simulation-created="handleSimulationCreated"
          />
        </template>
        <template v-else-if="!isSubPage">
          <SimulationDescription
            :config-type="activeSimulation"
            @start-simulation="startSimulation"
            @view-history="viewHistory"
            @analyze-data="showAnalyzer = true"
          />
        </template>
        <template v-else-if="showHistory">
          <div class="page-wrapper">
            <SimulationHistory
              :config-type="activeSimulation"
              @back-to-description="goHome"
            />
          </div>
        </template>
        <template v-else-if="showAnalyzer">
          <div class="page-wrapper">
            <DataAnalyzer
              :config-type="activeSimulation"
              @back-to-description="goHome"
            />
          </div>
        </template>
        <template v-else>
          <div class="simulation-full-container">
            <SimulationRunner
              :config-type="activeSimulation"
              @back-to-description="goHome"
            />
          </div>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, provide } from 'vue';
import { Sunny, Moon, Plus, Folder, VideoPlay, List, DataAnalysis, Back } from '@element-plus/icons-vue';
import './style.css';
import SimulationRunner from './components/SimulationRunner.vue'
import SimulationDescription from './components/SimulationDescription.vue'
import SimulationHistory from './components/SimulationHistory.vue'
import DataAnalyzer from './components/DataAnalyzer.vue'
import AISystemCreator from './components/AISystemCreator.vue'
import { useI18n } from './i18n'

const activeSimulation = ref('default')
const showSimulation = ref(false)
const showHistory = ref(false)
const showAnalyzer = ref(false)
const showAICreator = ref(false)
const isDark = ref(false)
const availableSimulations = ref(['default', 'TEOG', 'info_propagation'])

// 判断是否在子页面（运行大盘、历史、数据分析）
const isSubPage = computed(() => {
  return showSimulation.value || showHistory.value || showAnalyzer.value || showAICreator.value;
})

const { t, setLocale, getLocale } = useI18n()
provide('useI18n', useI18n)

const formatSimulationName = (simId) => {
  if (!simId) return ''
  if (simId === simId.toUpperCase()) {
    return simId.replace(/_/g, ' ')
  }
  return simId
    .split('_')
    .map(part => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

const goHome = () => {
  showSimulation.value = false;
  showHistory.value = false;
  showAnalyzer.value = false;
  showAICreator.value = false;
}

const handleSelect = (index) => {
  if (index === 'ai_creator') {
    showAICreator.value = true
    showSimulation.value = false
    showHistory.value = false
    showAnalyzer.value = false
  } else {
    activeSimulation.value = index
    goHome() // 切回主页看描述
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
  if (!availableSimulations.value.includes(simulationName)) {
    availableSimulations.value.push(simulationName)
  }
  activeSimulation.value = simulationName
  goHome()
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  document.documentElement.className = isDark.value ? 'dark' : ''
}

const toggleLanguage = () => {
  const currentLocale = getLocale()
  const newLocale = currentLocale === 'zh-CN' ? 'en-US' : 'zh-CN'
  setLocale(newLocale)
}

const loadAvailableSimulations = async () => {
  try {
    const response = await fetch('/api/ai_system/list_projects')
    const data = await response.json()
    
    if (data.projects) {
      const projectNames = data.projects.map(p => p.name)
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
/* 全局布局 */
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f2f5f9;
  color: #303133;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  overflow: hidden;
}

/* 高级顶部导航栏 */
.premium-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 64px;
  padding: 0 24px;
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  z-index: 100;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background-color 0.2s;
}

.logo-area:hover {
  background-color: #f5f7fa;
}

.logo-icon {
  font-size: 28px;
}

.app-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(120deg, #409eff, #36cfc9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 0.5px;
}

.subpage-nav {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nav-divider {
  height: 24px;
  margin: 0 8px;
}

.current-sim-name {
  font-size: 14px;
  font-weight: 600;
  color: #606266;
  background: #f0f2f5;
  padding: 6px 16px;
  border-radius: 20px;
}

.nav-btn-group {
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  border-radius: 20px;
  overflow: hidden;
}

.back-btn {
  margin-left: 8px;
  font-weight: 600;
}

.header-controls {
  display: flex;
  align-items: center;
}

.theme-lang-group {
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  border-radius: 50%;
}

/* 主体容器 */
.main-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  position: relative;
}

/* 高级侧边栏 */
.premium-sidebar {
  width: 280px;
  background: #ffffff;
  border-right: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.02);
  z-index: 10;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 20px 24px 10px;
}

.sidebar-title {
  font-size: 12px;
  font-weight: 700;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.sidebar-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 20px;
}

.sidebar-menu::-webkit-scrollbar {
  width: 4px;
}
.sidebar-menu::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 2px;
}

:deep(.el-menu-item-group__title) {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  padding-left: 12px;
  margin-top: 10px;
}

.sim-item, .creator-item {
  height: 44px;
  line-height: 44px;
  border-radius: 8px;
  margin-bottom: 4px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.sim-item:hover, .creator-item:hover {
  background-color: #f5f7fa;
  transform: translateX(4px);
}

.sidebar-menu .is-active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
}

.menu-item-label {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-left: 8px;
}

/* 内容区 */
.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  transition: padding 0.3s ease;
}

.main-content.is-subpage {
  padding: 0; /* 子页面通常需要全屏控制自己的padding */
  background: #f2f5f9;
}

.page-wrapper {
  padding: 24px;
  height: 100%;
  box-sizing: border-box;
}

/* 运行页面的特殊布局 */
.simulation-full-container {
  display: flex;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

/* 动画效果 */
.slide-left-enter-active,
.slide-left-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-left-enter-from,
.slide-left-leave-to {
  transform: translateX(-100%);
  opacity: 0;
  width: 0 !important;
}

.fade-in {
  animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-5px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 暗黑模式支持 */
.dark {
  background-color: #141414;
  color: #e5eaf3;
}
.dark .premium-header,
.dark .premium-sidebar {
  background: #1d1e1f;
  border-color: #2b2b2c;
}
.dark .current-sim-name {
  background: #2b2b2c;
  color: #a3a6ad;
}
.dark .main-content.is-subpage {
  background: #141414;
}
.dark .sim-item:hover {
  background: #2b2b2c;
}
.dark .sidebar-menu .is-active {
  background: #18222c;
}
</style>