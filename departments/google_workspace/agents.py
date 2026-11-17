"""Service-bounded agents for the Google Workspace department."""

from dataclasses import dataclass
from typing import Awaitable, Callable


Dispatch = Callable[[str, dict], Awaitable[dict]]


@dataclass(frozen=True)
class GoogleWorkspaceAgent:
    name: str
    service: str
    tools: frozenset[str]

    async def execute(self, tool: str, arguments: dict, dispatch: Dispatch) -> dict:
        if tool not in self.tools:
            raise ValueError(f"{self.name} cannot execute Google tool: {tool}")
        return await dispatch(tool, arguments)


AGENTS = (
    GoogleWorkspaceAgent("Gmail Agent", "gmail", frozenset({
        "gmail_search", "gmail_read", "gmail_create_draft",
        "gmail_send_draft", "gmail_list_labels",
    })),
    GoogleWorkspaceAgent("Calendar Agent", "calendar", frozenset({
        "calendar_list_events", "calendar_get_event", "calendar_create_event",
        "calendar_list_calendars", "calendar_current_time", "calendar_update_event",
        "calendar_delete_event", "calendar_check_availability",
        "calendar_create_calendar", "calendar_delete_calendar", "calendar_add_attachment",
    })),
    GoogleWorkspaceAgent("Tasks Agent", "tasks", frozenset({
        "tasks_list_lists", "tasks_list_tasks", "tasks_create_task", "tasks_complete_task",
    })),
    GoogleWorkspaceAgent("Drive Agent", "drive", frozenset({
        "drive_search_files", "drive_get_file", "drive_read_text_file",
    })),
    GoogleWorkspaceAgent("Docs Agent", "docs", frozenset({"docs_read_document"})),
    GoogleWorkspaceAgent("Sheets Agent", "sheets", frozenset({
        "sheets_get_spreadsheet", "sheets_read_range",
    })),
)

AGENT_BY_TOOL = {tool: agent for agent in AGENTS for tool in agent.tools}
AGENT_NAMES = [agent.name for agent in AGENTS]
