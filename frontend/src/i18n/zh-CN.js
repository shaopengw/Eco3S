export default {
  common: {
    confirm: '确认',
    cancel: '取消',
    save: '保存',
    delete: '删除',
    edit: '编辑',
    back: '返回',
    submit: '提交',
    reset: '重置',
    search: '搜索',
    loading: '加载中...',
    success: '成功',
    error: '错误',
    warning: '警告',
    info: '信息',
    close: '关闭',
    continue: '继续',
    skip: '跳过',
    retry: '重试',
    regenerate: '重新生成',
    useExisting: '使用现有文件',
    index: '序号',
    unknownFile: '未知文件',
    noReason: '未提供原因',
    modification: '修改',
    modificationApplied: '已应用修改',
    yes: '是',
    no: '否'
  },
  header: {
    title: 'Eco3S',
    topNav: {
      aria: '主导航',
      intro: '介绍',
      workbench: '工作台',
      ai: 'AI 系统'
    },
    nav: {
      dashboard: '运行大盘',
      history: '运行历史',
      analysis: '数据分析',
      backHome: '返回首页'
    },
    localeAria: '界面语言'
  },

  settings: {
    open: '模型与 API 设置',
    drawerTitle: '模型与 API 配置',
    drawerHint: '运行模拟或 AI 流程前先在此填写接口地址与密钥。API Key 留空表示不改动已保存的值。',
    providerKeyPh: '厂商键名（如 OPENAI）',
    modelTypes: '模型类型（英文逗号分隔）',
    modelTypesPh: '例如 gpt-4o, gpt-3.5-turbo',
    modelPlatform: '模型平台（ModelPlatformType）',
    urlEnv: 'Base URL 环境变量名',
    urlEnvPh: '例如 OPENAI_API_BASE_URL',
    baseUrl: 'Base URL 取值',
    apiKeyEnv: 'API Key 环境变量名',
    apiKeyEnvPh: '例如 OPENAI_API_KEY',
    apiKey: 'API Key 取值',
    apiKeyConfigured: '已保存',
    apiKeyPlaceholder: '粘贴 API Key',
    apiKeyLeaveBlank: '留空则保留当前密钥',
    allowRandom: '允许随机选用',
    allowRandomHelp: '开启后，该模型可被系统随机选用；关闭后，系统不会自动选择它，但仍可手动指定使用。',
    addProvider: '添加厂商',
    remove: '删除',
    confirmRemove: '从列表中删除该厂商？',
    needOneProvider: '请至少保留一个已命名的厂商后再保存。',
    save: '保存',
    loadFailed: '加载 API 配置失败',
    saveFailed: '保存失败',
    saveSuccess: '已保存。若后端已在运行，请重启后再试。',
    precheckMessage: '请先在设置中配置 API Key 后再开始（缺少）'
  },

  menu: {
    createNew: '创建新模拟',
    aiAssisted: 'AI辅助创建',
    existingSimulations: '已有模拟',
    projectList: '项目列表'
  },
  aiCreator: {
    title: 'AI辅助模拟系统创建器',
    steps: {
      requirement: '需求输入',
      parsing: '需求解析',
      design: '系统设计',
      coding: '代码生成',
      simulation: '运行测试',
      evaluation: '评估优化'
    },
    requirement: {
      title: '输入模拟需求',
      instructions: '使用说明',
      instructionText: '请用自然语言描述您想要创建的模拟实验。系统将自动：',
      instructionList: [
        '分析需求并选择合适的模块',
        '生成设计文档和配置文件',
        '自动编写模拟器代码和入口文件',
        '运行模拟并评估结果'
      ],
      mode: {
        auto: '自动模式 - 一次性完成所有步骤',
        interactive: '交互模式 - 每个阶段等待确认'
      },
      experienceMode:{
        light: '轻量化模式',
        full: '完整模式',
        explanation: '轻量化模式适合初步体验，小规模运行成功后即结束。完整模式可能需要更多时间和资源。若没有明确的研究目标或仅想试用，建议选择轻量化模式。'
      },
      placeholder: '例如：我想研究气候变化对居民迁移的影响，需要模拟100个居民在不同气候条件下的行为，观察他们在极端天气下的决策...',
      examples: '示例需求：',
      exampleList: [
        '我希望研究在一个有极端气候的世界中，政府如何通过调整税收和运河维护投资来平衡财政并抑制叛乱。模拟中应包含政府、居民和叛军三种角色，极端气候会随机发生并对运河造成破坏。',
        '我想研究气候变化对居民迁移的影响，需要模拟100个居民在不同气候条件下的行为，观察他们在极端天气下的决策',
        '我想创建一个信息传播模拟，研究不同的信息传播策略如何影响公众对政策的接受度'
      ],
      startCreation: '开始创建',
      inputRequired: '请输入模拟需求'
    },
    phases: {
      parsing: {
        title: '需求解析中',
        description: '正在分析您的需求',
        task: 'AI正在解析您的需求，识别关键要素，选择合适的模块...',
        completed: '需求解析完成',
        simulationName: '模拟名称',
        simulationType: '模拟类型',
        projectDir: '项目目录',
        timestamp: '需求解析',
        cardTitle: '需求解析完成'
      },
      design: {
        title: '系统设计中',
        description: '正在设计系统架构',
        task: '根据需求生成系统设计文档和配置文件，规划整体架构...',
        completed: '系统设计完成',
        designDoc: '设计文档',
        moduleConfig: '模块配置',
        viewDoc: '查看设计文档',
        generatedDoc: '已生成 description.md',
        generatedConfig: '已生成 modules_config.yaml',
        timestamp: '系统设计',
        cardTitle: '系统设计完成'
      },
      coding: {
        title: '代码生成中',
        description: '正在生成代码文件',
        task: '自动编写模拟器代码、入口文件和配置文件...',
        completed: '代码生成完成',
        simulatorCode: '模拟器代码',
        entryFile: '入口文件',
        configFiles: '个配置文件',
        promptFiles: '个提示词文件',
        timestamp: '代码生成',
        cardTitle: '代码生成完成',
        generating: '正在生成代码...',
        files: {
          simulator: '模拟器代码 (simulator.py)',
          main: '入口文件 (main.py)',
          config: '配置文件 (config.yaml)',
          prompts: '提示词文件 (prompts.yaml)'
        }
      },
      simulation: {
        title: '模拟运行中',
        running: '正在运行模拟...',
        smallScale: '运行小规模测试验证基本功能...',
        largeScale: '运行大规模测试获取完整数据...',
        completed: '模拟运行完成',
        success: '模拟成功运行！结果已保存到实验数据目录。',
        smallScaleCompleted: '小规模测试完成',
        continueTest: '继续大规模测试',
        mechanismAdjust: '机制解释与调整（可选）',
        testOptions: '您可以选择直接进行大规模测试，或先进行机制调整优化后再测试',
        timestamp: '模拟运行',
        smallScaleTimestamp: '小规模测试',
        smallScaleSuccess: '小规模测试成功运行！'
      },
      evaluation: {
        title: '评估优化中',
        running: '正在评估优化...',
        task: '分析模拟结果，评估是否符合预期，提供优化建议...',
        completed: '评估优化结果',
        needsAdjustment: '需要调整',
        meetsExpectations: '结果符合预期',
        report: '评估报告',
        diagnosis: '诊断建议',
        fileToModify: '文件名',
        reason: '修改原因',
        confirmOptimization: '检测到配置需要调整。请选择是否应用优化建议。',
        applyOptimization: '应用优化调整',
        skipOptimization: '跳过优化',
        modifications: '配置修改记录',
        optimizationCompleted: '优化已完成',
        optimizationSuccess: '模拟结果已达到预期目标，无需进一步调整。',
        timestamp: '评估优化',
        timestampCompleted: '评估完成'
      }
    },
    interactive: {
      reviewResults: '请审查当前阶段的结果',
      feedbackPlaceholder: '输入您的反馈意见（留空表示接受当前结果）',
      confirmContinue: '确认并继续',
      regenerate: '重新生成',
      viewFiles: '查看文件',
      cancel: '取消',
      note: '您可以直接修改生成的文件，或提供反馈意见重新生成。所有后续代码将严格依据设计文档生成。'
    },
    completion: {
      title: '全流程完成',
      message: 'AI系统创建完成！您可以在模拟列表中找到新创建的项目。',
      goToSimulation: '前往模拟',
      createNew: '创建新项目',
      backToHome: '返回首页'
    },
    errors: {
      title: '创建过程出现错误',
      message: '创建过程出现错误，请查看输出日志了解详情。',
      retryStep: '重试当前步骤',
      restart: '重新开始'
    },
    mechanism: {
      title: '机制解释与调整助手',
      yourInput: '您',
      aiAssistant: 'AI助手',
      inputPlaceholder: '输入您的问题或调整建议... (输入 \'done\' 完成对话)',
      send: '发送',
      finish: '完成对话',
      adjustmentList: '已收集的调整需求',
      noAdjustments: '暂无调整需求',
      requirement: '需求'
    },
    confirmation: {
      title: '需要确认',
      existingFile: '发现已存在的文件',
      prompt: '是否重新生成？',
      yes: '重新生成',
      no: '使用现有文件',
      note: {
        regenerate: '选择"重新生成"：将删除现有文件并生成新的内容',
        useExisting: '选择"使用现有文件"：跳过此步骤，保留并使用已存在的文件'
      }
    }
  },
  
  simulation: {
    startButton: '开始模拟',
    historyButton: '模拟历史',
    analyzeButton: '数据分析',
    detailBadge: '项目概览',
    loadingDoc: '正在加载项目说明…',
    loadError: '无法加载该项目的说明文档。',
    emptyDoc: '该项目暂无说明内容。'
  },
  
  simulationRunner: {
    title: '模拟运行器',
    firstRunMayTakeLong: '首次运行可能较长，请耐心等待',
    config: '系统配置',
    backButton: '返回描述页面',
    runButton: '运行模拟',
    running: '运行中...',
    ready: '系统就绪',
    mapTitle: '实时居民分布图',
    activeResidents: '活跃居民',
    noMapData: '暂无轨迹数据',
    runToGenerate: '请先运行模拟生成数据',
    logTitle: '运行日志',
    waitingCmd: '等待执行指令...',
    analysisTitle: '实时数据分析',
    noChartData: '暂无图表数据',
    residentArchive: '居民档案 #{id}',
    residentId: '居民ID',
    town: '所在城镇',
    job: '职业',
    employmentStatus: '就业状态',
    employed: '已就业',
    unemployed: '失业',
    income: '财产/收入',
    satisfaction: '满意度',
    healthIndex: '健康指数',
    unknown: '未知',
    none: '无',
    close: '关闭',
    results: '结果图表',
    basicInfo: '基本信息',
    yearlyDecisions: '历年决策',
    recentMemory: '近期决策与记忆',
    longtermMemory: '长期记忆',
    roleDecision: '决策思考',
    roleEnv: '环境与经历',
    reason: '思考',
    decision: '决策',
    desiredJob: '期望职业',
    speech: '言论',
    noData: '暂无记录'
  },
  charts: {
    unemployment_rate: '失业率 (%)',
    migration_rate: '迁移率 (%)',
    population: '人口总数',
    government_budget: '政府预算',
    rebellion_strength: '叛军力量',
    rebellion_resources: '叛军资源',
    average_satisfaction: '平均满意度',
    tax_rate: '税率',
    river_navigability: '运河通航能力',
    gdp: 'GDP',
    rebellions: '叛乱次数'
  },
  
  simulationHistory: {
    title: '模拟历史',
    backButton: '返回描述页面',
    logsTab: '运行日志',
    plotsTab: '结果图表',
    logDialogTitle: '日志内容',
    loadFailed: '加载历史数据失败',
    loadLogFailed: '加载日志内容失败',
    plotTitles: {
      rebellions: '叛乱次数',
      unemployment: '失业率',
      population: '人口数量',
      government: '政府预算',
      rebellion: '叛乱强度',
      average: '平均满意度',
      tax: '税率',
      river: '河流通航性',
      gdp: 'GDP',
      urban: '城市规模',
      conversation: '对话量',
      knowledge: '知识问答准确率',
      incentive: '激励性选择',
      default: '结果图表',
    },
  },
  
  dataAnalyzer: {
    title: '数据分析',
    population: '人口数量(p)',
    year: '年份(y)',
    startButton: '开始分析',
    populationPlaceholder: '可选，用于过滤结果',
    yearPlaceholder: '可选，用于过滤结果',
    reportTitle: '统计报告',
    plotsTitle: '分析图表',
    success: '分析完成',
    failed: '分析失败，请检查参数后重试',
    requestFailed: '分析请求失败',
  },
  
  configEditor: {
    title: '配置编辑器',
    simulationParams: '模拟参数',
    groupDecisionParams: '群体决策参数',
    dataParams: '数据参数',
    saveButton: '保存配置',
    inputPlaceholder: '请输入',
    loadFailed: '加载配置失败',
    saveFailed: '保存配置失败',
    saveSuccess: '配置保存成功',
  },

  landing: {
    eyebrow: '大语言模型驱动的多智能体因果模拟',
    heroTitle: 'Eco3S · 经济社会系统仿真实验室',
    heroLead:
      'Eco3S（Economic Social System Simulation）面向复杂经济与社会系统：共演物理–社会环境、结构因果反事实推演，以及 SAR（模拟–分析–精炼）自动化，把自然语言研究问题变成可复现、可对比的实验流水线。',
    ctaWorkbench: '进入可视化工作台',
    ctaAi: 'AI 辅助创建（SAR）',
    pillar1Title: '共演环境设计',
    pillar1Body:
      '物理层（气候、地理等）与社会层（异质信息网络 HIN）双层动态耦合：群体行为改变设施与环境，环境变化又驱动迁移、动荡等涌现行为。',
    pillar2Title: '结构因果模拟（SCS）',
    pillar2Body:
      '任意步保存快照，施加政策或气候等干预（类比 do-算子），重新运行以估计因果效应，而不止于相关性轨迹展示。',
    pillar3Title: 'SAR 自动化范式',
    pillar3Body:
      '多角色 AI 协作：需求分析 → 架构与配置生成 → 运行排错 → 结果诊断与闭环优化，把高维研究目标沉淀为稳健代码与配置。',
    modesTitle: '两种使用方式',
    modesSub: '从顶刊对齐的基准复现，到开放式假设探索。',
    mode1Tag: '传统模拟',
    mode1Title: '论文级基准场景',
    mode1Body:
      '内置运河衰败与叛乱、治理起源、信息传播等场景，对齐高影响力经济学研究中的核心机制与空间/网络结构。',
    mode2Tag: 'AI 辅助',
    mode2Title: '用自然语言描述想法',
    mode2Body:
      '由 AI 委员会自动生成与迭代配置与代码、运行与修复，并支持一键轨迹解析、统计图与可读因果叙事分析。',
    footnote: '* 目前处于早期开发阶段，欢迎感兴趣的研究者加入测试与反馈！',
    navHint: '也可随时通过顶部导航在介绍、工作台与 AI 系统之间切换。'
  }
}
