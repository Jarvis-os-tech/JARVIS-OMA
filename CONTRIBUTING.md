# Contributing to JARVIS-OMA

Thank you for your interest in contributing to JARVIS-OMA!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Jarvis-os-tech/JARVIS-OMA.git
   cd JARVIS-OMA
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Ensure system audio tools are installed (on Arch/Omarchy):
   ```bash
   # Requires PipeWire with pw-record, pw-play, and pactl
   ./run.sh --check
   ```

## Running Tests

Before submitting changes, run the test suite to ensure all tests pass:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s . -p 'test_*.py' -v
```

## Adding Skills

Custom skills can be added as JSON manifests inside `skill_manifests/` or loaded from an external directory via `--skill-dir`. See [skill_manifests/omarchy-defaults.json](skill_manifests/omarchy-defaults.json) for schema examples.

## Pull Requests

1. Create a feature branch (`git checkout -b feat/your-feature-name`).
2. Make atomic commits using [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, etc.).
3. Verify that all unit and regression tests pass.
4. Push your branch and open a Pull Request.
