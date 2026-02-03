<template>
  <div class="simulation-runner">
    <div class="header">
      <h2>{{ t('simulationRunner.title') }}</h2>
      <el-button @click="$emit('back-to-description')" type="text">
        {{ t('simulationRunner.backButton') }}
      </el-button>
    </div>

    <div class="control-panel">
      <el-button
        type="primary"
        :loading="isRunning"
        @click="runSimulation"
      >
        {{ isRunning ? t('simulationRunner.running') : t('simulationRunner.runButton') }}
      </el-button>
    </div>

    <div class="content-scroll-container">
      <div class="output-panel" ref="outputPanel">
        <pre>{{ output }}</pre>
      </div>

      <div class="results-panel">
        <h3>{{ t('simulationRunner.results') }}</h3>
        <div v-if="Object.keys(chartData).length > 0" class="charts-container">
          <div v-for="(chart, key) in chartData" :key="key" class="chart-item">
            <Line
              v-if="chart.datasets[0].data.length > 0"
              :data="chart"
              :options="getChartOptions(chart.title)"
            />
          </div>
        </div>
        <div v-else-if="plotPaths.length > 0" class="plots-container">
          <div v-for="(path, index) in plotPaths" :key="index" class="plot-item">
            <el-image
              :src="`/api/${path.replace(/\\/g, '/')}`"
              :alt="'结果图表 ' + (index + 1)"
              :preview-src-list="[`/api/${path.replace(/\\/g, '/')}`]"
              fit="contain"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted, reactive, inject } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'

// 注册 Chart.js 组件
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
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

const runSimulation = async () => {
  try {
    isRunning.value = true
    output.value = ''
    // 重置图表数据
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

// 图表数据结构重构
const chartData = reactive({})

// 图表基础配置
const getChartOptions = (title) => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: {
    duration: 300
  },
  plugins: {
    title: {
      display: true,
      text: title,
      font: {
        size: 16,
        weight: 'bold'
      }
    },
    legend: {
      display: false  // 隐藏数据集标签
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      grid: {
        drawBorder: false,
        color: 'rgba(0, 0, 0, 0.1)'
      }
    },
    x: {
      grid: {
        display: false
      }
    }
  }
})

const updateCharts = (data) => {
  if (!data) return
  console.log('接收到的数据:', data);
  
  // 确保数据格式正确
  if (!data.years || !Array.isArray(data.years)) return;
  
  // 遍历数据并更新或创建对应的图表
  Object.entries(data).forEach(([key, values], index) => {
    // 跳过非数组类型的数据和years键
    if (!Array.isArray(values) || key === 'years') return;

    // 每次都重新创建图表数据
    chartData[key] = {
      title: getChartTitle(key),
      labels: [...data.years],
      datasets: [{
        data: [...values],
        borderColor: getChartColor(index),
        backgroundColor: getChartColor(index, 0.2),
        tension: 0.1,
        fill: true
      }]
    }
  });
}

const startStatusCheck = () => {
  statusCheckInterval.value = setInterval(async () => {
    try {
      const response = await fetch(`/api/simulation_status/${processId.value}`)
      const data = await response.json()
      
      if (data.output) {
        output.value += data.output
        if (outputPanel.value) {
          outputPanel.value.scrollTop = outputPanel.value.scrollHeight
        }
      }
      if (data.running_data && Object.keys(data.running_data).length > 0) {
        console.log('接收到实时数据:', data.running_data);
        updateCharts(data.running_data)
      }
      
      if (data.status === 'completed' || data.status === 'error') {
        isRunning.value = false
        clearInterval(statusCheckInterval.value)
        if (Object.keys(data.running_data || {}).length === 0) {
          plotPaths.value = data.plot_paths || []
        }
      }
    } catch (error) {
      console.error('检查状态失败:', error)
      isRunning.value = false
      clearInterval(statusCheckInterval.value)
    }
  }, 1000)  // 每秒检查一次状态
}

// 获取图表标题 - 首字母大写
const getChartTitle = (key) => {
  return key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')
}

// 动态生成图表颜色
const getChartColor = (index, alpha = 1) => {
  const colorPalette = [
    [75, 192, 192],    // 青色
    [255, 99, 132],    // 红色
    [153, 102, 255],   // 紫色
    [255, 159, 64],    // 橙色
    [54, 162, 235],    // 蓝色
    [255, 206, 86],    // 黄色
    [75, 192, 75],     // 绿色
    [235, 54, 162],    // 粉色
    [192, 75, 192],    // 品红
    [162, 235, 54]     // 黄绿
  ]
  const color = colorPalette[index % colorPalette.length]
  return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`
}

onUnmounted(() => {
  if (statusCheckInterval.value) {
    clearInterval(statusCheckInterval.value)
  }
})
</script>

<style scoped>
.simulation-runner {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color);
  border-radius: 8px;
  overflow: hidden;
}

.content-scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.output-panel {
  background-color: var(--el-bg-color-page);
  border-radius: 4px;
  padding: 16px;
  margin-bottom: 16px;
  max-height: 400px;
  min-height: 200px;
  overflow-y: auto;
  flex-shrink: 0;
}

.results-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-top: 1px solid var(--el-border-color-light);
  padding-top: 16px;
}

.charts-container {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  padding: 8px;
}

.plots-container {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  padding: 8px;
}

.chart-item {
  background-color: var(--el-bg-color-page);
  padding: 16px;
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
  height: 300px;
  min-width: 400px;
  flex: 1;
}

.plot-item {
  background-color: var(--el-bg-color-page);
  padding: 16px;
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
  height: 300px;
  min-width: 400px;
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}

.plot-item .el-image {
  max-width: 100%;
  max-height: 100%;
}
</style>