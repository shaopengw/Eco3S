# Experiment Design Document

## 1. Basic Information

**Experiment Name:** asset_market_bubble_sim

**Experiment Objective:** Observe the formation and collapse of asset market bubbles

**Background Description:** Create a continuous double auction market where agents trade, to explore the bubble and crash cycles where asset prices deviate from fundamental value.

**Original Requirements:** Create a continuous double auction market. In this market, a virtual asset with a fixed dividend period (e.g., a token lasting for 15 trading periods, with a fixed dividend of 0.1 yuan per period, value dropping to zero after expiration) will be traded. Agents initially hold different combinations of cash and assets, and make buying and selling decisions based on their internal beliefs, observations of the market, and other agents' behaviors. The system needs to dynamically inject differentiated risk preferences, information processing methods (e.g., fundamental analysis, technical analysis, or herding behavior), and private information (potentially noisy) for each agent. The core objective is to self-organize the emergence of asset price deviations from fundamental value (bubbles and crashes) through completely decentralized agent interactions. The entire simulation environment should record and visualize all transactions, order book depth, individual belief and asset distribution evolution, and the overall price series.

## 2. System Module Selection

### Mandatory Modules
- **Resident System** - Individual agent decision-making
- **Map System** - Geospatial and town distribution
- **Time System** - Simulation time step management
- **Population System** - Population growth, migration, death

### Optional Modules
- **Government System** - Policy making, tax management
- **Social Network** - Social relationships, information dissemination

## 3. Agent Design

### Resident Agents
- **Number:** 100-500
- **Key Attributes:** Cash, asset portfolio
- **Core Behaviors:**
  - `buy_asset` - Purchase assets
  - `sell_asset` - Sell assets
  - `analyze_market` - Analyze market trends
  - `follow_trend` - Follow market hotspots
  - `update_beliefs` - Update individual beliefs

### Government Agent [Optional]
- **Core Functions:** Policy making, market regulation

## 4. Environment Settings

### 4.1 Geographic Environment
- **Number of Towns:** 1
- **Spatial Characteristics:** Clustered distribution
- **Natural Resource Distribution:** None
- **Inter-town Distances:** None

### 4.3 Economic Environment
- **Basic Living Cost:** 0

## 5. Key Metrics

- **Asset Price** - Observe asset price changes over time
- **Trading Volume** - Record trading volume per period
- **Asset Distribution** - Statistically track asset distribution across agents

## 6. Simulation Parameters

### 6.1 Basic Parameters
- **Initial Cash Amount (initial_cash):** 100 units
- **Dividend Amount (dividend_amount):** 0.1 units
- **Trading Periods (trading_periods):** 15 periods
- **Simulation Name (simulation_name):** "asset_market_bubble_sim"

### 6.2 Behavioral Parameters
- **Response Probability (response_probability):** 0.1
- **Max Retry Attempts (max_retry_attempts):** 3

## 7. Interaction Mechanisms

- **Resident ↔ Resident:** Agents interact with each other to buy and sell assets
- **Resident ↔ Government:** Government regulates the market and enacts policies to influence market behavior

## 8. Expected Results

**Research Hypothesis:** Agent interactions will lead to asset price bubbles and crashes.

**Expected Findings:** Observe the degree of deviation of asset prices from fundamental value, and explore the timing of bubble formation and factors leading to crashes.

---

## Supplementary Notes

**Special Settings:** None

**Known Limitations:** None
