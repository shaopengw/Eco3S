# India Demonetization Information Propagation Experiment

## 1. Basic Information

**Experiment name:** info_propagation (India Demonetization Information Propagation Experiment)

**Experiment objective:** To compare how different message lengths and propagation strategies affect residents' understanding and choices regarding key rules of the demonetization policy (survey‑type experiment).

**Background setting:** Uses the 2016 Indian demonetization announcement as the core stimulus material. Residents receive policy information within a limited time window and form understanding and choices. The information source can be considered "official notification," while social networks are allowed to influence individual cognitive updating.

**Experimental window and steps:** Runs for 3 time steps total (`total_years=3`); each step can be seen as one information‑contact and reaction cycle. Resident states are reset between conditions to ensure comparability.

## 2. Core Objects and Experimental Settings

**Participants/Agent subjects:** 200 residents, each with the following basic attributes:
- `gender`: Gender
- `lifespan`: Remaining lifespan
- `satisfaction`: Satisfaction with current life (0‑100)
- `health_index`: Health status (1‑5)
- `location`: Position (x, y) and the town they belong to
- `personality`: Personality defined by random adjectives

**Behaviors:**
- `receive_and_decide_response`: Receives the official message and immediately plans whether to speak.
- `spread_speech_in_network`: If deciding to speak, the speech is propagated through the social network to all connected neighbors, triggering memory updates on their side.
- `update_knowledge_memory`: After each round of information reception and discussion, summarizes the information and updates long‑term knowledge memory.

**Stimulus/Information and prompts:**
The stimulus material comes from the demonetization announcement, including a short message (`propaganda_message_short`) and a long message (`propaganda_message_long`). The long message covers more complete rules and restrictions; the short message retains the core provisions.

## 3. Experimental Control Logic

This experiment strictly controls variables: same set of residents, same map and social structure, same set of evaluation questions. Only "message length / propagation strategy" is changed as the independent variable. Measures of understanding, choice distribution, and propagation process indicators are the dependent variables.

**Treatment conditions / Experimental groups (four strategies, enumerated as `PropagationStrategy`):**

1. **S_NCK (Seed strategy, No Common Knowledge)**  
   - Selects `seed_count` seed residents based on a weighted average of degree, betweenness, and closeness centrality. Only seeds receive the official message; non‑seeds receive an empty message.  
   - For all residents, `public_notice` is: "Only some villagers in the village received the government information."

2. **S_CK (Seed strategy, Common Knowledge)**  
   - Seed selection and message distribution are the same as above.  
   - For seed residents, `public_notice` is: "Only some villagers received the government information, and all villagers know that you received it." For non‑seeds: "Only some villagers in the village received the government information."

3. **BC_NCK (Broadcast strategy, No Common Knowledge)**  
   - The official message is sent to all residents.  
   - `public_notice` is empty.

4. **BC_CK (Broadcast strategy, Common Knowledge)**  
   - The official message is sent to all residents.  
   - `public_notice` is: "You know that all villagers received the government information, and all villagers know that you received it."

## 4. Experimental Procedure

**Overall flow:** Run each treatment condition sequentially, ensuring each condition starts from the same initial state. Record processes and results.

1. **Initialization:** Load configuration, create residents, a single town, and a social network (heterogeneous graph + hypergraph).
2. **Strategy loop:** Execute the four propagation strategies in order (S_NCK, S_CK, BC_NCK, BC_CK). For each strategy:
   1. **Reset state:** Reset all residents' memories and experiment‑related counters.
   2. **Time‑step loop:** Run `total_years` time steps. In each time step:
      - **Information presentation:** Distribute the official message and common knowledge to residents according to the current strategy (broadcast/seed, CK/NCK).
      - **Individual reaction:** Residents receive the information, plan, and may speak/discuss in the social network.
      - **Social diffusion:** The speech content propagates through the social network, triggering memory updates in neighbors.
      - **Memory summarization:** All residents call an LLM to update their long‑term knowledge memory.
   3. **Post‑strategy evaluation:** After the time‑step loop finishes:
      - **Knowledge survey** (`run_knowledge_survey`): Send a standardized questionnaire to all residents, parse answers via LLM, calculate per‑question accuracy and overall accuracy.
      - **Incentive choice survey** (`run_incentive_survey`): Present a binary economic decision question; collect the distribution of choices to simulate real trust in the policy.
   4. **Save results:** Record the conversation volume (`conversation_volume`) and survey results for that strategy.

3. **Completion and analysis:** After all strategies have been executed, save the full experimental results to a JSON file and call plotting functions to generate comparative charts, visually showing differences across strategies in conversation volume, knowledge accuracy, and incentive choices.

## 5. Key Indicators

- **Process indicators:** Number of information touches, social propagation rounds, response rate, and **conversation volume** (total number of spontaneous policy discussions by residents in the social network).
- **Cognitive indicators (Knowledge/Understanding):** Accuracy of the **knowledge survey** (per‑question accuracy and overall accuracy).
- **Behavioral/attitudinal indicators (Choice/Attitude):** Distribution of choices in the **incentive choice survey** (support/oppose or willingness to act).

## 6. Reproducible Output Description

- Run parameters: `initial_population=200`, `total_years=3`, `strategy=BC_CK` (example), `response_probability=0.2`, `seed_count=1`.
- Output: Statistical results and charts for each condition are saved under the `history/info_propagation/` directory in the corresponding experiment subfolder.