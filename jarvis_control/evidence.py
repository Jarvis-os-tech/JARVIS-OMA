"""Conservative recognition of clear operational turns, independent of the model."""
import re
from .nlu import NLUEngine

META_TOOLS=frozenset({'discover_domain_tools','list_capabilities','get_assistant_status','play_local_filler','parse_command_values'})


def requires_action_evidence(text, app_names=(), *, tool_attempted=False):
    text=NLUEngine.normalize_text(text or '').casefold()
    live_status=bool(re.match(r"^(?:is|are)\b.*\b(?:connected|muted|active|running|open)\b|"
        r"^(?:what(?:'s| is)|which)\s+(?:(?:the|my|current|system|display|speaker)\s+)*(?:volume|brightness|workspace)\b",text))
    if not NLUEngine._is_action_request(text) and not live_status:
        return False
    if tool_attempted:return True
    if re.search(r'\b(volume|brightness|workspace|application|app|browser|window|terminal|'
                 r'file|folder|directory|clipboard|message|email|phone|bluetooth|wifi|screen|'
                 r'microphone|whatsapp|chrome|firefox|task|reminder|account|service|'
                 r'linkedin|github|slack|notion|spotify|google|discord|twitter|jira|linear)\b',text):
        return True
    return any(isinstance(name,str) and name and re.search(r'\b'+re.escape(name.casefold())+r'\b',text)
               for name in app_names)
