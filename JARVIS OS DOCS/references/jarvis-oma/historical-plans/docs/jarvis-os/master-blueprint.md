# JARVIS OMA Master Blueprint

This document is the full brainstorming map for the future of JARVIS OMA. It is intentionally broader than the current implementation. Each item will later become a design, implementation task, test plan, or explicit decision to defer.

## 1. Identity and operating model

JARVIS OMA is a personal AI operating layer for Linux and Omarchy. It combines voice, text, vision, memory, desktop control, system control, external services, proactive automation, and multiple specialist agents.

The target is not one giant unrestricted AI process. The target is a supervised personal computer system with:

- A conversational interface
- A shared understanding of computer state
- A planner and task manager
- Safe capability adapters
- GUI and system control
- A multi-agent supervisor
- Persistent memory
- Verification and audit trails
- A visible user control surface

## 2. Major subsystems

### A. Runtime and operating foundation

- Main JARVIS service and lifecycle
- Startup, shutdown, restart, crash recovery
- Configuration files, environment variables, profiles, and secrets
- User service and boot/login integration
- Local IPC and control socket
- Event bus and internal message routing
- Structured logging and diagnostics
- Health checks and self-test mode
- Version and migration management
- Plugin and capability discovery
- Resource limits and graceful degradation

### B. Human interaction

- Full-duplex voice conversation
- Wake word or push-to-talk modes
- Barge-in and interruption
- Text input and command mode
- Multimodal file attachment
- Screen sharing and camera input
- Spoken confirmations
- Desktop notifications
- Streaming progress updates
- Clarifying questions
- Explain-what-I-am-doing mode
- Quiet mode and focus mode
- Accessibility-friendly interaction
- Multiple personas or voices
- Language and translation support

### C. Perception and awareness

- Focused application and window
- All open windows and workspaces
- Screen screenshots and regions
- OCR and visible text
- Accessibility tree
- Application state
- Clipboard state
- Audio input/output state
- Network state
- CPU, memory, disk, battery, and temperature
- Running processes and services
- Connected devices and monitors
- Active project and repository
- Running JARVIS tasks and agents
- Calendar, reminders, and todo state
- User presence and idle/active state

The future goal is one timestamped `DesktopState`, not many unrelated observations.

### D. Intent understanding and planning

- Convert natural language into a goal
- Detect whether the request is informational or action-oriented
- Extract constraints, deadlines, and preferences
- Identify ambiguity and ask questions
- Break goals into steps
- Detect dependencies between steps
- Estimate risk, time, and required capabilities
- Select tools and agents
- Create a plan before complex execution
- Update plans when the environment changes
- Pause and resume plans
- Recover from failed steps
- Explain plans in simple language

### E. System control

- Volume, mute, microphone, and audio routing
- Brightness and display management
- Lock, sleep, hibernate, reboot, and shutdown
- Wi-Fi and Bluetooth
- Network diagnostics
- Process inspection and termination
- Service inspection and management
- Package and application installation with approval
- Environment variables and shell profiles
- USB and device inspection
- Battery and power management
- Monitor and display layout
- Keyboard layout and input methods
- Timezone and locale
- Notifications
- Clipboard
- Screenshots and screen recording

### F. Window manager and desktop control

- Open and close applications
- Focus windows
- Move, resize, maximize, minimize, float, and fullscreen
- Switch workspaces
- Create named workspace layouts
- Save and restore desktop sessions
- Arrange applications by task
- Create coding, meeting, research, and media modes
- Detect crashed or frozen applications
- Move windows between monitors
- Manage virtual desktops
- Control panels, bars, and widgets

### G. Universal GUI control

JARVIS should use the most reliable control method available:

1. Native application API or command line
2. Desktop accessibility tree
3. Browser automation protocol
4. Keyboard shortcuts
5. Vision and coordinate interaction

Capabilities:

- Observe the current screen
- Find buttons, menus, fields, tabs, and dialogs
- Click, double-click, drag, scroll, type, paste, and send shortcuts
- Read and describe visible content
- Interact with unknown applications
- Detect modal dialogs and confirmation prompts
- Verify visible changes after actions
- Retry safely when an action did not take effect
- Stop immediately on user interruption
- Record evidence for every meaningful GUI action

### H. Application and browser control

- Application discovery and launching
- Application-specific adapters
- Browser tabs, navigation, forms, downloads, and page reading
- Search and research workflows
- Login-aware but approval-controlled actions
- File upload and download
- Web page summarization and extraction
- Browser session awareness
- Safe handling of untrusted web content
- Site-specific workflows

### I. Filesystem and project control

- List, inspect, read, write, edit, copy, move, trash, and delete
- Search names and content
- File previews and metadata
- Project discovery
- Git status, diff, branch, commit, and worktree awareness
- Workspace creation and cleanup
- Build and test execution through approved adapters
- Artifact tracking
- Backup and rollback
- Safe-path policies
- Dry-run mode
- User-visible change summaries

### J. Multi-agent operating system

Agent roles:

- Supervisor
- Planner
- Researcher
- Programmer
- Tester
- Debugger
- Security reviewer
- Documentation writer
- GUI operator
- System administrator
- Memory curator

Agent features:

- Discover installed agents
- Select the best agent for a task
- Spawn visible or background sessions
- Use isolated workspaces and worktrees
- Set timeouts and resource budgets
- Stream progress
- Detect waiting, failure, and completion
- Cancel jobs
- Retry or reassign jobs
- Share structured artifacts
- Run independent reviews
- Verify acceptance criteria
- Resume after restart
- Keep a durable job history
- Prevent overlapping unsafe edits

### K. Memory and personalization

- Conversation history
- Explicit facts and preferences
- User profile
- JARVIS personality and values
- Project context
- Decisions and requirements
- Open questions
- Goals and long-running tasks
- Documents and notes
- Semantic retrieval
- Obsidian synchronization
- Provenance and confidence
- Corrections and revision history
- Forget and clear controls
- Prompt-injection filtering
- Private local memory options
- Memory inspection dashboard

### L. Proactive behavior

- Reminders
- Calendar awareness
- Todo monitoring
- Agent job monitoring
- System health monitoring
- Application crash monitoring
- Build and test monitoring
- File and project change monitoring
- Scheduled routines
- Context-aware greetings
- Deadline warnings
- Meaningful-change notifications
- Quiet hours
- User-configurable autonomy
- Global pause and stop controls

### M. External services and communication

- Google Calendar, Gmail, Tasks, Drive, Docs, and Sheets
- GitHub repositories, issues, pull requests, and code analysis
- Web search and page extraction
- Future email and messaging providers
- Calendar scheduling
- Draft-before-send workflows
- Approval before external side effects
- Connector health and token management
- Per-connector permissions

### N. Security and trust

- Local-only control socket authentication
- Secret and token protection
- Capability permission scopes
- Risk classification
- Approval policies
- Protected system paths
- Agent workspace isolation
- Untrusted output handling
- Web content isolation
- Audit log
- Action explanations
- Emergency stop
- Safe mode
- Rate limiting
- Confirmation against destructive actions
- Recovery and rollback

Suggested risk levels:

| Level | Meaning | Examples |
|---|---|---|
| 0 | Read-only | Inspect screen, list windows, read system health |
| 1 | Reversible local action | Open app, change workspace, show notification |
| 2 | Local mutation | Edit files, install a plugin, change settings |
| 3 | Destructive or broad action | Delete files, kill processes, change networking |
| 4 | External side effect | Send email, publish code, create appointments |
| 5 | Critical system action | Shutdown, modify protected system configuration |

### O. User interface and shell

- Voice-first interaction
- Status indicator
- Current task and plan view
- Agent activity center
- Approval queue
- System health dashboard
- Memory browser
- Capability browser
- Event and audit timeline
- Error and recovery view
- Project workspace view
- Settings and autonomy controls
- Keyboard shortcuts
- Mobile or remote companion interface later

### P. Developer platform

- Capability manifest format
- Adapter interfaces
- Plugin SDK
- Permission declaration
- Verification declaration
- Test harness
- Mock desktop state
- Mock agent runner
- Capability simulator
- Versioned APIs
- Documentation generator
- Capability proposal workflow
- Performance tracing
- Compatibility checks

### Q. Reliability and quality

- Unit tests
- Integration tests
- GUI tests with controlled fixtures
- Voice session tests
- Agent orchestration tests
- Failure injection
- Permission tests
- Recovery tests
- State consistency checks
- Performance and latency metrics
- Resource leak detection
- Security review
- Human acceptance tests
- Daily workflow regression suite

## 3. The core JARVIS workflow

Every complex request should eventually follow this lifecycle:

```text
request
  ↓
interpret intent
  ↓
observe current state
  ↓
create plan
  ↓
classify risk
  ↓
request approval when needed
  ↓
execute actions or delegate agents
  ↓
observe again
  ↓
verify expected outcome
  ↓
record evidence
  ↓
explain result
  ↓
remember useful context
```

## 4. Example future workflows

### Coding workflow

Open the project, inspect the current branch, understand the issue, delegate implementation, run tests, ask for approval before publishing, review the diff, and summarize the result.

### Research workflow

Search the web, collect sources, compare claims, create notes, save a report, and remember the project context.

### Meeting workflow

Open the calendar event, prepare the relevant documents, arrange the desktop, enable the microphone and camera, and restore the previous workspace afterward.

### System recovery workflow

Detect a failing service, inspect logs and resources, explain likely causes, propose a repair, request approval, apply the change, and verify service health.

### Personal routine workflow

Use time, calendar, user preferences, active projects, and system state to prepare a personalized start-of-day or end-of-day routine.

## 5. Build order

The build order should be:

1. Shared state and event model
2. Capability registry and risk policy
3. Action execution and verification
4. Reliable GUI control
5. Durable task model
6. Multi-agent supervisor
7. Project and long-term memory
8. Proactive monitoring
9. Visual JARVIS shell
10. Advanced integrations and wider autonomy

The reason is simple: every later feature depends on knowing what is happening, controlling it safely, and proving what changed.

## 6. Feature status discipline

Every future idea must be placed in one of these states:

- Idea
- Researched
- Designed
- Planned
- In progress
- Implemented
- Tested
- Released
- Deferred
- Rejected

No feature should be considered complete because a command exists. It is complete only when its behavior, permissions, failure handling, verification, tests, and documentation are defined.
