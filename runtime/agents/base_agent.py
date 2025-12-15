"""
Base Agent: 所有Agent的基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """Agent基类：定义统一的输入/输出/约束接口"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        执行Agent职责
        返回：决策结果和状态更新
        """
        pass
    
    @abstractmethod
    def get_governing_question(self) -> str:
        """返回该Agent负责的治理问题"""
        pass

