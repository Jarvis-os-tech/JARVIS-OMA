"""Google Workspace department."""

from .agents import AGENT_NAMES, AGENTS, GoogleWorkspaceAgent
from .department import CONTROL_TOOLS, GoogleWorkspaceDepartment, google_workspace_department

__all__ = [
    "AGENT_NAMES", "AGENTS", "CONTROL_TOOLS", "GoogleWorkspaceAgent",
    "GoogleWorkspaceDepartment", "google_workspace_department",
]
