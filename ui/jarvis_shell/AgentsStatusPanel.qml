import QtQuick
import Quickshell.Io

SciFiPanel {
    id: agentsPanel
    title: "AI AGENTS STATUS"
    titleColor: "#00e5ff"
    implicitWidth: 320
    implicitHeight: 204
    property string updateAgentStatus: "Scheduled"

    function updateStatusLabel(raw) {
        var status = String(raw || "scheduled")
        if (status === "awaiting_approval") return "Waiting"
        if (status === "timed_out") return "Timed out"
        if (status === "approved") return "Approved"
        if (status === "denied") return "Denied"
        return "Scheduled"
    }

    FileView {
        id: agentRegistry
        path: "/home/g0pi/.local/state/jarvis/agents.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try {
                var data = JSON.parse(text())
                var records = Array.isArray(data.agents) ? data.agents : []
                for (var i = 0; i < records.length; i++) {
                    if (records[i].id === "omarchy-update-agent") {
                        agentsPanel.updateAgentStatus = agentsPanel.updateStatusLabel(records[i].status)
                        break
                    }
                }
            } catch (e) {}
        }
    }

    Row {
        anchors.fill: parent
        spacing: 12

        // Left List: Agents
        Column {
            width: parent.width - 96
            spacing: 8
            anchors.verticalCenter: parent.verticalCenter

            // 1. Hermes
            Row {
                width: parent.width
                spacing: 8
                Text { text: "H"; color: "#38bdf8"; font.weight: Font.Black; font.pixelSize: 11; width: 14 }
                Text { text: "Hermes"; color: "#d8f6ff"; font.pixelSize: 10; font.weight: Font.DemiBold; width: 90 }
                Text { text: "Active"; color: "#00f0a8"; font.pixelSize: 9; font.weight: Font.Bold }
            }

            // 2. OpenClaw
            Row {
                width: parent.width
                spacing: 8
                Text { text: "󰮇"; color: "#38bdf8"; font.pixelSize: 11; width: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "OpenClaw"; color: "#8aa2b3"; font.pixelSize: 10; font.weight: Font.Medium; width: 90 }
                Text { text: "Idle"; color: "#4f7285"; font.pixelSize: 9 }
            }

            // 3. OpenHuman
            Row {
                width: parent.width
                spacing: 8
                Text { text: "󰙌"; color: "#38bdf8"; font.pixelSize: 11; width: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "OpenHuman"; color: "#8aa2b3"; font.pixelSize: 10; font.weight: Font.Medium; width: 90 }
                Text { text: "Idle"; color: "#4f7285"; font.pixelSize: 9 }
            }

            // 4. Codex
            Row {
                width: parent.width
                spacing: 8
                Text { text: ""; color: "#38bdf8"; font.pixelSize: 11; width: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Codex"; color: "#d8f6ff"; font.pixelSize: 10; font.weight: Font.DemiBold; width: 90 }
                Text { text: "Active"; color: "#00f0a8"; font.pixelSize: 9; font.weight: Font.Bold }
            }

            // 5. Antigravity
            Row {
                width: parent.width
                spacing: 8
                Text { text: "✦"; color: "#38bdf8"; font.pixelSize: 11; width: 14 }
                Text { text: "Antigravity"; color: "#8aa2b3"; font.pixelSize: 10; font.weight: Font.Medium; width: 90 }
                Text { text: "Idle"; color: "#4f7285"; font.pixelSize: 9 }
            }

            // 6. Update Agent
            Row {
                width: parent.width
                spacing: 8
                Text { text: "󰚰"; color: "#f59e0b"; font.pixelSize: 11; width: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Update Agent"; color: "#d8f6ff"; font.pixelSize: 10; font.weight: Font.DemiBold; width: 90 }
                Text { text: agentsPanel.updateAgentStatus; color: "#f59e0b"; font.pixelSize: 9; font.weight: Font.Bold }
            }
        }

        // Right Graphic: Detailed Holographic Iron Man Mark LXXXV Armor Blueprint
        Canvas {
            id: armorCanvas
            width: 84
            height: parent.height
            property real scanY: 0

            Timer {
                interval: 20
                repeat: true
                running: true
                onTriggered: {
                    armorCanvas.scanY = (armorCanvas.scanY + 1.4) % armorCanvas.height;
                    armorCanvas.requestPaint();
                }
            }

            onPaint: {
                var ctx = getContext("2d");
                ctx.reset();
                var cx = width / 2;

                ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.5);
                ctx.lineWidth = 1.2;

                // 1. Helmet Contour (Angular Stark Faceplate)
                ctx.beginPath();
                ctx.moveTo(cx - 7, 8);
                ctx.lineTo(cx + 7, 8);
                ctx.lineTo(cx + 9, 14);
                ctx.lineTo(cx + 8, 24);
                ctx.lineTo(cx + 4, 28);
                ctx.lineTo(cx - 4, 28);
                ctx.lineTo(cx - 8, 24);
                ctx.lineTo(cx - 9, 14);
                ctx.closePath();
                ctx.stroke();

                // Glowing Eye Slits
                ctx.fillStyle = "#ffffff";
                ctx.fillRect(cx - 6, 17, 3.5, 1.5);
                ctx.fillRect(cx + 2.5, 17, 3.5, 1.5);

                // 2. Neck & Articulated Collar
                ctx.beginPath();
                ctx.moveTo(cx - 4, 28); ctx.lineTo(cx - 5, 33);
                ctx.moveTo(cx + 4, 28); ctx.lineTo(cx + 5, 33);
                ctx.stroke();

                // 3. Shoulder Pauldrons (Layered)
                ctx.beginPath();
                ctx.moveTo(cx - 8, 33); ctx.lineTo(cx - 26, 38); ctx.lineTo(cx - 28, 48); ctx.lineTo(cx - 18, 48);
                ctx.moveTo(cx + 8, 33); ctx.lineTo(cx + 26, 38); ctx.lineTo(cx + 28, 48); ctx.lineTo(cx + 18, 48);
                ctx.stroke();

                // 4. Chest Plate Contours
                ctx.beginPath();
                ctx.moveTo(cx - 18, 38); ctx.lineTo(cx, 42); ctx.lineTo(cx + 18, 38);
                ctx.lineTo(cx + 14, 62); ctx.lineTo(cx, 66); ctx.lineTo(cx - 14, 62);
                ctx.closePath();
                ctx.stroke();

                // Chest Arc Reactor (Unibeam Core)
                ctx.fillStyle = "#ffffff";
                ctx.beginPath();
                ctx.arc(cx, 51, 3.5, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = "#00e5ff";
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.arc(cx, 51, 6.5, 0, Math.PI * 2);
                ctx.stroke();

                // 5. Abdominal Plating (Segmented bands)
                ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.4);
                ctx.lineWidth = 1.0;
                for (var b = 0; b < 3; b++) {
                    var by = 68 + b * 5;
                    ctx.beginPath();
                    ctx.moveTo(cx - 10 + b, by); ctx.lineTo(cx + 10 - b, by);
                    ctx.stroke();
                }

                // 6. Arms & Repulsor Gauntlets
                ctx.beginPath();
                ctx.moveTo(cx - 24, 48); ctx.lineTo(cx - 22, 80); ctx.lineTo(cx - 18, 80);
                ctx.moveTo(cx + 24, 48); ctx.lineTo(cx + 22, 80); ctx.lineTo(cx + 18, 80);
                ctx.stroke();

                // 7. Waist & Armored Legs
                ctx.beginPath();
                ctx.moveTo(cx - 12, 84); ctx.lineTo(cx - 11, 130); ctx.lineTo(cx - 6, 130); ctx.lineTo(cx - 6, 88);
                ctx.moveTo(cx + 12, 84); ctx.lineTo(cx + 11, 130); ctx.lineTo(cx + 6, 130); ctx.lineTo(cx + 6, 88);
                ctx.stroke();

                // Laser Scan Line Sweep
                var scanGrad = ctx.createLinearGradient(0, armorCanvas.scanY - 4, 0, armorCanvas.scanY + 4);
                scanGrad.addColorStop(0, "rgba(0, 229, 255, 0.0)");
                scanGrad.addColorStop(0.5, "rgba(0, 229, 255, 0.85)");
                scanGrad.addColorStop(1, "rgba(0, 229, 255, 0.0)");
                ctx.fillStyle = scanGrad;
                ctx.fillRect(0, armorCanvas.scanY - 3, width, 6);
            }
        }
    }
}
