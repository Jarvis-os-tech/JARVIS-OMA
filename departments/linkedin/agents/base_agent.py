"""Base agent class for LinkedIn Department specialists.
Provides shared tooling for reference retrieval, state management, and LLM calls via NVIDIA NIM.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Any, Optional

from ..config import config, LinkedInConfig
from ..nim_client import nim_client, NIMClient
from ..tools import linkedin_tools, LinkedInTools

logger = logging.getLogger("departments.linkedin.agents")


@dataclass
class AgentResult:
    success: bool
    agent_id: str
    agent_name: str
    output: Any
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class BaseLinkedInAgent(ABC):
    """Abstract base class for all 12 LinkedIn department agents."""

    agent_id: str = "A0"
    agent_name: str = "BaseAgent"
    description: str = ""

    def __init__(
        self,
        cfg: Optional[LinkedInConfig] = None,
        client: Optional[NIMClient] = None,
        tools: Optional[LinkedInTools] = None,
    ):
        self.cfg = cfg or config
        self.client = client or (NIMClient(cfg) if cfg is not None else nim_client)
        self.tools = tools or linkedin_tools

    def read_reference(self, filename: str) -> str:
        """Read a documentation or formula reference from references/."""
        path = self.cfg.references_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def read_state(self, filename: str) -> str:
        """Read a state or context file from state/."""
        path = self.cfg.state_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_state(self, filename: str, content: str) -> Path:
        """Write or update a state file in state/."""
        path = self.cfg.state_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_json_state(self, filename: str) -> dict[str, Any]:
        """Read JSON state file, or return empty dict."""
        raw = self.read_state(filename)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception as e:
            logger.warning("Failed to parse JSON state %s: %s", filename, e)
            return {}

    def write_json_state(self, filename: str, data: dict[str, Any]) -> Path:
        """Write JSON state formatted."""
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        return self.write_state(filename, formatted)

    def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        extract_final: bool = True,
    ) -> str:
        """Execute a completion via NVIDIA NIM."""
        delimited_prompt = prompt
        if extract_final:
            delimited_prompt += "\n\nIMPORTANT: Enclose your final completed deliverable strictly inside <final_output> and </final_output> tags."

        messages = [{"role": "user", "content": delimited_prompt}]
        response = self.client.generate(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )
        if not response.success:
            raise RuntimeError(f"NIM generation failed ({self.agent_id}): {response.error}")

        raw = response.content
        if extract_final and "<final_output>" in raw:
            parts = raw.split("<final_output>", 1)[1]
            if "</final_output>" in parts:
                return parts.split("</final_output>", 1)[0].strip()
            return parts.strip()
        return raw.strip()

    @abstractmethod
    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        """Execute the agent's core task."""
        pass
