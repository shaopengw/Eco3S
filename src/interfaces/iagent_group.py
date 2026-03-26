"""通用群体系统接口。

目标：群体提供一套可复用的“群体级能力”抽象，
并允许通过插件系统按接口进行发现/约束。

说明：
- 该接口只约束“群体层”的能力（如讨论调度），不强制约束成员/领导者/信息官等细分角色。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IAgentGroup(ABC):
    """群体系统抽象接口（Group-level）。"""

    # 约定：实现方应提供 group_type/prompts/group_log 等基础属性。

    @abstractmethod
    async def orchestrate_group_decision(
        self,
        *,
        agents: Any,
        group_param: Any,
        group_type: Optional[str] = None,
        ordinary_type: type = object,
        leader_type: type = object,
        info_officer_types: tuple[type, ...] = (),
        enabled: bool | None = None,
        max_rounds: int | None = None,
        shuffle: bool = True,
    ) -> Optional[str]:
        """统一的群体讨论->决策调度。"""

        raise NotImplementedError
