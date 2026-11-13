#!/usr/bin/env bash
# JARVIS OS Shell Exit-Code & Long Command Voice Hook
# Non-blocking, <5ms startup, reports failures and >15s commands.

# Only run in interactive shells
[[ $- == *i* ]] || return 0 2>/dev/null || exit 0

__jarvis_hook_sock="/run/user/${UID:-1000}/jarvis-voice-speak.sock"
__jarvis_cmd_start=0
__jarvis_last_cmd=""
__jarvis_cmd_active=0

__jarvis_preexec() {
    # Skip inside PROMPT_COMMAND evaluation or empty commands
    if [[ "${__jarvis_cmd_active:-0}" -eq 1 ]]; then
        return
    fi
    __jarvis_cmd_active=1
    __jarvis_cmd_start=$SECONDS
    __jarvis_last_cmd="$BASH_COMMAND"
}

__jarvis_postexec() {
    local exit_code=$?
    local cmd_active=${__jarvis_cmd_active:-0}
    __jarvis_cmd_active=0

    # Only process if a user command actually ran
    if [[ "$cmd_active" -ne 1 ]]; then
        return
    fi

    local elapsed=$((SECONDS - __jarvis_cmd_start))
    local raw_cmd="${__jarvis_last_cmd:-}"
    
    # Extract only the base executable name (e.g., pytest, git, cargo)
    local base_cmd
    base_cmd=$(echo "$raw_cmd" | awk '{print $1}')
    base_cmd="${base_cmd##*/}"

    # Filter out empty or internal commands
    if [[ -z "$base_cmd" || "$base_cmd" == "__jarvis"* || "$base_cmd" == "history"* || "$base_cmd" == "clear" || "$base_cmd" == "ls" ]]; then
        return
    fi

    # Trigger condition: failed exit code (except 130 Ctrl+C) OR duration > 15s
    local should_notify=0
    local priority="normal"
    local message=""

    if [[ "$exit_code" -ne 0 && "$exit_code" -ne 130 && "$exit_code" -ne 148 ]]; then
        should_notify=1
        priority="critical"
        if [[ "$elapsed" -ge 2 ]]; then
            message="Command ${base_cmd} failed with exit code ${exit_code} after ${elapsed} seconds."
        else
            message="Command ${base_cmd} failed with exit code ${exit_code}."
        fi
    elif [[ "$elapsed" -ge 15 ]]; then
        should_notify=1
        priority="normal"
        message="Command ${base_cmd} completed after ${elapsed} seconds."
    fi

    if [[ "$should_notify" -eq 1 && -S "$__jarvis_hook_sock" ]]; then
        local payload
        payload=$(printf '{"text": "%s", "priority": "%s", "source": "terminal", "dedup_key": "shell_%s_%d"}\n' \
            "$message" "$priority" "$base_cmd" "$exit_code")

        # Completely detached non-blocking delivery (<2ms)
        (
            if command -v socat >/dev/null 2>&1; then
                printf '%s' "$payload" | socat -t 0.1 - "UNIX-CONNECT:${__jarvis_hook_sock}" >/dev/null 2>&1
            elif command -v nc >/dev/null 2>&1; then
                printf '%s' "$payload" | nc -U -w 1 "$__jarvis_hook_sock" >/dev/null 2>&1
            fi
        ) >/dev/null 2>&1 &
    fi
}

# Attach to bash DEBUG trap and PROMPT_COMMAND
trap '__jarvis_preexec' DEBUG
if [[ -z "${PROMPT_COMMAND:-}" ]]; then
    PROMPT_COMMAND="__jarvis_postexec"
elif [[ "$PROMPT_COMMAND" != *"__jarvis_postexec"* ]]; then
    PROMPT_COMMAND="__jarvis_postexec; ${PROMPT_COMMAND}"
fi
