"""数据处理审计日志。

记录外生变量在生成过程中的所有人工/自动处理动作，便于后续审计与追溯。
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


class DataProcessingLog:
    """轻量级 JSONL 数据处理日志。"""

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._buffer: list = []
        # 预先创建目录，避免首次写入失败
        if log_path:
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

    def record(
        self,
        operation: str,
        indicator: str,
        period: Any,
        method: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录一条处理动作。

        Args:
            operation: 操作类型，如 backward_extrapolate / forecast /
                       missing_value_impute / outlier_3sigma_replace /
                       frequency_convert / llm_generate。
            indicator: 指标代码或变量 slug。
            period: 受影响的时间段（年份、年份区间或 period 对象）。
            method: 具体方法描述，后向外推请统一使用 "人工外推"。
            details: 额外信息字典。
        """
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "operation": operation,
            "indicator": indicator,
            "period": period,
            "method": method,
            "details": details or {},
        }
        self._buffer.append(entry)
        # 每次记录都立即追加，保证即使流程中断也能审计
        if not self.log_path:
            return
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            # 写入失败不中断主流程，但保留在内存 buffer 中
            pass

    def to_list(self) -> list:
        """返回当前已记录的所有条目（含未 flush 的 buffer）。"""
        return list(self._buffer)
