<template>
  <div class="simulation-dashboard">
    <!-- Header -->
    <header class="dashboard-header">
      <div class="header-left">
        <div class="title-group">
          <h2 class="title">{{ t('simulationRunner.title') }}</h2>
          <el-tag :type="isRunning ? 'success' : 'info'" effect="light" class="status-tag" round>
            <span v-if="isRunning" class="status-dot"></span>
            {{ isRunning ? t('simulationRunner.running') : t('simulationRunner.ready') }}
          </el-tag>
        </div>
      </div>
      <div class="header-right">
        <el-button
          class="config-btn"
          icon="Setting"
          size="large"
          @click="showConfigDrawer = true"
          round
        >
          {{ t('simulationRunner.config') || '系统配置' }}
        </el-button>
        <el-button
          type="primary"
          class="run-btn"
          size="large"
          :loading="isRunning"
          @click="runSimulation"
          round
        >
          {{ isRunning ? t('simulationRunner.running') : t('simulationRunner.runButton') }}
        </el-button>
      </div>
    </header>

    <!-- Main Content -->
    <div class="dashboard-content">
      
      <!-- Left Column: Map & Terminal -->
      <div class="left-col">
        <!-- Map Card -->
        <div class="card map-card">
          <div class="card-header">
            <h3><span class="icon">🗺️</span> {{ t('simulationRunner.mapTitle') }}</h3>
            <div class="card-actions">
              <div class="resident-count cursor-pointer" v-if="residentNodes.length" @click="showResidentListDrawer = true">
                <span class="pulse-dot"></span>
                {{ t('simulationRunner.activeResidents') }}: <strong>{{ residentNodes.length }}</strong>
              </div>
            </div>
          </div>
          <div class="card-body map-wrapper">
            <MapDisplay
              ref="mapDisplayRef"
              :nodes="residentNodes"
              :towns-data="townsData"
              :theme="configType"
              @node-click="onNodeClick"
            />
          </div>
        </div>
      </div>

      <!-- Right Column: Charts -->
      <div class="right-col">
        <!-- Terminal Card -->
        <div class="card terminal-card">
          <div class="card-header">
            <h3><span class="icon">💻</span> {{ t('simulationRunner.logTitle') }}</h3>
          </div>
          <div class="card-body terminal-wrapper" ref="outputPanel">
            <div class="terminal-content">
              <pre v-if="output">{{ output }}</pre>
              <div v-else class="empty-terminal">
                <span class="blinking-cursor">_</span> {{ t('simulationRunner.waitingCmd') }}
              </div>
            </div>
          </div>
        </div>

        <div class="card charts-card">
          <div class="card-header">
            <h3><span class="icon">📈</span> {{ t('simulationRunner.analysisTitle') }}</h3>
          </div>
          <div class="card-body charts-wrapper">
            <div v-if="Object.keys(chartData).length === 0 && plotPaths.length === 0" class="empty-charts">
              <el-empty :description="t('simulationRunner.noChartData')" :image-size="120" />
            </div>
            
            <div class="charts-grid">
              <!-- Real-time Charts -->
              <template v-if="Object.keys(chartData).length > 0">
                <div v-for="(chart, key) in chartData" :key="key" class="chart-item">
                  <Line
                    v-if="chart.datasets[0].data.length > 0"
                    :data="chart"
                    :options="getChartOptions(getChartTitle(key))"
                  />
                </div>
              </template>
              
              <!-- Legacy Plot Images -->
              <template v-if="plotPaths.length > 0">
                <div v-for="(path, index) in plotPaths" :key="'plot-' + index" class="plot-item">
                  <el-image
                    :src="`/api/${path.replace(/\\/g, '/')}`"
                    :alt="t('simulationRunner.results') + ' ' + (index + 1)"
                    :preview-src-list="[`/api/${path.replace(/\\/g, '/')}`]"
                    fit="contain"
                  />
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- Node Detail Dialog -->
    <el-dialog v-model="showNodeDialog" :title="selectedNodeTitle" width="550px" class="custom-dialog">
      <div v-if="selectedNode" class="node-detail">
        <el-tabs v-model="activeTab" class="resident-tabs">
          <el-tab-pane :label="t('simulationRunner.basicInfo') || '基本信息'" name="basic">
            <el-descriptions :column="1" border class="detail-descriptions">
              <el-descriptions-item :label="t('simulationRunner.residentId')">
                <span class="detail-value">#{{ selectedNode.resident_id }}</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('simulationRunner.town')">
                <span class="detail-value">{{ selectedNode.town || t('simulationRunner.unknown') }}</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('simulationRunner.job')">
                <el-tag size="small" effect="dark" :type="getJobTagType(selectedNode.job)">
                  {{ selectedNode.job || t('simulationRunner.none') }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('simulationRunner.employmentStatus')">
                <span :class="['status-text', selectedNode.employed ? 'success' : 'danger']">
                  {{ selectedNode.employed ? t('simulationRunner.employed') : t('simulationRunner.unemployed') }}
                </span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('simulationRunner.income')">
                <span class="money-text">{{ selectedNode.income ?? t('simulationRunner.unknown') }}</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('simulationRunner.satisfaction')">
                <el-progress 
                  :percentage="selectedNode.satisfaction != null ? Number(selectedNode.satisfaction.toFixed(1)) : 0" 
                  :color="getSatisfactionColor" 
                  :stroke-width="10"
                />
              </el-descriptions-item>
              <el-descriptions-item :label="t('simulationRunner.healthIndex')">
                <el-progress 
                  :percentage="selectedNode.health_index != null ? Number(selectedNode.health_index) : 0" 
                  status="success" 
                  :stroke-width="10"
                />
              </el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <el-tab-pane :label="t('simulationRunner.yearlyDecisions') || '历年决策'" name="decisions">
            <div class="decision-timeline-container">
              <el-timeline v-if="selectedNode.yearly_decisions && selectedNode.yearly_decisions.length > 0" class="decision-timeline">
                <el-timeline-item 
                  v-for="(decision, index) in selectedNode.yearly_decisions.slice().reverse()" 
                  :key="index"
                  :timestamp="decision.year + '年'"
                  placement="top"
                  :color="getDecisionColor(decision.select)"
                  size="large"
                >
                  <el-card class="decision-card" shadow="hover">
                    <div class="decision-header">
                      <span class="decision-action">{{ decision.action || '未知决策' }}</span>
                      <el-tag size="small" type="info" v-if="decision.desired_job">{{ decision.desired_job }}</el-tag>
                    </div>
                    <div class="decision-reason" v-if="decision.reason">
                      <span class="label">思考：</span>{{ decision.reason }}
                    </div>
                    <div class="decision-speech" v-if="decision.speech">
                      <span class="label">发言：</span>"<em>{{ decision.speech }}</em>"
                    </div>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
              <el-empty v-else :description="t('simulationRunner.noData') || '暂无历年决策数据'" :image-size="60" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <el-button @click="showNodeDialog = false" round>{{ t('simulationRunner.close') }}</el-button>
      </template>
    </el-dialog>

    <!-- Config Drawer -->
    <el-drawer
      v-model="showConfigDrawer"
      :title="t('configEditor.title') || '配置编辑器'"
      direction="rtl"
      size="450px"
      class="config-drawer"
    >
      <ConfigEditor
        :config-type="configType"
        @config-saved="handleConfigSaved"
      />
    </el-drawer>

    <!-- Resident List Drawer -->
    <el-drawer
      v-model="showResidentListDrawer"
      title="居民列表"
      direction="ltr"
      size="350px"
      class="resident-list-drawer"
    >
      <div class="resident-list-container">
        <el-input
          v-model="searchResidentQuery"
          placeholder="搜索居民ID或职业..."
          prefix-icon="Search"
          clearable
          class="resident-search"
        />
        <el-scrollbar>
          <div class="resident-items">
            <div 
              v-for="node in filteredResidentNodes" 
              :key="node.resident_id" 
              class="resident-list-item"
              @click="highlightResidentOnMap(node)"
            >
              <div class="item-header">
                <span class="resident-id">#{{ node.resident_id }}</span>
                <el-tag size="small" effect="dark" :type="getJobTagType(node.job)">
                  {{ node.job || '无业' }}
                </el-tag>
              </div>
              <div class="item-body">
                <span class="town-info"><el-icon><Location /></el-icon> {{ node.town || '未知城镇' }}</span>
                <span class="sat-info" :style="{ color: getSatisfactionColor(node.satisfaction) }">
                  满意度: {{ node.satisfaction != null ? Number(node.satisfaction.toFixed(1)) : 0 }}%
                </span>
              </div>
            </div>
            <el-empty v-if="filteredResidentNodes.length === 0" description="未找到匹配的居民" :image-size="60" />
          </div>
        </el-scrollbar>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onUnmounted, onMounted, reactive, inject, nextTick } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import MapDisplay from './MapDisplay.vue'
import ConfigEditor from './ConfigEditor.vue'
import { Setting, Search, Location } from '@element-plus/icons-vue'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const useI18nFunc = inject('useI18n')
const { t } = useI18nFunc()

const props = defineProps({
  configType: {
    type: String,
    required: true
  }
})

const isRunning = ref(false)
const output = ref('')
const processId = ref(null)
const statusCheckInterval = ref(null)
const outputPanel = ref(null)
const plotPaths = ref([])
const residentNodes = ref([])
const townsData = ref(null)
const showNodeDialog = ref(false)
const selectedNode = ref(null)
const selectedNodeTitle = ref('')
const activeTab = ref('basic')
const showConfigDrawer = ref(false)
const showResidentListDrawer = ref(false)
const searchResidentQuery = ref('')
const mapDisplayRef = ref(null)

import { computed } from 'vue'

const filteredResidentNodes = computed(() => {
  if (!searchResidentQuery.value) return residentNodes.value
  const query = searchResidentQuery.value.toLowerCase()
  return residentNodes.value.filter(node => 
    String(node.resident_id).toLowerCase().includes(query) ||
    (node.job && node.job.toLowerCase().includes(query)) ||
    (node.town && node.town.toLowerCase().includes(query))
  )
})

const highlightResidentOnMap = (node) => {
  // 当点击列表中的居民时，可以高亮显示并定位地图
  if (mapDisplayRef.value) {
    mapDisplayRef.value.highlightResident(node.resident_id)
  }
  showResidentListDrawer.value = false
}

const handleConfigSaved = () => {
  showConfigDrawer.value = false
  // 可以根据需要添加其他刷新逻辑
}

const scrollToBottom = () => {
  nextTick(() => {
    if (outputPanel.value) {
      outputPanel.value.scrollTop = outputPanel.value.scrollHeight
    }
  })
}

const runSimulation = async () => {
  try {
    isRunning.value = true
    output.value = ''
    residentNodes.value = []
    Object.keys(chartData).forEach(key => {
      chartData[key].labels = []
      chartData[key].datasets[0].data = []
    })

    const response = await fetch(`/api/run/${props.configType}`)
    const data = await response.json()

    if (data.process_id) {
      processId.value = data.process_id
      startStatusCheck()
    }
  } catch (error) {
    console.error(t('simulationRunner.startFailed') + ':', error)
    isRunning.value = false
  }
}

const chartData = reactive({})

const getChartOptions = (title) => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: {
    duration: 400,
    easing: 'easeOutQuart'
  },
  interaction: {
    mode: 'index',
    intersect: false,
  },
  plugins: {
    title: {
      display: true,
      text: title,
      color: '#303133',
      font: {
        size: 15,
        weight: '600',
        family: "'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif"
      },
      padding: { top: 10, bottom: 20 }
    },
    legend: {
      display: false
    },
    tooltip: {
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      titleColor: '#303133',
      bodyColor: '#606266',
      borderColor: '#ebeef5',
      borderWidth: 1,
      padding: 10,
      boxPadding: 4,
      usePointStyle: true
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      grid: {
        color: '#f0f2f5',
        drawBorder: false,
      },
      ticks: { color: '#909399' }
    },
    x: {
      grid: {
        display: false
      },
      ticks: { color: '#909399', maxTicksLimit: 10 }
    }
  }
})

const updateCharts = (data) => {
  if (!data) return
  if (!data.years || !Array.isArray(data.years)) return;

  Object.entries(data).forEach(([key, values], index) => {
    if (!Array.isArray(values) || key === 'years') return;

    chartData[key] = {
      title: getChartTitle(key),
      labels: [...data.years],
      datasets: [{
        label: getChartTitle(key),
        data: [...values],
        borderColor: getChartColor(index),
        backgroundColor: getChartColor(index, 0.15),
        borderWidth: 2,
        pointBackgroundColor: '#ffffff',
        pointBorderColor: getChartColor(index),
        pointBorderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
        tension: 0.3,
        fill: true
      }]
    }
  });
}

const fetchResidentStates = async () => {
  if (!processId.value) return
  try {
    const response = await fetch(`/api/resident_states/${processId.value}`)
    const data = await response.json()
    if (data.residents && Array.isArray(data.residents)) {
      residentNodes.value = data.residents
    }
  } catch (error) {
    console.error('获取居民位置失败:', error)
  }
}

const fetchTownsData = async () => {
  try {
    const response = await fetch(`/api/towns/${props.configType}`)
    if (response.ok) {
      townsData.value = await response.json()
    }
  } catch (error) {
    console.error('获取城镇数据失败:', error)
  }
}

onMounted(() => {
  fetchTownsData()
})

const startStatusCheck = () => {
  statusCheckInterval.value = setInterval(async () => {
    try {
      const response = await fetch(`/api/simulation_status/${processId.value}`)
      const data = await response.json()

      if (data.output) {
        output.value += data.output
        scrollToBottom()
      }
      if (data.running_data && Object.keys(data.running_data).length > 0) {
        updateCharts(data.running_data)
      }

      await fetchResidentStates()
      
      // Update selected node if dialog is open
      if (showNodeDialog.value && selectedNode.value) {
        const updatedNode = residentNodes.value.find(n => n.resident_id === selectedNode.value.resident_id)
        if (updatedNode) {
          selectedNode.value = updatedNode
        }
      }

      if (data.status === 'completed' || data.status === 'error') {
        isRunning.value = false
        clearInterval(statusCheckInterval.value)
        if (Object.keys(data.running_data || {}).length === 0) {
          plotPaths.value = data.plot_paths || []
        }
        await fetchResidentStates()
      }
    } catch (error) {
      console.error('检查状态失败:', error)
      isRunning.value = false
      clearInterval(statusCheckInterval.value)
    }
  }, 1000)
}

const getChartTitle = (key) => {
  const i18nKey = `charts.${key}`
  const translated = t(i18nKey)
  // 检查是否翻译成功（有些 i18n 配置失败时返回原文 key）
  if (translated && translated !== i18nKey && !translated.includes('charts.')) {
    return translated
  }
  return key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')
}

const getChartColor = (index, alpha = 1) => {
  const colorPalette = [
    [64, 158, 255],  // Primary blue
    [103, 194, 58],  // Success green
    [230, 162, 60],  // Warning orange
    [245, 108, 108], // Danger red
    [142, 113, 199], // Purple
    [234, 100, 169], // Pink
    [32, 178, 170],  // Light sea green
    [250, 140, 22],  // Sunset orange
  ]
  const color = colorPalette[index % colorPalette.length]
  return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`
}

const onNodeClick = (node) => {
  // Update selected node ensuring we get the latest data
  const latestNode = residentNodes.value.find(n => n.resident_id === node.resident_id) || node
  selectedNode.value = latestNode
  selectedNodeTitle.value = t('simulationRunner.residentArchive').replace('{id}', latestNode.resident_id)
  activeTab.value = 'basic'
  showNodeDialog.value = true
}

const formatMemoryContent = (content) => {
  if (!content) return ''
  // 尝试解析 JSON
  try {
    const cleaned = content.replace(/^```json\s*|\s*```$/g, '').trim()
    const data = JSON.parse(cleaned)
    let html = '<div class="decision-json">'
    if (data.reason) html += `<div class="decision-item"><span class="decision-label">${t('simulationRunner.reason') || '思考'}:</span> ${data.reason}</div>`
    if (data.select) html += `<div class="decision-item"><span class="decision-label">${t('simulationRunner.decision') || '决策'}:</span> 选项 ${data.select}</div>`
    if (data.desired_job) html += `<div class="decision-item"><span class="decision-label">${t('simulationRunner.desiredJob') || '期望职业'}:</span> ${data.desired_job}</div>`
    if (data.speech) html += `<div class="decision-item"><span class="decision-label">${t('simulationRunner.speech') || '言论'}:</span> "<em>${data.speech}</em>"</div>`
    html += '</div>'
    return html
  } catch (e) {
    // 替换换行符为 <br>
    return content.replace(/\n/g, '<br>')
  }
}

const getJobTagType = (job) => {
  const map = { '农民': 'success', '工人': 'info', '商人': 'warning', '叛军': 'danger' }
  return map[job] || ''
}

const getDecisionColor = (selectValue) => {
  // 根据不同的选项值返回不同的颜色
  const selectStr = String(selectValue);
  const colorMap = {
    '1': '#f56c6c', // 加入叛军（红色）
    '2': '#e6a23c', // 迁移（橙色）
    '3': '#67c23a', // 工作（绿色）
  };
  return colorMap[selectStr] || '#409eff'; // 默认蓝色
}

const getSatisfactionColor = (percentage) => {
  if (percentage < 40) return '#f56c6c'
  if (percentage < 70) return '#e6a23c'
  return '#67c23a'
}

onUnmounted(() => {
  if (statusCheckInterval.value) {
    clearInterval(statusCheckInterval.value)
  }
})
</script>

<style scoped>
/* 整体布局 */
.simulation-dashboard {
  height: 100%;
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #f2f5f9;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  overflow: hidden;
}

/* 头部 */
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  letter-spacing: 0.5px;
}

.status-tag {
  font-weight: 500;
  border: none;
}

.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #67c23a;
  margin-right: 6px;
  box-shadow: 0 0 6px #67c23a;
  animation: blink 1.5s infinite;
}

@keyframes blink {
  0% { opacity: 1; }
  50% { opacity: 0.4; }
  100% { opacity: 1; }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.config-btn {
  font-weight: 600;
  padding: 12px 24px;
  color: #606266;
  border: 1px solid #dcdfe6;
  background: #ffffff;
  transition: all 0.3s;
}
.config-btn:hover {
  color: #409eff;
  border-color: #c6e2ff;
  background: #ecf5ff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.1);
}

.run-btn {
  font-weight: 600;
  padding: 12px 32px;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
  transition: all 0.3s;
}
.run-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.4);
}

/* 主体内容网格 */
.dashboard-content {
  flex: 1;
  display: grid;
  grid-template-columns: 1.5fr 1fr; /* 左侧更宽，右侧稍窄 */
  gap: 24px;
  padding: 24px 32px;
  overflow: hidden;
}

.left-col, .right-col {
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow: hidden;
}

/* 通用卡片样式 */
.card {
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #ebeef5;
}

.card-header {
  padding: 16px 24px;
  border-bottom: 1px solid #f0f2f5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fafafa;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon {
  font-size: 18px;
}

.card-body {
  padding: 20px;
  flex: 1;
  overflow: hidden;
}

/* 左侧：地图 */
.map-card {
  flex: 1; /* 地图填满左侧 */
}
.map-wrapper {
  padding: 0; /* 地图填满卡片 */
  position: relative;
}
.resident-count {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(103, 194, 58, 0.1);
  color: #67c23a;
  border-radius: 20px;
  font-size: 13px;
}
.cursor-pointer {
  cursor: pointer;
  transition: background-color 0.2s;
}
.cursor-pointer:hover {
  background: rgba(103, 194, 58, 0.2);
}

.resident-list-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.resident-search {
  padding: 0 16px 12px;
  border-bottom: 1px solid #ebeef5;
}

.resident-items {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.resident-list-item {
  padding: 12px;
  border-radius: 8px;
  background-color: #f8f9fa;
  border: 1px solid #ebeef5;
  cursor: pointer;
  transition: all 0.2s ease;
}

.resident-list-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #c6e2ff;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.resident-id {
  font-weight: 700;
  color: #303133;
  font-size: 14px;
}

.item-body {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.town-info {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #606266;
}

.sat-info {
  font-weight: 600;
}
.resident-count strong {
  color: #409eff;
}
.pulse-dot {
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(64, 158, 255, 0); }
  100% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0); }
}

/* 右侧：终端日志与图表 */
.terminal-card {
  flex: 0 0 220px; /* 固定高度，不占用过多空间 */
}
.terminal-wrapper {
  padding: 12px;
  background: #1e1e1e;
  border-radius: 0 0 16px 16px;
}
.terminal-content {
  height: 100%;
  overflow-y: auto;
  color: #a6e22e;
  font-family: "Fira Code", Consolas, Monaco, "Andale Mono", "Ubuntu Mono", monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 8px;
}
.terminal-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.empty-terminal {
  color: #888;
  display: flex;
  align-items: center;
}
.blinking-cursor {
  font-weight: bold;
  animation: blink 1s step-end infinite;
}
/* 自定义滚动条 - 终端 */
.terminal-content::-webkit-scrollbar {
  width: 6px;
}
.terminal-content::-webkit-scrollbar-thumb {
  background: #444;
  border-radius: 3px;
}

/* 图表区域 */
.charts-card {
  flex: 1;
  min-height: 0; /* 防止内容溢出 */
}
.charts-wrapper {
  overflow-y: auto;
  padding: 16px;
}
.charts-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
}
.chart-item {
  height: 280px;
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.02);
  border: 1px solid #ebeef5;
  transition: transform 0.3s, box-shadow 0.3s;
}
.chart-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
}

.empty-charts {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 自定义滚动条 - 亮色 */
.charts-wrapper::-webkit-scrollbar {
  width: 6px;
}
.charts-wrapper::-webkit-scrollbar-track {
  background: transparent;
}
.charts-wrapper::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}
.charts-wrapper::-webkit-scrollbar-thumb:hover {
  background: #c0c4cc;
}

/* 详情弹窗样式 */
.detail-descriptions {
  margin-top: 10px;
}
.detail-value {
  font-weight: 600;
  color: #303133;
}
.status-text {
  font-weight: bold;
}
.status-text.success { color: #67c23a; }
.status-text.danger { color: #f56c6c; }
.money-text {
  color: #e6a23c;
  font-family: monospace;
  font-weight: 600;
  font-size: 14px;
}

/* 居民详情 Tabs */
.resident-tabs {
  margin-top: -10px;
}
.memory-list-container, .longterm-list-container {
  max-height: 400px;
  overflow-y: auto;
  padding-right: 8px;
}
.memory-list-container::-webkit-scrollbar, .longterm-list-container::-webkit-scrollbar {
  width: 6px;
}
.memory-list-container::-webkit-scrollbar-thumb, .longterm-list-container::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}
.memory-item {
  padding: 12px;
  margin-bottom: 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
  background: #f8f9fa;
  border-left: 3px solid #909399;
}
.memory-item.assistant {
  background: #f0f9eb;
  border-left-color: #67c23a;
}
.memory-item.user {
  background: #ecf5ff;
  border-left-color: #409eff;
}
.memory-role {
  font-weight: bold;
  margin-bottom: 6px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 6px;
}
.role-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.memory-item.assistant .memory-role { color: #67c23a; }
.memory-item.user .memory-role { color: #409eff; }
.memory-content {
  color: #303133;
}
.longterm-item {
  padding: 12px;
  margin-bottom: 12px;
  border-radius: 8px;
  background: #fdf6ec;
  border: 1px solid #e1f3d8;
  color: #303133;
  font-size: 13px;
  line-height: 1.6;
}

.decision-timeline-container {
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.decision-timeline {
  padding-left: 4px;
}

.decision-card {
  margin-bottom: 0;
}

.decision-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.decision-action {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.decision-reason, .decision-speech {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  margin-top: 6px;
}

.decision-reason .label, .decision-speech .label {
  font-weight: 600;
  color: #909399;
}

.decision-speech em {
  color: #2b579a;
  font-style: italic;
}

:deep(.el-timeline-item__timestamp) {
  font-size: 14px;
  font-weight: bold;
  color: #409eff;
}

/* 动态决策 HTML 样式 */
:deep(.decision-item) {
  margin-bottom: 4px;
}
:deep(.decision-label) {
  font-weight: 600;
  color: #606266;
}

/* Config Drawer Styling */
:deep(.config-drawer .el-drawer__header) {
  margin-bottom: 0;
  padding: 20px 24px;
  border-bottom: 1px solid #ebeef5;
  font-weight: 600;
  color: #303133;
}
:deep(.config-drawer .el-drawer__body) {
  padding: 0;
  overflow: hidden;
}
:deep(.config-drawer .config-editor) {
  height: 100%;
  border: none;
  box-shadow: none;
}
</style>