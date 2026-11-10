"""LinkedIn Department Agent Registry.
Exports all 12 specialized agents and base classes.
"""

from .base_agent import BaseLinkedInAgent, AgentResult
from .a1_profile_optimizer import ProfileOptimizerAgent
from .a2_content_planner import ContentPlannerAgent
from .a3_post_writer import PostWriterAgent
from .a4_reply_handler import ReplyHandlerAgent
from .a5_repurposer import RepurposerAgent
from .a6_thread_monitor import ThreadMonitorAgent
from .a7_engager_analytics import EngagerAnalyticsAgent
from .a8_employee_advocacy import EmployeeAdvocacyAgent
from .a9_hook_extractor import HookExtractorAgent
from .a10_humanizer import HumanizerAgent
from .a11_interviewer import InterviewerAgent
from .a12_content_scheduler import ContentSchedulerAgent

AGENT_REGISTRY = {
    "A1": ProfileOptimizerAgent,
    "A2": ContentPlannerAgent,
    "A3": PostWriterAgent,
    "A4": ReplyHandlerAgent,
    "A5": RepurposerAgent,
    "A6": ThreadMonitorAgent,
    "A7": EngagerAnalyticsAgent,
    "A8": EmployeeAdvocacyAgent,
    "A9": HookExtractorAgent,
    "A10": HumanizerAgent,
    "A11": InterviewerAgent,
    "A12": ContentSchedulerAgent,
}

__all__ = [
    "BaseLinkedInAgent",
    "AgentResult",
    "AGENT_REGISTRY",
    "ProfileOptimizerAgent",
    "ContentPlannerAgent",
    "PostWriterAgent",
    "ReplyHandlerAgent",
    "RepurposerAgent",
    "ThreadMonitorAgent",
    "EngagerAnalyticsAgent",
    "EmployeeAdvocacyAgent",
    "HookExtractorAgent",
    "HumanizerAgent",
    "InterviewerAgent",
    "ContentSchedulerAgent",
]
