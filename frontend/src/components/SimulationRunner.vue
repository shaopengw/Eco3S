<template>
  <div class="simulation-runner">
    <div class="header">
      <h2>模拟运行器</h2>
      <el-button @click="$emit('back-to-description')" type="text">
        返回描述页面
      </el-button>
    </div>

    <div class="control-panel">
      <el-button
        type="primary"
        :loading="isRunning"
        @click="runSimulation"
      >
        {{ isRunning ? '运行中...' : '运行模拟' }}
      </el-button>
    </div>

    <div class="content-scroll-container">
      <div class="output-panel" ref="outputPanel">
        <pre>{{ output }}</pre>
      </div>

      <div class="results-panel">
        <h3>实验结果</h3>
        <div class="charts-container">
          <div v-for="(chart, key) in chartData" :key="key" class="chart-item">
            <Line
              v-if="chart.datasets[0].data.length > 0"
              :data="chart"
              :options="getChartOptions(chart.title)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted, reactive } from 'vue'
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
    console.error('启动模拟失败:', error)
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
      display: true,
      position: 'top'
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
  Object.entries(data).forEach(([key, values]) => {
    // 跳过非数组类型的数据和years键
    if (!Array.isArray(values) || key === 'years') return;

    // 每次都重新创建图表数据
    chartData[key] = {
      title: getChartTitle(key),
      labels: [...data.years],
      datasets: [{
        label: getDatasetLabel(key),
        data: [...values],
        borderColor: getChartColor(key),
        backgroundColor: getChartColor(key, 0.2),
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
      }
    } catch (error) {
      console.error('检查状态失败:', error)
      isRunning.value = false
      clearInterval(statusCheckInterval.value)
    }
  }, 1000)  // 每秒检查一次状态
}

// 获取图表标题
const getChartTitle = (key) => {
  const titles = {
    population: '人口数量变化',
    unemployment_rate: '失业率变化',
    government_budget: '政府预算变化',
    rebellions: '叛乱次数变化',
    rebellion_strength: '叛乱强度变化',
    average_satisfaction: '平均满意度变化',
    tax_rate: '税率变化',
    river_navigability: '河流通航性变化',
    gdp: 'GDP变化',
    urban_scale: '城市规模变化'
  }
  return titles[key] || key
}

// 获取数据集标签
const getDatasetLabel = (key) => {
  const labels = {
    population: '人口数量',
    unemployment_rate: '失业率',
    government_budget: '政府预算',
    rebellions: '叛乱次数',
    rebellion_strength: '叛乱强度',
    average_satisfaction: '平均满意度',
    tax_rate: '税率',
    river_navigability: '河流通航性',
    gdp: 'GDP',
    urban_scale: '城市规模'
  }
  return labels[key] || key
}

// 获取图表颜色
const getChartColor = (key, alpha = 1) => {
  const colors = {
    population: `rgba(75, 192, 192, ${alpha})`,
    unemployment_rate: `rgba(255, 99, 132, ${alpha})`,
    government_budget: `rgba(153, 102, 255, ${alpha})`,
    rebellions: `rgba(255, 159, 64, ${alpha})`,
    rebellion_strength: `rgba(255, 99, 132, ${alpha})`,
    average_satisfaction: `rgba(75, 192, 192, ${alpha})`,
    tax_rate: `rgba(153, 102, 255, ${alpha})`,
    river_navigability: `rgba(54, 162, 235, ${alpha})`,
    gdp: `rgba(255, 206, 86, ${alpha})`,
    urban_scale: `rgba(75, 192, 192, ${alpha})`
  }
  return colors[key] || `rgba(75, 192, 192, ${alpha})`
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

.chart-item {
  background-color: var(--el-bg-color-page);
  padding: 16px;
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
  height: 300px;
  min-width: 400px;
  flex: 1;
}
</style>