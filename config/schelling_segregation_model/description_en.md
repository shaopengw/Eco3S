# Schelling Segregation Model Simulation Experiment Design Document

## 1. Basic Information

**Experiment Name:** schelling_segregation_model

**Experiment Objective:** Reconstruct the Schelling segregation model to reveal the mechanisms of urban ethnic spatial segregation

**Background:** The Schelling segregation model is a multi-agent model based on an N×N grid, studying emergent phenomena in urban population distribution.

**Original Requirements:** {'simulation_name': 'schelling_segregation_model', 'description': "Simulation of schelling's segregation model", 'key_requirements': ['economic decision-making', 'government policy'], 'simulation_type': 'decision'}

## 2. System Module Selection

### Mandatory Modules (Cannot be deleted)
- **Resident System**
- **Map System**
- **Time System**
- **Population System**

### Optional Modules (Keep as needed)
- **Government System**
- **Rebellion System**

## 3. Agent Design

### Resident Agent
- **Quantity:** Randomly distributed on the grid
- **Key Attributes:** Health index, lifespan, satisfaction, income
- **Core Behaviors:**
  - `work`
  - `join_country`
  - `self_sufficiency`
  - `migrate`
  - `join_rebellion`

### Government Agent
- **Core Functions:** Policy formulation, tax management
- **Key Attributes:** Budget, policy orientation

### Rebellion Agent
- **Core Functions:** Social conflict, rebellion simulation
- **Key Attributes:** Power value, resources, morale

## 4. Environment Settings

### 4.1 Geographic Environment
- **Number of towns:** N×N grid
- **Spatial characteristics:** Describe relationships between towns
- **Distribution of natural resources:** Uniform distribution / Concentrated distribution
- **Distances between towns:** Set distances

### 4.2 Climate Conditions
- **Change pattern:** Describe climatic patterns
- **Extreme events:** Description and impact
- **Climate change magnitude:** Description

### 4.3 Economic Environment
- **Basic cost of living:** Set value

### 4.4 Occupation and Job Market
- **Occupation types:** Specify
- **Base salary per occupation:** Set value

## 5. Key Indicators

- **Population Size**
- **Average Satisfaction**
- **GDP (Gross Domestic Product)**
- **Unemployment Rate**
- **Resident Migration Rate**
- **Social Stability Index**

## 6. Simulation Parameters

### 6.1 Basic Parameters
- **Initial population size (initial_population)**
- **Simulation start year (start_year)**
- **Total simulation years (total_years)**
- **Birth rate (birth_rate)**
- **Map width (map_width)**
- **Map height (map_height)**
- **Simulation name (simulation_name)**

### 6.2 Behavioral Parameters
- **Response probability (response_probability)**
- **Maximum retry attempts (max_retry_attempts)**
- **Retry delay (retry_delay)**
- **Resume from cache (resume_from_cache)**

### 6.3 Group Decision Parameters
- **Government group decision (group_decision.government)**
- **Rebellion group decision (group_decision.rebellion)**

## 7. Interaction Mechanisms

- **Resident ↔ Government:** Influences policies and behaviors
- **Resident ↔ Resident:** Social interaction, information dissemination
- **Resident ↔ Environment:** Climate, resource utilization
- **Government ↔ Rebellion:** Confrontation or cooperation

## 8. Expected Results

**Research hypothesis:** Re-simulating the Schelling model can verify emergent phenomena

**Expected findings:** Different residential segregation tendencies will lead to different spatial segregation patterns

---

## Additional Notes

**Special settings:** None
**Known limitations:** The simplified model may not fully cover all situations

=== User Feedback ===
The Schelling model is an economic term proposed by Nobel laureate Thomas Schelling in 1971. It uses a multi-agent model to reveal the emergent mechanism of urban ethnic spatial segregation. The model simulates urban population distribution on an N×N grid. Two types of residents (e.g., red/blue) are randomly distributed on a grid containing 10% empty spaces. When the proportion of same-type residents among the eight surrounding neighbors falls below a set threshold, the resident chooses to move to any empty space. The model contains two core mechanisms: threshold-based individual behavioral rules, and macro-pattern emergence triggered by micro-interactions. Experiments show that when residents' segregation tendency is 50%, clear boundaries form; at 30% segregation tendency, the average similarity still reaches 70%; at 80% segregation tendency, frequent moves lead to integration. This demonstrates the non-linear relationship between individual preferences and group outcomes—the phenomenon of "emergence."

Based on user feedback, adjustments and improvements have been made in the new design document to better align with the characteristics and requirements of the Schelling segregation model.