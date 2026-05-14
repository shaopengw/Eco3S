export default {
  common: {
    confirm: 'Confirm',
    cancel: 'Cancel',
    save: 'Save',
    delete: 'Delete',
    edit: 'Edit',
    back: 'Back',
    submit: 'Submit',
    reset: 'Reset',
    search: 'Search',
    loading: 'Loading...',
    success: 'Success',
    error: 'Error',
    warning: 'Warning',
    info: 'Info',
    close: 'Close',
    continue: 'Continue',
    skip: 'Skip',
    retry: 'Retry',
    regenerate: 'Regenerate',
    useExisting: 'Use Existing File',
    index: 'No.',
    unknownFile: 'Unknown File',
    noReason: 'No reason provided',
    modification: 'Modification',
    modificationApplied: 'Modification applied',
    yes: 'Yes',
    no: 'No'
  },
  header: {
    title: 'Eco3S',
    topNav: {
      aria: 'Main sections',
      intro: 'Overview',
      workbench: 'Workbench',
      ai: 'AI system'
    },
    nav: {
      dashboard: 'Dashboard',
      history: 'History',
      analysis: 'Analysis',
      backHome: 'Home'
    },
    localeAria: 'Interface language'
  },

  settings: {
    open: 'Model & API settings',
    drawerTitle: 'Model API configuration',
    drawerHint: 'Set endpoints and keys here before running simulations or AI flows. Leave API key empty to keep the current saved value.',
    providerKeyPh: 'Provider name (e.g. OPENAI)',
    modelTypes: 'Model types (comma-separated)',
    modelTypesPh: 'e.g. gpt-4o, gpt-3.5-turbo',
    modelPlatform: 'Model platform',
    urlEnv: 'Base URL environment variable',
    urlEnvPh: 'e.g. OPENAI_API_BASE_URL',
    baseUrl: 'Base URL value',
    apiKeyEnv: 'API key environment variable',
    apiKeyEnvPh: 'e.g. OPENAI_API_KEY',
    apiKey: 'API key value',
    apiKeyConfigured: 'Saved',
    apiKeyPlaceholder: 'Paste API key',
    apiKeyLeaveBlank: 'Leave blank to keep the current key',
    allowRandom: 'Allow random selection',
    allowRandomHelp: 'When enabled, this model can be randomly selected by the system. When disabled, the system will not automatically pick it, but you can still manually specify it.',
    addProvider: 'Add provider',
    remove: 'Remove',
    confirmRemove: 'Remove this provider from the list?',
    needOneProvider: 'Keep at least one provider with a name before saving.',
    save: 'Save',
    loadFailed: 'Failed to load API configuration',
    saveFailed: 'Save failed',
    saveSuccess: 'Saved. Restart the backend if it was already running.',
    precheckMessage: 'Configure API keys in settings before starting (missing)'
  },

  menu: {
    createNew: 'Create New',
    aiAssisted: 'AI Assisted Creation',
    existingSimulations: 'Existing Simulations',
    projectList: 'Projects'
  },
  aiCreator: {
    title: 'AI-Assisted Simulation System Creator',
    steps: {
      requirement: 'Requirement Input',
      parsing: 'Requirement Parsing',
      design: 'System Design',
      coding: 'Code Generation',
      simulation: 'Running Tests',
      evaluation: 'Evaluation & Optimization'
    },
    requirement: {
      title: 'Input Simulation Requirements',
      instructions: 'Instructions',
      instructionText: 'Please describe your simulation experiment in natural language. The system will automatically:',
      instructionList: [
        'Analyze requirements and select appropriate modules',
        'Generate design documents and configuration files',
        'Automatically write simulator code and entry files',
        'Run simulation and evaluate results'
      ],
      mode: {
        auto: 'Auto Mode - Complete all steps at once',
        interactive: 'Interactive Mode - Wait for confirmation at each stage'
      },
      experienceMode:{
        light: 'Lightweight Mode',
        full: 'Full Mode',
        explanation: 'Lightweight mode is suitable for initial experience, ending after successful small-scale run. Full mode may require more time and resources. If you don\'t have a clear research goal or just want to try it out, lightweight mode is recommended.'
      },
      placeholder: 'Example: I want to study the impact of climate change on resident migration, simulating 100 residents\' behavior under different climate conditions, observing their decisions during extreme weather...',
      examples: 'Example Requirements:',
      exampleList: [
        'I want to study how governments balance budgets and suppress rebellions by adjusting taxes and canal maintenance investments in a world with extreme climate. The simulation should include three roles: government, residents, and rebels. Extreme climate events will occur randomly and damage canals.',
        'I want to study the impact of climate change on resident migration, simulating 100 residents\' behavior under different climate conditions, observing their decisions during extreme weather.',
        'I want to create an information dissemination simulation to study how different information dissemination strategies affect public acceptance of policies.'
      ],
      startCreation: 'Start Creation',
      inputRequired: 'Please input simulation requirements'
    },
    phases: {
      parsing: {
        title: 'Parsing Requirements',
        description: 'Analyzing your requirements',
        task: 'AI is parsing your requirements, identifying key elements, selecting appropriate modules...',
        completed: 'Requirement Parsing Complete',
        simulationName: 'Simulation Name',
        simulationType: 'Simulation Type',
        projectDir: 'Project Directory',
        timestamp: 'Requirement Parsing',
        cardTitle: 'Requirement Parsing Complete'
      },
      design: {
        title: 'Designing System',
        description: 'Designing system architecture',
        task: 'Generating system design documents and configuration files based on requirements, planning overall architecture...',
        completed: 'System Design Complete',
        designDoc: 'Design Document',
        moduleConfig: 'Module Configuration',
        viewDoc: 'View Design Document',
        generatedDoc: 'Generated description.md',
        generatedConfig: 'Generated modules_config.yaml',
        timestamp: 'System Design',
        cardTitle: 'System Design Complete'
      },
      coding: {
        title: 'Generating Code',
        description: 'Generating code files',
        task: 'Automatically writing simulator code, entry files, and configuration files...',
        completed: 'Code Generation Complete',
        simulatorCode: 'Simulator Code',
        entryFile: 'Entry File',
        configFiles: 'configuration files',
        promptFiles: 'prompt files',
        timestamp: 'Code Generation',
        cardTitle: 'Code Generation Complete',
        generating: 'Generating code...',
        files: {
          simulator: 'Simulator Code (simulator.py)',
          main: 'Entry File (main.py)',
          config: 'Configuration Files (config.yaml)',
          prompts: 'Prompt Files (prompts.yaml)'
        }
      },
      simulation: {
        title: 'Running Simulation',
        running: 'Running simulation...',
        smallScale: 'Running small-scale test to verify basic functionality...',
        largeScale: 'Running large-scale test to obtain complete data...',
        completed: 'Simulation Run Complete',
        success: 'Simulation ran successfully! Results have been saved to the experiment data directory.',
        smallScaleCompleted: 'Small-scale Test Complete',
        continueTest: 'Continue Large-scale Test',
        mechanismAdjust: 'Mechanism Explanation & Adjustment (Optional)',
        testOptions: 'You can choose to proceed directly with large-scale testing, or perform mechanism adjustment and optimization first',
        timestamp: 'Simulation Run',
        smallScaleTimestamp: 'Small-scale Test',
        smallScaleSuccess: 'Small-scale test ran successfully!'
      },
      evaluation: {
        title: 'Evaluating & Optimizing',
        running: 'Evaluating and optimizing...',
        task: 'Analyzing simulation results, evaluating whether they meet expectations, providing optimization suggestions...',
        completed: 'Evaluation & Optimization Results',
        needsAdjustment: 'Needs Adjustment',
        meetsExpectations: 'Meets Expectations',
        report: 'Evaluation Report',
        diagnosis: 'Diagnostic Recommendations',
        fileToModify: 'File Name',
        reason: 'Reason for Modification',
        confirmOptimization: 'Configuration adjustment detected. Please choose whether to apply optimization suggestions.',
        applyOptimization: 'Apply Optimization',
        skipOptimization: 'Skip Optimization',
        modifications: 'Configuration Modification Log',
        optimizationCompleted: 'Optimization Complete',
        optimizationSuccess: 'Simulation results have met expected goals, no further adjustment needed.',
        timestamp: 'Evaluation & Optimization',
        timestampCompleted: 'Evaluation Complete'
      }
    },
    interactive: {
      reviewResults: 'Please review the results of the current phase',
      feedbackPlaceholder: 'Enter your feedback (leave blank to accept current results)',
      confirmContinue: 'Confirm and Continue',
      regenerate: 'Regenerate',
      viewFiles: 'View Files',
      cancel: 'Cancel',
      note: 'You can directly modify the generated files, or provide feedback to regenerate. All subsequent code will strictly follow the design document.'
    },
    completion: {
      title: 'Complete Process Finished',
      message: 'AI system creation complete! You can find the newly created project in the simulation list.',
      goToSimulation: 'Go to Simulation',
      createNew: 'Create New Project',
      backToHome: 'Back to Home'
    },
    errors: {
      title: 'Error During Creation',
      message: 'An error occurred during the creation process. Please check the output logs for details.',
      retryStep: 'Retry Current Step',
      restart: 'Restart'
    },
    mechanism: {
      title: 'Mechanism Explanation & Adjustment Assistant',
      yourInput: 'You',
      aiAssistant: 'AI Assistant',
      inputPlaceholder: 'Enter your question or adjustment suggestion... (type \'done\' to finish)',
      send: 'Send',
      finish: 'Finish Dialogue',
      adjustmentList: 'Collected Adjustment Requirements',
      noAdjustments: 'No adjustment requirements yet',
      requirement: 'Requirement'
    },
    confirmation: {
      title: 'Confirmation Required',
      existingFile: 'Existing file found',
      prompt: 'Do you want to regenerate?',
      yes: 'Regenerate',
      no: 'Use Existing File',
      note: {
        regenerate: 'Choose "Regenerate": Will delete existing file and generate new content',
        useExisting: 'Choose "Use Existing File": Skip this step, keep and use the existing file'
      }
    }
  },
  
  simulation: {
    startButton: 'Start Simulation',
    historyButton: 'Simulation History',
    analyzeButton: 'Data Analysis',
    detailBadge: 'Project overview',
    loadingDoc: 'Loading documentation…',
    loadError: 'Could not load this project’s documentation.',
    emptyDoc: 'No description is available for this project yet.'
  },
  
  simulationRunner: {
    title: 'Simulation Runner',
    firstRunMayTakeLong: 'First run may take longer, please be patient',
    config: 'Settings',
    backButton: 'Back to Description',
    runButton: 'Run Simulation',
    running: 'Running...',
    ready: 'System Ready',
    mapTitle: 'Real-time Resident Map',
    activeResidents: 'Active Residents',
    noMapData: 'No Map Data',
    runToGenerate: 'Please run simulation first',
    logTitle: 'Running Log',
    waitingCmd: 'Waiting for system command...',
    analysisTitle: 'Real-time Analysis',
    noChartData: 'No Chart Data',
    residentArchive: 'Resident Archive #{id}',
    residentId: 'Resident ID',
    town: 'Town',
    job: 'Job',
    employmentStatus: 'Employment',
    employed: 'Employed',
    unemployed: 'Unemployed',
    income: 'Income/Assets',
    satisfaction: 'Satisfaction',
    healthIndex: 'Health Index',
    unknown: 'Unknown',
    none: 'None',
    close: 'Close',
    results: 'Result Plot',
    basicInfo: 'Basic Info',
    yearlyDecisions: 'Yearly Decisions',
    recentMemory: 'Recent Decisions',
    longtermMemory: 'Long-term Memory',
    roleDecision: 'Decision & Thoughts',
    roleEnv: 'Environment',
    reason: 'Reasoning',
    decision: 'Decision',
    desiredJob: 'Desired Job',
    speech: 'Speech',
    noData: 'No Records'
  },
  charts: {
    unemployment_rate: 'Unemployment Rate (%)',
    migration_rate: 'Migration Rate (%)',
    population: 'Total Population',
    government_budget: 'Gov Budget',
    rebellion_strength: 'Rebellion Strength',
    rebellion_resources: 'Rebellion Resources',
    average_satisfaction: 'Avg Satisfaction',
    tax_rate: 'Tax Rate',
    river_navigability: 'River Navigability',
    gdp: 'GDP',
    rebellions: 'Rebellions Count'
  },
  
  simulationHistory: {
    title: 'Simulation History',
    backButton: 'Back to Description',
    logsTab: 'Run Logs',
    plotsTab: 'Result Plots',
    logDialogTitle: 'Log Content',
    loadFailed: 'Failed to load history data',
    loadLogFailed: 'Failed to load log content',
    plotTitles: {
      rebellions: 'Rebellions Count',
      unemployment: 'Unemployment Rate',
      population: 'Population',
      government: 'Government Budget',
      rebellion: 'Rebellion Intensity',
      average: 'Average Satisfaction',
      tax: 'Tax Rate',
      river: 'River Navigability',
      gdp: 'GDP',
      urban: 'Urban Size',
      conversation: 'Conversation Volume',
      knowledge: 'Knowledge Q&A Accuracy',
      incentive: 'Incentive Choices',
      default: 'Result Plot',
    },
  },
  
  dataAnalyzer: {
    title: 'Data Analysis',
    population: 'Population (p)',
    year: 'Year (y)',
    startButton: 'Start Analysis',
    populationPlaceholder: 'Optional, for filtering results',
    yearPlaceholder: 'Optional, for filtering results',
    reportTitle: 'Statistical Report',
    plotsTitle: 'Analysis Plots',
    success: 'Analysis completed',
    failed: 'Analysis failed, please check parameters and try again',
    requestFailed: 'Analysis request failed',
  },
  
  configEditor: {
    title: 'Config Editor',
    simulationParams: 'Simulation Parameters',
    groupDecisionParams: 'Group Decision Parameters',
    dataParams: 'Data Parameters',
    saveButton: 'Save Config',
    inputPlaceholder: 'Please enter',
    loadFailed: 'Failed to load configuration',
    saveFailed: 'Failed to save configuration',
    saveSuccess: 'Configuration saved successfully',
  },

  landing: {
    eyebrow: 'LLM-powered multi-agent simulation',
    heroTitle: 'Eco3S · Economic & social system lab',
    heroLead:
      'Eco3S (Economic Social System Simulation) is a research-grade, reproducible platform: a co-evolving physical–social environment, structural causal counterfactuals, and SAR automation that turns natural-language hypotheses into runnable experiments.',
    ctaWorkbench: 'Open visualization workbench',
    ctaAi: 'AI-assisted creation (SAR)',
    pillar1Title: 'Co-evolving environment',
    pillar1Body:
      'Two-layer dynamics of physical settings (climate, geography) and social structure (HIN). Collective behavior reshapes the world; environmental change drives migration, unrest, and more.',
    pillar2Title: 'Structural causal simulation',
    pillar2Body:
      'Snapshot any step, apply interventions (do-operator style), and re-run for rigorous causal effect estimation—beyond purely correlational traces.',
    pillar3Title: 'Simulate–Analyze–Refine',
    pillar3Body:
      'A committee of specialized agents turns high-dimensional research goals into robust models: requirements → design → code → run-and-fix → refinement.',
    modesTitle: 'Two ways to run experiments',
    modesSub: 'From journal-aligned benchmarks to open-ended exploration.',
    mode1Tag: 'Traditional',
    mode1Title: 'Paper-grade benchmarks',
    mode1Body:
      'Shipped scenarios (canal decay & rebellion, origins of governance, information propagation) reproduce mechanisms from top-field economics work.',
    mode2Tag: 'AI-assisted',
    mode2Title: 'Describe it; the system builds it',
    mode2Body:
      'Natural-language goals drive automatic configuration, code generation, debugging, and multi-round optimization—then analyze trajectories in one click.',
    footnote: '* Currently in early development, welcome interested researchers to join testing and feedback!',
    navHint: 'You can also switch sections anytime from the top navigation.'
  }
}
