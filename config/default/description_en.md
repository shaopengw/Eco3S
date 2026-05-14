# Default Simulation – Decline of the Grand Canal Scenario Description

## 1. Basic Information

**Experiment Name:** default

**Experiment Objective:** To study the dynamic evolution and interaction mechanisms of population, economy, government, rebels, and other factors in Qing dynasty canal-side society.

**Background:** This simulation is set in Qing dynasty canal-side society, focusing on the socio-economic system of 15 major canal-side towns and 12 non-canal towns along the Beijing-Hangzhou Grand Canal. During the simulation, multiple agents (residents, government, rebels) interact under the influence of geographic, economic, social, and climatic environments, revealing complex patterns of social system change.

## 2. System Modules
- **Resident System** – Individual agent behavior and decision-making
- **Map System** – Geographic space and town distribution
- **Time System** – Simulation time step management
- **Population System** – Population growth, migration, death
- **Government System** – Policy making, tax management, military force maintenance
- **Rebel System** – Social conflict, rebellion simulation, resource looting
- **Climate System** – Weather changes, natural disasters affecting the canal and economy
- **Employment Market** – Job selection, unemployment rate, wage system
- **Social Network** – Interpersonal relationships, information diffusion, group behavior
- **Transport Economy** – Canal trade, transport costs, economic activity

## 3. Agent Design

### Resident Agent
- **Number:** Initially 2000, dynamically grows with birth rate
- **Key Attributes:**
  - Satisfaction – reflects satisfaction with life and government
  - Income – annual income from occupation
  - Job – current type of work
  - Location – current town
  - Social network connections – social relationships with other residents
- **Core Behaviors (implemented):**
  - **Employment related:**
    - `work` – find or continue working, can specify desired occupation and minimum wage
  - **Migration related:**
    - `migrate` – move to a new town, can optionally update occupation
  - **Social conflict:**
    - `join_rebellion` – join rebel forces (requires certain conditions)
  - **Social interaction:**
    - social conversations with neighbors
    - influenced by rebel propaganda
    - spread information within social network

### Government Agent
- **Composition:** Multiple ordinary government agents + high‑ranking government agent + information officer
- **Core Functions:**
  - Tax policy formulation and adjustment
  - Allocation of canal maintenance resources
  - Military deployment and rebellion suppression
  - Social governance and livelihood improvement
- **Key Attributes:**
  - Budget – government available funds
  - Military strength – total number of officials and soldiers
  - Tax rate – current tax percentage
- **Decision Mechanism:** Supports group decision‑making (when enabled, conducts 2 rounds of discussion, information officer summarizes, leader decides)

### Rebel Agent
- **Composition:** Multiple ordinary rebels + rebel leader + rebels information officer
- **Core Functions:**
  - Launch rebel attacks on towns
  - Propaganda to incite residents to join
  - Plunder resources to strengthen rebel forces
  - Challenge government authority
- **Key Attributes:**
  - Strength – total number of rebels
  - Resources – available funds
  - Morale – affects rebellion success rate
- **Decision Mechanism:** Supports group decision‑making (disabled in current configuration, leader directly decides)

## 4. Environment Settings

### 4.1 Geographic Environment
- **Number of Towns:** 27 (15 canal‑side towns + 12 non‑canal towns)
- **Spatial Characteristics:**
  - Canal‑side towns: distributed along the Beijing‑Hangzhou Grand Canal from Beijing to Hangzhou
  - Non‑canal towns: scattered around the canal region
  - Geographic range: longitude 109.0°–125.0°E, latitude 30.0°–41.0°N
- **Natural Resource Distribution:** Canal‑side towns have canal trade advantages; non‑canal towns are mainly agricultural
- **Inter‑town Distances:** Calculated based on real geographic coordinates, affects migration cost and transport cost

### 4.2 Climate Conditions
- **Variation Pattern:** Based on historical climate data (experiment_dataset/climate_data/climate.csv), simulating climate impact on canal navigability
- **Extreme Events:** Abnormal climate reduces canal navigability, affecting trade and employment
- **Climate Variation Range:** Climate impact factor changes dynamically over time, affecting the natural decay rate of the canal

### 4.3 Economic Environment
- **Subsistence Cost:** 8 taels/year, required for residents to maintain basic survival
- **GDP Calculation:** Sum of income of all non‑rebel residents

### 4.4 Occupations and Employment Market
- **Occupation Types and Base Wages:**
  - Farmer: 10 taels/year
  - General worker: 12 taels/year
  - Canal maintenance worker: 15 taels/year
  - Official/soldier: 20 taels/year
  - Merchant: 30 taels/year
  - Rebel: 8 taels/year

- **Occupational Distribution Ratio (by town type):**
  - Canal‑side towns: higher proportion of merchants and canal maintenance workers (merchants 5‑10%, canal maintenance workers 20‑30%)
  - Non‑canal towns: higher proportion of farmers (70‑80%), no canal maintenance workers

## 5. Key Indicators

**Core indicators monitored during simulation and their significance:**

- **Total Population** – reflects social scale and population growth trend, influenced by birth rate and death rate
- **Average Satisfaction** – overall satisfaction of residents (0‑100), reflects social harmony and government effectiveness
- **GDP** – sum of annual income of all non‑rebel residents, reflects economic development level
- **Unemployment Rate** – proportion of unemployed residents in total population, reflects employment market conditions
- **Government Budget** – government available funds, affects policy implementation capacity
- **Rebel Strength** – total number of rebels, reflects social conflict intensity
- **Rebel Resources** – rebel available funds, affects rebellion capacity
- **Tax Rate** – current tax percentage, affects government revenue and resident satisfaction
- **River Navigability** – canal status (0‑100), affects employment and trade for canal‑related occupations
- **Rebellions** – number of rebellion events per year, reflects social stability

## 6. Simulation Parameters

### 6.1 Basic Parameters
- **Initial Population:** 2000
- **Simulation Start Year:** 1650
- **Total Simulation Years:** 15 (1650‑1665)
- **Birth Rate:** 0.05 (baseline, dynamically adjusted with average satisfaction)
- **Map Width:** 100
- **Map Height:** 150
- **Simulation Name:** "" (default empty, can be customized)

### 6.2 Behavior Parameters
- **Response Probability:** 0.05 (probability that a resident performs a decision action per year)
- **Max Retry Attempts:** 3 (number of retries when LLM call fails)
- **Retry Delay:** 1 second
- **Resume from Cache:** 0 (disabled)
- **Save Cache:** 0 (disabled)

### 6.3 Group Decision Parameters
- **Government Group Decision:**
  - Enabled: 1 (enabled)
  - Max discussion rounds: 2
- **Rebel Group Decision:**
  - Enabled: 0 (disabled, rebel leader decides directly)
  - Max discussion rounds: 2

## 7. Interaction Mechanisms

**Key interaction flows among agents:**

- **Resident ↔ Government:**
  - Residents influence government decisions through satisfaction feedback
  - Government tax adjustments affect resident income and satisfaction
  - Government military fights rebels, affecting residents’ sense of security
  - Government canal maintenance investment affects resident employment opportunities

- **Resident ↔ Resident:**
  - Information diffusion in social network (network structure updated every 3‑5 years)
  - Rebel propaganda influences neighbors to join rebellion
  - Social conversations influence opinions and behavior decisions

- **Resident ↔ Environment:**
  - Climate change affects canal navigability, which in turn affects employment choices
  - Canal status affects job opportunities for canal maintenance workers and merchants
  - Residents decide whether to migrate based on town economic conditions

- **Government ↔ Rebel:**
  - Rebels launch attacks on towns; government sends military to suppress
  - Battle outcomes computed with non‑linear advantage loss model
  - Force ratio affects battle losses and rebellion success rate

- **Rebel ↔ Resident:**
  - Rebels use propaganda to incite residents to join
  - Residents with low satisfaction are more susceptible
  - Rebels obtain resources from supporters

## 8. Expected Results

**Research Hypotheses:**
1. There is a non‑linear relationship between government tax rate and resident satisfaction – excessively high tax rates lead to lower satisfaction and increased rebellion
2. Changes in canal navigability significantly affect employment rates and economic development in canal‑side towns
3. Group decision‑making (enabled for government) produces more robust policies, better balancing multiple interests compared to single‑leader decision‑making

**Expected Findings:**
- Social system stability is jointly influenced by multiple factors: economic, political, climate, etc.
- The canal, as critical infrastructure, shows a positive correlation between maintenance investment and economic development
- Rebel forces grow rapidly under specific conditions (low satisfaction, high unemployment)
- Government budget management strategies have a significant impact on long‑term social stability

---

## Additional Notes

**Special Settings:**
- Rebel income is fixed at 6 taels/person/year (calculated based on strength)
- Combat losses use a non‑linear advantage loss model, accounting for extreme advantage protection and random perturbation
- Social network structure is randomly updated every 3‑5 years
- Newborn residents automatically join the social network and are assigned to a town

**Known Limitations:**
- Short simulation time (15 years) may not capture some long‑term trends
- Resident decisions are generated by LLM and have some randomness
- Climate data is based on historical records and does not account for sudden extreme climate events
- Occupation wages are fixed and do not reflect dynamic market supply‑demand adjustments

## Data Recording

The system automatically records and visualizes all the above key indicators over time. Data is stored in the `data/` directory in CSV format. This data enables:
- Time series analysis
- Indicator correlation studies
- Policy effect evaluation
- Exploration of social evolution patterns