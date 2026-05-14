<template>
  <div class="app-container">
    <header class="app-header premium-header">
      <div class="header-center-cluster">
        <div class="header-block-logo">
          <div class="logo-area" @click="onLogoClick" :title="t('header.topNav.workbench')">
            <div class="logo-icon">🌍</div>
            <h1 class="app-title">{{ t('header.title') }}</h1>
          </div>
        </div>

        <nav
          v-show="showPrimaryTopNav"
          class="primary-top-nav"
          :aria-label="t('header.topNav.aria')"
        >
          <button
            type="button"
            class="ptn-item"
            :class="{ active: primaryView === 'landing' }"
            @click="navigateTo('landing')"
          >
            <el-icon class="ptn-ico"><Reading /></el-icon>
            <span>{{ t('header.topNav.intro') }}</span>
          </button>
          <button
            type="button"
            class="ptn-item"
            :class="{ active: primaryView === 'workbench' }"
            @click="navigateTo('workbench')"
          >
            <el-icon class="ptn-ico"><Odometer /></el-icon>
            <span>{{ t('header.topNav.workbench') }}</span>
          </button>
          <button
            type="button"
            class="ptn-item"
            :class="{ active: primaryView === 'ai' }"
            @click="navigateTo('ai')"
          >
            <el-icon class="ptn-ico"><MagicStick /></el-icon>
            <span>{{ t('header.topNav.ai') }}</span>
          </button>
        </nav>

        <div v-if="isSubPage && primaryView !== 'ai'" class="subpage-nav fade-in">
          <span v-if="primaryView !== 'ai'" class="current-sim-name">
            {{ formatSimulationName(activeSimulation) }}
          </span>

          <el-button-group
            v-if="primaryView === 'workbench' && (showSimulation || showHistory || showAnalyzer)"
            class="nav-btn-group"
          >
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
              @click="openAnalyzer"
              icon="DataAnalysis"
              round
            >
              {{ t('header.nav.analysis') }}
            </el-button>
          </el-button-group>

          <el-button
            v-if="primaryView !== 'ai'"
            class="back-btn"
            icon="Back"
            @click="handleSubBack"
            text
            bg
            round
          >
            {{ t('header.nav.backHome') }}
          </el-button>
        </div>

        <div class="header-cluster-tail">
          <div
            class="locale-segment"
            role="group"
            :aria-label="t('header.localeAria')"
          >
            <button
              type="button"
              class="locale-seg"
              :class="{ active: getLocale() === 'zh-CN' }"
              @click="setLocale('zh-CN')"
            >
              中
            </button>
            <button
              type="button"
              class="locale-seg"
              :class="{ active: getLocale() === 'en-US' }"
              @click="setLocale('en-US')"
            >
              EN
            </button>
          </div>
          <el-button
            class="settings-entry-btn"
            :title="t('settings.open')"
            circle
            @click="showModelSettings = true"
          >
            <el-icon><Setting /></el-icon>
          </el-button>
        </div>
      </div>

      <ModelApiSettings v-model="showModelSettings" @saved="onModelSettingsSaved" />
    </header>

    <div class="main-container">
      <!-- Premium Sidebar (Hidden on subpages) -->
      <transition name="slide-left">
        <aside v-show="primaryView === 'workbench' && !isWorkbenchDeepPage" class="premium-sidebar">
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
      <main
        class="main-content"
        :class="{
          'is-subpage': isSubPage,
          'is-landing': primaryView === 'landing',
          'is-workbench-hub': workbenchHub
        }"
      >
        <transition name="view-fade" mode="out-in">
          <div class="main-view-layer" :key="viewLayerKey">
            <template v-if="primaryView === 'landing'">
              <HomeLanding
                @enter="() => navigateTo('workbench')"
                @enter-ai="() => navigateTo('ai')"
              />
            </template>
            <template v-else-if="primaryView === 'ai'">
              <AISystemCreator
                @back="() => navigateTo('workbench')"
                @simulation-created="handleSimulationCreated"
              />
            </template>
            <template v-else-if="!isSubPage">
              <SimulationDescription
                :config-type="activeSimulation"
                :simulation-label="formatSimulationName(activeSimulation)"
                @start-simulation="startSimulation"
                @view-history="viewHistory"
                @analyze-data="openAnalyzer"
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
          </div>
        </transition>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, provide } from 'vue';
import { Plus, Folder, VideoPlay, List, DataAnalysis, Back, Reading, Odometer, MagicStick, Setting } from '@element-plus/icons-vue';
import './style.css';
import SimulationRunner from './components/SimulationRunner.vue'
import SimulationDescription from './components/SimulationDescription.vue'
import SimulationHistory from './components/SimulationHistory.vue'
import DataAnalyzer from './components/DataAnalyzer.vue'
import AISystemCreator from './components/AISystemCreator.vue'
import HomeLanding from './components/HomeLanding.vue'
import ModelApiSettings from './components/ModelApiSettings.vue'
import { useI18n } from './i18n'
import { ElMessage } from 'element-plus'

const readStoredPrimaryView = () => {
  try {
    const v = sessionStorage.getItem('eco3s_primary_view')
    if (v === 'landing' || v === 'workbench' || v === 'ai') return v
  } catch {
    /* private mode */
  }
  return 'landing'
}

const primaryView = ref(readStoredPrimaryView())

const activeSimulation = ref('default')
const showSimulation = ref(false)
const showHistory = ref(false)
const showAnalyzer = ref(false)
const showModelSettings = ref(false)
const availableSimulations = ref(['default', 'TEOG', 'info_propagation'])

const experimentPrecheckOk = ref(true)
const experimentPrecheckMissing = ref([])

const isWorkbenchDeepPage = computed(
  () => showSimulation.value || showHistory.value || showAnalyzer.value
)

const isSubPage = computed(() => {
  return (
    showSimulation.value ||
    showHistory.value ||
    showAnalyzer.value ||
    primaryView.value === 'ai'
  )
})

const workbenchHub = computed(() => {
  return (
    primaryView.value === 'workbench' &&
    !showSimulation.value &&
    !showHistory.value &&
    !showAnalyzer.value
  )
})

/** Hide Intro / Workbench / AI tabs while the simulation runner is open */
const showPrimaryTopNav = computed(
  () => !(primaryView.value === 'workbench' && (showSimulation.value || showHistory.value || showAnalyzer.value))
)

const viewLayerKey = computed(() => {
  if (primaryView.value === 'landing') return 'layer-landing'
  if (primaryView.value === 'ai') return 'layer-ai'
  if (showSimulation.value) return 'layer-wb-sim'
  if (showHistory.value) return 'layer-wb-hist'
  if (showAnalyzer.value) return 'layer-wb-anlz'
  return `layer-wb-desc-${activeSimulation.value}`
})

const { t, setLocale, getLocale } = useI18n()
provide('useI18n', useI18n)

async function fetchExperimentPrecheck() {
  try {
    const r = await fetch('/api/settings/experiment_precheck')
    if (!r.ok) throw new Error('precheck')
    const d = await r.json()
    experimentPrecheckOk.value = Boolean(d.ok)
    experimentPrecheckMissing.value = Array.isArray(d.missing) ? d.missing : []
  } catch {
    experimentPrecheckOk.value = false
    experimentPrecheckMissing.value = []
  }
}

async function ensureApiKeysForExperiment() {
  await fetchExperimentPrecheck()
  if (experimentPrecheckOk.value) return true
  const names = experimentPrecheckMissing.value.map((m) => m.env || m.provider).join(', ')
  ElMessage({
    message: names ? `${t('settings.precheckMessage')}: ${names}` : t('settings.precheckMessage'),
    type: 'warning',
    duration: 6000,
    showClose: true
  })
  showModelSettings.value = true
  return false
}

function onModelSettingsSaved(precheck) {
  if (precheck && typeof precheck.ok === 'boolean') {
    experimentPrecheckOk.value = precheck.ok
    experimentPrecheckMissing.value = Array.isArray(precheck.missing) ? precheck.missing : []
  } else {
    fetchExperimentPrecheck()
  }
}

provide('ensureApiKeysForExperiment', ensureApiKeysForExperiment)

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

const persistPrimaryView = (view) => {
  try {
    sessionStorage.setItem('eco3s_primary_view', view)
  } catch {
    /* ignore */
  }
}

const navigateTo = (view) => {
  primaryView.value = view
  persistPrimaryView(view)
  goHome()
}

const handleSubBack = () => {
  if (primaryView.value === 'ai') {
    navigateTo('workbench')
  } else {
    goHome()
  }
}

const openAnalyzer = () => {
  showAnalyzer.value = true
  showHistory.value = false
  showSimulation.value = false
}

const onLogoClick = () => {
  navigateTo('workbench')
}

const goHome = () => {
  showSimulation.value = false
  showHistory.value = false
  showAnalyzer.value = false
}

const handleSelect = (index) => {
  if (index === 'ai_creator') {
    navigateTo('ai')
  } else {
    activeSimulation.value = index
    navigateTo('workbench')
  }
}

const startSimulation = () => {
  if (primaryView.value !== 'workbench') {
    primaryView.value = 'workbench'
    persistPrimaryView('workbench')
  }
  showSimulation.value = true
  showHistory.value = false
  showAnalyzer.value = false
}

const viewHistory = () => {
  if (primaryView.value !== 'workbench') {
    primaryView.value = 'workbench'
    persistPrimaryView('workbench')
  }
  showHistory.value = true
  showSimulation.value = false
  showAnalyzer.value = false
}

const handleConfigSaved = () => {
  // 配置保存后的处理逻辑
}

const handleSimulationCreated = (simulationName) => {
  if (!availableSimulations.value.includes(simulationName)) {
    availableSimulations.value.push(simulationName)
  }
  activeSimulation.value = simulationName
  navigateTo('workbench')
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
  fetchExperimentPrecheck()
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

/* 高级顶部导航栏：中间内容居中成组，右侧主题/语言固定 */
.premium-header {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 64px;
  padding: 10px 20px;
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  z-index: 100;
  flex-shrink: 0;
}

.header-center-cluster {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px 24px;
  row-gap: 8px;
  max-width: min(1200px, 100%);
}

.header-block-logo {
  margin-left: -12px;
}

.header-cluster-tail {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-left: 28px;
  flex-shrink: 0;
}

.locale-segment {
  display: inline-flex;
  align-items: center;
  padding: 3px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.18);
  background: linear-gradient(180deg, #ffffff 0%, #f7f8fb 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8), 0 6px 18px rgba(15, 23, 42, 0.08);
  flex-shrink: 0;
}

.locale-seg {
  border: none;
  margin: 0;
  padding: 5px 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1.1;
  border-radius: 999px;
  cursor: pointer;
  background: transparent;
  color: #6b7280;
  font-family: inherit;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.locale-seg:hover {
  color: #111827;
  background: rgba(64, 158, 255, 0.12);
}

.locale-seg.active {
  background: linear-gradient(135deg, #409eff 0%, #36cfc9 100%);
  color: #ffffff;
  box-shadow: 0 6px 14px rgba(64, 158, 255, 0.35);
  transform: translateY(-0.5px);
}

.settings-entry-btn {
  border: 1px solid #dcdfe6;
}

.primary-top-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.ptn-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #606266;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
  white-space: nowrap;
}

.ptn-item:hover {
  background: #f0f2f5;
  color: #303133;
}

.ptn-item.active {
  color: #409eff;
  background: linear-gradient(120deg, rgba(64, 158, 255, 0.14), rgba(54, 207, 201, 0.1));
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.2);
}

.ptn-ico {
  font-size: 16px;
}

@media (max-width: 960px) {
  .header-cluster-tail {
    margin-left: 12px;
  }

  .ptn-item span {
    display: none;
  }
  .ptn-item {
    padding: 8px 10px;
  }
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

/* 主体容器 */
.main-container {
  display: flex;
  flex: 1;
  min-height: 0;
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
  min-height: 0;
  overflow-y: auto;
  padding: 24px;
  transition: padding 0.3s ease;
}

.main-content.is-subpage {
  padding: 0;
  background: #f2f5f9;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.main-content.is-subpage .main-view-layer {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content.is-landing {
  padding: 0;
  background: linear-gradient(180deg, #eef4ff 0%, #f5f7fb 45%, #f0fdfa 100%);
}

.main-content.is-workbench-hub {
  padding: 20px 24px 28px;
  background: linear-gradient(180deg, #eef4ff 0%, #f2f5f9 38%, #f2f5f9 100%);
}

.main-view-layer {
  min-height: 100%;
}

.view-fade-enter-active,
.view-fade-leave-active {
  transition: opacity 0.22s ease;
}

.view-fade-enter-from,
.view-fade-leave-to {
  opacity: 0;
}

.page-wrapper {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 24px;
  box-sizing: border-box;
  overflow: hidden;
}

/* 运行页面的特殊布局 */
.simulation-full-container {
  display: flex;
  flex: 1;
  min-height: 0;
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
</style>