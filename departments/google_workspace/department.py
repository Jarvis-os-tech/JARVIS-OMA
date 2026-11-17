"""Google Workspace department router."""

from collections.abc import Awaitable, Callable

from connectors import google_workspace

from .agents import AGENT_BY_TOOL, AGENTS


CONTROL_TOOLS = frozenset({"google_authorize", "google_connection_status"})


class GoogleWorkspaceDepartment:
    def __init__(self, dispatch: Callable[[str, dict], Awaitable[dict]] | None = None):
        self.agents = AGENTS
        self._dispatch = dispatch

    async def execute(self, tool: str, arguments: dict) -> dict:
        dispatch = self._dispatch or google_workspace.dispatch
        if tool in CONTROL_TOOLS:
            return await dispatch(tool, arguments)
        agent = AGENT_BY_TOOL.get(tool)
        if agent is None:
            raise ValueError(f"Google Workspace department does not own tool: {tool}")
        return await agent.execute(tool, arguments, dispatch)


google_workspace_department = GoogleWorkspaceDepartment()
