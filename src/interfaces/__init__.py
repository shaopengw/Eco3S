"""
接口模块
定义系统各个核心模块的抽象接口
"""

# Environment interfaces
from .imap import IMap
from .iclimate import IClimateSystem
from .ijob_market import IJobMarket
from .ipopulation import IPopulation
from .isocial_network import IHeterogeneousGraph, IHypergraph, ISocialNetwork
from .itime import ITime
from .itowns import ITowns
from .itransport_economy import ITransportEconomy

# Agent interfaces
from .igovernment import (
    IOrdinaryGovernmentAgent,
    IHighRankingGovernmentAgent,
    IGovernment,
    IGovernmentSharedInformationPool,
    IInformationOfficer as IGovernmentInformationOfficer
)
from .irebels import (
    IOrdinaryRebel,
    IRebelLeader,
    IRebellion,
    IRebelsSharedInformationPool,
    IRebelInformationOfficer
)
from .iresident import (
    IResidentSharedInformationPool,
    IResidentGroup,
    IResident
)

__all__ = [
    # Environment interfaces
    'IMap',
    'IClimateSystem',
    'IJobMarket',
    'IPopulation',
    'IHeterogeneousGraph',
    'IHypergraph',
    'ISocialNetwork',
    'ITime',
    'ITowns',
    'ITransportEconomy',
    # Government interfaces
    'IOrdinaryGovernmentAgent',
    'IHighRankingGovernmentAgent',
    'IGovernment',
    'IGovernmentSharedInformationPool',
    'IGovernmentInformationOfficer',
    # Rebellion interfaces
    'IOrdinaryRebel',
    'IRebelLeader',
    'IRebellion',
    'IRebelsSharedInformationPool',
    'IRebelInformationOfficer',
    # Resident interfaces
    'IResidentSharedInformationPool',
    'IResidentGroup',
    'IResident',
]
