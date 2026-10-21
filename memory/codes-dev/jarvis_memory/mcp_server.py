"""Local stdio MCP transport for the universal JARVIS memory service.

The server deliberately does not listen on a network socket.  Each process is
started for one named client with explicit scope and mutation permissions.  It
implements the small JSON-RPC subset needed by MCP clients without adding a
runtime dependency on an MCP SDK.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any, TextIO

from .knowledge import KnowledgeStore
from .service_facade import MemoryServiceError, UniversalMemoryService
from .store import _cross_process_lock


MCP_PROTOCOL_VERSION = "2025-06-18"
READ_TOOLS = frozenset({"memory_search", "memory_read", "memory_history", "memory_status"})
MUTATION_TOOLS = frozenset({"memory_propose", "memory_commit", "memory_correct", "memory_forget"})
ALL_TOOLS = READ_TOOLS | MUTATION_TOOLS
PERMISSIONS = frozenset({"propose", "commit", "correct", "forget"})


class MCPMemoryError(ValueError):
    """Safe client-visible transport or authorization error."""


@dataclass(frozen=True, slots=True)
class ClientPolicy:
    client_id: str
    read_scopes: frozenset[str]
    write_scopes: frozenset[str]
    permissions: frozenset[str] = frozenset()

    def __post_init__(self):
        if (not self.client_id or len(self.client_id) > 128 or
                any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in self.client_id)):
            raise MCPMemoryError("client_id must use 1-128 letters, numbers, dot, underscore or hyphen")
        if not self.read_scopes:
            raise MCPMemoryError("at least one read scope is required")
        if not self.permissions <= PERMISSIONS:
            raise MCPMemoryError("unsupported client permission")
        if self.permissions and not self.write_scopes:
            raise MCPMemoryError("write permissions require at least one write scope")

    @staticmethod
    def _allows(allowed: frozenset[str], scope: str) -> bool:
        return "*" in allowed or scope in allowed

    def can_read(self, scope: str) -> bool:
        return self._allows(self.read_scopes, scope)

    def can_write(self, scope: str) -> bool:
        return self._allows(self.write_scopes, scope)


class AuditLog:
    """Append-only mutation metadata; memory content is never copied here."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, *, client_id: str, operation: str, request_id: Any,
               scope: str = "", record_id: str = "", outcome: str):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        entry = {
            "timestamp": time.time(), "client_id": client_id, "operation": operation,
            "request_id_hash": sha256(str(request_id).encode("utf-8")).hexdigest(),
            "scope": scope, "record_id": record_id, "outcome": outcome,
        }
        encoded = json.dumps(entry, ensure_ascii=True, separators=(",", ":")) + "\n"
        with _cross_process_lock(self.path.with_suffix(self.path.suffix + ".lock")):
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, encoded.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
            os.chmod(self.path, 0o600)


def _object(value, name="arguments"):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MCPMemoryError(f"{name} must be an object")
    return value


class UniversalMemoryMCP:
    """Authorization and MCP tool mapping around ``UniversalMemoryService``."""

    def __init__(self, service: UniversalMemoryService, policy: ClientPolicy,
                 audit: AuditLog, *, max_request_bytes=64 * 1024,
                 max_response_bytes=256 * 1024):
        self.service = service
        self.policy = policy
        self.audit = audit
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self._lock = threading.RLock()

    def tool_names(self):
        names = set(READ_TOOLS)
        names.update("memory_" + permission for permission in self.policy.permissions)
        return sorted(names)

    def _require_permission(self, permission):
        if permission not in self.policy.permissions:
            raise MCPMemoryError(f"client is not permitted to {permission} memory")

    def _read_record(self, record_id):
        record = self.service.read(record_id)
        if not self.policy.can_read(record["scope"]):
            raise MCPMemoryError("record is outside the client's read scopes")
        return record

    def _writable_record(self, record_id, permission):
        self._require_permission(permission)
        record = self.service.read(record_id)
        if not self.policy.can_write(record["scope"]):
            raise MCPMemoryError("record is outside the client's write scopes")
        return record

    def call_tool(self, name, arguments, request_id=None):
        if name not in ALL_TOOLS or name not in self.tool_names():
            raise MCPMemoryError("unknown or unauthorized memory tool")
        args = _object(arguments)
        with self._lock:
            if name == "memory_status":
                result = self.service.status()
                result.update(client_id=self.policy.client_id,
                              read_scopes=sorted(self.policy.read_scopes),
                              permissions=sorted(self.policy.permissions))
                return result
            if name == "memory_search":
                requested = args.get("scopes")
                if requested is None:
                    if "*" in self.policy.read_scopes:
                        raise MCPMemoryError("clients with wildcard access must specify search scopes")
                    requested = sorted(self.policy.read_scopes)
                if (not isinstance(requested, list) or
                        not all(isinstance(scope, str) and self.policy.can_read(scope) for scope in requested)):
                    raise MCPMemoryError("search scopes exceed the client's read scopes")
                return self.service.search(
                    query=args.get("query", ""), scopes=requested, types=args.get("types"),
                    limit=args.get("limit", 20), cursor=args.get("cursor"),
                    include_proposals=bool(args.get("include_proposals", False)))
            if name == "memory_read":
                return self._read_record(args.get("record_id"))
            if name == "memory_history":
                self._read_record(args.get("record_id"))
                return {"revisions": self.service.history(args.get("record_id"))}

            operation = name.removeprefix("memory_")
            scope = ""
            record_id = str(args.get("record_id") or args.get("proposal_id") or "")
            try:
                if name == "memory_propose":
                    self._require_permission("propose")
                    record = _object(args.get("record"), "record")
                    scope = record.get("scope", "")
                    if not isinstance(scope, str) or not self.policy.can_write(scope):
                        raise MCPMemoryError("proposal scope exceeds the client's write scopes")
                    sensitivity = record.get("sensitivity", "private")
                    if sensitivity not in {"public", "internal", "private"}:
                        raise MCPMemoryError("unsupported proposal sensitivity")
                    record = dict(record, author=self.policy.client_id,
                                  agent_id=self.policy.client_id,
                                  authority="agent", sensitivity=sensitivity)
                    result = self.service.propose(record, args.get("evidence_refs", ()))
                    record_id = result["id"]
                elif name == "memory_commit":
                    record = self._writable_record(args.get("proposal_id"), "commit")
                    scope, record_id = record["scope"], record["id"]
                    result = self.service.commit(record_id)
                elif name == "memory_correct":
                    record = self._writable_record(args.get("record_id"), "correct")
                    scope, record_id = record["scope"], record["id"]
                    result = self.service.correct(
                        record_id, args.get("replacement"), args.get("reason", ""),
                        author=self.policy.client_id, agent_id=self.policy.client_id,
                        authority="agent")
                else:
                    record = self._writable_record(args.get("record_id"), "forget")
                    scope, record_id = record["scope"], record["id"]
                    result = self.service.forget(record_id)
            except Exception:
                self.audit.append(client_id=self.policy.client_id, operation=operation,
                                  request_id=request_id, scope=scope, record_id=record_id,
                                  outcome="rejected")
                raise
            self.audit.append(client_id=self.policy.client_id, operation=operation,
                              request_id=request_id, scope=scope, record_id=record_id,
                              outcome="accepted")
            return result

    @staticmethod
    def tools():
        record_id = {"type": "string", "minLength": 1, "maxLength": 128}
        return {
            "memory_search": {"description": "Search authorized shared-memory scopes.", "inputSchema": {
                "type": "object", "properties": {"query": {"type": "string", "maxLength": 500},
                    "scopes": {"type": "array", "items": {"type": "string"}},
                    "types": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    "cursor": {"type": "string"}, "include_proposals": {"type": "boolean"}}}},
            "memory_read": {"description": "Read one authorized memory record.", "inputSchema": {
                "type": "object", "required": ["record_id"], "properties": {"record_id": record_id}}},
            "memory_history": {"description": "Read the revision history of one authorized record.", "inputSchema": {
                "type": "object", "required": ["record_id"], "properties": {"record_id": record_id}}},
            "memory_status": {"description": "Show memory service and client capability status.",
                              "inputSchema": {"type": "object", "properties": {}}},
            "memory_propose": {"description": "Propose a non-authoritative memory for review.", "inputSchema": {
                "type": "object", "required": ["record"], "properties": {
                    "record": {"type": "object", "required": ["text", "scope"]},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}}}}},
            "memory_commit": {"description": "Commit an authorized proposal.", "inputSchema": {
                "type": "object", "required": ["proposal_id"], "properties": {"proposal_id": record_id}}},
            "memory_correct": {"description": "Correct an authorized committed memory.", "inputSchema": {
                "type": "object", "required": ["record_id", "replacement"], "properties": {
                    "record_id": record_id, "replacement": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "reason": {"type": "string", "maxLength": 1000}}}},
            "memory_forget": {"description": "Delete an authorized memory revision family.", "inputSchema": {
                "type": "object", "required": ["record_id"], "properties": {"record_id": record_id}}},
        }

    def _success(self, request_id, result):
        response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        if len(json.dumps(response, ensure_ascii=False).encode("utf-8")) > self.max_response_bytes:
            raise MCPMemoryError("response exceeds configured size limit")
        return response

    @staticmethod
    def _error(request_id, code, message):
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": code, "message": message}}

    def handle(self, message):
        request_id = message.get("id") if isinstance(message, dict) else None
        try:
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                raise MCPMemoryError("invalid JSON-RPC request")
            method = message.get("method")
            params = _object(message.get("params"), "params")
            if method == "initialize":
                return self._success(request_id, {"protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "jarvis-universal-memory", "version": "1"}})
            if method in {"notifications/initialized", "notifications/cancelled"}:
                return None
            if method == "ping":
                return self._success(request_id, {})
            if method == "tools/list":
                definitions = self.tools()
                return self._success(request_id, {"tools": [dict(name=name, **definitions[name])
                    for name in self.tool_names()]})
            if method == "tools/call":
                result = self.call_tool(params.get("name"), params.get("arguments"), request_id)
                return self._success(request_id, {"content": [{"type": "text",
                    "text": json.dumps(result, ensure_ascii=False)}], "isError": False})
            return self._error(request_id, -32601, "method not found")
        except (MCPMemoryError, MemoryServiceError, ValueError, TypeError, KeyError) as error:
            return self._error(request_id, -32602, str(error)[:500])
        except Exception:
            return self._error(request_id, -32603, "internal memory service error")

    def serve(self, input_stream: TextIO, output_stream: TextIO):
        for line in input_stream:
            if len(line.encode("utf-8")) > self.max_request_bytes:
                response = self._error(None, -32600, "request exceeds configured size limit")
            else:
                try:
                    response = self.handle(json.loads(line))
                except json.JSONDecodeError:
                    response = self._error(None, -32700, "invalid JSON")
            if response is not None:
                output_stream.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                output_stream.flush()


def build_parser():
    parser = argparse.ArgumentParser(description="Local stdio MCP server for JARVIS universal memory")
    parser.add_argument("--database", required=True, help="Absolute path to the JARVIS knowledge SQLite file")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--read-scope", action="append", required=True)
    parser.add_argument("--write-scope", action="append", default=[])
    parser.add_argument("--permission", action="append", choices=sorted(PERMISSIONS), default=[])
    parser.add_argument("--audit-log", help="Audit JSONL path; defaults beside the database")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    database = Path(args.database).expanduser()
    if not database.is_absolute():
        raise SystemExit("--database must be an absolute path")
    audit_path = Path(args.audit_log).expanduser() if args.audit_log else database.with_name("memory_mcp_audit.jsonl")
    if not audit_path.is_absolute():
        raise SystemExit("--audit-log must be an absolute path")
    policy = ClientPolicy(args.client_id, frozenset(args.read_scope),
                          frozenset(args.write_scope), frozenset(args.permission))
    server = UniversalMemoryMCP(UniversalMemoryService(KnowledgeStore(database)), policy, AuditLog(audit_path))
    server.serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["AuditLog", "ClientPolicy", "MCPMemoryError", "UniversalMemoryMCP", "main"]
