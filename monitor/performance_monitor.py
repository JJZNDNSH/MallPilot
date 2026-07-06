"""
亮点：利用 Monitor 监控 Agent 在线表现。
保留异常检测、告警、动态降权和 Prometheus 暴露能力，
但对外文案切换为 MallPilot 的 guide/order/after_sales 语义。
"""
import asyncio
import logging
import statistics
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

import httpx
from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)


class Severity(Enum):
    """做什么：定义告警等级；为什么：统一告警展示和后续外发格式。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """做什么：描述单条告警；为什么：让监控结果可直接序列化输出。"""

    severity: Severity  # 做什么：记录告警等级；为什么：便于区分处理优先级。
    metric: str  # 做什么：记录指标名；为什么：便于定位异常来源。
    message: str  # 做什么：记录告警文案；为什么：供 API 或 webhook 直接展示。
    value: float  # 做什么：记录当前值；为什么：便于判断异常幅度。
    threshold: float  # 做什么：记录阈值；为什么：便于解释触发原因。
    ts: str = field(default_factory=lambda: datetime.now().isoformat())  # 做什么：记录触发时间；为什么：便于追踪时间线。
    resolved: bool = False  # 做什么：记录是否已恢复；为什么：便于只展示活跃告警。


@dataclass
class Suggestion:
    """做什么：描述优化建议；为什么：把监控结果转换成可执行动作。"""

    title: str  # 做什么：保存建议标题；为什么：便于前端或日志快速扫描。
    detail: str  # 做什么：保存建议背景；为什么：解释为什么需要处理。
    action: str  # 做什么：保存建议动作；为什么：给运维或研发一个直接下一步。
    priority: int  # 做什么：保存优先级；为什么：便于排序展示。


class AnomalyDetector:
    """
    做什么：基于滑动窗口做 Z-score 异常检测。
    为什么：让 Monitor 不只看固定阈值，也能发现短时突增和突降。
    """

    def __init__(self, window: int = 60, sensitivity: float = 2.5):
        """做什么：初始化检测器；为什么：为不同指标维护独立历史窗口。"""
        self._window = window
        self._sensitivity = sensitivity
        self._history: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=window))

    def record(self, metric: str, value: float) -> Optional[Dict[str, Any]]:
        """做什么：写入一个样本并检测异常；为什么：让监控循环一次完成采集与判定。"""
        history = self._history[metric]
        history.append(value)
        if len(history) < self._window // 2:
            return None

        mean = statistics.mean(history)
        stdev = statistics.stdev(history) if len(history) > 1 else 0.0
        if stdev == 0:
            return None

        z_score = abs(value - mean) / stdev
        if z_score > self._sensitivity:
            return {
                "metric": metric,
                "value": value,
                "mean": mean,
                "z_score": round(z_score, 2),
                "severity": "high" if z_score > self._sensitivity * 1.5 else "medium",
            }
        return None


class PerformanceMonitor:
    """
    做什么：监控 Agent 与工具的在线表现。
    为什么：将实时指标回写给编排器，形成 Monitor 闭环降权亮点。
    """

    THRESHOLDS = {
        "agent_success_rate": (0.90, Severity.ERROR, "less_than"),
        "tool_success_rate": (0.95, Severity.WARNING, "less_than"),
        "agent_avg_ms": (3000, Severity.WARNING, "greater_than"),
        "tool_avg_ms": (5000, Severity.ERROR, "greater_than"),
    }

    def __init__(
        self,
        orchestrator,
        tool_manager,
        interval_s: float = 10.0,
        webhook_url: Optional[str] = None,
        prometheus_port: Optional[int] = None,
    ):
        """做什么：初始化监控器；为什么：为后台采集循环准备依赖和状态。"""
        self._orchestrator = orchestrator
        self._tool_manager = tool_manager
        self._interval = interval_s
        self._webhook = webhook_url
        self._detector = AnomalyDetector()

        self._alerts: List[Alert] = []
        self._suggestions: List[Suggestion] = []
        self._active = False
        self._task: Optional[asyncio.Task] = None
        self._prom: Dict[str, Any] = {}

        if prometheus_port:
            self._setup_prometheus(prometheus_port)

    def _setup_prometheus(self, port: int) -> None:
        """做什么：初始化 Prometheus 指标；为什么：让外部系统可抓取监控数据。"""
        self._prom = {
            "agent_success_rate": Gauge("agent_success_rate", "Agent success rate", ["agent"]),
            "agent_latency_ms": Histogram("agent_latency_ms", "Agent latency in milliseconds", ["agent"]),
            "tool_success_rate": Gauge("tool_success_rate", "Tool success rate", ["tool"]),
            "requests_total": Counter("requests_total", "Total orchestrated requests"),
        }
        start_http_server(port)
        logger.info("Prometheus 已启动: :%s", port)

    async def start(self) -> None:
        """做什么：启动采集循环；为什么：应用生命周期内持续观察在线表现。"""
        if self._active:
            return
        self._active = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Monitor 已启动，采集间隔 %.1fs", self._interval)

    async def stop(self) -> None:
        """做什么：停止采集循环；为什么：应用退出时需要安全收尾。"""
        self._active = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        """做什么：执行采集循环；为什么：周期性刷新统计、告警和建议。"""
        while self._active:
            try:
                await self._collect()
            except Exception as ex:
                logger.error("Monitor 采集异常: %s", ex)
            await asyncio.sleep(self._interval)

    async def _collect(self) -> None:
        """做什么：采集实时统计；为什么：支撑异常检测、告警和路由降权。"""
        agent_stats = self._orchestrator.get_stats()
        tool_stats = self._tool_manager.get_stats()
        routing_penalties: Dict[str, float] = {}

        for agent_key, stats in agent_stats.items():
            success_rate = stats["success_rate"]
            avg_ms = stats["avg_ms"]

            # 做什么：对 Agent 成功率和延迟做异常检测。
            # 为什么：补充固定阈值无法覆盖的突发性波动。
            for metric_name, metric_value in [("agent_success_rate", success_rate), ("agent_avg_ms", avg_ms)]:
                anomaly = self._detector.record(f"{metric_name}:{agent_key}", metric_value)
                if anomaly:
                    logger.warning(
                        "异常检测[%s] %s=%.3f z=%s",
                        agent_key,
                        metric_name,
                        metric_value,
                        anomaly["z_score"],
                    )

            self._check_threshold("agent_success_rate", success_rate, agent_key)
            self._check_threshold("agent_avg_ms", avg_ms, agent_key)

            if "agent_success_rate" in self._prom:
                self._prom["agent_success_rate"].labels(agent=agent_key).set(success_rate)
                self._prom["agent_latency_ms"].labels(agent=agent_key).observe(avg_ms)

            routing_penalties[agent_key] = self._routing_penalty(success_rate, avg_ms)

        for tool_name, stats in tool_stats.items():
            success_rate = stats["success_rate"]
            avg_ms = stats["avg_latency_ms"]
            consecutive_fails = stats["consecutive_fails"]

            self._check_threshold("tool_success_rate", success_rate, tool_name)
            self._check_threshold("tool_avg_ms", avg_ms, tool_name)

            if "tool_success_rate" in self._prom:
                self._prom["tool_success_rate"].labels(tool=tool_name).set(success_rate)

            if consecutive_fails >= 3:
                self._add_suggestion(
                    Suggestion(
                        title=f"工具 {tool_name} 连续失败 {consecutive_fails} 次",
                        detail=(
                            f"成功率 {success_rate:.1%}，平均耗时 {avg_ms:.0f}ms，"
                            f"熔断状态 {stats['circuit_state']}"
                        ),
                        action="1. 检查依赖服务是否可用\n2. 核对查询参数与超时设置\n3. 必要时为主链路准备更明确的降级文案",
                        priority=9,
                    )
                )

        updater = getattr(self._orchestrator, "update_routing_penalties", None)
        if updater:
            updater(routing_penalties)
        self._generate_routing_suggestions(agent_stats)

    @staticmethod
    def _routing_penalty(success_rate: float, avg_ms: float) -> float:
        """做什么：把在线表现映射成降权系数；为什么：交给编排器动态调整路由权重。"""
        penalty = 0.0
        if success_rate < 0.90:
            penalty += min(0.5, (0.90 - success_rate) * 2)
        if avg_ms > 3000:
            penalty += min(0.4, (avg_ms - 3000) / 10000)
        return min(penalty, 0.9)

    def _check_threshold(self, metric: str, value: float, label: str) -> None:
        """做什么：执行阈值告警；为什么：让严重问题可以立刻被看见。"""
        if metric not in self.THRESHOLDS:
            return
        threshold, severity, operator = self.THRESHOLDS[metric]
        triggered = (operator == "less_than" and value < threshold) or (
            operator == "greater_than" and value > threshold
        )
        if not triggered:
            return

        alert = Alert(
            severity=severity,
            metric=f"{metric}:{label}",
            message=f"{label} 的 {metric} = {value:.3f}，阈值 {threshold}",
            value=value,
            threshold=threshold,
        )
        self._alerts.append(alert)
        logger.warning("[%s] %s", severity.value.upper(), alert.message)

        # 做什么：异步发送 webhook。
        # 为什么：避免外部告警服务阻塞主监控循环。
        if self._webhook:
            asyncio.create_task(self._send_webhook(alert))

    def _generate_routing_suggestions(self, agent_stats: Dict[str, Any]) -> None:
        """做什么：生成路由优化建议；为什么：把监控信号转成可执行调优方向。"""
        for agent_key, stats in agent_stats.items():
            if stats["success_rate"] < 0.85 and stats["total"] > 10:
                scene_hint = {
                    "guide": "商品推荐、对比和预算建议",
                    "order": "订单、物流、地址和发票查询",
                    "after_sales": "退款、退货、换货和投诉说明",
                }.get(agent_key, "当前业务场景")
                self._add_suggestion(
                    Suggestion(
                        title=f"Agent {agent_key} 成功率偏低",
                        detail=(
                            f"成功率 {stats['success_rate']:.1%}，平均耗时 {stats['avg_ms']:.0f}ms，"
                            f"当前路由分 {stats['routing_score']:.3f}"
                        ),
                        action=(
                            f"1. 复查 {scene_hint} 的提示词和 Skills 覆盖度\n"
                            "2. 检查结构化上下文是否足够，例如商品库或订单库是否注入命中\n"
                            "3. 观察是否需要补充复合场景的 few-shot 与评测样例"
                        ),
                        priority=8,
                    )
                )

    def _add_suggestion(self, suggestion: Suggestion) -> None:
        """做什么：加入优化建议；为什么：避免重复刷屏并保留最高价值建议。"""
        if any(item.title == suggestion.title for item in self._suggestions):
            return
        self._suggestions.append(suggestion)
        logger.info("优化建议 [P%s]: %s", suggestion.priority, suggestion.title)

    async def _send_webhook(self, alert: Alert) -> None:
        """做什么：发送外部告警；为什么：支持与企业监控平台集成。"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(self._webhook, json=asdict(alert))  # type: ignore[arg-type]
        except Exception as ex:
            logger.error("Webhook 发送失败: %s", ex)

    def summary(self) -> Dict[str, Any]:
        """做什么：返回监控摘要；为什么：供 API 层直接暴露监控结果。"""
        return {
            "agent_stats": self._orchestrator.get_stats(),
            "tool_stats": self._tool_manager.get_stats(),
            "active_alerts": [asdict(alert) for alert in self._alerts if not alert.resolved][-10:],
            "suggestions": [
                {"title": item.title, "action": item.action, "priority": item.priority}
                for item in sorted(self._suggestions, key=lambda suggestion: -suggestion.priority)[:5]
            ],
        }
