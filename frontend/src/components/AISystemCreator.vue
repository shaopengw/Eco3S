<template>
  <div class="ai-system-creator">
    <div class="creator-header">
      <h2>{{ t('aiCreator.title') }}</h2>
      <el-button @click="$emit('back')" text>{{ t('common.back') }}</el-button>
    </div>

    <!-- 步骤指示器 -->
    <el-steps :active="currentStep" finish-status="success" align-center class="steps-container">
      <el-step :title="t('aiCreator.steps.requirement')" />
      <el-step :title="t('aiCreator.steps.parsing')" />
      <el-step :title="t('aiCreator.steps.design')" />
      <el-step :title="t('aiCreator.steps.coding')" />
      <el-step :title="t('aiCreator.steps.simulation')" />
      <el-step :title="t('aiCreator.steps.evaluation')" />
    </el-steps>

    <!-- 步骤1: 需求输入 -->
    <div v-if="currentStep === 0" class="step-content">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>{{ t('aiCreator.requirement.title') }}</span>
          </div>
        </template>
        
        <div class="requirement-input">
          <el-alert
            :title="t('aiCreator.requirement.instructions')"
            type="info"
            :closable="false"
            show-icon
            style="align-items: flex-start"
          >
            <p>{{ t('aiCreator.requirement.instructionText') }}</p>
            <ul>
              <li v-for="(item, index) in t('aiCreator.requirement.instructionList')" :key="index">{{ item }}</li>
            </ul>
          </el-alert>

          <div class="mode-selection">
            <el-radio-group v-model="mode">
              <el-radio value="auto">{{ t('aiCreator.requirement.mode.auto') }}</el-radio>
              <el-radio value="interactive">{{ t('aiCreator.requirement.mode.interactive') }}</el-radio>
            </el-radio-group>
          </div>

          <el-input
            v-model="requirement"
            type="textarea"
            :rows="8"
            :placeholder="t('aiCreator.requirement.placeholder')"
          />

          <div class="example-requirements">
            <span>{{ t('aiCreator.requirement.examples') }}</span>
            <el-tag
              v-for="example in exampleRequirements"
              :key="example"
              @click="requirement = example"
              style="cursor: pointer; margin: 4px;"
            >
              {{ example.substring(0, 30) }}...
            </el-tag>
          </div>

          <div class="actions">
            <el-button type="primary" @click="startCreation" :loading="loading">
              {{ t('aiCreator.requirement.startCreation') }}
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 步骤2-5: 进度显示 -->
    <div v-else class="step-content">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>{{ currentPhaseTitle }}</span>
            <el-tag :type="statusType">{{ statusText }}</el-tag>
          </div>
        </template>

        <!-- 执行时间线 -->
        <div class="execution-timeline">
          <el-timeline>
            <!-- 需求解析阶段 -->
            <el-timeline-item
              v-if="phaseResults?.requirement_dict"
              :timestamp="t('aiCreator.phases.parsing.timestamp')"
              type="success"
              size="large"
              hollow
              placement="top"
            >
              <el-card shadow="hover">
                <template #header>
                  <span class="timeline-card-title">📋 {{ t('aiCreator.phases.parsing.cardTitle') }}</span>
                </template>
                <el-descriptions :column="2" border>
                  <el-descriptions-item :label="t('aiCreator.phases.parsing.simulationName')">
                    {{ phaseResults.simulation_name }}
                  </el-descriptions-item>
                  <el-descriptions-item :label="t('aiCreator.phases.parsing.simulationType')">
                    {{ phaseResults.requirement_dict.simulation_type }}
                  </el-descriptions-item>
                  <el-descriptions-item :label="t('aiCreator.phases.parsing.projectDir')" :span="2">
                    {{ phaseResults.project_dir }}
                  </el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-timeline-item>

            <!-- 系统设计阶段 -->
            <el-timeline-item
              v-if="phaseResults?.design_results"
              :timestamp="t('aiCreator.phases.design.timestamp')"
              type="success"
              size="large"
              hollow
              placement="top"
            >
              <el-card shadow="hover">
                <template #header>
                  <span class="timeline-card-title">🎨 {{ t('aiCreator.phases.design.cardTitle') }}</span>
                </template>
                <el-descriptions :column="1" border>
                  <el-descriptions-item :label="t('aiCreator.phases.design.designDoc')">
                    {{ t('aiCreator.phases.design.generatedDoc') }}
                  </el-descriptions-item>
                  <el-descriptions-item :label="t('aiCreator.phases.design.moduleConfig')">
                    {{ t('aiCreator.phases.design.generatedConfig') }}
                  </el-descriptions-item>
                </el-descriptions>
                <el-button @click="viewDesignDoc" size="small" style="margin-top: 8px;">
                  {{ t('aiCreator.phases.design.viewDoc') }}
                </el-button>
              </el-card>
            </el-timeline-item>

            <!-- 代码生成完成 -->
            <el-timeline-item
              v-if="phaseResults?.coding_results && status !== 'coding'"
              :timestamp="t('aiCreator.phases.coding.timestamp')"
              type="success"
              size="large"
              hollow
              placement="top"
            >
              <el-card shadow="hover">
                <template #header>
                  <span class="timeline-card-title">💻 {{ t('aiCreator.phases.coding.cardTitle') }}</span>
                </template>
                <el-space wrap>
                  <el-tag v-if="phaseResults.coding_results.simulator_files" type="success">
                    ✓ {{ t('aiCreator.phases.coding.simulatorCode') }}
                  </el-tag>
                  <el-tag v-if="phaseResults.coding_results.main_files" type="success">
                    ✓ {{ t('aiCreator.phases.coding.entryFile') }}
                  </el-tag>
                  <el-tag v-if="phaseResults.coding_results.config_files" type="success">
                    ✓ {{ phaseResults.coding_results.config_files.length }} {{ t('aiCreator.phases.coding.configFiles') }}
                  </el-tag>
                  <el-tag v-if="phaseResults.coding_results.prompt_files" type="success">
                    ✓ {{ phaseResults.coding_results.prompt_files.length }} {{ t('aiCreator.phases.coding.promptFiles') }}
                  </el-tag>
                </el-space>
              </el-card>
            </el-timeline-item>

            <!-- 代码生成进行中 -->
            <el-timeline-item
              v-if="status === 'coding'"
              :timestamp="t('aiCreator.phases.coding.timestamp')"
              type="primary"
              size="large"
              :hollow="false"
              placement="top"
            >
              <el-card shadow="hover" class="active-phase-card">
                <template #header>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <el-icon class="rotating"><Loading /></el-icon>
                    <span class="timeline-card-title">💻 {{ t('aiCreator.phases.coding.generating') }}</span>
                  </div>
                </template>
                <div class="coding-progress">
                  <div class="progress-item" v-for="(file, index) in codingFileProgress" :key="index">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                      <el-icon v-if="file.status === 'completed'" color="#67C23A"><Check /></el-icon>
                      <el-icon v-else-if="file.status === 'processing'" class="rotating" color="#409EFF"><Loading /></el-icon>
                      <el-icon v-else color="#C0C4CC"><Document /></el-icon>
                      <span :style="{ color: file.status === 'completed' ? '#67C23A' : file.status === 'processing' ? '#409EFF' : '#909399' }">
                        {{ file.name }}
                      </span>
                    </div>
                    <el-progress
                      v-if="file.status !== 'pending'"
                      :percentage="file.progress"
                      :status="file.status === 'completed' ? 'success' : undefined"
                      :indeterminate="file.status === 'processing'"
                      :show-text="false"
                      style="margin-bottom: 12px;"
                    />
                  </div>
                  <div v-if="latestLogMessage" class="latest-log-message">
                    <el-icon class="log-icon"><InfoFilled /></el-icon>
                    <span class="log-text">{{ latestLogMessage }}</span>
                  </div>
                </div>
              </el-card>
            </el-timeline-item>

            <!-- 其他进行中的阶段 -->
            <el-timeline-item
              v-if="(status === 'parsing' || status === 'designing') && loading"
              :timestamp="status === 'parsing' ? t('aiCreator.phases.parsing.timestamp') : t('aiCreator.phases.design.timestamp')"
              type="primary"
              size="large"
              :hollow="false"
              placement="top"
            >
              <el-card shadow="hover" class="active-phase-card">
                <template #header>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <el-icon class="rotating"><Loading /></el-icon>
                    <span class="timeline-card-title">{{ currentPhaseDescription }}</span>
                  </div>
                </template>
                <div style="color: var(--el-text-color-secondary); line-height: 1.8; margin-bottom: 12px;">
                  {{ phaseTaskDescription }}
                </div>
                <el-progress
                  :percentage="progressPercentage"
                  :indeterminate="true"
                  status="primary"
                />
                <div v-if="latestLogMessage" class="latest-log-message" style="margin-top: 12px;">
                  <el-icon class="log-icon"><InfoFilled /></el-icon>
                  <span class="log-text">{{ latestLogMessage }}</span>
                </div>
              </el-card>
            </el-timeline-item>

            <!-- 模拟运行中 -->
            <el-timeline-item
              v-if="status === 'running_simulation'"
              :timestamp="t('aiCreator.phases.simulation.timestamp')"
              type="primary"
              size="large"
              :hollow="false"
              placement="top"
            >
              <el-card shadow="hover" class="active-phase-card">
                <template #header>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <el-icon class="rotating"><Loading /></el-icon>
                    <span class="timeline-card-title">🎯 {{ t('aiCreator.phases.simulation.running') }}</span>
                  </div>
                </template>
                <div style="color: var(--el-text-color-secondary); line-height: 1.8; margin-bottom: 12px;">
                  {{ testType === 'small' ? t('aiCreator.phases.simulation.smallScale') : t('aiCreator.phases.simulation.largeScale') }}
                </div>
                <el-progress
                  :percentage="70"
                  :indeterminate="true"
                  status="primary"
                />
                <div v-if="latestLogMessage" class="latest-log-message" style="margin-top: 12px;">
                  <el-icon class="log-icon"><InfoFilled /></el-icon>
                  <span class="log-text">{{ latestLogMessage }}</span>
                </div>
              </el-card>
            </el-timeline-item>

            <!-- 模拟完成 -->
            <el-timeline-item
              v-if="phaseResults?.simulation_results && status !== 'running_simulation' && status !== 'small_scale_completed'"
              :timestamp="t('aiCreator.phases.simulation.timestamp')"
              type="success"
              size="large"
              hollow
              placement="top"
            >
              <el-card shadow="hover">
                <template #header>
                  <span class="timeline-card-title">🎯 {{ t('aiCreator.phases.simulation.completed') }}</span>
                </template>
                <el-alert type="success" :closable="false" show-icon>
                  {{ t('aiCreator.phases.simulation.success') }}
                </el-alert>
              </el-card>
            </el-timeline-item>

            <!-- 小规模测试完成 -->
            <el-timeline-item
              v-if="status === 'small_scale_completed'"
              :timestamp="t('aiCreator.phases.simulation.smallScaleTimestamp')"
              type="primary"
              size="large"
              :hollow="false"
              placement="top"
            >
              <el-card shadow="hover" class="active-phase-card">
                <template #header>
                  <span class="timeline-card-title">🎯 {{ t('aiCreator.phases.simulation.smallScaleCompleted') }}</span>
                </template>
                <el-alert type="success" :closable="false" show-icon style="margin-bottom: 12px;">
                  ✅ {{ t('aiCreator.phases.simulation.smallScaleSuccess') }}
                </el-alert>
                <div>
                  <el-space>
                    <el-button size="small" type="primary" @click="runLargeScaleTest" :loading="loading">
                      {{ t('aiCreator.phases.simulation.continueTest') }}
                    </el-button>
                    <el-button size="small" @click="runMechanismAdjust" :loading="loading">
                      {{ t('aiCreator.phases.simulation.mechanismAdjust') }}
                    </el-button>
                  </el-space>
                  <el-alert type="info" :closable="false" style="margin-top: 8px;" show-icon>
                    {{ t('aiCreator.phases.simulation.testOptions') }}
                  </el-alert>
                </div>
              </el-card>
            </el-timeline-item>

            <!-- 评估优化阶段 -->
            <el-timeline-item
              v-if="phaseResults?.evaluation_results || status === 'evaluating'"
              :timestamp="status === 'evaluating' || status === 'evaluation_waiting_confirm' ? t('aiCreator.phases.evaluation.timestamp') : t('aiCreator.phases.evaluation.timestampCompleted')"
              :type="status === 'evaluating' || status === 'evaluation_waiting_confirm' ? 'primary' : 'success'"
              size="large"
              :hollow="!(status === 'evaluating' || status === 'evaluation_waiting_confirm')"
              placement="top"
            >
              <el-card shadow="hover" :class="{ 'active-phase-card': status === 'evaluating' || status === 'evaluation_waiting_confirm' }">
                <template #header>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <el-icon v-if="status === 'evaluating'" class="rotating"><Loading /></el-icon>
                    <span class="timeline-card-title">📊 {{ status === 'evaluating' ? t('aiCreator.phases.evaluation.running') : t('aiCreator.phases.evaluation.completed') }}</span>
                  </div>
                </template>
                
                <!-- 评估进行中的进度展示 -->
                <div v-if="status === 'evaluating'">
                  <div style="color: var(--el-text-color-secondary); line-height: 1.8; margin-bottom: 12px; font-size: 15px;">
                    {{ t('aiCreator.phases.evaluation.task') }}
                  </div>
                  <el-progress
                    :percentage="70"
                    :indeterminate="true"
                    status="primary"
                  />
                </div>

                <!-- 评估结果 -->
                <div v-if="phaseResults?.evaluation_results">
                  <el-tag
                    :type="phaseResults.evaluation_results.needs_adjustment ? 'warning' : 'success'"
                    size="large"
                    effect="dark"
                    style="margin-bottom: 16px;"
                  >
                    {{ phaseResults.evaluation_results.needs_adjustment ? '⚠️ ' + t('aiCreator.phases.evaluation.needsAdjustment') : '✅ ' + t('aiCreator.phases.evaluation.meetsExpectations') }}
                  </el-tag>

                <div v-if="phaseResults.evaluation_results.evaluation_report">
                  <el-divider content-position="left">
                    <el-icon><Document /></el-icon>
                    {{ t('aiCreator.phases.evaluation.report') }}
                  </el-divider>
                  <div class="report-content markdown-body" v-html="renderedEvaluationReport"></div>
                </div>

                <div v-if="phaseResults.evaluation_results.diagnosis_result">
                  <el-divider content-position="left">
                    <el-icon><Tools /></el-icon>
                    {{ t('aiCreator.phases.evaluation.diagnosis') }}
                  </el-divider>
                  <el-table
                    :data="phaseResults.evaluation_results.diagnosis_result.files_to_modify || []"
                    style="width: 100%; margin-bottom: 16px;"
                    border
                  >
                    <el-table-column :label="t('common.index')" type="index" width="60" align="center" />
                    <el-table-column :label="t('aiCreator.phases.evaluation.fileToModify')" width="200">
                      <template #default="scope">
                        <el-tag size="small" type="info">{{ scope.row.file_name || t('common.unknownFile') }}</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column :label="t('aiCreator.phases.evaluation.reason')">
                      <template #default="scope">
                        <div style="line-height: 1.6; white-space: pre-wrap;">
                          {{ scope.row.reason || scope.row.modification || t('common.noReason') }}
                        </div>
                      </template>
                    </el-table-column>
                  </el-table>

                  <div v-if="phaseResults.evaluation_results.waiting_user_confirmation" style="margin-top: 16px;">
                    <el-alert type="warning" :closable="false" style="margin-bottom: 12px;">
                      ⚠️ {{ t('aiCreator.phases.evaluation.confirmOptimization') }}
                    </el-alert>
                    <div style="display: flex; gap: 12px; justify-content: center;">
                      <el-button type="primary" @click="applyOptimization" :disabled="loading">
                        {{ t('aiCreator.phases.evaluation.applyOptimization') }}
                      </el-button>
                      <el-button @click="skipOptimization" :disabled="loading">
                        {{ t('aiCreator.phases.evaluation.skipOptimization') }}
                      </el-button>
                    </div>
                  </div>
                </div>

                <div v-if="phaseResults.evaluation_results.modification_results">
                  <el-divider content-position="left">
                    <el-icon><EditPen /></el-icon>
                    {{ t('aiCreator.phases.evaluation.modifications') }}
                  </el-divider>
                  <el-timeline v-if="Array.isArray(phaseResults.evaluation_results.modification_results) && phaseResults.evaluation_results.modification_results.length > 0">
                    <el-timeline-item
                      v-for="(mod, index) in phaseResults.evaluation_results.modification_results"
                      :key="index"
                      :timestamp="mod.file || `${t('common.modification')} ${index + 1}`"
                      type="success"
                    >
                      {{ mod.description || t('common.modificationApplied') }}
                    </el-timeline-item>
                  </el-timeline>
                </div>

                <div v-if="phaseResults.evaluation_results.optimization_completed">
                  <el-alert type="success" :closable="false" show-icon>
                    <template #title>
                      <strong>🎉 {{ t('aiCreator.phases.evaluation.optimizationCompleted') }}</strong>
                    </template>
                    {{ t('aiCreator.phases.evaluation.optimizationSuccess') }}
                  </el-alert>
                </div>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </div>

        <!-- 交互模式的操作按钮 -->
        <div v-if="mode === 'interactive' && showInteractiveActions" class="actions">
          <el-alert
            v-if="status === 'design_completed'"
            :title="t('aiCreator.interactive.reviewResults')"
            type="info"
            :closable="false"
            style="margin-bottom: 12px;"
          >
            {{ t('aiCreator.interactive.note') }}
          </el-alert>
          
          <el-input
            v-model="userFeedback"
            type="textarea"
            :rows="3"
            :placeholder="t('aiCreator.interactive.feedbackPlaceholder')"
            style="margin-bottom: 12px;"
          />
          
          <el-button-group>
            <el-button type="primary" @click="continueToNextPhase" :loading="loading">
              <el-icon><Check /></el-icon>
              {{ t('aiCreator.interactive.confirmContinue') }}
            </el-button>
            <el-button @click="regeneratePhase" :loading="loading" :disabled="!userFeedback.trim()">
              <el-icon><Refresh /></el-icon>
              {{ t('aiCreator.interactive.regenerate') }}
            </el-button>
            <el-button @click="viewCurrentFiles" v-if="canViewFiles">
              <el-icon><Document /></el-icon>
              {{ t('aiCreator.interactive.viewFiles') }}
            </el-button>
            <el-button @click="cancelCreation">
              <el-icon><Close /></el-icon>
              {{ t('aiCreator.interactive.cancel') }}
            </el-button>
          </el-button-group>
        </div>

        <!-- 完成状态的操作 -->
        <div v-if="isCompleted" class="actions">
          <el-alert type="success" :closable="false" style="margin-bottom: 12px;">
            🎉 {{ t('aiCreator.completion.message') }}
          </el-alert>
          <el-button-group>
            <el-button type="primary" @click="goToSimulation">
              {{ t('aiCreator.completion.goToSimulation') }}
            </el-button>
            <el-button @click="resetCreator">
              {{ t('aiCreator.completion.createNew') }}
            </el-button>
            <el-button @click="$emit('back')">
              {{ t('aiCreator.completion.backToHome') }}
            </el-button>
          </el-button-group>
        </div>

        <!-- 错误状态 -->
        <div v-if="hasError" class="actions">
          <el-alert type="error" :closable="false" style="margin-bottom: 12px;">
            ❌ {{ t('aiCreator.errors.message') }}
          </el-alert>
          <el-button-group>
            <el-button @click="retryCurrentPhase" :loading="loading">
              {{ t('aiCreator.errors.retryStep') }}
            </el-button>
            <el-button @click="resetCreator">
              {{ t('aiCreator.errors.restart') }}
            </el-button>
          </el-button-group>
        </div>
      </el-card>
    </div>

    <!-- 设计文档查看对话框 -->
    <el-dialog v-model="showDesignDialog" title="设计文档" width="80%">
      <div style="margin-bottom: 12px;">
        <el-radio-group v-model="designDocMode">
          <el-radio-button value="preview">预览</el-radio-button>
          <el-radio-button value="edit">编辑</el-radio-button>
        </el-radio-group>
      </div>
      
      <div v-if="designDocMode === 'preview'" v-html="renderedDesignDoc" class="design-doc-content"></div>
      <el-input
        v-else
        v-model="designDocEditable"
        type="textarea"
        :rows="20"
        class="design-doc-editor"
      />
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showDesignDialog = false">取消</el-button>
          <el-button 
            v-if="designDocMode === 'edit'" 
            type="primary" 
            @click="saveDesignDoc"
            :loading="savingDesignDoc"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 机制调整对话框 -->
    <el-dialog
      v-model="showMechanismDialog"
      title="机制解释与调整助手"
      width="70%"
      :close-on-click-modal="false"
      @close="closeMechanismDialog"
    >
      <div class="mechanism-dialog-container">
        <!-- 左侧：对话区域 -->
        <div class="mechanism-dialog-left">
          <div class="mechanism-dialog-messages" ref="messagesContainer">
            <div
              v-for="(msg, index) in mechanismDialogHistory"
              :key="index"
              :class="['message-item', msg.role === 'user' ? 'user-message' : 'assistant-message']"
            >
              <div class="message-header">
                <span class="message-role">{{ msg.role === 'user' ? '您' : 'AI助手' }}</span>
                <span class="message-time">{{ msg.timestamp }}</span>
              </div>
              <div class="message-content">
                <pre style="white-space: pre-wrap; margin: 0; font-family: inherit;">{{ msg.content }}</pre>
              </div>
            </div>
          </div>
          
          <div class="mechanism-dialog-input">
            <el-input
              v-model="mechanismUserInput"
              type="textarea"
              :rows="3"
              placeholder="输入您的问题或调整建议... (输入 'done' 完成对话)"
              @keydown.ctrl.enter="sendMechanismMessage"
              :disabled="mechanismLoading"
            />
            <div class="mechanism-dialog-actions">
              <el-button
                type="primary"
                @click="sendMechanismMessage"
                :loading="mechanismLoading"
                :disabled="!mechanismUserInput.trim()"
              >
                发送 (Ctrl+Enter)
              </el-button>
              <el-button @click="finishMechanismAdjust" :loading="mechanismLoading">
                完成对话
              </el-button>
            </div>
          </div>
        </div>
        
        <!-- 右侧：调整需求列表 -->
        <div class="mechanism-dialog-right">
          <h4>已收集的调整需求</h4>
          <div class="adjustment-list">
            <el-empty v-if="adjustmentList.length === 0" description="暂无调整需求" :image-size="60" />
            <el-timeline v-else>
              <el-timeline-item
                v-for="(item, index) in adjustmentList"
                :key="index"
                :timestamp="`需求 ${index + 1}`"
              >
                {{ item }}
              </el-timeline-item>
            </el-timeline>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 用户确认对话框 -->
    <el-dialog 
      v-model="showConfirmDialog" 
      :title="confirmType === 'yes_no' ? '需要确认' : confirmMessage" 
      width="50%" 
      :close-on-click-modal="false" 
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div v-if="confirmType === 'input'" style="margin-bottom: 20px;">
        <el-input v-model="confirmInput" :placeholder="confirmMessage" />
      </div>
      
      <div v-else-if="confirmType === 'choice'" style="margin-bottom: 20px;">
        <el-radio-group v-model="confirmInput">
          <el-radio v-for="option in confirmOptions" :key="option" :label="option">
            {{ option }}
          </el-radio>
        </el-radio-group>
      </div>

      <div v-else-if="confirmType === 'yes_no'">
        <el-alert type="warning" :closable="false" style="margin-bottom: 16px;">
          <template #title>
            <div style="font-size: 16px; font-weight: bold;">
              {{ confirmMessage }}
            </div>
          </template>
        </el-alert>
        <el-descriptions :column="1" border v-if="confirmMessage.includes('文件')">
          <el-descriptions-item label="操作说明">
            <div>
              <p><strong>选择"重新生成"</strong>：将删除现有文件并生成新的内容</p>
              <p><strong>选择"使用现有文件"</strong>：跳过此步骤，保留并使用已存在的文件</p>
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <template #footer>
        <div v-if="confirmType === 'yes_no'" style="display: flex; justify-content: flex-end; gap: 12px;">
          <el-button @click="handleConfirm(false)" size="large">
            <el-icon><Close /></el-icon>
            使用现有文件
          </el-button>
          <el-button type="primary" @click="handleConfirm(true)" size="large">
            <el-icon><Refresh /></el-icon>
            重新生成
          </el-button>
        </div>
        <div v-else>
          <el-button type="primary" @click="handleConfirm(true)">提交</el-button>
        </div>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, onUnmounted, nextTick, inject } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Refresh, Document, Close, Loading, Tools, EditPen, InfoFilled } from '@element-plus/icons-vue'
import { marked } from 'marked'

const emit = defineEmits(['back', 'simulation-created'])

// 使用i18n
const useI18nFunc = inject('useI18n')
const { t } = useI18nFunc()

// 状态变量
const currentStep = ref(0)
const mode = ref('auto')
const requirement = ref('')
const sessionId = ref(null)
const status = ref('')
const phase = ref('')
const phaseResults = ref(null)
const loading = ref(false)
const userFeedback = ref('')
const showDesignDialog = ref(false)
const designDoc = ref('')
const designDocMode = ref('preview')  // 'preview' 或 'edit'
const designDocEditable = ref('')  // 可编辑的设计文档内容
const savingDesignDoc = ref(false)
const showConfirmDialog = ref(false)
const confirmMessage = ref('')
const confirmType = ref('')
const confirmOptions = ref([])
const confirmInput = ref('')
const testType = ref('small')  // 'small' 或 'large'
const versionHistory = ref({ design: 0, coding: 0 })

// 机制调整对话相关
const showMechanismDialog = ref(false)
const mechanismDialogHistory = ref([])  // 对话历史
const mechanismUserInput = ref('')  // 用户输入
const mechanismLoading = ref(false)  // 对话加载中
const mechanismOverview = ref('')  // 机制概览
const adjustmentList = ref([])  // 收集到的调整需求列表

// 实时日志显示
const latestLogMessage = ref('')  // 最新的INFO日志消息
const allOutputLines = ref([])  // 累积所有输出行

// 编码进度追踪
const codingStartTime = ref(null)
const codingProgress = ref({
  simulator: { status: 'pending', progress: 0 },
  main: { status: 'pending', progress: 0 },
  config: { status: 'pending', progress: 0 },
  prompts: { status: 'pending', progress: 0 }
})

let statusCheckTimer = null

// 示例需求（从i18n获取）
const exampleRequirements = computed(() => t('aiCreator.requirement.exampleList'))

// 计算属性
const currentPhaseTitle = computed(() => {
  const titles = {
    parse: '需求解析中',
    design: '系统设计中',
    coding: '代码生成中',
    simulation: '运行模拟中',
    evaluation: '评估优化中'
  }
  const baseTitle = titles[phase.value] || '处理中'
  
  // 添加版本信息
  if (phase.value === 'design' && versionHistory.value.design > 0) {
    return `${baseTitle} (版本 ${versionHistory.value.design})`
  }
  if (phase.value === 'coding' && versionHistory.value.coding > 0) {
    return `${baseTitle} (版本 ${versionHistory.value.coding})`
  }
  
  return baseTitle
})

const statusType = computed(() => {
  if (status.value === 'error') return 'danger'
  if (status.value === 'completed') return 'success'
  return 'primary'
})

const statusText = computed(() => {
  const texts = {
    parsing: '解析中...',
    parsed: '解析完成',
    designing: '设计中...',
    design_completed: '设计完成',
    coding: '编码中...',
    coding_completed: '编码完成',
    running_simulation: '模拟运行中...',
    small_scale_completed: '小规模测试完成',
    simulation_completed: '模拟完成',
    mechanism_adjusting: '机制调整中...',
    mechanism_adjust_completed: '机制调整完成',
    mechanism_adjust_skipped: '跳过机制调整',
    applying_adjustments: '应用调整中...',
    adjustments_applied: '调整已应用',
    evaluating: '评估中...',
    evaluation_waiting_confirm: '评估完成，等待确认',
    applying_optimization: '应用优化中...',
    optimization_applied: '优化已应用',
    completed: '全部完成',
    error: '出错',
    simulation_failed: '模拟失败'
  }
  return texts[status.value] || status.value
})

const showInteractiveActions = computed(() => {
  const shouldShow = mode.value === 'interactive' && [
    'parsed', 
    'design_completed', 
    'coding_completed',
    'evaluation_waiting_confirm'
  ].includes(status.value)
  console.log(`🔍 交互按钮显示检查: mode=${mode.value}, status=${status.value}, loading=${loading.value}, shouldShow=${shouldShow}`)
  return shouldShow
})

const waitingForFeedback = computed(() => {
  return showInteractiveActions.value
})

const isCompleted = computed(() => {
  return status.value === 'completed'
})

const hasError = computed(() => {
  return status.value === 'error'
})

const canViewFiles = computed(() => {
  return phaseResults.value && (
    phaseResults.value.config_dir ||
    phaseResults.value.coding_results
  )
})

const progressPercentage = computed(() => {
  const stepPercentages = {
    parse: 10,
    design: 30,
    coding: 50,
    simulation: 70,
    evaluation: 90
  }
  return stepPercentages[phase.value] || 0
})

const currentPhaseDescription = computed(() => {
  if (!phase.value) return ''
  
  const descriptions = {
    parse: '正在分析您的需求',
    design: '正在设计系统架构',
    coding: '正在生成代码文件',
    simulation: '正在运行模拟测试',
    evaluation: '正在评估结果'
  }
  return descriptions[phase.value] || ''
})

const phaseTaskDescription = computed(() => {
  const tasks = {
    parse: 'AI正在解析您的需求，识别关键要素，选择合适的模块...',
    design: '根据需求生成系统设计文档和配置文件，规划整体架构...',
    coding: '自动编写模拟器代码、入口文件和配置文件...',
    simulation: testType.value === 'small' ? '运行小规模测试验证基本功能...' : '运行大规模测试获取完整数据...',
    evaluation: '分析模拟结果，评估是否符合预期，提供优化建议...'
  }
  return tasks[phase.value] || ''
})

const renderedDesignDoc = computed(() => {
  return marked(designDoc.value)
})

const renderedEvaluationReport = computed(() => {
  if (phaseResults.value?.evaluation_results?.evaluation_report) {
    return marked(phaseResults.value.evaluation_results.evaluation_report)
  }
  return ''
})

const codingFileProgress = computed(() => {
  if (status.value !== 'coding') return []
  
  // 使用持久化的进度状态
  const files = [
    { name: '模拟器代码 (simulator.py)', status: codingProgress.value.simulator.status, progress: codingProgress.value.simulator.progress },
    { name: '入口文件 (main.py)', status: codingProgress.value.main.status, progress: codingProgress.value.main.progress },
    { name: '配置文件 (config.yaml)', status: codingProgress.value.config.status, progress: codingProgress.value.config.progress },
    { name: '提示词文件 (prompts.yaml)', status: codingProgress.value.prompts.status, progress: codingProgress.value.prompts.progress }
  ]
  
  return files
})

// 方法
const startCreation = async () => {
  if (!requirement.value.trim()) {
    ElMessage.warning(t('aiCreator.requirement.inputRequired'))
    return
  }

  loading.value = true
  currentStep.value = 1

  try {
    // 1. 解析需求
    const response = await fetch('/api/ai_system/parse_requirement', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirement_text: requirement.value })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || t('aiCreator.phases.parsing.title'))
    }

    sessionId.value = data.session_id
    status.value = data.status

    // 开始轮询状态
    startStatusPolling()

  } catch (error) {
    ElMessage.error(error.message)
    loading.value = false
    currentStep.value = 0
  }
}

const startStatusPolling = () => {
  // 清除现有定时器
  if (statusCheckTimer) {
    clearInterval(statusCheckTimer)
  }

  // 每2秒检查一次状态
  statusCheckTimer = setInterval(async () => {
    await checkStatus()
  }, 2000)
}

const stopStatusPolling = () => {
  if (statusCheckTimer) {
    clearInterval(statusCheckTimer)
    statusCheckTimer = null
  }
}

// 更新编码进度的函数
const updateCodingProgress = (msg) => {
  const logMsg = msg.toLowerCase()
  
  // 检测simulator相关进度 - 只向前推进，不后退
  if ((logMsg.includes('simulator') || logMsg.includes('模拟器')) && 
      codingProgress.value.simulator.status !== 'completed') {
    if (logMsg.includes('已生成') || logMsg.includes('已完成') || logMsg.includes('completed')) {
      codingProgress.value.simulator = { status: 'completed', progress: 100 }
      // simulator完成后，main开始
      if (codingProgress.value.main.status === 'pending') {
        codingProgress.value.main = { status: 'processing', progress: 0 }
      }
      console.log('🎯 Simulator 已完成')
    } else if ((logMsg.includes('生成') || logMsg.includes('完善') || logMsg.includes('步骤')) &&
               codingProgress.value.simulator.status === 'pending') {
      codingProgress.value.simulator = { status: 'processing', progress: 50 }
      console.log('⚙️ Simulator 处理中')
    }
  }
  
  // 检测main文件相关进度
  if ((logMsg.includes('main') || logMsg.includes('入口')) && 
      codingProgress.value.main.status !== 'completed') {
    // 确保simulator已完成
    if (codingProgress.value.simulator.status !== 'completed') {
      codingProgress.value.simulator = { status: 'completed', progress: 100 }
    }
    
    if (logMsg.includes('已生成') || logMsg.includes('已完成') || logMsg.includes('completed')) {
      codingProgress.value.main = { status: 'completed', progress: 100 }
      // main完成后，config开始
      if (codingProgress.value.config.status === 'pending') {
        codingProgress.value.config = { status: 'processing', progress: 0 }
      }
      console.log('🎯 Main 已完成')
    } else if ((logMsg.includes('生成') || logMsg.includes('完善') || logMsg.includes('步骤')) &&
               codingProgress.value.main.status === 'pending') {
      codingProgress.value.main = { status: 'processing', progress: 50 }
      console.log('⚙️ Main 处理中')
    }
  }
  
  // 检测配置文件相关进度
  if ((logMsg.includes('config') || logMsg.includes('配置')) && 
      codingProgress.value.config.status !== 'completed') {
    // 确保前面的都完成
    if (codingProgress.value.simulator.status !== 'completed') {
      codingProgress.value.simulator = { status: 'completed', progress: 100 }
    }
    if (codingProgress.value.main.status !== 'completed') {
      codingProgress.value.main = { status: 'completed', progress: 100 }
    }
    
    if (logMsg.includes('已生成') || logMsg.includes('已完成') || logMsg.includes('completed')) {
      codingProgress.value.config = { status: 'completed', progress: 100 }
      // config完成后，prompts开始
      if (codingProgress.value.prompts.status === 'pending') {
        codingProgress.value.prompts = { status: 'processing', progress: 0 }
      }
      console.log('🎯 Config 已完成')
    } else if (logMsg.includes('生成') && codingProgress.value.config.status === 'pending') {
      codingProgress.value.config = { status: 'processing', progress: 50 }
      console.log('⚙️ Config 处理中')
    }
  }
  
  // 检测提示词文件相关进度
  if ((logMsg.includes('prompt') || logMsg.includes('提示词')) && 
      codingProgress.value.prompts.status !== 'completed') {
    // 确保前面的都完成
    if (codingProgress.value.simulator.status !== 'completed') {
      codingProgress.value.simulator = { status: 'completed', progress: 100 }
    }
    if (codingProgress.value.main.status !== 'completed') {
      codingProgress.value.main = { status: 'completed', progress: 100 }
    }
    if (codingProgress.value.config.status !== 'completed') {
      codingProgress.value.config = { status: 'completed', progress: 100 }
    }
    
    if (logMsg.includes('已生成') || logMsg.includes('已完成') || logMsg.includes('completed')) {
      codingProgress.value.prompts = { status: 'completed', progress: 100 }
      console.log('🎯 Prompts 已完成')
    } else if (logMsg.includes('生成') && codingProgress.value.prompts.status === 'pending') {
      codingProgress.value.prompts = { status: 'processing', progress: 50 }
      console.log('⚙️ Prompts 处理中')
    }
  }
  
  // 检测编码阶段完成
  if (logMsg.includes('编码阶段完成') || logMsg.includes('coding') && logMsg.includes('completed')) {
    codingProgress.value.simulator = { status: 'completed', progress: 100 }
    codingProgress.value.main = { status: 'completed', progress: 100 }
    codingProgress.value.config = { status: 'completed', progress: 100 }
    codingProgress.value.prompts = { status: 'completed', progress: 100 }
    console.log('🎉 编码阶段全部完成')
  }
}

const checkStatus = async () => {
  if (!sessionId.value) return

  try {
    const response = await fetch(`/api/ai_system/status/${sessionId.value}`)
    const data = await response.json()

    const prevStatus = status.value
    const prevPhase = phase.value
    
    status.value = data.status
    phase.value = data.phase
    
    // 累积输出行
    if (data.output && typeof data.output === 'string' && data.output.trim()) {
      const newLines = data.output.split('\n').filter(line => line.trim())
      allOutputLines.value.push(...newLines)
      
      // 只保留最近1000行，避免内存溢出
      if (allOutputLines.value.length > 1000) {
        allOutputLines.value = allOutputLines.value.slice(-1000)
      }
      
      // 从新接收到的行中提取最新的有效日志
      for (let i = newLines.length - 1; i >= 0; i--) {
        const line = newLines[i].trim()
        if (line.includes('INFO') || line.includes('✓') || line.includes('修改') || line.includes('修复') || line.includes('尝试') || line.includes('步骤')) {
          // 多种格式的日志提取
          let msg = ''
          
          // 格式1: 标准INFO日志
          const infoMatch = line.match(/INFO\s*-\s*(.+)$/)
          if (infoMatch && infoMatch[1]) {
            msg = infoMatch[1].trim()
          } 
          // 格式2: 带时间戳的日志
          else if (line.match(/\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]/)) {
            const timeMatch = line.match(/\]\s*(.+)$/)
            if (timeMatch && timeMatch[1]) {
              msg = timeMatch[1].trim()
              // 移除可能的INFO前缀
              msg = msg.replace(/^INFO\s*-\s*/, '')
            }
          }
          // 格式3: 直接的消息（带特殊符号）
          else if (line.includes('✓') || line.includes('修改') || line.includes('修复') || line.includes('尝试') || line.includes('步骤')) {
            msg = line.replace(/^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*/, '')
          }
          
          // 过滤掉空消息、过长的日志和无用信息
          if (msg.length > 0 && msg.length < 300 && 
              !msg.includes('Traceback') && 
              !msg.includes('Exception') &&
              !msg.includes('====') &&
              !msg.includes('Detected change')) {  // 避免分隔线和文件变更检测
            // 清理消息中的ANSI颜色代码
            msg = msg.replace(/\x1b\[[0-9;]*m/g, '')
            latestLogMessage.value = msg
            console.log('📝 提取到日志:', msg)  // 调试输出
            
            // 如果是编码阶段，更新编码进度
            if (status.value === 'coding') {
              updateCodingProgress(msg)
            }
            
            break
          }
        }
      }
    }

    // 更新结果
    if (data.results) {
      phaseResults.value = data.results
      
      // 更新版本历史 - 只在状态首次改变时增加
      if (data.phase === 'design' && data.status === 'design_completed' && prevStatus !== 'design_completed') {
        versionHistory.value.design += 1
      } else if (data.phase === 'coding' && data.status === 'coding_completed' && prevStatus !== 'coding_completed') {
        versionHistory.value.coding += 1
      }
    }

    // 处理用户确认请求
    if (data.waiting_confirmation && !showConfirmDialog.value) {
      confirmMessage.value = data.confirmation_message
      confirmType.value = data.confirmation_type
      confirmOptions.value = data.confirmation_options || []
      confirmInput.value = ''
      showConfirmDialog.value = true
      console.log('显示确认对话框:', data.confirmation_message)
    }

    // 打印状态信息用于调试
    if (prevStatus !== data.status || prevPhase !== data.phase) {
      console.log(`状态变化: [${prevPhase}/${prevStatus}] -> [${data.phase}/${data.status}]`)
      console.log('当前模式:', mode.value)
    }

    // 更新步骤
    updateCurrentStep(data.phase, data.status)

    // 在阶段完成时重置 loading 状态
    if ((data.status === 'parsed' || data.status.includes('completed') || data.status === 'evaluation_waiting_confirm') && loading.value) {
      console.log(`🔄 重置加载状态前: loading=${loading.value}, status=${data.status}`)
      loading.value = false
      console.log(`✅ 重置加载状态后: loading=${loading.value}`)
    }

    // 处理状态变化 - 只在状态改变时触发自动模式
    if (mode.value === 'auto' && prevStatus !== data.status) {
      if (data.status === 'parsed') {
        // 自动模式：继续设计阶段
        console.log('✓ 自动触发设计阶段')
        setTimeout(() => runDesignPhase(), 1000)
      } else if (data.status === 'design_completed') {
        // 自动模式：继续编码阶段
        console.log('✓ 自动触发编码阶段')
        setTimeout(() => runCodingPhase(), 1000)
      } else if (data.status === 'coding_completed') {
        // 自动模式：运行小规模模拟
        console.log('✓ 自动触发小规模模拟')
        setTimeout(() => runSimulation('small'), 1000)
      } else if (data.status === 'small_scale_completed') {
        // 小规模完成后，继续大规模测试（自动模式）
        console.log('✓ 小规模完成，继续大规模测试')
        setTimeout(() => runLargeScaleTest(), 1000)
      }
    }
    
    if (data.status === 'completed' || data.status === 'error' || data.status === 'simulation_failed') {
      // 停止轮询
      console.log('✓ 流程结束，停止轮询')
      stopStatusPolling()
      loading.value = false
    }

  } catch (error) {
    console.error('检查状态失败:', error)
  }
}

const updateCurrentStep = (currentPhase, currentStatus) => {
  const stepMap = {
    parse: 1,
    design: 2,
    coding: 3,
    simulation: 4,
    evaluation: 5
  }

  const step = stepMap[currentPhase] || 1
  
  // 如果阶段完成，前进到下一步
  if (currentStatus.includes('completed')) {
    currentStep.value = step + 1
  } else {
    currentStep.value = step
  }
}

const runDesignPhase = async () => {
  console.log('🚀 开始调用设计阶段API...')
  loading.value = true
  
  try {
    const response = await fetch('/api/ai_system/run_design', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        user_feedback: userFeedback.value || null
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '运行设计阶段失败')
    }

    console.log('✓ 设计阶段API调用成功')
    userFeedback.value = ''
    // loading 会在状态变化为 design_completed 或 error 时重置

  } catch (error) {
    console.error('❌ 设计阶段API调用失败:', error)
    ElMessage.error(error.message)
    loading.value = false
  }
}

const runCodingPhase = async () => {
  console.log('🚀 开始调用编码阶段API...')
  loading.value = true
  codingStartTime.value = Date.now()
  
  // 重置编码进度
  codingProgress.value = {
    simulator: { status: 'processing', progress: 0 },
    main: { status: 'pending', progress: 0 },
    config: { status: 'pending', progress: 0 },
    prompts: { status: 'pending', progress: 0 }
  }
  
  try {
    const response = await fetch('/api/ai_system/run_coding', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        user_feedback: userFeedback.value || null
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '运行编码阶段失败')
    }

    console.log('✓ 编码阶段API调用成功')
    userFeedback.value = ''

  } catch (error) {
    console.error('❌ 编码阶段API调用失败:', error)
    ElMessage.error(error.message)
    loading.value = false
  }
}

const runSimulation = async (test_type = 'small') => {
  console.log(`🚀 开始调用模拟运行API... (${test_type === 'small' ? '小规模' : '大规模'}测试)`)
  loading.value = true
  testType.value = test_type
  
  try {
    const response = await fetch('/api/ai_system/run_simulation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        test_type: test_type
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '运行模拟失败')
    }

    console.log('✓ 模拟运行API调用成功')

  } catch (error) {
    console.error('❌ 模拟运行API调用失败:', error)
    ElMessage.error(error.message)
    loading.value = false
  }
}

const continueToNextPhase = () => {
  if (status.value === 'parsed') {
    runDesignPhase()
  } else if (status.value === 'design_completed') {
    runCodingPhase()
  } else if (status.value === 'coding_completed') {
    runSimulation('small')
  }
}

const regeneratePhase = () => {
  if (!userFeedback.value.trim()) {
    ElMessage.warning('请输入反馈意见以重新生成')
    return
  }
  continueToNextPhase()
}

const retryCurrentPhase = () => {
  if (phase.value === 'parse') {
    startCreation()
  } else {
    continueToNextPhase()
  }
}

const cancelCreation = () => {
  stopStatusPolling()
  resetCreator()
}

const resetCreator = () => {
  stopStatusPolling()
  currentStep.value = 0
  requirement.value = ''
  sessionId.value = null
  status.value = ''
  phase.value = ''
  phaseResults.value = null
  loading.value = false
  userFeedback.value = ''
  latestLogMessage.value = ''  // 清空日志消息
  allOutputLines.value = []  // 清空累积的输出
  // 重置编码进度
  codingProgress.value = {
    simulator: { status: 'pending', progress: 0 },
    main: { status: 'pending', progress: 0 },
    config: { status: 'pending', progress: 0 },
    prompts: { status: 'pending', progress: 0 }
  }
}

const viewDesignDoc = async () => {
  if (!phaseResults.value?.config_dir) return

  try {
    const configDir = phaseResults.value.config_dir
    const simulationName = phaseResults.value.simulation_name
    
    // 从后端获取设计文档
    const response = await fetch(`/api/description/${simulationName}`)
    const data = await response.json()
    
    designDoc.value = data.description || '无法加载设计文档'
    designDocEditable.value = designDoc.value
    designDocMode.value = 'preview'
    showDesignDialog.value = true

  } catch (error) {
    ElMessage.error('加载设计文档失败')
  }
}

const saveDesignDoc = async () => {
  if (!phaseResults.value?.simulation_name) return
  
  savingDesignDoc.value = true
  
  try {
    const response = await fetch('/api/ai_system/save_design_doc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        simulation_name: phaseResults.value.simulation_name,
        content: designDocEditable.value
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '保存设计文档失败')
    }

    designDoc.value = designDocEditable.value
    ElMessage.success('设计文档已保存')
    showDesignDialog.value = false

  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    savingDesignDoc.value = false
  }
}

const goToSimulation = () => {
  if (phaseResults.value?.simulation_name) {
    emit('simulation-created', phaseResults.value.simulation_name)
  }
}

const viewCurrentFiles = () => {
  if (!phaseResults.value) return
  
  // 根据当前阶段显示不同的文件
  let message = '生成的文件位置：\n\n'
  
  if (phaseResults.value.config_dir) {
    message += `配置目录: ${phaseResults.value.config_dir}\n`
  }
  
  if (phaseResults.value.coding_results) {
    const coding = phaseResults.value.coding_results
    if (coding.simulator_files) {
      message += `\n模拟器: ${coding.simulator_files[0]}`
    }
    if (coding.main_files) {
      message += `\n入口文件: ${coding.main_files[0]}`
    }
    if (coding.config_files) {
      message += `\n\n配置文件 (${coding.config_files.length}个):`
      coding.config_files.forEach(f => {
        message += `\n  - ${f}`
      })
    }
  }
  
  ElMessage.info({
    message: message,
    duration: 5000,
    showClose: true
  })
}

const runMechanismAdjust = async () => {
  console.log('🚀 打开机制调整对话框...')
  
  // 重置对话状态
  mechanismDialogHistory.value = []
  mechanismUserInput.value = ''
  mechanismOverview.value = ''
  adjustmentList.value = []
  mechanismLoading.value = true
  showMechanismDialog.value = true
  
  try {
    // 获取机制概览
    const response = await fetch('/api/ai_system/mechanism_overview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '获取机制概览失败')
    }

    mechanismOverview.value = data.overview
    mechanismDialogHistory.value.push({
      role: 'assistant',
      content: `【当前机制概览】\n\n${data.overview}\n\n您可以提问关于模拟的任何问题，或提出调整建议。输入 'done' 完成对话。`,
      timestamp: new Date().toLocaleTimeString()
    })
    
    console.log('✓ 机制概览获取成功')

  } catch (error) {
    console.error('❌ 获取机制概览失败:', error)
    ElMessage.error(error.message)
    showMechanismDialog.value = false
  } finally {
    mechanismLoading.value = false
  }
}

const runLargeScaleTest = async () => {
  console.log('🚀 开始大规模测试...')
  loading.value = true
  
  try {
    const response = await fetch('/api/ai_system/run_simulation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        test_type: 'large'
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '启动大规模测试失败')
    }

    console.log('✓ 大规模测试启动成功')
    testType.value = 'large'
    
    // 启动状态轮询
    startStatusPolling()

  } catch (error) {
    console.error('❌ 大规模测试启动失败:', error)
    ElMessage.error(error.message)
    loading.value = false
  }
}

const applyAdjustments = async (adjustmentsText) => {
  console.log('🚀 应用机制调整...')
  loading.value = true
  
  try {
    const response = await fetch('/api/ai_system/apply_adjustments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        adjustments: adjustmentsText
      })
    })

    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '应用调整失败')
    }

    console.log('✓ 机制调整应用成功')

  } catch (error) {
    console.error('❌ 应用调整失败:', error)
    ElMessage.error(error.message)
    loading.value = false
  }
}

const sendMechanismMessage = async () => {
  const message = mechanismUserInput.value.trim()
  if (!message) return
  
  // 添加用户消息到历史
  mechanismDialogHistory.value.push({
    role: 'user',
    content: message,
    timestamp: new Date().toLocaleTimeString()
  })
  
  mechanismUserInput.value = ''
  
  // 检查是否是结束命令
  if (message.toLowerCase() === 'done') {
    await finishMechanismAdjust()
    return
  }
  
  mechanismLoading.value = true
  
  try {
    const response = await fetch('/api/ai_system/mechanism_chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        message: message
      })
    })
    
    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '发送消息失败')
    }
    
    // 添加AI回复到历史
    mechanismDialogHistory.value.push({
      role: 'assistant',
      content: data.response,
      timestamp: new Date().toLocaleTimeString()
    })
    
    // 如果是调整需求，更新需求列表
    if (data.intent === 'adjustment' && data.confirmed) {
      adjustmentList.value.push(data.adjustment_description)
    }
    
  } catch (error) {
    console.error('❌ 发送消息失败:', error)
    ElMessage.error(error.message)
  } finally {
    mechanismLoading.value = false
    // 滚动到底部
    nextTick(() => {
      const container = document.querySelector('.mechanism-dialog-messages')
      if (container) {
        container.scrollTop = container.scrollHeight
      }
    })
  }
}

const finishMechanismAdjust = async () => {
  mechanismLoading.value = true
  
  try {
    // 将收集到的需求发送给后端
    if (adjustmentList.value.length > 0) {
      const requirementsText = adjustmentList.value.map((req, i) => `${i + 1}. ${req}`).join('\n')
      
      mechanismDialogHistory.value.push({
        role: 'assistant',
        content: `✓ 收集到 ${adjustmentList.value.length} 项调整需求，正在应用...`,
        timestamp: new Date().toLocaleTimeString()
      })
      
      // 应用调整
      await applyAdjustments(requirementsText)
      
      ElMessage.success('机制调整需求已提交')
    } else {
      ElMessage.info('未收集到调整需求')
    }
    
    showMechanismDialog.value = false
    
  } catch (error) {
    console.error('❌ 完成机制调整失败:', error)
    ElMessage.error(error.message)
  } finally {
    mechanismLoading.value = false
  }
}

const applyOptimization = async () => {
  console.log('🚀 开始应用优化调整...')
  
  // 不要在这里设置loading，由后端状态变化来控制
  try {
    const response = await fetch('/api/ai_system/apply_optimization', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value
      })
    })
    
    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '应用优化失败')
    }
    
    ElMessage.success('开始应用优化调整')
    console.log('✓ 优化调整已启动')
    
    // 隐藏确认按钮，由后端状态更新控制显示
    if (phaseResults.value?.evaluation_results) {
      phaseResults.value.evaluation_results.waiting_user_confirmation = false
    }
    
  } catch (error) {
    console.error('❌ 应用优化失败:', error)
    ElMessage.error(error.message)
  }
}

const skipOptimization = async () => {
  try {
    const result = await ElMessageBox.confirm(
      '确定要跳过优化调整吗？这可能会影响模拟的准确性。',
      '确认',
      {
        confirmButtonText: '确定跳过',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    // 用户确认跳过，调用后端API
    const response = await fetch('/api/ai_system/skip_optimization', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value
      })
    })
    
    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.error || '跳过优化失败')
    }
    
    // 隐藏确认按钮
    if (phaseResults.value?.evaluation_results) {
      phaseResults.value.evaluation_results.waiting_user_confirmation = false
    }
    
    ElMessage.info('已跳过优化调整')
    console.log('✓ 已跳过优化调整')
    
  } catch (error) {
    if (error !== 'cancel') {
      console.error('❌ 跳过优化失败:', error)
      ElMessage.error(error.message || '跳过优化失败')
    }
  }
}

const closeMechanismDialog = () => {
  if (adjustmentList.value.length > 0) {
    ElMessageBox.confirm(
      '您有未提交的调整需求，确定要关闭吗？',
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      showMechanismDialog.value = false
    }).catch(() => {})
  } else {
    showMechanismDialog.value = false
  }
}

const handleConfirm = async (confirmed) => {
  try {
    console.log('发送确认请求:', { sessionId: sessionId.value, confirmed, input: confirmInput.value })
    
    const response = await fetch(`/api/ai_system/confirm/${sessionId.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        confirmed: confirmed,
        input: confirmInput.value
      })
    })

    const data = await response.json()
    console.log('确认响应:', data)

    if (!response.ok) {
      throw new Error(data.error || '发送确认失败')
    }

    console.log('✓ 用户确认已发送:', confirmed ? '是' : '否')
    showConfirmDialog.value = false
    confirmInput.value = ''
    
    ElMessage.success(confirmed ? '已选择重新生成' : '已选择使用现有文件')

  } catch (error) {
    console.error('❌ 发送确认失败:', error)
    ElMessage.error(error.message)
  }
}

// 清理
onUnmounted(() => {
  stopStatusPolling()
})
</script>

<style scoped>
.ai-system-creator {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  font-size: 1rem;
}

.creator-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.creator-header h2 {
  font-size: 1.8rem;
  font-weight: 600;
}

.steps-container {
  margin-bottom: 30px;
}

.steps-container :deep(.el-step__title) {
  font-size: 1.1rem;
}

.step-content {
  flex: 1;
  overflow-y: auto;
}

.requirement-input {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.requirement-input :deep(.el-alert__title) {
  font-size: 1.1rem;
}

.requirement-input :deep(.el-alert__description) {
  font-size: 1rem;
}

.requirement-input :deep(.el-input__inner),
.requirement-input :deep(.el-textarea__inner) {
  font-size: 1rem;
}

.mode-selection {
  margin: 16px 0;
}

.mode-selection :deep(.el-radio__label) {
  font-size: 1rem;
}

.example-requirements {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.example-requirements span {
  font-size: 1rem;
}

.example-requirements :deep(.el-tag) {
  font-size: 0.95rem;
}

.progress-display {
  margin-bottom: 20px;
}

.rotating {
  animation: rotate 1.5s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.execution-timeline {
  margin-top: 20px;
}

.execution-timeline :deep(.el-timeline-item__timestamp) {
  font-weight: 700;
  font-size: 1.25rem;
  color: var(--el-text-color-primary);
}

.timeline-card-title {
  font-size: 1.05rem;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

/* 增大所有描述列表的字体 */
.execution-timeline :deep(.el-descriptions__label),
.execution-timeline :deep(.el-descriptions__content) {
  font-size: 0.95rem !important;
  padding: 10px 12px !important;
}

.execution-timeline :deep(.el-descriptions__label) {
  font-weight: 500 !important;
}

/* 增大表格字体 */
.execution-timeline :deep(.el-table) {
  font-size: 0.95rem !important;
}

.execution-timeline :deep(.el-table th),
.execution-timeline :deep(.el-table td) {
  font-size: 0.95rem !important;
  padding: 10px 8px !important;
}

.execution-timeline :deep(.el-table__header th) {
  font-size: 0.95rem !important;
  font-weight: 600 !important;
}

.execution-timeline :deep(.el-table__body td) {
  font-size: 0.95rem !important;
}

/* 增大Alert字体 */
.execution-timeline :deep(.el-alert__description),
.execution-timeline :deep(.el-alert__title) {
  font-size: 1.05rem;
}

/* 增大Tag字体 */
.execution-timeline :deep(.el-tag) {
  font-size: 1rem;
}

/* 增大按钮字体 */
.execution-timeline :deep(.el-button) {
  font-size: 1.05rem;
}

.active-phase-card {
  border: 2px solid var(--el-color-primary);
  box-shadow: 0 0 12px rgba(64, 158, 255, 0.2);
}

.coding-progress {
  padding: 8px 0;
}

.progress-item {
  margin-bottom: 8px;
}

.coding-summary {
  padding: 8px 0;
}

.phase-results {
  margin-top: 20px;
}

.result-section {
  margin-bottom: 20px;
}

.result-section h4 {
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
}

.actions {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.actions :deep(.el-input__inner),
.actions :deep(.el-textarea__inner) {
  font-size: 1rem;
}

.actions :deep(.el-button) {
  font-size: 1.05rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1.15rem;
}

.card-header :deep(.el-tag) {
  font-size: 1rem;
}

.design-doc-content {
  line-height: 1.6;
  max-height: 600px;
  overflow-y: auto;
  font-size: 1.05rem;
}

.design-doc-content :deep(h1) {
  font-size: 1.6rem;
  margin-bottom: 16px;
}

.design-doc-content :deep(h2) {
  font-size: 1.4rem;
  margin: 16px 0;
}

.design-doc-content :deep(p) {
  margin: 12px 0;
  font-size: 1.05rem;
}

.design-doc-content :deep(ul),
.design-doc-content :deep(ol) {
  padding-left: 24px;
  margin: 12px 0;
  font-size: 1.05rem;
}

.design-doc-content :deep(li) {
  font-size: 1.05rem;
}

.design-doc-content :deep(code) {
  background-color: var(--el-fill-color-light);
  padding: 2px 4px;
  border-radius: 4px;
  font-size: 0.95rem;
}

.design-doc-content :deep(pre) {
  background-color: var(--el-fill-color);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 16px 0;
}

.design-doc-editor {
  font-family: 'Courier New', monospace;
  font-size: 1rem;
}

.design-doc-editor :deep(textarea) {
  font-family: 'Courier New', monospace;
  line-height: 1.6;
  font-size: 1rem;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 机制调整对话框样式 */
.mechanism-dialog-container {
  display: flex;
  gap: 20px;
  height: 600px;
  font-size: 1.05rem;
}

.mechanism-dialog-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mechanism-dialog-right {
  width: 300px;
  border-left: 1px solid var(--el-border-color);
  padding-left: 20px;
  display: flex;
  flex-direction: column;
}

.mechanism-dialog-right h4 {
  margin: 0 0 16px 0;
  color: var(--el-text-color-primary);
}

.mechanism-dialog-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  background-color: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.message-item {
  margin-bottom: 16px;
  padding: 12px;
  border-radius: 8px;
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.user-message {
  background-color: var(--el-color-primary-light-9);
  margin-left: 60px;
}

.assistant-message {
  background-color: var(--el-fill-color-blank);
  margin-right: 60px;
  border: 1px solid var(--el-border-color-light);
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 0.95rem;
}

.message-role {
  font-weight: bold;
  color: var(--el-text-color-primary);
  font-size: 1rem;
}

.user-message .message-role {
  color: var(--el-color-primary);
}

.message-time {
  color: var(--el-text-color-secondary);
}

.message-content {
  color: var(--el-text-color-regular);
  line-height: 1.6;
  font-size: 1.05rem;
}

.mechanism-dialog-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mechanism-dialog-input :deep(.el-textarea__inner) {
  font-size: 1rem;
}

.mechanism-dialog-input :deep(.el-button) {
  font-size: 1rem;
}

.mechanism-dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.adjustment-list {
  flex: 1;
  overflow-y: auto;
}

/* 评估结果样式 */
.evaluation-card {
  margin-top: 16px;
}

.evaluation-status {
  text-align: center;
  margin-bottom: 20px;
}

.evaluation-report {
  margin-bottom: 20px;
}

.report-content {
  max-height: 400px;
  overflow-y: auto;
  background-color: var(--el-fill-color-light);
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
}

.report-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}

/* Markdown渲染样式 */
.markdown-body {
  line-height: 1.6;
  color: var(--el-text-color-regular);
  font-size: 1rem;
}

.markdown-body :deep(h1) {
  font-size: 1.4rem;
  font-weight: 600;
  margin: 16px 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
  color: var(--el-text-color-primary);
}

.markdown-body :deep(h2) {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 14px 0 10px 0;
  color: var(--el-text-color-primary);
}

.markdown-body :deep(h3) {
  font-size: 1.15rem;
  font-weight: 600;
  margin: 12px 0 8px 0;
  color: var(--el-text-color-primary);
}

.markdown-body :deep(p) {
  margin: 8px 0;
  font-size: 1rem;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 24px;
  margin: 8px 0;
  font-size: 1rem;
}

.markdown-body :deep(li) {
  margin: 4px 0;
  font-size: 1rem;
}

.markdown-body :deep(code) {
  background-color: var(--el-fill-color);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.95rem;
  color: var(--el-color-danger);
}

.markdown-body :deep(pre) {
  background-color: var(--el-fill-color);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 12px 0;
  border: 1px solid var(--el-border-color-lighter);
}

.markdown-body :deep(pre code) {
  background-color: transparent;
  padding: 0;
  color: var(--el-text-color-regular);
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--el-color-primary);
  padding-left: 12px;
  margin: 12px 0;
  color: var(--el-text-color-secondary);
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--el-border-color);
  padding: 8px 12px;
  text-align: left;
}

.markdown-body :deep(th) {
  background-color: var(--el-fill-color-light);
  font-weight: 600;
}

.markdown-body :deep(strong) {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.markdown-body :deep(em) {
  font-style: italic;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--el-border-color-light);
  margin: 16px 0;
}

.diagnosis-info,
.modification-results,
.optimization-completed {
  margin-bottom: 20px;
}

.evaluation-card :deep(.el-divider__text) {
  background-color: var(--el-bg-color);
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

/* 最新日志消息样式 */
.latest-log-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-top: 12px;
  background-color: var(--el-fill-color-lighter);
  border-left: 3px solid var(--el-color-primary);
  border-radius: 4px;
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.latest-log-message .log-icon {
  color: var(--el-color-primary);
  font-size: 1rem;
  flex-shrink: 0;
}

.latest-log-message .log-text {
  flex: 1;
  line-height: 1.5;
  word-break: break-word;
}

</style>
