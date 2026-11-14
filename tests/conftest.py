import sys
from pathlib import Path
from unittest.mock import MagicMock

root = str(Path(__file__).resolve().parent.parent)
sys.path = [p for p in sys.path if p != root]
sys.path.insert(0, root)

try:
    import sounddevice  # noqa: F401
except Exception:
    mock_sd = MagicMock()
    mock_sd.default = MagicMock()
    mock_sd.query_devices.return_value = [{'name': 'default', 'max_input_channels': 2, 'max_output_channels': 2}]
    mock_sd.InputStream = MagicMock()
    mock_sd.OutputStream = MagicMock()
    mock_sd.RawInputStream = MagicMock()
    mock_sd.RawOutputStream = MagicMock()
    mock_sd.PortAudioError = type('PortAudioError', (Exception,), {})
    mock_sd.CallbackStop = type('CallbackStop', (Exception,), {})
    mock_sd.CallbackAbort = type('CallbackAbort', (Exception,), {})
    sys.modules['sounddevice'] = mock_sd

