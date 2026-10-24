import QtQuick

// Aura Field concept adapted for JARVIS from amunozdev/voiceorbs (MIT).
// Native Quickshell Canvas implementation; no React or WebGL dependency.
Item {
    id: root

    property string orbitState: "idle"
    property real level: 0.0
    property real speed: 1.0
    property bool reducedMotion: false

    implicitWidth: 96
    implicitHeight: 96

    readonly property color colorA: {
        if (orbitState === "speaking") return "#ff4da6"
        if (orbitState === "thinking") return "#a855f7"
        if (orbitState === "connecting") return "#818cf8"
        if (orbitState === "standby" || orbitState === "disabled") return "#64748b"
        if (orbitState === "error" || orbitState === "offline") return "#fb7185"
        return "#21d4fd"
    }
    readonly property color colorB: {
        if (orbitState === "speaking") return "#ffb86b"
        if (orbitState === "thinking") return "#22d3ee"
        if (orbitState === "connecting") return "#38bdf8"
        if (orbitState === "standby" || orbitState === "disabled") return "#334155"
        if (orbitState === "error" || orbitState === "offline") return "#ef4444"
        return "#34d399"
    }

    Canvas {
        id: field
        anchors.fill: parent
        property real clock: 0
        property real energy: 0
        property real lastTick: 0

        Timer {
            interval: root.reducedMotion ? 80 : 16
            repeat: true
            running: root.visible
            onTriggered: {
                var now = Date.now() / 1000
                if (field.lastTick === 0) field.lastTick = now
                var dt = Math.min(0.1, now - field.lastTick)
                field.lastTick = now
                var stateRate = root.orbitState === "standby" || root.orbitState === "disabled" ? 0.22
                              : root.orbitState === "thinking" ? 1.25
                              : root.orbitState === "speaking" ? 1.55
                              : root.orbitState === "listening" ? 1.0 : 0.5
                field.clock += dt * root.speed * stateRate

                var procedural = 0.05
                if (root.orbitState === "listening")
                    procedural = 0.22 + 0.16 * (0.5 + 0.5 * Math.sin(field.clock * 7.1))
                else if (root.orbitState === "speaking")
                    procedural = 0.34 + 0.28 * (0.5 + 0.5 * Math.sin(field.clock * 10.4))
                else if (root.orbitState === "thinking")
                    procedural = 0.20 + 0.12 * (0.5 + 0.5 * Math.sin(field.clock * 4.2))
                else if (root.orbitState === "connecting")
                    procedural = 0.14
                else if (root.orbitState === "standby" || root.orbitState === "disabled")
                    procedural = 0.015
                else if (root.orbitState === "error" || root.orbitState === "offline")
                    procedural = 0.08 + 0.08 * (0.5 + 0.5 * Math.sin(field.clock * 2.2))

                var target = Math.max(root.level, procedural)
                field.energy += (target - field.energy) * (1 - Math.exp(-10 * dt))
                field.requestPaint()
            }
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var cx = width / 2
            var cy = height / 2
            var size = Math.min(width, height)
            if (size <= 0) return

            function rgb(color) {
                var h = color.toString().replace("#", "")
                var n = parseInt(h, 16)
                return {r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255}
            }
            function rgba(c, a) { return "rgba(" + c.r + "," + c.g + "," + c.b + "," + a + ")" }

            var a = rgb(root.colorA)
            var b = rgb(root.colorB)
            var e = field.energy
            var t = field.clock
            var standby = root.orbitState === "standby" || root.orbitState === "disabled"
            var base = size * (standby ? 0.25 : 0.30)
            var open = root.orbitState === "listening" ? size * 0.055 : 0
            var radius = base + open + size * 0.055 * e

            var glow = ctx.createRadialGradient(cx, cy, radius * 0.35, cx, cy, radius * 1.65)
            glow.addColorStop(0, rgba(a, standby ? 0.08 : 0.28 + e * 0.12))
            glow.addColorStop(0.48, rgba(b, standby ? 0.06 : 0.18 + e * 0.16))
            glow.addColorStop(1, "rgba(0,0,0,0)")
            ctx.fillStyle = glow
            ctx.beginPath()
            ctx.arc(cx, cy, radius * 1.65, 0, Math.PI * 2)
            ctx.fill()

            ctx.lineCap = "round"
            var points = 112
            for (var layer = 0; layer < 3; layer++) {
                ctx.beginPath()
                for (var i = 0; i <= points; i++) {
                    var angle = i / points * Math.PI * 2
                    var wave = Math.sin(angle * 3 + t * 2.4 + layer * 1.7)
                             + 0.48 * Math.sin(angle * 7 - t * 1.8 + layer)
                    var ripple = wave * size * (0.006 + e * 0.025)
                    var rr = radius + ripple + (layer - 1) * size * 0.018
                    var x = cx + Math.cos(angle) * rr
                    var y = cy + Math.sin(angle) * rr
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                }
                var mix = layer / 2
                var c = {
                    r: Math.round(a.r * (1 - mix) + b.r * mix),
                    g: Math.round(a.g * (1 - mix) + b.g * mix),
                    b: Math.round(a.b * (1 - mix) + b.b * mix)
                }
                ctx.strokeStyle = rgba(c, standby ? 0.22 : 0.42 + e * 0.42)
                ctx.lineWidth = Math.max(1, size * (0.012 + e * 0.015))
                ctx.stroke()
            }

            var core = ctx.createRadialGradient(cx - radius * 0.18, cy - radius * 0.2,
                                                0, cx, cy, radius * 0.58)
            core.addColorStop(0, standby ? "rgba(203,213,225,0.32)" : "rgba(255,255,255,0.92)")
            core.addColorStop(0.28, rgba(a, standby ? 0.30 : 0.82))
            core.addColorStop(1, rgba(b, standby ? 0.10 : 0.28))
            ctx.fillStyle = core
            ctx.beginPath()
            ctx.arc(cx, cy, radius * (0.28 + e * 0.04), 0, Math.PI * 2)
            ctx.fill()
        }
    }
}
