import asyncio
from workflow.langgraph_workflow import BankAgentWorkflow

async def test():
    wf = BankAgentWorkflow()
    await wf.initialize()

    result = await wf.process_message(
        message="j'ai perdu ma carte",
        user_id="test",
        session_id="test-judge-graph",
    )

    print("Nodes visités :", result.get("nodes_visited"))
    print("Judge présent :", "judge" in result.get("nodes_visited", []))
    print("Requires HITL :", result.get("requires_hitl"))
    print("Réponse finale :", result.get("response")[:300])

asyncio.run(test())