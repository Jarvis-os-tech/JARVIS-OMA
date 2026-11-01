"""Tests for safe filesystem operations, TaskRunner, and DesktopSkills integration.

Verifies:
1. Filesystem safety and bounds: make_directory, write_text, append_text,
   read_text, replace_text, inspect_path, search_files, search_file_content,
   copy_path, move_path, trash_path, delete_path, and critical path protection.
2. Step-by-step TaskRunner: validation, execution, ground-truth disk checks,
   retention limits, failure halting, and cancellation.
3. DesktopSkills integration: list_files (filesystem.list), read_file (filesystem.read),
   search_files (filesystem.search), search_file_content (filesystem.grep), and
   start_task/task_status.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import pytest

import filesystem as fs
from filesystem import (
    FileOperationError,
    make_directory,
    write_text,
    append_text,
    read_text,
    replace_text,
    inspect_path,
    search_files,
    search_file_content,
    copy_path,
    move_path,
    trash_path,
    delete_path,
    CRITICAL_PATHS,
)
import task_runner
from filesystem.task_runner import TaskRunner, TaskPlanError
from skills.skills import DesktopSkills
from skills.errors import SkillError


# =====================================================================
# 1. Direct Filesystem Tests
# =====================================================================

def test_make_directory(tmp_path: Path):
    target = tmp_path / "sub" / "deep_dir"
    res = make_directory(str(target))
    assert res["status"] == "created"
    assert res["verified"] is True
    assert target.is_dir()

    # Idempotent
    res2 = make_directory(str(target))
    assert res2["status"] == "created"
    assert res2["verified"] is True


def test_write_and_read_text(tmp_path: Path):
    file_path = tmp_path / "test.txt"
    content = "Hello, JARVIS OS!\nSecond Line."

    # Write
    res_w = write_text(str(file_path), content)
    assert res_w["status"] == "written"
    assert res_w["verified"] is True
    assert res_w["bytes"] == len(content.encode("utf-8"))
    assert "sha256" in res_w["evidence"]

    # Overwrite protection
    with pytest.raises(FileOperationError, match="file exists"):
        write_text(str(file_path), "New content", overwrite=False)

    # Overwrite allowed
    res_w2 = write_text(str(file_path), "Replaced content", overwrite=True)
    assert res_w2["status"] == "written"
    assert res_w2["verified"] is True

    # Read
    res_r = read_text(str(file_path))
    assert res_r["content"] == "Replaced content"
    assert res_r["offset"] == 0
    assert res_r["chars_read"] == len("Replaced content")
    assert res_r["truncated"] is False


def test_read_text_offset_and_truncation(tmp_path: Path):
    file_path = tmp_path / "numbers.txt"
    long_content = "".join(f"line_{i:04d}\n" for i in range(100))
    write_text(str(file_path), long_content)

    # Read with max_chars
    res = read_text(str(file_path), offset=0, max_chars=30)
    assert res["chars_read"] == 30
    assert res["truncated"] is True
    assert res["has_more"] is True
    assert res["content"] == long_content[:30]

    # Read with offset
    res_offset = read_text(str(file_path), offset=30, max_chars=30)
    assert res_offset["chars_read"] == 30
    assert res_offset["content"] == long_content[30:60]

    # Bounds validation
    with pytest.raises(FileOperationError, match="offset must be nonnegative"):
        read_text(str(file_path), offset=-1)
    with pytest.raises(FileOperationError, match="max_chars must be from 1 to 100000"):
        read_text(str(file_path), max_chars=0)
    with pytest.raises(FileOperationError, match="max_chars must be from 1 to 100000"):
        read_text(str(file_path), max_chars=200000)


def test_append_text(tmp_path: Path):
    file_path = tmp_path / "append_test.txt"
    write_text(str(file_path), "Line 1\n")

    res_app = append_text(str(file_path), "Line 2\n")
    assert res_app["status"] == "appended"
    assert res_app["verified"] is True
    assert res_app["bytes_appended"] == len("Line 2\n".encode("utf-8"))

    readback = read_text(str(file_path))["content"]
    assert readback == "Line 1\nLine 2\n"


def test_replace_text(tmp_path: Path):
    file_path = tmp_path / "edit_test.txt"
    write_text(str(file_path), "The quick brown fox jumps over the lazy dog.")

    # Single match edit
    res = replace_text(str(file_path), old="quick brown fox", new="swift orange cat")
    assert res["status"] == "edited"
    assert res["verified"] is True

    readback = read_text(str(file_path))["content"]
    assert readback == "The swift orange cat jumps over the lazy dog."

    # Zero matches
    with pytest.raises(FileOperationError, match="expected exactly one matching passage; found 0"):
        replace_text(str(file_path), old="nonexistent", new="anything")

    # Ambiguous matches (>1)
    write_text(str(file_path), "apple banana apple", overwrite=True)
    with pytest.raises(FileOperationError, match="expected exactly one matching passage; found 2"):
        replace_text(str(file_path), old="apple", new="orange")


def test_inspect_path(tmp_path: Path):
    file_path = tmp_path / "inspect.txt"
    write_text(str(file_path), "Line 1\nLine 2\nLine 3\n")

    info = inspect_path(str(file_path))
    assert info["exists"] is True
    assert info["type"] == "file"
    assert info["size"] > 0
    assert info["line_count"] == 3
    assert info["is_readable"] is True
    assert info["is_writable"] is True

    # Nonexistent
    missing = inspect_path(str(tmp_path / "does_not_exist"))
    assert missing["exists"] is False


def test_search_files(tmp_path: Path):
    (tmp_path / "src" / "modules").mkdir(parents=True)
    (tmp_path / "src" / "main.py").write_text("print('main')", encoding="utf-8")
    (tmp_path / "src" / "modules" / "helper.py").write_text("def h(): pass", encoding="utf-8")
    (tmp_path / "src" / "notes.txt").write_text("notes", encoding="utf-8")
    (tmp_path / "src" / ".secret").write_text("hidden", encoding="utf-8")

    # Match .py files
    res = search_files(str(tmp_path), query=".py")
    assert len(res["matches"]) == 2
    match_basenames = {Path(p).name for p in res["matches"]}
    assert match_basenames == {"main.py", "helper.py"}

    # Hidden files excluded by default
    res_hidden = search_files(str(tmp_path), query="secret", include_hidden=False)
    assert len(res_hidden["matches"]) == 0

    # Hidden files included
    res_hidden_incl = search_files(str(tmp_path), query="secret", include_hidden=True)
    assert len(res_hidden_incl["matches"]) == 1


def test_search_file_content_grep(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "intro.md").write_text("# Welcome\nJARVIS OS brings desktop autonomy.\nEnjoy!", encoding="utf-8")
    (docs / "specs.md").write_text("# Specs\nMemory limit: 8MiB\nJARVIS OS handles voice.", encoding="utf-8")
    (docs / "other.txt").write_text("irrelevant data", encoding="utf-8")

    # Grep across directory
    res = search_file_content(str(docs), query="JARVIS OS")
    assert res["query"] == "JARVIS OS"
    assert len(res["matches"]) == 2
    assert all("JARVIS OS" in m["line"] for m in res["matches"])

    # Grep within single file
    res_single = search_file_content(str(docs / "intro.md"), query="Welcome")
    assert len(res_single["matches"]) == 1
    assert res_single["matches"][0]["line_number"] == 1


def test_copy_and_move_path(tmp_path: Path):
    src = tmp_path / "original.txt"
    write_text(str(src), "Data to copy/move")

    # Copy
    dst_copy = tmp_path / "backup.txt"
    res_c = copy_path(str(src), str(dst_copy))
    assert res_c["status"] == "copied"
    assert res_c["verified"] is True
    assert dst_copy.exists()
    assert src.exists()

    # Move
    dst_move = tmp_path / "moved.txt"
    res_m = move_path(str(src), str(dst_move))
    assert res_m["status"] == "moved"
    assert res_m["verified"] is True
    assert dst_move.exists()
    assert not src.exists()


def test_trash_and_delete_path(tmp_path: Path, monkeypatch):
    # Route Trash to isolated tmp dir
    fake_trash = tmp_path / "fake_local_share"
    monkeypatch.setenv("XDG_DATA_HOME", str(fake_trash))

    item_trash = tmp_path / "trash_me.txt"
    write_text(str(item_trash), "To be trashed")
    res_t = trash_path(str(item_trash))
    assert res_t["status"] == "trashed"
    assert not item_trash.exists()
    assert Path(res_t["trash_path"]).exists()

    # Permanent delete
    item_del = tmp_path / "delete_me.txt"
    write_text(str(item_del), "To be deleted")
    res_d = delete_path(str(item_del))
    assert res_d["status"] == "deleted"
    assert not item_del.exists()

    # Delete non-empty dir without recursive=True fails
    non_empty = tmp_path / "non_empty"
    non_empty.mkdir()
    (non_empty / "child.txt").write_text("child")
    with pytest.raises(FileOperationError, match="directory is not empty"):
        delete_path(str(non_empty), recursive=False)

    # Delete non-empty dir with recursive=True succeeds
    res_dr = delete_path(str(non_empty), recursive=True)
    assert res_dr["status"] == "deleted"
    assert not non_empty.exists()


def test_critical_paths_protection():
    # Attempting to delete or trash critical paths must raise FileOperationError
    for crit in ("/", "/bin", "/etc", "/usr", str(Path.home())):
        with pytest.raises(FileOperationError, match="cannot delete system root or home"):
            delete_path(crit, recursive=True)
        with pytest.raises(FileOperationError, match="cannot trash this path"):
            trash_path(crit)


# =====================================================================
# 2. TaskRunner Tests
# =====================================================================

def test_task_runner_module_alias():
    """Verify task_runner.py in repo root redirects to filesystem.task_runner."""
    assert task_runner.TaskRunner is TaskRunner
    assert task_runner.TaskPlanError is TaskPlanError


@pytest.mark.asyncio
async def test_task_runner_plan_validation():
    runner = TaskRunner(execute=lambda t, a: None, validate=lambda t, a: True)

    # Empty / too long description
    with pytest.raises(TaskPlanError, match="description must be 1 to 200 characters"):
        runner.start("", "[]")

    # Malformed JSON
    with pytest.raises(TaskPlanError, match="must be a JSON array"):
        runner.start("test", "not json")

    # Empty steps array
    with pytest.raises(TaskPlanError, match="must have 1 to 30 steps"):
        runner.start("test", "[]")

    # Step missing args
    with pytest.raises(TaskPlanError, match="must contain tool and args"):
        runner.start("test", json.dumps([{"tool": "write_file"}]))

    # Unsupported tool
    with pytest.raises(TaskPlanError, match="unavailable tool or invalid arguments"):
        runner.start("test", json.dumps([{"tool": "unsupported_shell", "args": {}}]))

    # Validator rejection
    strict_runner = TaskRunner(execute=lambda t, a: None, validate=lambda t, a: False)
    with pytest.raises(TaskPlanError, match="unavailable tool or invalid arguments"):
        strict_runner.start("test", json.dumps([{"tool": "write_file", "args": {"path": "a"}}]))

    await runner.close()
    await strict_runner.close()


@pytest.mark.asyncio
async def test_task_runner_execution_and_ground_truth(tmp_path: Path):
    async def mock_execute(tool: str, args: dict):
        if tool == "make_directory":
            return make_directory(args["path"])
        elif tool == "write_file":
            return write_text(args["path"], args["content"], overwrite=args.get("overwrite", False))
        elif tool == "append_file":
            return append_text(args["path"], args["content"])
        raise ValueError(f"Unknown tool {tool}")

    def mock_validate(tool: str, args: dict):
        return True

    runner = TaskRunner(mock_execute, mock_validate)

    dir_path = tmp_path / "task_out"
    file_path = dir_path / "result.txt"

    plan = [
        {"tool": "make_directory", "args": {"path": str(dir_path)}},
        {"tool": "write_file", "args": {"path": str(file_path), "content": "Alpha\n"}},
        {"tool": "append_file", "args": {"path": str(file_path), "content": "Beta\n"}},
    ]

    job_info = runner.start("Create and populate test file", json.dumps(plan))
    task_id = job_info["id"]

    # Wait for completion
    for _ in range(50):
        status = runner.status(task_id)
        if status["status"] in ("completed", "failed", "cancelled"):
            break
        await asyncio.sleep(0.05)

    assert status["status"] == "completed"
    assert status["completed_steps"] == 3
    assert status["total_steps"] == 3
    assert file_path.read_text(encoding="utf-8") == "Alpha\nBeta\n"

    # Verify event queue received the task event
    event = await asyncio.wait_for(runner.events.get(), timeout=2.0)
    assert event["kind"] == "task"
    assert event["id"] == task_id
    assert event["status"] == "completed"

    await runner.close()


@pytest.mark.asyncio
async def test_task_runner_failure_halts_remaining_steps(tmp_path: Path):
    async def failing_execute(tool: str, args: dict):
        if tool == "write_file":
            raise RuntimeError("Disk write I/O error")
        return {"status": "created", "verified": True}

    runner = TaskRunner(failing_execute, lambda t, a: True)
    plan = [
        {"tool": "write_file", "args": {"path": str(tmp_path / "fail.txt"), "content": "..."}},
        {"tool": "write_file", "args": {"path": str(tmp_path / "never.txt"), "content": "..."}},
    ]

    info = runner.start("Failure test", json.dumps(plan))
    task_id = info["id"]

    for _ in range(50):
        status = runner.status(task_id)
        if status["status"] in ("completed", "failed", "cancelled"):
            break
        await asyncio.sleep(0.05)

    assert status["status"] == "failed"
    assert status["completed_steps"] == 0
    assert status["steps"][0]["status"] == "failed"
    assert "Disk write I/O error" in status["steps"][0]["error"]
    assert status["steps"][1]["status"] == "pending"

    await runner.close()


@pytest.mark.asyncio
async def test_task_runner_cancellation(tmp_path: Path):
    step_started = asyncio.Event()

    async def slow_execute(tool: str, args: dict):
        step_started.set()
        await asyncio.sleep(0.5)
        return write_text(args["path"], args["content"])

    runner = TaskRunner(slow_execute, lambda t, a: True)
    plan = [
        {"tool": "write_file", "args": {"path": str(tmp_path / "f1.txt"), "content": "1"}},
        {"tool": "write_file", "args": {"path": str(tmp_path / "f2.txt"), "content": "2"}},
    ]

    info = runner.start("Slow task", json.dumps(plan))
    task_id = info["id"]

    await step_started.wait()
    runner.cancel(task_id)

    for _ in range(50):
        status = runner.status(task_id)
        if status["status"] in ("completed", "failed", "cancelled"):
            break
        await asyncio.sleep(0.05)

    assert status["status"] == "cancelled"
    await runner.close()


# =====================================================================
# 3. DesktopSkills Integration Tests
# =====================================================================

@pytest.mark.asyncio
async def test_desktop_skills_filesystem_operations(tmp_path: Path):
    skills = DesktopSkills()

    # 1. make_directory
    test_dir = tmp_path / "skills_test_dir"
    res_mkdir = await skills.execute("make_directory", {"path": str(test_dir)})
    assert res_mkdir["status"] == "created"
    assert res_mkdir["verified"] is True
    assert test_dir.is_dir()

    # 2. write_file
    test_file = test_dir / "sample.txt"
    res_w = await skills.execute("write_file", {
        "path": str(test_file),
        "content": "First line of JARVIS OS data\nSecond line: autonomy in action\nThird line."
    })
    assert res_w["status"] == "written"
    assert res_w["verified"] is True

    # 3. list_files (filesystem.list)
    res_list = await skills.execute("list_files", {"path": str(test_dir), "limit": 10})
    assert res_list["count"] == 1
    assert res_list["entries"][0]["name"] == "sample.txt"

    # 4. read_file (filesystem.read)
    res_r = await skills.execute("read_file", {"path": str(test_file), "offset": 0, "max_chars": 50})
    assert "First line" in res_r["content"]
    assert res_r["chars_read"] <= 50

    # 5. search_files (filesystem.search)
    res_s = await skills.execute("search_files", {"path": str(test_dir), "query": "sample"})
    assert len(res_s["matches"]) == 1
    assert res_s["matches"][0] == str(test_file)

    # 6. search_file_content (filesystem.grep)
    res_g = await skills.execute("search_file_content", {"path": str(test_dir), "query": "autonomy"})
    assert len(res_g["matches"]) == 1
    assert res_g["matches"][0]["path"] == str(test_file)
    assert res_g["matches"][0]["line_number"] == 2

    # 7. append_file
    res_app = await skills.execute("append_file", {"path": str(test_file), "content": "\nFourth line appended."})
    assert res_app["status"] == "appended"
    assert res_app["verified"] is True

    # 8. inspect_file
    res_info = await skills.execute("inspect_file", {"path": str(test_file)})
    assert res_info["exists"] is True
    assert res_info["type"] == "file"
    assert res_info["line_count"] == 4

    # 9. edit_file
    res_edit = await skills.execute("edit_file", {
        "path": str(test_file),
        "old": "autonomy in action",
        "new": "desktop excellence"
    })
    assert res_edit["status"] == "edited"
    assert res_edit["verified"] is True

    # 10. delete_path
    res_del = await skills.execute("delete_path", {"path": str(test_dir), "recursive": True})
    assert res_del["status"] == "deleted"
    assert not test_dir.exists()


@pytest.mark.asyncio
async def test_desktop_skills_task_runner_flow(tmp_path: Path):
    skills = DesktopSkills()

    work_dir = tmp_path / "task_workflow"
    out_file = work_dir / "report.md"

    plan = [
        {"tool": "make_directory", "args": {"path": str(work_dir)}},
        {"tool": "write_file", "args": {"path": str(out_file), "content": "# System Report\n"}},
        {"tool": "append_file", "args": {"path": str(out_file), "content": "- Checkpoint 1: Verified\n"}},
    ]

    # start_task
    start_res = await skills.execute("start_task", {
        "description": "Multi-step build workflow",
        "plan_json": json.dumps(plan),
    })
    task_id = start_res["id"]
    assert start_res["status"] in ("queued", "running", "completed")

    # Poll task_status
    for _ in range(50):
        status = await skills.execute("task_status", {"task_id": task_id})
        if status["status"] in ("completed", "failed", "cancelled"):
            break
        await asyncio.sleep(0.05)

    assert status["status"] == "completed"
    assert status["completed_steps"] == 3
    assert out_file.is_file()
    assert "# System Report" in out_file.read_text(encoding="utf-8")

    # list_tasks
    task_list = await skills.execute("list_tasks", {})
    assert any(t["id"] == task_id for t in task_list["tasks"])
