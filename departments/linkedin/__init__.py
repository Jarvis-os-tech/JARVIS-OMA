"""LinkedIn Department for JARVIS OS.
Self-contained multi-agent organization dedicated exclusively to LinkedIn strategy, copy, QA, and growth.
"""

from .config import config, LinkedInConfig
from .nim_client import nim_client, NIMClient, NIMResponse
from .department import linkedin_dept, LinkedInDepartment, ReviewPackage

__all__ = [
    "config",
    "LinkedInConfig",
    "nim_client",
    "NIMClient",
    "NIMResponse",
    "linkedin_dept",
    "LinkedInDepartment",
    "ReviewPackage",
]
