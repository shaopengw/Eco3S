<template>
  <el-drawer
    v-model="visible"
    :title="t('settings.drawerTitle')"
    direction="rtl"
    size="520px"
    destroy-on-close
    class="model-api-settings-drawer"
    @open="onOpen"
  >
    <div v-loading="loading" class="settings-body">
      <p class="settings-tip">{{ t('settings.drawerHint') }}</p>

      <section v-for="(row, index) in rows" :key="row.id" class="provider-card">
        <div class="provider-head">
          <el-input
            v-model="row.name"
            class="provider-name-input"
            :placeholder="t('settings.providerKeyPh')"
          />
          <el-button type="danger" text @click="removeRow(index)">
            {{ t('settings.remove') }}
          </el-button>
        </div>

        <el-form label-position="top" size="default" class="provider-form">
          <el-form-item :label="t('settings.modelTypes')">
            <el-input
              v-model="modelTypesText[row.id]"
              :placeholder="t('settings.modelTypesPh')"
              clearable
            />
          </el-form-item>
          <el-form-item :label="t('settings.modelPlatform')">
            <el-input v-model="row.spec.model_platform" clearable />
          </el-form-item>
          <el-form-item :label="t('settings.urlEnv')">
            <el-input v-model="row.spec.url_env" clearable :placeholder="t('settings.urlEnvPh')" />
          </el-form-item>
          <el-form-item v-if="row.spec.url_env" :label="t('settings.baseUrl')">
            <el-input v-model="envForm[String(row.spec.url_env).trim()]" clearable />
          </el-form-item>
          <el-form-item :label="t('settings.apiKeyEnv')">
            <el-input v-model="row.spec.api_key_env" clearable :placeholder="t('settings.apiKeyEnvPh')" />
          </el-form-item>
          <el-form-item v-if="row.spec.api_key_env">
            <template #label>
              <span class="label-with-badge">
                {{ t('settings.apiKey') }}
                <el-tag
                  v-if="apiKeyWasSet[row.id] && !(envForm[String(row.spec.api_key_env).trim()] || '').trim()"
                  size="small"
                  type="info"
                  effect="plain"
                  class="key-badge"
                >
                  {{ t('settings.apiKeyConfigured') }}
                </el-tag>
              </span>
            </template>
            <el-input
              v-model="envForm[String(row.spec.api_key_env).trim()]"
              type="password"
              show-password
              :placeholder="apiKeyPlaceholder(row.id)"
              clearable
            />
          </el-form-item>

          <div class="switch-inline">
            <span class="switch-inline-label">
              {{ t('settings.allowRandom') }}
              <el-tooltip :content="t('settings.allowRandomHelp')" placement="top" effect="dark">
                <el-icon class="help-icon"><QuestionFilled /></el-icon>
              </el-tooltip>
            </span>
            <el-switch v-model="row.spec.allow_random" />
          </div>
        </el-form>
      </section>

      <el-button class="add-btn" @click="addRow">
        + {{ t('settings.addProvider') }}
      </el-button>

      <div class="drawer-footer">
        <el-button @click="visible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveAll">
          {{ t('settings.save') }}
        </el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, reactive, watch, inject } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const useI18nFunc = inject('useI18n')
const { t } = useI18nFunc()

const props = defineProps({
  modelValue: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = ref(false)
watch(
  () => props.modelValue,
  (v) => {
    visible.value = v
  },
  { immediate: true }
)
watch(visible, (v) => emit('update:modelValue', v))

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const envForm = reactive({})
const modelTypesText = reactive({})
const apiKeyWasSet = reactive({})

const newRowId = () =>
  typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `r-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

const deepClone = (o) => JSON.parse(JSON.stringify(o || {}))

const emptySpec = () => ({
  model_types: ['gpt-4o'],
  model_platform: 'OPENAI',
  url_env: 'OPENAI_API_BASE_URL',
  api_key_env: 'OPENAI_API_KEY',
  allow_random: true
})

const normalizeSpec = (spec) => {
  const s = { ...spec }
  if (typeof s.allow_random !== 'boolean') s.allow_random = s.allow_random !== false
  return s
}

const syncModelTypesForRow = (row) => {
  const mt = row.spec.model_types
  modelTypesText[row.id] = Array.isArray(mt) ? mt.join(', ') : String(mt || '')
}

const applyModelTypesForRow = (row) => {
  const raw = (modelTypesText[row.id] || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean)
  row.spec.model_types = raw.length ? raw : ['']
}

const apiKeyPlaceholder = (rowId) => {
  if (apiKeyWasSet[rowId]) return t('settings.apiKeyLeaveBlank')
  return t('settings.apiKeyPlaceholder')
}

const clearAuxState = () => {
  Object.keys(envForm).forEach((k) => delete envForm[k])
  Object.keys(modelTypesText).forEach((k) => delete modelTypesText[k])
  Object.keys(apiKeyWasSet).forEach((k) => delete apiKeyWasSet[k])
}

const onOpen = () => {
  loadData()
}

const loadData = async () => {
  loading.value = true
  try {
    const r = await fetch('/api/settings/api_models')
    if (!r.ok) throw new Error('load')
    const data = await r.json()

    clearAuxState()
    rows.value = Object.entries(data.models || {}).map(([name, spec]) => ({
      id: newRowId(),
      name,
      spec: normalizeSpec(deepClone(spec))
    }))

    for (const row of rows.value) {
      syncModelTypesForRow(row)
    }

    for (const row of data.env_hints || []) {
      const ue = row.url_env
      const ak = row.api_key_env
      if (ue) envForm[String(ue).trim()] = row.base_url || ''
      if (ak) {
        const rid = rows.value.find((x) => x.name === row.provider)?.id
        if (rid) apiKeyWasSet[rid] = Boolean(row.api_key_configured)
        envForm[String(ak).trim()] = ''
      }
    }
  } catch {
    ElMessage.error(t('settings.loadFailed'))
  } finally {
    loading.value = false
  }
}

const addRow = () => {
  const id = newRowId()
  rows.value.push({
    id,
    name: '',
    spec: normalizeSpec(emptySpec())
  })
  syncModelTypesForRow(rows.value[rows.value.length - 1])
}

const removeRow = async (index) => {
  try {
    await ElMessageBox.confirm(t('settings.confirmRemove'), t('settings.remove'), {
      type: 'warning',
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel')
    })
  } catch {
    return
  }
  const removed = rows.value[index]
  rows.value.splice(index, 1)
  if (removed) {
    delete modelTypesText[removed.id]
    delete apiKeyWasSet[removed.id]
  }
}

const buildModelsObject = () => {
  const out = {}
  const used = new Set()
  for (const row of rows.value) {
    const base = String(row.name || '').trim()
    if (!base) continue
    applyModelTypesForRow(row)
    let key = base
    if (used.has(key)) {
      let suffix = 2
      while (used.has(`${base}_${suffix}`)) suffix += 1
      key = `${base}_${suffix}`
    }
    used.add(key)
    out[key] = deepClone(row.spec)
  }
  return out
}

const saveAll = async () => {
  for (const row of rows.value) {
    applyModelTypesForRow(row)
  }

  const models = buildModelsObject()
  if (Object.keys(models).length === 0) {
    ElMessage.warning(t('settings.needOneProvider'))
    return
  }

  saving.value = true
  try {
    const env_updates = {}
    for (const row of rows.value) {
      const key = String(row.name || '').trim()
      if (!key) continue
      const spec = row.spec
      if (spec.url_env) {
        const k = String(spec.url_env).trim()
        const v = (envForm[k] || '').trim()
        if (v) env_updates[k] = v
      }
      if (spec.api_key_env) {
        const k = String(spec.api_key_env).trim()
        const v = (envForm[k] || '').trim()
        if (v) env_updates[k] = v
      }
    }

    const r = await fetch('/api/settings/api_models', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        models,
        env_updates
      })
    })
    const data = await r.json()
    if (!r.ok) throw new Error(data.error || 'save')

    ElMessage.success(t('settings.saveSuccess'))
    emit('saved', data.precheck)
    visible.value = false
  } catch {
    ElMessage.error(t('settings.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.settings-body {
  padding: 4px 6px 28px;
  max-width: 520px;
}

.settings-tip {
  margin: 0 0 16px;
  font-size: 13px;
  line-height: 1.5;
  color: #5f6b7a;
  background: linear-gradient(120deg, rgba(64, 158, 255, 0.12), rgba(54, 207, 201, 0.08));
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(64, 158, 255, 0.18);
}

.provider-card {
  margin-bottom: 16px;
  padding: 16px 16px 14px;
  border-radius: 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: linear-gradient(180deg, #ffffff 0%, #f7f9fc 100%);
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.08);
}

.provider-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.provider-name-input {
  flex: 1;
  font-weight: 700;
}

.provider-form {
  margin-top: 4px;
}

.label-with-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.key-badge {
  font-weight: 500;
}

.switch-inline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 10px 0 4px;
  padding: 4px 0;
}

.switch-inline-label {
  font-size: 14px;
  color: #606266;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.help-icon {
  font-size: 14px;
  color: #9ca3af;
  cursor: help;
}

.help-icon:hover {
  color: #409eff;
}

.add-btn {
  width: 100%;
  margin-bottom: 8px;
  border: 1px dashed rgba(64, 158, 255, 0.45);
  color: #1f6fe5;
  background: rgba(64, 158, 255, 0.08);
  font-weight: 600;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

:deep(.model-api-settings-drawer .el-drawer__header) {
  margin-bottom: 6px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  background: linear-gradient(120deg, rgba(64, 158, 255, 0.08), rgba(54, 207, 201, 0.06));
}

:deep(.model-api-settings-drawer .el-drawer__title) {
  font-weight: 700;
  letter-spacing: 0.02em;
}

:deep(.model-api-settings-drawer .el-input__wrapper) {
  border-radius: 10px;
}

:deep(.model-api-settings-drawer .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.18);
}

:deep(.model-api-settings-drawer .el-form-item__label) {
  color: #4b5563;
  font-weight: 600;
}
</style>
