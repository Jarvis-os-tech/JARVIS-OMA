from unittest.mock import AsyncMock

import pytest

from connectors import google_workspace
from departments.google_workspace import (
    AGENTS,
    CONTROL_TOOLS,
    GoogleWorkspaceDepartment,
)
from skills import DesktopSkills


@pytest.mark.asyncio
async def test_every_google_tool_has_exactly_one_department_owner():
    owned = [tool for agent in AGENTS for tool in agent.tools]
    assert len(owned) == len(set(owned))
    assert set(owned) | set(CONTROL_TOOLS) == set(google_workspace.TOOLS)
    assert not set(owned) & set(CONTROL_TOOLS)


@pytest.mark.asyncio
async def test_service_agent_rejects_another_services_tool_without_dispatch():
    dispatch = AsyncMock(return_value={"success": True})
    gmail = next(agent for agent in AGENTS if agent.service == "gmail")

    with pytest.raises(ValueError, match="Gmail Agent cannot execute"):
        await gmail.execute("calendar_list_events", {}, dispatch)

    dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_department_routes_service_and_control_tools_through_one_dispatch_seam():
    dispatch = AsyncMock(return_value={"success": True})
    department = GoogleWorkspaceDepartment(dispatch)

    assert (await department.execute("gmail_read", {"message_id": "m1"}))["success"]
    assert (await department.execute("google_connection_status", {}))["success"]
    assert dispatch.await_args_list[0].args == ("gmail_read", {"message_id": "m1"})
    assert dispatch.await_args_list[1].args == ("google_connection_status", {})


@pytest.mark.asyncio
async def test_department_rejects_unknown_tool_without_dispatch():
    dispatch = AsyncMock(return_value={"success": True})
    department = GoogleWorkspaceDepartment(dispatch)

    with pytest.raises(ValueError, match="does not own tool"):
        await department.execute("execute_shell", {})

    dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_unified_jarvis_catalog_lists_google_workspace_department():
    desktop = DesktopSkills()
    try:
        result = await desktop.execute("list_system_agents", {})
    finally:
        await desktop.close_agent_jobs()

    assert result["department_counts"]["Google Workspace"] == 6
    assert {agent["name"] for agent in result["agents"] if agent.get("department") == "Google Workspace"} == {
        "Gmail Agent", "Calendar Agent", "Tasks Agent", "Drive Agent", "Docs Agent", "Sheets Agent",
    }
    assert result["summary"].startswith("JARVIS has 38 registered agents.")
