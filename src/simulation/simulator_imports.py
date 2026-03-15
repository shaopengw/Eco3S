"""
Simulator 模块统一导入文件
包含所有 simulator 需要的标准库、第三方库和项目内部模块
"""

import asyncio
import json
import random
import sys
import os
import re
import logging
import inspect
from datetime import datetime
from collections import defaultdict
from enum import Enum
from typing import List, Dict, Optional
import pandas as pd
import yaml
import networkx as nx
from colorama import Back
import numpy as np

# 导入接口类型（用于类型注解）
from src.interfaces import (
    # Environment interfaces
    IMap,
    IClimateSystem,
    IJobMarket,
    IPopulation,
    ISocialNetwork,
    ITime,
    ITowns,
    ITransportEconomy,
    # Government interfaces
    IOrdinaryGovernmentAgent,
    IHighRankingGovernmentAgent,
    IGovernment,
    IGovernmentSharedInformationPool,
    IGovernmentInformationOfficer,
    # Rebellion interfaces
    IOrdinaryRebel,
    IRebelLeader,
    IRebellion,
    IRebelsSharedInformationPool,
    IRebelInformationOfficer,
    # Resident interfaces
    IResidentSharedInformationPool,
    IResidentGroup,
    IResident
)

# 导入具体实现类（仅用于实例化）
from src.agents.government import (
    OrdinaryGovernmentAgent,
    HighRankingGovernmentAgent,
    InformationOfficer
)
from src.agents.rebels import (
    OrdinaryRebel, 
    RebelLeader, 
    InformationOfficer as RebelsInformationOfficer
)
from src.agents.resident import Resident
from src.agents.resident_agent_generator import generate_new_residents
from src.environment.social_network import SocialNetwork
from src.environment.towns import Towns
from src.environment.time import Time

from src.utils.simulation_context import SimulationContext
from src.utils.logger import LogManager
from src.utils.di_container import DIContainer

