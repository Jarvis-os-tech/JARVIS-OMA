#!/usr/bin/env bash
# JARVIS OS Shell Exit-Code & Long Command Voice Hook
# Non-blocking, <5ms startup, reports failures and >15s commands.
# Supports bash and zsh.

# Only run in interactive shells
if [ -n "$BASH_VERSION" ]; then
    [[ $- == *i* ]] || return 0 2>/dev/null || exit 0
elif [ -n "$ZSH_VERSION" ]; then
    [[ -o interactive ]] || return 0 2>/dev/null || exit 0
fi

__jarvis_hook_sock="/run/user/${UID:-1000}/jarvis-voice-speak.sock"
__jarvis_cmd_start=0
__jarvis_last_cmd=""
__jarvis_cmd_active=0

__jarvis_dispatch_speech() {
    local message="$1"
    local priority="$2"
    local base_cmd="$3"
    local exit_code="$4"

    if [[ -S "$__jarvis_hook_sock" ]]; then
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

__jarvis_evaluate_command() {
    local exit_code=$1
    local elapsed=$2
    local raw_cmd="$3"

    # Extract only the base executable name
    local base_cmd
    base_cmd=$(echo "$raw_cmd" | awk '{print $1}')
    base_cmd="${base_cmd##*/}"

    # Filter out empty or internal commands
    if [[ -z "$base_cmd" || "$base_cmd" == "__jarvis"* || "$base_cmd" == "history"* || "$base_cmd" == "clear" || "$base_cmd" == "ls" ]]; then
        return
    fi

    # Trigger condition: failed exit code (except 130 Ctrl+C) OR duration > 15s
    if [[ "$exit_code" -ne 0 && "$exit_code" -ne 130 && "$exit_code" -ne 148 ]]; then
        local message
        if [[ "$elapsed" -ge 2 ]]; then
            message="Command ${base_cmd} failed with exit code ${exit_code} after ${elapsed} seconds."
        else
            message="Command ${base_cmd} failed with exit code ${exit_code}."
        fi
        __jarvis_dispatch_speech "$message" "critical" "$base_cmd" "$exit_code"
    elif [[ "$elapsed" -ge 15 ]]; then
        local message="Command ${base_cmd} completed after ${elapsed} seconds."
        __jarvis_dispatch_speech "$message" "normal" "$base_cmd" "$exit_code"
    fi
}

if [ -n "$ZSH_VERSION" ]; then
    autoload -Uz add-zsh-hook 2>/dev/null

    __jarvis_zsh_preexec() {
        __jarvis_cmd_start=$SECONDS
        __jarvis_last_cmd="$1"
        __jarvis_cmd_active=1
    }

    __jarvis_zsh_precmd() {
        local exit_code=$?
        local cmd_active=${__jarvis_cmd_active:-0}
        __jarvis_cmd_active=0

        if [[ "$cmd_active" -eq 1 ]]; then
            local elapsed=$((SECONDS - __jarvis_cmd_start))
            __jarvis_evaluate_command "$exit_code" "$elapsed" "${__jarvis_last_cmd:-}"
        fi
    }

    add-zsh-hook preexec __jarvis_zsh_preexec 2>/dev/null
    add-zsh-hook precmd __jarvis_zsh_precmd 2>/dev/null

elif [ -n "$BASH_VERSION" ]; then

    __jarvis_bash_preexec() {
        if [[ "${__jarvis_cmd_active:-0}" -eq 1 ]]; then
            return
        fi
        __jarvis_cmd_active=1
        __jarvis_cmd_start=$SECONDS
        __jarvis_last_cmd="$BASH_COMMAND"
    }

    __jarvis_bash_postexec() {
        local exit_code=$?
        local cmd_active=${__jarvis_cmd_active:-0}
        __jarvis_cmd_active=0

        if [[ "$cmd_active" -eq 1 ]]; then
            local elapsed=$((SECONDS - __jarvis_cmd_start))
            __jarvis_evaluate_command "$exit_code" "$elapsed" "${__jarvis_last_cmd:-}"
        fi
    }

    trap '__jarvis_bash_preexec' DEBUG
    if [[ -z "${PROMPT_COMMAND:-}" ]]; then
        PROMPT_COMMAND="__jarvis_bash_postexec"
    elif [[ "$PROMPT_COMMAND" != *"__jarvis_bash_postexec"* ]]; then
        PROMPT_COMMAND="__jarvis_bash_postexec; ${PROMPT_COMMAND}"
    fi
fi
