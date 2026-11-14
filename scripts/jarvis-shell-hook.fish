# JARVIS OS Shell Exit-Code & Long Command Voice Hook for Fish Shell
# Non-blocking, <5ms startup, reports failures and >15s commands.

status is-interactive; or exit 0

set -g __jarvis_hook_sock "/run/user/"(id -u)"/jarvis-voice-speak.sock"
set -g __jarvis_cmd_start 0
set -g __jarvis_last_cmd ""
set -g __jarvis_cmd_active 0

function __jarvis_fish_preexec --on-event fish_preexec
    set -g __jarvis_cmd_active 1
    set -g __jarvis_cmd_start (date +%s)
    set -g __jarvis_last_cmd $argv[1]
end

function __jarvis_fish_postexec --on-event fish_postexec
    set -l exit_code $status
    if test "$__jarvis_cmd_active" -ne 1
        return
    end
    set -g __jarvis_cmd_active 0

    set -l now (date +%s)
    set -l elapsed (math $now - $__jarvis_cmd_start)
    set -l raw_cmd "$__jarvis_last_cmd"

    set -l base_cmd (string split ' ' -- $raw_cmd)[1]
    set base_cmd (basename -- $base_cmd)

    if test -z "$base_cmd"; or string match -q "__jarvis*" -- $base_cmd; or string match -q "history*" -- $base_cmd; or test "$base_cmd" = "clear"; or test "$base_cmd" = "ls"
        return
    end

    if test "$exit_code" -ne 0 -a "$exit_code" -ne 130 -a "$exit_code" -ne 148
        set -l message ""
        if test "$elapsed" -ge 2
            set message "Command $base_cmd failed with exit code $exit_code after $elapsed seconds."
        else
            set message "Command $base_cmd failed with exit code $exit_code."
        end
        if test -S "$__jarvis_hook_sock"
            set -l payload (printf '{"text": "%s", "priority": "critical", "source": "terminal", "dedup_key": "shell_%s_%d"}\n' "$message" "$base_cmd" "$exit_code")
            fish -c "printf '%s' '$payload' | socat -t 0.1 - 'UNIX-CONNECT:$__jarvis_hook_sock' 2>/dev/null" &>/dev/null &
        end
    else if test "$elapsed" -ge 15
        set -l message "Command $base_cmd completed after $elapsed seconds."
        if test -S "$__jarvis_hook_sock"
            set -l payload (printf '{"text": "%s", "priority": "normal", "source": "terminal", "dedup_key": "shell_%s_%d"}\n' "$message" "$base_cmd" "$exit_code")
            fish -c "printf '%s' '$payload' | socat -t 0.1 - 'UNIX-CONNECT:$__jarvis_hook_sock' 2>/dev/null" &>/dev/null &
        end
    end
end
