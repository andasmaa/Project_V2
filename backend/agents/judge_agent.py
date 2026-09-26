"""
judge_agent.py — Agent évaluateur qualité (LLM as a Judge)
Utilisé par judge_node dans langgraph_workflow.py.
"""

from agents.base_agent import BaseAgent
from typing import Dict


class JudgeAgent(BaseAgent):
    """
    Évalue la qualité des réponses des autres agents avant envoi au client.
    N'est jamais routé directement par le graphe (pas d'intention "judge"),
    donc process() n'est pas utilisé — seul call_llm() (hérité de BaseAgent)
    est appelé depuis judge_node().
    """

    def __init__(self):
        super().__init__("JUDGE", "qwen:7b")

    async def process(self, message: str, context: Dict = None) -> Dict:
        raise NotImplementedError(
            "JudgeAgent est invoqué via call_llm() directement dans judge_node(), "
            "pas via process()."
        )