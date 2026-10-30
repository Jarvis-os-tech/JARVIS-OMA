-- Keep only your personal keybinding overrides here. Add new bindings or
-- unbind defaults before replacing them.

-- See current bindings and descriptions:
--   omarchy menu keybindings --print

-- To disable every Omarchy default binding, set this in
-- ~/.config/hypr/hyprland.lua before require("default.hypr.omarchy"), then add
-- only the bindings you want below:
--   omarchy_default_bindings = false

-- To disable all preinstalled app/webapp bindings, set:
--   omarchy_preinstalled_bindings = false

-- Add a new binding.
-- o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")

-- Change an existing binding by unbinding it first, then binding the key again.
-- This example changes SUPER+SPACE from the launcher to the Omarchy root menu.
-- hl.unbind("SUPER + SPACE")
-- o.bind("SUPER + SPACE", "Omarchy menu", "omarchy-menu toggle root")

-- Disable a default binding without replacing it.
-- hl.unbind("SUPER + SHIFT + B")

-- Logitech MX Keys examples:
-- o.bind("SUPER + SHIFT + S", nil, "omarchy-capture-screenshot")
-- o.bind("SUPER + H", nil, "voxtype record toggle")
-- o.bind("SUPER + PERIOD", nil, "omarchy-shell shell toggle omarchy.emojis")

-- linux-voice / omarchy-dictate: Fast Groq Whisper & Gemini voice dictation
if o.cmd_present("linux-voice") or o.cmd_present("omarchy-dictate") then
  o.bind("SUPER + H", "Voice dictation", "linux-voice toggle")
end

-- JARVIS Voice OS controls
if o.cmd_present("jarvisctl") then
-- JARVIS disconnected 2026-10-30:   o.bind("SUPER + SHIFT + J", "JARVIS Voice", "jarvisctl toggle")  -- Toggle JARVIS listen/mute
-- JARVIS disconnected 2026-10-30:   o.bind("SUPER + CTRL + J", "JARVIS Config", "alacritty -e jarvisctl status")  -- Debug/Status
end

-- Keybindings menu (prioritizes JARVIS Voice & Config at the top)
hl.unbind("SUPER + K")
o.bind("SUPER + K", "Keybindings", os.getenv("HOME") .. "/.local/bin/omarchy-menu-keybindings")

-- Voice control: legacy bindings cleaned
hl.unbind("SUPER + SHIFT + V")
hl.unbind("SUPER + GRAVE")
hl.unbind("SUPER + SHIFT + GRAVE")

-- Spotlight Apps panel (io.github.jeocrypto.launchpad)
o.bind("SUPER + A", "Spotlight Apps", "omarchy-shell shell toggle io.github.jeocrypto.launchpad")

o.bind("CTRL + W", "Launch browser", "omarchy launch browser")

-- Voice Buddy Desktop Overlay
o.bind("SUPER + V", "Voice Buddy Desktop", "~/.local/bin/voice-buddy-desktop")

-- hermes-companion
o.bind("SUPER + ALT + H", "Hermes: listen", "/home/g0pi/.hermes/hermes-agent/venv/bin/python /home/g0pi/.config/omarchy/plugins/hermes.companion/daemon/companion.py --ctl listen")
o.bind("SUPER + ALT + E", "Hermes: toggle eyes", "/home/g0pi/.hermes/hermes-agent/venv/bin/python /home/g0pi/.config/omarchy/plugins/hermes.companion/daemon/companion.py --ctl toggle-eyes")
o.bind("SUPER + ALT + S", "Hermes: hush", "/home/g0pi/.hermes/hermes-agent/venv/bin/python /home/g0pi/.config/omarchy/plugins/hermes.companion/daemon/companion.py --ctl hush")

-- BEGIN omarchy-dynamic-island
-- Added by the omarchy-dynamic-island plugin and removed with it. Change the key
-- with "keybind" in its entry in ~/.config/omarchy/shell.json.
o.bind("SUPER + ALT + I", "Toggle island reserved space", "omarchy-shell dynamic-island reserveSpace toggle")
-- END omarchy-dynamic-island
