"""
亮点：端到端评测框架。
保留 LLM-as-Judge、意图识别评测和回归对比能力，
但评测语义切换为 MallPilot 综合电商导购助手。
"""
import json
import logging
import pathlib
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from core.intent_recognizer import IntentRecognizer

logger = logging.getLogger(__name__)


@dataclass
class IntentTestCase:
    """做什么：定义单条意图测试样例；为什么：统一评测输入格式。"""

    message: str  # 做什么：保存测试消息；为什么：供识别链路直接消费。
    expected_intent: str  # 做什么：保存期望意图；为什么：用于计算准确率和 F1。
    context: Optional[Dict[str, Any]] = None  # 做什么：保留附加上下文；为什么：便于扩展复杂评测场景。


@dataclass
class QualityScores:
    """做什么：描述 LLM-as-Judge 评分；为什么：统一保存各质量维度。"""

    relevance: float  # 做什么：评估相关性；为什么：判断回答是否直达用户问题。
    accuracy: float  # 做什么：评估准确性；为什么：判断商品、订单、售后信息是否可靠。
    completeness: float  # 做什么：评估完整性；为什么：判断回答是否覆盖关键步骤和限制。
    helpfulness: float  # 做什么：评估可执行性；为什么：判断用户是否能据此继续操作。
    judge_failed: bool = False  # 做什么：记录评委是否失败；为什么：便于区分真实低分和模型异常。
    error: Optional[str] = None  # 做什么：记录评委错误；为什么：排查失败原因时需要使用。

    @property
    def overall(self) -> float:
        """做什么：计算综合分；为什么：给单条用例快速判定是否通过。"""
        return statistics.mean([self.relevance, self.accuracy, self.completeness, self.helpfulness])


@dataclass
class EvalResult:
    """做什么：描述单条评测结果；为什么：统一收集到报告中。"""

    test_id: str  # 做什么：保存测试编号；为什么：便于定位失败用例。
    passed: bool  # 做什么：记录是否通过；为什么：便于统计通过率。
    scores: Dict[str, float]  # 做什么：保存分项得分；为什么：便于后续回归对比。
    detail: str = ""  # 做什么：保存简要说明；为什么：方便在 API 侧展示摘要。
    metadata: Dict[str, Any] = field(default_factory=dict)  # 做什么：保存原始上下文；为什么：便于排查和复现。


@dataclass
class EvalReport:
    """做什么：描述完整评测报告；为什么：为 /eval/run 和基线落盘提供统一结构。"""

    timestamp: str  # 做什么：保存评测时间；为什么：用于回归对比和审计。
    total: int  # 做什么：保存总用例数；为什么：便于统计覆盖规模。
    passed: int  # 做什么：保存通过数；为什么：便于统计通过率。
    pass_rate: float  # 做什么：保存通过率；为什么：快速衡量整体质量。
    avg_scores: Dict[str, float]  # 做什么：保存平均分；为什么：支撑回归检测。
    regressions: List[str]  # 做什么：保存退化项；为什么：提示需要重点修复的指标。
    recommendations: List[str]  # 做什么：保存优化建议；为什么：给后续迭代提供行动方向。
    results: List[EvalResult]  # 做什么：保存明细结果；为什么：支持逐条排查。


class LLMJudge:
    """
    做什么：用 LLM 评估 MallPilot 回复质量。
    为什么：把导购、订单、售后回复的质量评估自动化，便于持续回归。
    """

    JUDGE_PROMPT = """你是 MallPilot 综合电商导购助手的质检专家。请结合问题与上下文，对下面回复打分。

用户问题: {question}
Agent 回复: {response}
{context_section}

请从四个维度给出 0.0-1.0 分，并只返回 JSON：
- relevance: 回复是否紧扣用户当前问题。
- accuracy: 商品、订单、售后说明是否准确且没有明显编造。
- completeness: 是否覆盖关键步骤、限制条件和下一步建议。
- helpfulness: 用户是否能据此继续行动。

返回格式示例：
{{"relevance": 0.92, "accuracy": 0.88, "completeness": 0.85, "helpfulness": 0.9}}
"""

    def __init__(self, client: AsyncAnthropic, model: str):
        """做什么：初始化评委模型；为什么：供后续多条用例复用。"""
        self._client = client
        self._model = model

    async def judge(self, question: str, response: str, context: Optional[str] = None) -> QualityScores:
        """做什么：评估单条回复；为什么：产出标准化质量分数。"""
        context_section = f"补充上下文: {context}" if context else ""
        prompt = self.JUDGE_PROMPT.format(
            question=self._clean_text(question),
            response=self._clean_text(response),
            context_section=self._clean_text(context_section),
        )
        try:
            result = await self._client.messages.create(
                model=self._model,
                max_tokens=256,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = result.content[0].text
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            return QualityScores(
                relevance=float(data.get("relevance", 0.5)),
                accuracy=float(data.get("accuracy", 0.5)),
                completeness=float(data.get("completeness", 0.5)),
                helpfulness=float(data.get("helpfulness", 0.5)),
            )
        except Exception as ex:
            logger.warning("LLM Judge 失败: %s", ex)
            return QualityScores(
                relevance=0.5,
                accuracy=0.5,
                completeness=0.5,
                helpfulness=0.5,
                judge_failed=True,
                error=str(ex),
            )

    @staticmethod
    def _clean_text(value: Any) -> str:
        """做什么：清理异常字符；为什么：避免评测请求因编码问题失败。"""
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.encode("utf-8", errors="ignore").decode("utf-8")


class IntentEvaluator:
    """做什么：评测意图识别；为什么：量化 guide/order/after_sales 路由准确率。"""

    def __init__(self, recognizer: IntentRecognizer):
        """做什么：接收识别器实例；为什么：复用主项目意图识别配置。"""
        self._recognizer = recognizer

    async def evaluate(self, cases: List[IntentTestCase]) -> Dict[str, Any]:
        """做什么：运行意图评测；为什么：生成准确率、F1 和用例明细。"""
        predictions: List[str] = []
        ground_truth: List[str] = []
        case_details: List[Dict[str, Any]] = []

        for case in cases:
            result = await self._recognizer.recognize(case.message)
            predicted = result.intent.value
            predictions.append(predicted)
            ground_truth.append(case.expected_intent)
            case_details.append(
                {
                    "message": case.message,
                    "expected": case.expected_intent,
                    "predicted": predicted,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                }
            )

        correct = sum(pred == truth for pred, truth in zip(predictions, ground_truth))
        accuracy = correct / len(predictions) if predictions else 0.0

        per_class: Dict[str, Dict[str, float]] = {}
        for label in sorted(set(ground_truth + predictions)):
            true_positive = sum(pred == label and truth == label for pred, truth in zip(predictions, ground_truth))
            false_positive = sum(pred == label and truth != label for pred, truth in zip(predictions, ground_truth))
            false_negative = sum(pred != label and truth == label for pred, truth in zip(predictions, ground_truth))
            precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
            recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
            f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
            per_class[label] = {"precision": precision, "recall": recall, "f1": f1_score}

        macro_f1 = statistics.mean(metrics["f1"] for metrics in per_class.values()) if per_class else 0.0
        return {
            "accuracy": round(accuracy, 4),
            "macro_f1": round(macro_f1, 4),
            "per_class": per_class,
            "total": len(cases),
            "correct": correct,
            "cases": case_details,
        }


class EndToEndEvaluator:
    """
    做什么：执行完整端到端评测。
    为什么：把意图识别、对话质量和回归检测统一成一条评测链路。
    """

    PASS_THRESHOLD = 0.75  # 做什么：定义通过线；为什么：保持线上评测判定一致。

    def __init__(
        self,
        orchestrator,
        recognizer: IntentRecognizer,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        baseline_path: Optional[str] = None,
    ):
        """做什么：初始化评测器；为什么：复用主业务编排器与评委模型。"""
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncAnthropic(**kwargs)

        self._orchestrator = orchestrator
        self._judge = LLMJudge(client, model)
        self._intent_evaluator = IntentEvaluator(recognizer)
        self._history: List[EvalReport] = []
        self._baseline_path = pathlib.Path(baseline_path) if baseline_path else None
        self._baseline: Optional[EvalReport] = self._load_baseline()

    async def run(
        self,
        intent_cases: Optional[List[IntentTestCase]] = None,
        dialog_cases: Optional[List[Dict[str, Any]]] = None,
    ) -> EvalReport:
        """做什么：运行完整评测；为什么：供 API 一次性返回当前系统质量快照。"""
        results: List[EvalResult] = []
        all_scores: Dict[str, List[float]] = {
            "relevance": [],
            "accuracy": [],
            "completeness": [],
            "helpfulness": [],
        }

        intent_metrics: Dict[str, Any] = {}
        if intent_cases:
            intent_metrics = await self._intent_evaluator.evaluate(intent_cases)
            results.append(
                EvalResult(
                    test_id="intent_recognition",
                    passed=intent_metrics["accuracy"] >= self.PASS_THRESHOLD,
                    scores={
                        "accuracy": intent_metrics["accuracy"],
                        "macro_f1": intent_metrics["macro_f1"],
                    },
                    detail=f"意图准确率 {intent_metrics['accuracy']:.1%}，Macro-F1 {intent_metrics['macro_f1']:.3f}",
                    metadata={
                        "total": intent_metrics.get("total", 0),
                        "correct": intent_metrics.get("correct", 0),
                        "cases": intent_metrics.get("cases", []),
                    },
                )
            )

        if dialog_cases:
            for index, case in enumerate(dialog_cases):
                case_results = await self._evaluate_dialog_case(case, index)
                results.extend(case_results)
                for case_result in case_results:
                    for metric in all_scores:
                        if metric in case_result.scores:
                            all_scores[metric].append(case_result.scores[metric])

        avg_scores = {name: round(statistics.mean(values), 4) for name, values in all_scores.items() if values}
        if intent_metrics:
            avg_scores["intent_accuracy"] = intent_metrics["accuracy"]

        passed_count = sum(1 for result in results if result.passed)
        pass_rate = passed_count / len(results) if results else 0.0
        regressions = self._detect_regressions(avg_scores)
        recommendations = self._recommendations(avg_scores)

        report = EvalReport(
            timestamp=datetime.now().isoformat(),
            total=len(results),
            passed=passed_count,
            pass_rate=round(pass_rate, 4),
            avg_scores=avg_scores,
            regressions=regressions,
            recommendations=recommendations,
            results=results,
        )
        self._history.append(report)
        self._save_baseline(report)
        return report

    async def _evaluate_dialog_case(self, case: Dict[str, Any], case_idx: int) -> List[EvalResult]:
        """做什么：评测单轮或多轮对话；为什么：验证编排、记忆和工具链是否协同正常。"""
        from agents.agent_orchestrator import Request as OrchestratorRequest

        questions = self._dialog_turns(case)
        if not questions:
            return []

        conv_id = str(case.get("conv_id") or f"eval_{case_idx}")
        user_id = str(case.get("user_id") or "eval_user")
        history: List[Dict[str, str]] = []
        results: List[EvalResult] = []

        for turn_idx, question in enumerate(questions):
            context = self._history_context(history)
            request = OrchestratorRequest(
                message=question,
                user_id=user_id,
                conv_id=conv_id,
                context=context,
                history=history[-6:] if history else None,
            )
            orchestrator_result = await self._orchestrator.run(request)
            answer = orchestrator_result.response
            scores = await self._judge.judge(question, answer, context=context or None)

            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer})

            test_id = f"dialog_{case_idx}" if len(questions) == 1 else f"dialog_{case_idx}_turn_{turn_idx}"
            results.append(
                EvalResult(
                    test_id=test_id,
                    passed=scores.overall >= self.PASS_THRESHOLD,
                    scores={
                        "relevance": scores.relevance,
                        "accuracy": scores.accuracy,
                        "completeness": scores.completeness,
                        "helpfulness": scores.helpfulness,
                        "overall": scores.overall,
                    },
                    detail=f"Q: {question[:30]}... -> 综合评分 {scores.overall:.3f}",
                    metadata={
                        "question": question,
                        "response": answer,
                        "agent_type": orchestrator_result.agent_type.value,
                        "intent": orchestrator_result.intent.value if orchestrator_result.intent else None,
                        "turn": turn_idx,
                        "conv_id": conv_id,
                        "judge_failed": scores.judge_failed,
                        "judge_error": scores.error,
                    },
                )
            )

        return results

    @staticmethod
    def _dialog_turns(case: Dict[str, Any]) -> List[str]:
        """做什么：解析对话轮次；为什么：兼容单轮与多轮用例配置。"""
        turns = case.get("turns")
        if isinstance(turns, list):
            return [str(item) for item in turns if str(item).strip()]
        question = case.get("question")
        return [str(question)] if question else []

    @staticmethod
    def _history_context(history: List[Dict[str, str]]) -> str:
        """做什么：序列化多轮历史；为什么：让 Judge 理解当前轮次上下文。"""
        if not history:
            return ""
        lines = [f"{item['role']}: {item['content']}" for item in history[-8:]]
        return "[评测多轮历史]\n" + "\n".join(lines)

    def _detect_regressions(self, current: Dict[str, float]) -> List[str]:
        """做什么：检测指标退化；为什么：避免新改动让导购链路悄悄回退。"""
        previous_report = self._history[-1] if self._history else self._baseline
        if previous_report is None:
            return []
        previous_scores = previous_report.avg_scores
        regressions: List[str] = []
        for metric, value in current.items():
            if metric in previous_scores and previous_scores[metric] > 0:
                delta = (value - previous_scores[metric]) / previous_scores[metric]
                if delta < -0.05:
                    regressions.append(
                        f"{metric}: {previous_scores[metric]:.3f} -> {value:.3f} (退化 {abs(delta):.1%})"
                    )
        return regressions

    def _recommendations(self, scores: Dict[str, float]) -> List[str]:
        """做什么：生成优化建议；为什么：让评测输出可直接指导下一轮调优。"""
        recommendations: List[str] = []
        if scores.get("intent_accuracy", 1.0) < 0.90:
            recommendations.append("意图准确率低于 90%，建议补充导购、订单、售后复合场景的 few-shot。")
        if scores.get("relevance", 1.0) < 0.75:
            recommendations.append("相关性偏低，建议检查 guide/order/after_sales 的系统提示词边界。")
        if scores.get("completeness", 1.0) < 0.75:
            recommendations.append("完整性偏低，建议补充物流、发票、退换货等场景的下一步说明。")
        if scores.get("helpfulness", 1.0) < 0.75:
            recommendations.append("可执行性偏低，建议让回答明确给出查询结果、限制条件和下一步动作。")
        if not recommendations:
            recommendations.append("MallPilot 当前评测指标达标，可继续观察真实对话中的长尾场景。")
        return recommendations

    @property
    def history(self) -> List[EvalReport]:
        """做什么：返回历史报告；为什么：供外部调试或二次分析。"""
        return self._history

    def _load_baseline(self) -> Optional[EvalReport]:
        """做什么：读取基线报告；为什么：支持跨版本回归检测。"""
        if not self._baseline_path or not self._baseline_path.exists():
            return None
        try:
            data = json.loads(self._baseline_path.read_text(encoding="utf-8"))
            return self._report_from_dict(data)
        except Exception as ex:
            logger.warning("读取评测基线失败: %s", ex)
            return None

    def _save_baseline(self, report: EvalReport) -> None:
        """做什么：保存最新报告为基线；为什么：让下一次评测可以直接做回归对比。"""
        if not self._baseline_path:
            return
        try:
            self._baseline_path.parent.mkdir(parents=True, exist_ok=True)
            self._baseline_path.write_text(
                json.dumps(asdict(report), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._baseline = report
        except Exception as ex:
            logger.warning("保存评测基线失败: %s", ex)

    @staticmethod
    def _report_from_dict(data: Dict[str, Any]) -> EvalReport:
        """做什么：把字典恢复成报告对象；为什么：统一基线加载后的数据结构。"""
        return EvalReport(
            timestamp=data.get("timestamp", ""),
            total=int(data.get("total", 0)),
            passed=int(data.get("passed", 0)),
            pass_rate=float(data.get("pass_rate", 0.0)),
            avg_scores=dict(data.get("avg_scores", {})),
            regressions=list(data.get("regressions", [])),
            recommendations=list(data.get("recommendations", [])),
            results=[
                EvalResult(
                    test_id=item.get("test_id", ""),
                    passed=bool(item.get("passed", False)),
                    scores=dict(item.get("scores", {})),
                    detail=item.get("detail", ""),
                    metadata=dict(item.get("metadata", {})),
                )
                for item in data.get("results", [])
            ],
        )


DEFAULT_INTENT_CASES: List[IntentTestCase] = [
    IntentTestCase("预算 3000 想买续航好的手机", "guide"),
    IntentTestCase("帮我对比一下两款扫地机器人", "guide"),
    IntentTestCase("订单 MP20260706001 到哪了", "order"),
    IntentTestCase("我想补开发票", "order"),
    IntentTestCase("这笔订单想退货换个颜色", "after_sales"),
    IntentTestCase("收到商品有瑕疵，我要投诉", "complaint"),
    IntentTestCase("转人工，现在就处理", "escalation"),
    IntentTestCase("谢谢，推荐挺准的", "feedback"),
]

DEFAULT_DIALOG_CASES: List[Dict[str, Any]] = [
    {"question": "预算 3000 想买续航好的手机"},
    {"question": "订单 MP20260706001 到哪了，顺便帮我看看能不能补开发票"},
    {"question": "这笔订单想退货换个颜色"},
    {"question": "送给爸妈的空气炸锅有什么推荐，要操作简单一点"},
    {
        "turns": [
            "我上次买的吹风机不好用，想退货。",
            "订单号是 MP20260706004。",
            "那你再给我推荐一个轻一点、风温柔和的替代款。",
        ]
    },
    {
        "turns": [
            "我想买一个 500 元内的电动牙刷。",
            "对了，订单 MP20260706005 显示运输中，大概什么时候能到？",
        ]
    },
]
