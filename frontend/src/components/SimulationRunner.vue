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
        <div class="plots-container">
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
import { ref, onUnmounted } from 'vue'

const props = defineProps({
  configType: {
    type: String,
    required: true
  }
})

const isRunning = ref(false)
const output = ref('')
const plotPaths = ref([])
const processId = ref(null)
const statusCheckInterval = ref(null)
const outputPanel = ref(null)

const runSimulation = async () => {
  try {
    isRunning.value = true
    output.value = ''
    plotPaths.value = []
    
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

const startStatusCheck = () => {
  statusCheckInterval.value = setInterval(async () => {
    try {
      const response = await fetch(`/api/simulation_status/${processId.value}`)
      const data = await response.json()
      
      if (data.output) {
        output.value += data.output
        // 自动滚动到底部
        if (outputPanel.value) {
          outputPanel.value.scrollTop = outputPanel.value.scrollHeight
        }
      }
      
      if (data.plot_paths) {
        plotPaths.value = data.plot_paths
        console.log('plot_paths:', plotPaths.value)
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
  }, 1000)
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

.plots-container {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
  padding: 8px;
}

.plot-item {
  background-color: var(--el-bg-color-page);
  padding: 16px;
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
  height: fit-content;
}

.plot-item :deep(.el-image) {
  width: 100%;
  height: auto;
  cursor: pointer;
  display: block;
}

.plot-item :deep(.el-image img) {
  width: 100%;
  height: auto;
  border-radius: 4px;
  transition: transform 0.3s ease;
  display: block;
}

.plot-item :deep(.el-image img:hover) {
  transform: scale(1.02);
}
</style>