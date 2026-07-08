"""审计日志（Audit Ledger）。

CodeFixer 与 AuditorAgent 之间的共享文档，行为类似 git log：
只往后追加、不改旧记录、按时间顺序排。每条记录是一次"对某处修改的复核结论"，
供 CodeFixer 重新生成被驳回的改动时读取参考，避免重复犯同样的错。

存储位置：projects/<simulation_name>/audit/audit_ledger.json
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Dict, List, Optional


class AuditLedger:
    """审计日志的读写与"已驳回清单"维护。

    设计为无状态轻封装：每次操作都从磁盘读、改完原子写回，
    这样即便 CodeFixer 和 AuditorAgent 不在同一内存里也能共享同一份日志。
    """

    # 复核记录使用的中文键（与设计文档保持一致，方便人直接读）
    KEY_PROJECT = "项目名"
    KEY_RECORDS = "复核记录"
    KEY_REJECTED = "已驳回清单"

    def __init__(self, ledger_path: str, simulation_name: str = ""):
        self.ledger_path = ledger_path
        self.simulation_name = simulation_name

    # ---------- 基础读写 ----------

    def _empty(self) -> Dict:
        return {
            self.KEY_PROJECT: self.simulation_name,
            self.KEY_RECORDS: [],
            self.KEY_REJECTED: [],
        }

    def load(self) -> Dict:
        """读取整份日志；文件不存在或损坏时返回空结构。"""
        if not os.path.exists(self.ledger_path):
            return self._empty()
        try:
            with open(self.ledger_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return self._empty()
            data.setdefault(self.KEY_PROJECT, self.simulation_name)
            data.setdefault(self.KEY_RECORDS, [])
            data.setdefault(self.KEY_REJECTED, [])
            return data
        except Exception:
            # 日志损坏不应阻断主流程，直接当成空日志重新开始
            return self._empty()

    def _atomic_write(self, data: Dict) -> None:
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        tmp_path = self.ledger_path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.ledger_path)

    # ---------- 追加复核记录 ----------

    def append_record(
        self,
        round_no: int,
        location: str,
        summary: str,
        verdict: str,
        stage: str = "—",
        reason: str = "",
        suggestion: str = "—",
        signature: Optional[str] = None,
    ) -> None:
        """追加一条复核记录。

        Args:
            round_no: 第几轮审计
            location: 改动位置，如 "simulator.py 的 update_state 方法"
            summary: 改动摘要
            verdict: 结论，"通过" / "驳回" / "放弃"
            stage: 卡在哪一关，"第一关·匹配快检" / "第二关·语义审查" / "—"
            reason: 原因说明
            suggestion: 修正建议
            signature: 改法签名（用于"已驳回清单"去重），仅驳回时需要
        """
        data = self.load()
        record = {
            "轮次": round_no,
            "时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "改动位置": location,
            "改动摘要": summary,
            "结论": verdict,
            "卡在哪关": stage,
            "原因": reason,
            "修正建议": suggestion,
        }
        data[self.KEY_RECORDS].append(record)

        if verdict == "驳回":
            if not signature:
                # 兜底：为第二关语义审查等没有显式签名的驳回生成稳定签名
                signature = hashlib.md5(
                    f"{location}|{reason}".encode('utf-8')
                ).hexdigest()
            if signature not in data[self.KEY_REJECTED]:
                data[self.KEY_REJECTED].append(signature)

        self._atomic_write(data)

    # ---------- 供 CodeFixer 读取的反馈 ----------

    def get_recent_feedback(self, last_n: int = 8) -> str:
        """把最近 N 条复核记录格式化成给 CodeFixer 看的反馈文本。"""
        data = self.load()
        records = data[self.KEY_RECORDS][-last_n:]
        if not records:
            return "（暂无审计历史）"

        lines = []
        for r in records:
            line = (
                f"[第{r.get('轮次')}轮][{r.get('结论')}] {r.get('改动位置')}"
                f" —— {r.get('改动摘要', '')}"
            )
            if r.get('结论') == '驳回':
                line += f"\n    原因：{r.get('原因', '')}"
                if r.get('修正建议') and r.get('修正建议') != '—':
                    line += f"\n    建议：{r.get('修正建议')}"
            lines.append(line)
        return '\n'.join(lines)

    def rejected_signatures(self) -> List[str]:
        """返回已驳回清单。"""
        return self.load().get(self.KEY_REJECTED, [])

    def is_rejected(self, signature: str) -> bool:
        """某改法是否已经被驳回过（治"反复打同样补丁"）。"""
        return signature in self.rejected_signatures()
