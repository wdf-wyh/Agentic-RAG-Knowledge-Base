"""ABAC（属性基访问控制）策略引擎。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

from src.config.settings import Config
from src.models.auth import UserIdentity


@dataclass
class PolicyRule:
    action: str
    resource: str
    roles: List[str] = field(default_factory=list)
    allow_anonymous: bool = False
    require_same_tenant: bool = False
    description: str = ""


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    matched_rule: Optional[str] = None


# 默认企业策略：角色 + 动作 + 资源
DEFAULT_POLICIES: List[PolicyRule] = [
    PolicyRule("write", "knowledge_base", roles=["admin"], description="构建/上传知识库"),
    PolicyRule("delete", "files", roles=["admin"], description="删除知识库文件"),
    PolicyRule("write", "files", roles=["admin"], description="编辑知识库文件"),
    PolicyRule("read", "audit", roles=["admin", "auditor"], description="读取审计事件"),
    PolicyRule("read", "metrics", roles=["admin", "auditor"], description="读取监控指标"),
    PolicyRule("read", "quota", roles=["admin", "auditor"], description="读取配额成本"),
    PolicyRule("admin", "webhook", roles=["admin"], description="测试 Webhook"),
    PolicyRule("read", "webhook", roles=["admin", "auditor"], description="查看 Webhook"),
    PolicyRule("execute", "tools", roles=["admin"], description="执行受限工具"),
    PolicyRule("read", "eval", roles=["admin", "auditor"], description="查看评测报告"),
    PolicyRule("execute", "eval", roles=["admin"], description="触发企业回测"),
    PolicyRule("read", "traces", roles=["admin", "auditor"], description="查看 Trace"),
    PolicyRule("read", "query", roles=["admin", "auditor", "user"], allow_anonymous=True, description="知识库问答"),
    PolicyRule("read", "security", roles=["admin", "auditor"], description="查看安全策略"),
    PolicyRule("read", "compliance", roles=["admin", "auditor"], description="导出合规包"),
    PolicyRule("admin", "retention", roles=["admin"], description="执行数据保留清理"),
    PolicyRule("read", "retention", roles=["admin", "auditor"], description="查看数据保留状态"),
]


class AbacEngine:
    def __init__(self, policies: Optional[List[PolicyRule]] = None):
        self.policies = policies or list(DEFAULT_POLICIES)

    def list_policies(self) -> list[dict]:
        return [
            {
                "action": rule.action,
                "resource": rule.resource,
                "roles": rule.roles,
                "allow_anonymous": rule.allow_anonymous,
                "require_same_tenant": rule.require_same_tenant,
                "description": rule.description,
            }
            for rule in self.policies
        ]

    def evaluate(
        self,
        user: Optional[UserIdentity],
        action: str,
        resource: str,
        *,
        resource_tenant_id: Optional[str] = None,
    ) -> PolicyDecision:
        if not Config.ENABLE_ABAC:
            return PolicyDecision(allowed=True, reason="ABAC disabled")

        # 鉴权未开启时保持现有宽松行为，避免本地开发被阻断
        if not Config.ENABLE_AUTH and user is None:
            return PolicyDecision(allowed=True, reason="auth disabled")

        candidates = [
            rule
            for rule in self.policies
            if rule.action == action and rule.resource == resource
        ]
        if not candidates:
            return PolicyDecision(allowed=False, reason=f"无匹配策略: {action}:{resource}")

        user_roles: Set[str] = set(user.roles or []) if user else set()
        for rule in candidates:
            if user is None:
                if rule.allow_anonymous:
                    return PolicyDecision(allowed=True, reason="anonymous allowed", matched_rule=rule.description)
                continue

            if rule.roles and not user_roles.intersection(rule.roles):
                continue

            if rule.require_same_tenant and resource_tenant_id:
                if user.tenant_id != resource_tenant_id and "admin" not in user_roles:
                    continue

            return PolicyDecision(allowed=True, reason="matched", matched_rule=rule.description or f"{action}:{resource}")

        return PolicyDecision(
            allowed=False,
            reason=f"拒绝访问 {action}:{resource}（角色={sorted(user_roles) or ['anonymous']}）",
        )


_abac_engine: AbacEngine | None = None


def get_abac_engine() -> AbacEngine:
    global _abac_engine
    if _abac_engine is None:
        _abac_engine = AbacEngine()
    return _abac_engine
