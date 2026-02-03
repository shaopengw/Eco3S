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
    modificationApplied: 'Modification applied'
  },
  header: {
    title: 'Eco3S',
    lightMode: 'Light',
    darkMode: 'Dark',
    language: '中文'
  },
  menu: {
    createNew: 'Create New Simulation',
    aiAssisted: 'AI-Assisted Creation',
    existingSimulations: 'Existing Simulations'
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
  },
  
  simulationRunner: {
    title: 'Simulation Runner',
    backButton: 'Back to Description',
    runButton: 'Run Simulation',
    running: 'Running...',
    output: 'Output Log',
    realtime: 'Real-time Data',
    results: 'Simulation Results',
    startFailed: 'Failed to start simulation',
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
  }
}
