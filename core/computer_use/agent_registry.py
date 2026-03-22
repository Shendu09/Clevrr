from __future__ import annotations

from .task_agents import BrowserAgent, CodingAgent, FormAgent, WhatsAppAgent


class AgentRegistry:
    def __init__(self, config, gateway, user_id: str) -> None:
        self._agents = [
            WhatsAppAgent(config, gateway, user_id),
            CodingAgent(config, gateway, user_id),
            BrowserAgent(config, gateway, user_id),
            FormAgent(config, gateway, user_id),
        ]

    def get_agent(self, goal: str):
        for agent in self._agents:
            if agent.can_handle(goal):
                return agent
        return None

    def list_capabilities(self) -> list[str]:
        return [agent.__class__.__name__ for agent in self._agents]
