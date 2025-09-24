<template>
  <div class="simulation-description">
    <div class="description-content" v-html="renderedDescription"></div>
    <div class="action-buttons">
      <el-button @click="$emit('view-history')">模拟历史</el-button>
      <el-button type="primary" @click="$emit('start-simulation')">开始模拟</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  configType: {
    type: String,
    required: true
  }
})

const description = ref('')
const renderedDescription = ref('')

const loadDescription = async () => {
  try {
    const response = await fetch(`/api/description/${props.configType}`)
    const data = await response.json()
    description.value = data.description
    renderedDescription.value = marked(description.value)
  } catch (error) {
    console.error('加载模拟描述失败:', error)
  }
}

watch(() => props.configType, loadDescription)

onMounted(loadDescription)
</script>

<style scoped>
.simulation-description {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.description-content {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 20px;
  line-height: 1.6;
}

.description-content :deep(h1) {
  font-size: 24px;
  margin-bottom: 16px;
}

.description-content :deep(h2) {
  font-size: 20px;
  margin: 16px 0;
}

.description-content :deep(p) {
  margin: 12px 0;
}

.description-content :deep(ul),
.description-content :deep(ol) {
  padding-left: 24px;
  margin: 12px 0;
}

.description-content :deep(code) {
  background-color: var(--el-fill-color-light);
  padding: 2px 4px;
  border-radius: 4px;
}

.description-content :deep(pre) {
  background-color: var(--el-fill-color);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 16px 0;
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid var(--el-border-color-light);
}
</style>