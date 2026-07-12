from abc import ABC, abstractmethod

from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext


class BaseFlow(ABC):
    # 执行业务 Flow。
    @abstractmethod
    def run(self, context: FlowContext) -> list[SseEvent]:
        raise NotImplementedError
