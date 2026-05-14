<template>
  <div class="sim-page">
    <header class="sim-hero">
      <div class="sim-hero-icon" aria-hidden="true">📋</div>
      <div class="sim-hero-text">
        <p class="sim-badge">{{ t('simulation.detailBadge') }}</p>
        <h1 class="sim-title">{{ simulationLabel }}</h1>
        <p class="sim-meta">{{ configType }}</p>
      </div>
    </header>

    <div class="sim-card">
      <div v-if="loading" class="sim-state">
        <el-icon class="spin"><Loading /></el-icon>
        <span>{{ t('simulation.loadingDoc') }}</span>
      </div>
      <div v-else-if="loadError" class="sim-state sim-error">
        {{ t('simulation.loadError') }}
      </div>
      <div v-else-if="!hasContent" class="sim-state sim-muted">
        {{ t('simulation.emptyDoc') }}
      </div>
      <div v-else class="sim-prose markdown-body" v-html="renderedDescription"></div>
    </div>

    <footer class="sim-actions">
      <div class="sim-actions-inner">
        <el-button size="large" round @click="$emit('view-history')">
          <el-icon class="btn-ico"><List /></el-icon>
          {{ t('simulation.historyButton') }}
        </el-button>
        <el-button size="large" round @click="$emit('analyze-data')">
          <el-icon class="btn-ico"><DataAnalysis /></el-icon>
          {{ t('simulation.analyzeButton') }}
        </el-button>
        <el-button type="primary" size="large" round class="sim-cta-primary" @click="$emit('start-simulation')">
          <el-icon class="btn-ico"><VideoPlay /></el-icon>
          {{ t('simulation.startButton') }}
        </el-button>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, inject } from 'vue'
import { marked } from 'marked'
import { Loading, List, DataAnalysis, VideoPlay } from '@element-plus/icons-vue'
import i18n from '../i18n'

const useI18nFunc = inject('useI18n')
const { t, getLocale } = useI18nFunc()

const props = defineProps({
  configType: {
    type: String,
    required: true
  },
  simulationLabel: {
    type: String,
    default: ''
  }
})

const description = ref('')
const renderedDescription = ref('')
const loading = ref(true)
const loadError = ref(false)

const hasContent = computed(() => {
  const raw = description.value?.trim()
  return Boolean(raw && raw.length > 0)
})

const loadDescription = async () => {
  loading.value = true
  loadError.value = false
  description.value = ''
  renderedDescription.value = ''
  try {
    const lang = getLocale()
    const response = await fetch(`/api/description/${props.configType}?lang=${encodeURIComponent(lang)}`)
    const data = await response.json()
    description.value = data.description || ''
    renderedDescription.value = description.value ? marked(description.value) : ''
  } catch (error) {
    console.error('加载模拟描述失败:', error)
    loadError.value = true
  } finally {
    loading.value = false
  }
}

watch(() => props.configType, loadDescription)
watch(() => i18n.locale, loadDescription)

onMounted(loadDescription)
</script>

<style scoped>
.sim-page {
  max-width: 920px;
  margin: 0 auto;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  padding-bottom: 8px;
}

.sim-hero {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  margin-bottom: 20px;
  padding: 4px 4px 0;
}

.sim-hero-icon {
  flex-shrink: 0;
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(64, 158, 255, 0.12), rgba(54, 207, 201, 0.1));
  border: 1px solid rgba(64, 158, 255, 0.2);
  box-shadow: 0 8px 24px rgba(64, 158, 255, 0.08);
}

.sim-hero-text {
  min-width: 0;
}

.sim-badge {
  display: inline-block;
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #409eff;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(64, 158, 255, 0.1);
}

.sim-title {
  margin: 0 0 6px;
  font-size: clamp(1.35rem, 2.8vw, 1.75rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
  color: #111827;
}

.sim-meta {
  margin: 0;
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #9ca3af;
}

.sim-card {
  flex: 1;
  min-height: calc(100vh - 320px);
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: #ffffff;
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.sim-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 24px;
  font-size: 14px;
  color: #6b7280;
}

.sim-state .spin {
  font-size: 22px;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.sim-error {
  color: #f56c6c;
}

.sim-muted {
  color: #9ca3af;
}

.sim-prose {
  padding: 24px 28px 28px;
  max-height: calc(100vh - 380px);
  overflow-y: auto;
  line-height: 1.65;
  color: #374151;
}

.sim-prose :deep(h1) {
  font-size: 1.35rem;
  margin: 0 0 14px;
  color: #111827;
  font-weight: 700;
}

.sim-prose :deep(h2) {
  font-size: 1.12rem;
  margin: 22px 0 10px;
  color: #1f2937;
  font-weight: 700;
  padding-bottom: 6px;
  border-bottom: 1px solid #f3f4f6;
}

.sim-prose :deep(h3) {
  font-size: 1.02rem;
  margin: 16px 0 8px;
  color: #374151;
  font-weight: 600;
}

.sim-prose :deep(p) {
  margin: 10px 0;
}

.sim-prose :deep(ul),
.sim-prose :deep(ol) {
  padding-left: 22px;
  margin: 10px 0;
}

.sim-prose :deep(li) {
  margin: 4px 0;
}

.sim-prose :deep(a) {
  color: #409eff;
  text-decoration: none;
}

.sim-prose :deep(a:hover) {
  text-decoration: underline;
}

.sim-prose :deep(code) {
  font-size: 0.88em;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
  color: #b45309;
}

.sim-prose :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 16px 18px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 14px 0;
  font-size: 0.88rem;
  line-height: 1.5;
}

.sim-prose :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

.sim-prose :deep(blockquote) {
  margin: 14px 0;
  padding: 10px 16px;
  border-left: 4px solid #409eff;
  background: rgba(64, 158, 255, 0.06);
  border-radius: 0 8px 8px 0;
  color: #4b5563;
}

.sim-actions {
  margin-top: 20px;
  padding-top: 4px;
}

.sim-actions-inner {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding: 16px 4px 4px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}

.btn-ico {
  margin-right: 6px;
  vertical-align: middle;
}

.sim-cta-primary {
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.28);
}
</style>
