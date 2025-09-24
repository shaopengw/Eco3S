<template>
  <div class="simulation-history">
    <div class="header">
      <h2>模拟历史</h2>
      <el-button @click="$emit('back-to-description')" type="text">
        返回描述页面
      </el-button>
    </div>

    <div class="history-content">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="日志文件" name="logs">
          <div class="history-list">
            <el-collapse v-model="activeNames">
              <el-collapse-item v-for="(logs, timestamp) in groupedLogs" :key="timestamp" :title="formatTimestamp(timestamp)" :name="timestamp">
                <div class="log-files">
                  <div v-for="log in logs" :key="log.path" class="log-file">
                    <el-button @click="viewLog(log.path)" text>
                      {{ log.name }}
                    </el-button>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
          <el-dialog v-model="logDialogVisible" title="日志内容" width="80%" class="log-dialog">
            <pre class="log-content">{{ selectedLogContent }}</pre>
          </el-dialog>
        </el-tab-pane>
        
        <el-tab-pane label="结果图表" name="plots">
          <div class="history-list">
            <el-collapse v-model="activePlotNames">
              <el-collapse-item v-for="(plots, timestamp) in groupedPlots" :key="timestamp" :title="formatTimestamp(timestamp)" :name="timestamp">
                <div class="plot-grid">
                  <div v-for="plot in plots" :key="plot.path" class="plot-item">
                    <div class="plot-title">{{ getPlotTitle(plot.name) }}</div>
                    <el-image 
                      :src="`/api/${plot.path}`"
                      :preview-src-list="[`/api/${plot.path}`]"
                      fit="contain"
                    />
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'

const props = defineProps({
  configType: {
    type: String,
    required: true
  }
})

const activeTab = ref('logs')
const activeNames = ref([])
const activePlotNames = ref([])
const logDialogVisible = ref(false)
const selectedLogContent = ref('')
const historyData = ref({
  logs: [],
  plots: []
})

// 按时间戳分组的日志文件
const groupedLogs = computed(() => {
  const groups = {}
  historyData.value.logs.forEach(log => {
    const timestamp = log.path.match(/\d{8}_\d{6}/)?.[0]
    if (timestamp) {
      if (!groups[timestamp]) {
        groups[timestamp] = []
      }
      groups[timestamp].push(log)
    }
  })
  return groups
})

// 按时间戳分组的图表文件
const groupedPlots = computed(() => {
  const groups = {}
  historyData.value.plots.forEach(plot => {
    const timestamp = plot.path.match(/\d{8}_\d{6}/)?.[0]
    if (timestamp) {
      if (!groups[timestamp]) {
        groups[timestamp] = []
      }
      groups[timestamp].push(plot)
    }
  })
  return groups
})

const formatTimestamp = (timestamp) => {
  const year = timestamp.slice(0, 4)
  const month = timestamp.slice(4, 6)
  const day = timestamp.slice(6, 8)
  const hour = timestamp.slice(9, 11)
  const minute = timestamp.slice(11, 13)
  const second = timestamp.slice(13, 15)
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}

const getPlotTitle = (filename) => {
  const plotType = filename.split('_')[0]
  const titleMap = {
    'rebellions': '叛乱次数',
    'unemployment': '失业率',
    'population': '人口数量',
    'government': '政府预算',
    'rebellion': '叛乱强度',
    'average': '平均满意度',
    'tax': '税率',
    'river': '河流通航性',
    'gdp': 'GDP',
    'urban': '城市规模',
    'conversation': '对话量',
    'knowledge': '知识问答准确率',
    'incentive': '激励性选择'
  }
  return titleMap[plotType] || '结果图表'
}

const viewLog = async (logPath) => {
  try {
    const response = await fetch(`/api/log/${logPath}`)
    const content = await response.text()
    selectedLogContent.value = content
    logDialogVisible.value = true
  } catch (error) {
    console.error('加载日志内容失败:', error)
  }
}

const loadHistoryData = async () => {
  try {
    const response = await fetch(`/api/history/${props.configType}`)
    const data = await response.json()
    historyData.value = data
  } catch (error) {
    console.error('加载历史数据失败:', error)
  }
}

onMounted(() => {
  loadHistoryData()
})
</script>

<style scoped>
.simulation-history {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color);
  border-radius: 8px;
  overflow: hidden;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.history-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.history-list {
  margin-top: 16px;
}

.log-files {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-file {
  display: flex;
  align-items: center;
}

.plot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
  padding: 16px;
}

.plot-item {
  background-color: var(--el-bg-color-page);
  padding: 16px;
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
}

.plot-title {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 12px;
  text-align: center;
}

.log-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.log-content {
  padding: 16px;
  background-color: var(--el-bg-color-page);
  color: var(--el-text-color-regular);
  font-family: monospace;
  white-space: pre-wrap;
  overflow-x: auto;
  max-height: 70vh;
}
</style>