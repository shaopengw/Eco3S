<template>
  <div class="data-analyzer">
    <div class="analyzer-header">
      <h2>数据分析</h2>
      <div class="analyzer-controls">
        <el-form :inline="true" :model="analysisParams">
          <el-form-item label="人口数量(p)">
            <el-input-number 
              v-model="analysisParams.p" 
              :min="1"
              :step="1"
              placeholder="可选，用于过滤结果"
            />
          </el-form-item>
          <el-form-item label="年份(y)">
            <el-input-number 
              v-model="analysisParams.y" 
              :min="1"
              :step="1"
              placeholder="可选，用于过滤结果"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="runAnalysis">开始分析</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <div class="analysis-content" v-loading="loading">
      <!-- 统计报告展示 -->
      <div class="report-section" v-if="report">
        <h3>统计报告</h3>
        <div class="markdown-content" v-html="renderedReport"></div>
      </div>

      <!-- 图表展示 -->
      <div class="plots-section" v-if="plots.length > 0">
        <h3>分析图表</h3>
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
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'

const props = defineProps({
  configType: {
    type: String,
    required: true
  }
})

const analysisParams = ref({
  p: null,
  y: null
})

const loading = ref(false)
const report = ref('')
const plots = ref([])

const renderedReport = computed(() => {
  return report.value ? marked(report.value) : ''
})

const getPlotTitle = (filename) => {
  // 从文件名中提取图表标题
  const match = filename.match(/statistics_(.+)_\d{8}_\d{6}\.png/)
  if (match) {
    return match[1].replace(/_/g, ' ')
  }
  return filename
}

const runAnalysis = async () => {
  loading.value = true
  try {
    // 构建请求体，只包含非空参数
    const requestBody = {
      type: props.configType
    }

    if (analysisParams.value.p !== null && analysisParams.value.p !== '') {
      requestBody.p = analysisParams.value.p
    }
    if (analysisParams.value.y !== null && analysisParams.value.y !== '') {
      requestBody.y = analysisParams.value.y
    }

    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    })

    if (!response.ok) {
      throw new Error('分析请求失败')
    }

    const data = await response.json()
    
    // 更新报告和图表
    report.value = data.report
    plots.value = data.plots || []
    
    ElMessage.success('分析完成')
  } catch (error) {
    console.error('分析失败:', error)
    ElMessage.error('分析失败，请检查参数后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.data-analyzer {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color);
}

.analyzer-header {
  margin-bottom: 24px;
}

.analyzer-controls {
  margin-top: 16px;
}

.analysis-content {
  flex: 1;
  overflow-y: auto;
}

.report-section {
  margin-bottom: 32px;
}

.markdown-content {
  background-color: var(--el-bg-color-page);
  padding: 16px;
  border-radius: 8px;
  line-height: 1.6;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--el-border-color);
  padding: 8px;
  text-align: left;
}

.markdown-content :deep(th) {
  background-color: var(--el-fill-color-light);
}

.plot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  padding: 8px;
}

.plot-item {
  background-color: var(--el-bg-color-page);
  padding: 16px;
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
}

.plot-title {
  margin-bottom: 12px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.plot-item :deep(.el-image) {
  width: 100%;
  height: auto;
}

.plot-item :deep(.el-image img) {
  width: 100%;
  height: auto;
  border-radius: 4px;
  transition: transform 0.3s ease;
}

.plot-item :deep(.el-image img:hover) {
  transform: scale(1.02);
}
</style>