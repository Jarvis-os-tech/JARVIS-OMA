.pragma library

// Small, deterministic adapters between daemon/system data and presentation.
function number(value, fallback) {
  return typeof value === "number" && isFinite(value) ? value : fallback
}

function state(raw, muted, standby) {
  if (raw === "offline" || raw === "connecting" || raw === "error") return raw
  if (muted) return "muted"
  if (standby || raw === "standby") return "standby"
  if (raw === "ducked" || raw === "barged_in") return "listening"
  return ["idle", "listening", "speaking", "thinking", "processing"].indexOf(raw) >= 0 ? raw : "idle"
}

function label(value) {
  var labels = { offline: "Offline", connecting: "Connecting", error: "Needs attention",
    muted: "Mic muted", standby: "Local standby", idle: "Ready", listening: "Listening",
    speaking: "Speaking", thinking: "Thinking", processing: "Working" }
  return labels[value] || "Ready"
}

function tone(value) {
  if (value === "muted" || value === "standby" || value === "connecting") return "#f0ba73"
  if (value === "speaking") return "#78e8ba"
  if (value === "thinking" || value === "processing") return "#b7a2ff"
  if (value === "error") return "#fa8e9d"
  if (value === "offline") return "#8b99ae"
  return "#73e0ed"
}

function audioLevel(rms, available, muted) {
  if (!available || muted) return 0
  return Math.min(1, Math.sqrt(Math.max(0, number(rms, 0))) * 4)
}

function cpuSample(text) {
  var parts = String(text || "").split("\n")[0].trim().split(/\s+/)
  if (parts.shift() !== "cpu" || parts.length < 4) return null
  // Guest ticks are already included in user/nice; don't double-count them.
  var ticks = parts.slice(0, 8).map(Number)
  if (ticks.some(function(v) { return !isFinite(v) || v < 0 })) return null
  return { total: ticks.reduce(function(a, b) { return a + b }, 0), idle: ticks[3] + (ticks[4] || 0) }
}

function cpuUsage(previous, current) {
  if (!previous || !current || current.total <= previous.total || current.idle < previous.idle) return -1
  return Math.max(0, Math.min(1, 1 - (current.idle - previous.idle) / (current.total - previous.total)))
}

function memoryUsage(text) {
  var total = /^MemTotal:\s+(\d+)/m.exec(text || "")
  var available = /^MemAvailable:\s+(\d+)/m.exec(text || "")
  if (!total || !available || Number(total[1]) <= 0) return -1
  return Math.max(0, Math.min(1, 1 - Number(available[1]) / Number(total[1])))
}
