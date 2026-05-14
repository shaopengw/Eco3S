# Herd Behavior Experiment Design Document

## 1. Basic Information

**Experiment Name:** financial_herd_behavior_sim

**Experiment Objective:** Validate herd behavior in financial markets

**Background:** This experiment aims to simulate the herd behavior of investors in financial markets and explore the impact of group behavior on market volatility.

## 2. System Module Selection

### Mandatory Modules (Cannot be deleted)
- **Resident System** - Individual agent behavioral decision-making
- **Map System** - Geographic space and town distribution
- **Time System** - Simulation time step management
- **Population System** - Population growth, migration, death

## 3. Agent Design

### Resident Agent
- **Quantity:** Not specified, to be set according to actual needs
- **Core Behaviors:** Investment decision-making, risk preference, information acquisition
- **Key Attributes:** Asset holdings, investment portfolio, cognitive bias

## 4. Environment Settings

### 4.1 Geographic Environment
- **Number of towns:** Not applicable
- **Spatial characteristics:** Not applicable
- **Distribution of natural resources:** Not applicable
- **Distances between towns:** Not applicable

### 4.2 Climate Conditions [Optional]
- **Change pattern:** Not applicable
- **Extreme events:** Not applicable
- **Climate change magnitude:** Not applicable

### 4.3 Economic Environment
- **Initial GDP:** Not applicable
- **Basic cost of living:** Not applicable
- **Initial resources:** Not applicable

## 5. Key Indicators

- **Asset Price Volatility** - Reflects market fluctuation
- **Trading Frequency** - Describes the activeness of investor behavior
- **Investor Portfolio Concentration** - Reflects investors' asset allocation

## 6. Simulation Parameters

### 6.1 Basic Parameters
- **Total simulation time (total_simulation_time):** e.g., 1000 trading days
- **Initial number of investors (initial_investor_count):** e.g., 100 investors

### 6.2 Financial Parameters
- **Asset types (asset_types):** e.g., stocks, bonds, futures
- **Market information transmission channels (information_channel):** e.g., news media, social networks

## 7. Interaction Mechanisms

- **Information transfer among investors:** Investors influence each other's decisions through market information and social networks
- **Market price feedback:** Asset price fluctuations feed back to investors, influencing their decision-making behavior

## 8. Expected Results

**Research hypothesis:** Investors will be affected by herd behavior, leading to increased market volatility

**Expected findings:** The simulation will observe concentrated behavior among investor groups resulting in significant asset price fluctuations

---

## Additional Notes

**Special settings:** This experiment does not consider individual differences among investors or information asymmetry

**Known limitations:** The model simplifies market trading rules and asset class diversity, considering only basic investment behavior.