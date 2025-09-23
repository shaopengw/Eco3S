<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElForm, ElFormItem, ElInput, ElButton, ElMessage } from 'element-plus'

const props = defineProps({
  configType: {
    type: String,
    required: true
  }
})

const configData = ref({
  simulation: {},
  data: {}
})

const loadConfig = async () => {
  try {
    const response = await fetch(`/api/config/${props.configType}`)
    const data = await response.json()
    configData.value = data
  } catch (error) {
    ElMessage.error('加载配置失败')
    console.error('Error loading config:', error)
  }
}

const saveConfig = async () => {
  try {
    const processedConfigData = JSON.parse(JSON.stringify(configData.value)); // Deep copy to avoid modifying the original reactive object

    // Process simulation parameters
    if (processedConfigData.simulation) {
      for (const key in processedConfigData.simulation) {
        if (Object.prototype.hasOwnProperty.call(processedConfigData.simulation, key)) {
          if (key === 'group_decision' && typeof processedConfigData.simulation[key] === 'object') {
            for (const groupKey in processedConfigData.simulation[key]) {
              if (Object.prototype.hasOwnProperty.call(processedConfigData.simulation[key], groupKey)) {
                for (const subKey in processedConfigData.simulation[key][groupKey]) {
                  if (Object.prototype.hasOwnProperty.call(processedConfigData.simulation[key][groupKey], subKey)) {
                    const numValue = Number(processedConfigData.simulation[key][groupKey][subKey]);
                    if (!isNaN(numValue)) {
                      processedConfigData.simulation[key][groupKey][subKey] = numValue;
                    }
                  }
                }
              }
            }
          } else {
            const numValue = Number(processedConfigData.simulation[key]);
            if (!isNaN(numValue)) {
              processedConfigData.simulation[key] = numValue;
            }
          }
        }
      }
    }

    // Process data parameters
    if (processedConfigData.data) {
      for (const key in processedConfigData.data) {
        if (Object.prototype.hasOwnProperty.call(processedConfigData.data, key)) {
          const numValue = Number(processedConfigData.data[key]);
          if (!isNaN(numValue)) {
            processedConfigData.data[key] = numValue;
          }
        }
      }
    }

    const response = await fetch(`/api/config/${props.configType}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(processedConfigData)
    })
    
    if (response.ok) {
      ElMessage.success('配置保存成功')
    } else {
      throw new Error('保存失败')
    }
  } catch (error) {
    ElMessage.error('保存配置失败')
    console.error('Error saving config:', error)
  }
}

watch(() => props.configType, () => {
  loadConfig()
})

onMounted(() => {
  loadConfig()
})
</script>

<template>
  <div class="config-editor">
    <div class="config-header">
      <h3>配置编辑器</h3>
    </div>
    <div class="config-content">
      <el-form label-position="top" size="small">
        <template v-if="configData.simulation">
          <div class="section-header">模拟参数</div>
          <template v-for="(value, key) in configData.simulation" :key="key">
            <template v-if="key !== 'group_decision'">
              <el-form-item :label="key.replace('_', ' ').toUpperCase()">
                <el-input
                  v-model="configData.simulation[key]"
                  :placeholder="'请输入' + key"
                />
              </el-form-item>
            </template>
          </template>

          <template v-if="configData.simulation.group_decision">
            <div class="section-header">群体决策参数</div>
            <template
              v-for="(groupValue, groupKey) in configData.simulation.group_decision"
              :key="groupKey"
            >
              <template v-for="(value, key) in groupValue" :key="`${groupKey}-${key}`">
                <el-form-item
                  :label="
                    groupKey.replace('_', ' ').toUpperCase() +
                    ' - ' +
                    key.replace('_', ' ').toUpperCase()
                  "
                >
                  <el-input
                    v-model="configData.simulation.group_decision[groupKey][key]"
                    :placeholder="'请输入' + key"
                  />
                </el-form-item>
              </template>
            </template>
          </template>
        </template>

        <template v-if="configData.data">
          <div class="section-header">数据参数</div>
          <template v-for="(value, key) in configData.data" :key="key">
            <el-form-item :label="key.replace('_', ' ').toUpperCase()">
              <el-input
                v-model="configData.data[key]"
                :placeholder="'请输入' + key"
              />
            </el-form-item>
          </template>
        </template>

        <el-form-item class="save-button-container">
          <el-button type="primary" @click="saveConfig">保存配置</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.config-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color);
  border-radius: 8px;
}

.config-header {
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.config-header h3 {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 18px;
  font-weight: 500;
}

.config-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.section-header {
  margin: 16px 0 12px;
  padding-bottom: 8px;
  color: var(--el-text-color-primary);
  font-size: 16px;
  font-weight: 500;
  border-bottom: 1px solid var(--el-border-color-light);
}

:deep(.el-form-item) {
  margin-bottom: 12px;
}

:deep(.el-form-item__label) {
  padding-bottom: 4px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.save-button-container {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-light);
}

:deep(.el-input__wrapper) {
  box-shadow: none;
  border: 1px solid var(--el-border-color);
}

:deep(.el-input__wrapper:hover) {
  border-color: var(--el-border-color-hover);
}

:deep(.el-input__wrapper.is-focus) {
  border-color: var(--el-color-primary);
}
</style>