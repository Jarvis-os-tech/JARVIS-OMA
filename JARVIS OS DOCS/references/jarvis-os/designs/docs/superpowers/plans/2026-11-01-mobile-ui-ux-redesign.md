# JARVIS Mobile UI/UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the JARVIS Mobile Android client from a single-column test harness into a cybernetic, futuristic AI companion with a 3-tab Bottom Navigation architecture, an animated Arc Reactor voice core, a Devices & Permissions matrix, and a Settings Vault.

**Architecture:** Split the monolithic 524-line `MainActivity.kt` into modular Jetpack Compose screens and components (`AssistantScreen`, `DevicesScreen`, `SettingsScreen`, `CyberBottomNav`, `TopTelemetryBar`, `ArcReactorVisualizer`), bound together by a unified `CyberTheme` palette and shared reactive state from `SharedPreferences` and Android services.

**Tech Stack:** Kotlin, Jetpack Compose (Material 3), AndroidX Lifecycle & Coroutines, Android Canvas Animation APIs.

**Spec:** `docs/superpowers/specs/2026-11-01-mobile-ui-ux-design.md`

## Global Constraints
- Target SDK: Android 34 / Min SDK: 26.
- Strictly preserve existing `JarvisVoiceService` lifecycle, intent actions (`com.jarvis.os.action.START`, `STOP`, `SYNC_MEMORY`), and AEC audio pipeline.
- Maintain backward compatibility with `QrPairingScanner` and `ApiCredentials`.
- Zero raw `while(true)` loops or continuous CPU-polling animations when app is backgrounded.

---

### Task 1: Cybernetic Obsidian Theme & Design Tokens

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/ui/theme/Color.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/ui/theme/Theme.kt`

**Interfaces:**
- Produces: Color constants `ObsidianDark`, `CyberSurface`, `CyberBorder`, `ElectricCyan`, `ArcBlue`, `NeuralViolet`, `MatrixGreen`, `StandbyAmber`, `CyberError`, `TextWhite`, `TextMuted`, `TextCyan` and the `@Composable fun JarvisCyberTheme(content: @Composable () -> Unit)` wrapper.

- [ ] **Step 1: Create `Color.kt` with cybernetic palette tokens**

Create `mobile/app/src/main/java/com/jarvis/os/ui/theme/Color.kt`:
```kotlin
package com.jarvis.os.ui.theme

import androidx.compose.ui.graphics.Color

val ObsidianDark = Color(0xFF080A0F)
val CyberSurface = Color(0xFF111520)
val CyberSurfaceElevated = Color(0xFF161C2C)
val CyberBorder = Color(0xFF1F283C)
val CyberBorderGlow = Color(0x3300F2FE)

val ElectricCyan = Color(0xFF00F2FE)
val ArcBlue = Color(0xFF0077FE)
val NeuralViolet = Color(0xFF9B51E0)
val MatrixGreen = Color(0xFF00E676)
val StandbyAmber = Color(0xFFFFB300)
val CyberError = Color(0xFFFF5252)

val TextWhite = Color(0xFFFFFFFF)
val TextMuted = Color(0xFF8E9BAE)
val TextCyan = Color(0xFF7EE7F8)
```

- [ ] **Step 2: Create `Theme.kt` with Material3 dark color scheme mapping**

Create `mobile/app/src/main/java/com/jarvis/os/ui/theme/Theme.kt`:
```kotlin
package com.jarvis.os.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val CyberColorScheme = darkColorScheme(
    primary = ElectricCyan,
    onPrimary = ObsidianDark,
    secondary = ArcBlue,
    onSecondary = TextWhite,
    tertiary = NeuralViolet,
    background = ObsidianDark,
    surface = CyberSurface,
    onSurface = TextWhite,
    error = CyberError,
    onError = TextWhite
)

@Composable
fun JarvisCyberTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = CyberColorScheme,
        content = content
    )
}
```

- [ ] **Step 3: Verify compilation**

Run: `cd mobile && ./gradlew compileDebugKotlin`  
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 4: Commit**

```bash
git add mobile/app/src/main/java/com/jarvis/os/ui/theme/
git commit -m "feat(ui): add cybernetic obsidian theme and color tokens"
```

---

### Task 2: Reusable Top Telemetry Bar & Cybernetic Bottom Navigation Dock

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/ui/components/TopTelemetryBar.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/ui/components/CyberBottomNav.kt`

**Interfaces:**
- Consumes: `ObsidianDark`, `CyberSurface`, `ElectricCyan`, `MatrixGreen`, `StandbyAmber`, `TextWhite`, `TextMuted`.
- Produces:
  - `@Composable fun TopTelemetryBar(standbyActive: Boolean, appVersion: String = "v1.2.3")`
  - `@Composable fun CyberBottomNav(selectedTab: Int, onTabSelected: (Int) -> Unit)`

- [ ] **Step 1: Create `TopTelemetryBar.kt`**

Create `mobile/app/src/main/java/com/jarvis/os/ui/components/TopTelemetryBar.kt`:
```kotlin
package com.jarvis.os.ui.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.os.ui.theme.CyberBorder
import com.jarvis.os.ui.theme.CyberSurface
import com.jarvis.os.ui.theme.ElectricCyan
import com.jarvis.os.ui.theme.MatrixGreen
import com.jarvis.os.ui.theme.StandbyAmber
import com.jarvis.os.ui.theme.TextMuted
import com.jarvis.os.ui.theme.TextWhite

@Composable
fun TopTelemetryBar(
    standbyActive: Boolean,
    appVersion: String = "v1.2.3",
    modifier: Modifier = Modifier
) {
    val pulseTransition = rememberInfiniteTransition(label = "StatusPulse")
    val pulseAlpha by pulseTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "Alpha"
    )

    Row(
        modifier = modifier
            .fillMaxWidth()
            .height(56.dp)
            .padding(horizontal = 20.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = "JARVIS",
                fontSize = 18.sp,
                fontWeight = FontWeight.Black,
                color = TextWhite,
                letterSpacing = 2.sp
            )
            Spacer(modifier = Modifier.width(6.dp))
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .background(Color(0x3300F2FE))
                    .padding(horizontal = 6.dp, vertical = 2.dp)
            ) {
                Text(
                    text = appVersion,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    color = ElectricCyan
                )
            }
        }

        // Status Pill
        Row(
            modifier = Modifier
                .clip(RoundedCornerShape(20.dp))
                .background(CyberSurface)
                .border(1.dp, CyberBorder, RoundedCornerShape(20.dp))
                .padding(horizontal = 10.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(
                        if (standbyActive) MatrixGreen.copy(alpha = pulseAlpha)
                        else StandbyAmber
                    )
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = if (standbyActive) "STANDBY ACTIVE" else "PAUSED",
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = if (standbyActive) MatrixGreen else TextMuted,
                letterSpacing = 0.5.sp
            )
        }
    }
}
```

- [ ] **Step 2: Create `CyberBottomNav.kt`**

Create `mobile/app/src/main/java/com/jarvis/os/ui/components/CyberBottomNav.kt`:
```kotlin
package com.jarvis.os.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.os.ui.theme.CyberBorder
import com.jarvis.os.ui.theme.CyberSurfaceElevated
import com.jarvis.os.ui.theme.ElectricCyan
import com.jarvis.os.ui.theme.TextMuted

data class NavItem(val title: String, val icon: String)

@Composable
fun CyberBottomNav(
    selectedTab: Int,
    onTabSelected: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    val items = listOf(
        NavItem("Assistant", "🎙️"),
        NavItem("Devices", "💻"),
        NavItem("Settings", "⚙️")
    )

    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp, vertical = 12.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(64.dp)
                .clip(RoundedCornerShape(32.dp))
                .background(Color(0xF0111520))
                .border(1.dp, CyberBorder, RoundedCornerShape(32.dp))
                .padding(horizontal = 8.dp),
            horizontalArrangement = Arrangement.SpaceAround,
            verticalAlignment = Alignment.CenterVertically
        ) {
            items.forEachIndexed { index, item ->
                val isSelected = selectedTab == index
                val textColor by animateColorAsState(
                    targetValue = if (isSelected) ElectricCyan else TextMuted,
                    animationSpec = tween(200),
                    label = "NavTextColor"
                )
                val bgModifier = if (isSelected) {
                    Modifier
                        .clip(RoundedCornerShape(24.dp))
                        .background(CyberSurfaceElevated)
                        .border(1.dp, Color(0x3300F2FE), RoundedCornerShape(24.dp))
                } else {
                    Modifier
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp)
                        .then(bgModifier)
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null
                        ) { onTabSelected(index) },
                    contentAlignment = Alignment.Center
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        Text(
                            text = item.icon,
                            fontSize = 16.sp
                        )
                        if (isSelected) {
                            Text(
                                text = " " + item.title,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = textColor
                            )
                        }
                    }
                }
            }
        }
    }
}
```

- [ ] **Step 3: Verify compilation**

Run: `cd mobile && ./gradlew compileDebugKotlin`  
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 4: Commit**

```bash
git add mobile/app/src/main/java/com/jarvis/os/ui/components/TopTelemetryBar.kt mobile/app/src/main/java/com/jarvis/os/ui/components/CyberBottomNav.kt
git commit -m "feat(ui): add TopTelemetryBar and CyberBottomNav components"
```

---

### Task 3: Living Arc Reactor Voice Visualizer

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/ui/components/ArcReactorVisualizer.kt`

**Interfaces:**
- Consumes: `OverlayUiState` from `com.jarvis.os.overlay.OverlayState`.
- Produces:
  - `@Composable fun ArcReactorVisualizer(state: OverlayUiState, modifier: Modifier = Modifier, size: Dp = 220.dp, onClick: (() -> Unit)? = null)`

- [ ] **Step 1: Implement `ArcReactorVisualizer.kt` with multi-ring animation**

Create `mobile/app/src/main/java/com/jarvis/os/ui/components/ArcReactorVisualizer.kt`:
```kotlin
package com.jarvis.os.ui.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.jarvis.os.overlay.OverlayUiState
import kotlin.math.cos
import kotlin.math.sin

@Composable
fun ArcReactorVisualizer(
    state: OverlayUiState,
    modifier: Modifier = Modifier,
    size: Dp = 220.dp,
    onClick: (() -> Unit)? = null
) {
    val infiniteTransition = rememberInfiniteTransition(label = "ReactorTransition")

    val outerRotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(10000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "OuterRingRotation"
    )

    val innerRotation by infiniteTransition.animateFloat(
        initialValue = 360f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(6000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "InnerRingRotation"
    )

    val breathingScale by infiniteTransition.animateFloat(
        initialValue = 0.94f,
        targetValue = 1.06f,
        animationSpec = infiniteRepeatable(
            animation = tween(2200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "BreathingScale"
    )

    val reactiveScale = when (state) {
        is OverlayUiState.Listening -> (1.0f + (state.rms / 6000f).coerceIn(0f, 0.5f)) * breathingScale
        is OverlayUiState.Speaking -> (1.0f + (state.amplitude / 6000f).coerceIn(0f, 0.4f)) * breathingScale
        is OverlayUiState.Thinking -> breathingScale * 1.1f
        OverlayUiState.Idle -> breathingScale
    }

    val clickableModifier = if (onClick != null) {
        Modifier.clickable(
            interactionSource = remember { MutableInteractionSource() },
            indication = null,
            onClick = onClick
        )
    } else Modifier

    Box(
        modifier = modifier
            .size(size)
            .then(clickableModifier),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.size(size)) {
            val center = Offset(this.size.width / 2f, this.size.height / 2f)
            val baseRadius = (this.size.minDimension / 2f) * 0.72f * reactiveScale

            // 1. Outer ambient bloom glow
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        Color(0xFF00F2FE).copy(alpha = 0.35f),
                        Color(0xFF0077FE).copy(alpha = 0.18f),
                        Color(0xFF9B51E0).copy(alpha = 0.05f),
                        Color.Transparent
                    ),
                    center = center,
                    radius = baseRadius * 1.55f
                ),
                radius = baseRadius * 1.55f,
                center = center
            )

            // 2. Telemetry tick mark outer orbit
            rotate(outerRotation, pivot = center) {
                drawCircle(
                    color = Color(0xFF00F2FE).copy(alpha = 0.4f),
                    radius = baseRadius * 1.15f,
                    center = center,
                    style = Stroke(
                        width = 2.dp.toPx(),
                        pathEffect = PathEffect.dashPathEffect(floatArrayOf(14f, 18f), 0f)
                    )
                )
            }

            // 3. Counter-rotating segmented telemetry ring
            rotate(innerRotation, pivot = center) {
                drawCircle(
                    color = Color(0xFF0077FE).copy(alpha = 0.6f),
                    radius = baseRadius * 0.95f,
                    center = center,
                    style = Stroke(
                        width = 3.dp.toPx(),
                        pathEffect = PathEffect.dashPathEffect(floatArrayOf(30f, 20f), 0f)
                    )
                )
            }

            // 4. Solid metallic confinement ring
            drawCircle(
                color = Color(0xFF1F283C),
                radius = baseRadius * 0.75f,
                center = center,
                style = Stroke(width = 4.dp.toPx())
            )
            drawCircle(
                color = Color(0xFF00F2FE),
                radius = baseRadius * 0.75f,
                center = center,
                style = Stroke(width = 1.dp.toPx())
            )

            // 5. Arc core gradient sphere
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        Color(0xFFFFFFFF),
                        Color(0xFF7EE7F8),
                        Color(0xFF00F2FE),
                        Color(0xFF0052CC)
                    ),
                    center = center,
                    radius = baseRadius * 0.60f
                ),
                radius = baseRadius * 0.60f,
                center = center
            )

            // 6. Arc core radiator spokes (10 nodes)
            val spokes = 10
            for (i in 0 until spokes) {
                val angle = Math.toRadians((i * (360.0 / spokes) + innerRotation).toDouble())
                val start = Offset(
                    center.x + (cos(angle) * (baseRadius * 0.28f)).toFloat(),
                    center.y + (sin(angle) * (baseRadius * 0.28f)).toFloat()
                )
                val end = Offset(
                    center.x + (cos(angle) * (baseRadius * 0.72f)).toFloat(),
                    center.y + (sin(angle) * (baseRadius * 0.72f)).toFloat()
                )
                drawLine(
                    color = Color(0xFF080A0F),
                    start = start,
                    end = end,
                    strokeWidth = 3.dp.toPx()
                )
            }

            // 7. Core nucleus
            drawCircle(
                color = Color(0xFFFFFFFF),
                radius = baseRadius * 0.22f,
                center = center
            )
        }
    }
}
```

- [ ] **Step 2: Verify compilation**

Run: `cd mobile && ./gradlew compileDebugKotlin`  
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 3: Commit**

```bash
git add mobile/app/src/main/java/com/jarvis/os/ui/components/ArcReactorVisualizer.kt
git commit -m "feat(ui): implement ArcReactorVisualizer component"
```

---

### Task 4: Assistant (Voice Core) Screen

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/ui/screens/AssistantScreen.kt`

**Interfaces:**
- Consumes: `ArcReactorVisualizer`, `OverlayUiState`, `voiceStatus`, `executionStatus`, `standbyActive`, `hasVoiceKey`.
- Produces:
  - `@Composable fun AssistantScreen(standbyActive: Boolean, voiceStatus: String, executionStatus: String, hasVoiceKey: Boolean, onToggleStandby: () -> Unit, onOpenSetup: () -> Unit, onTalkTapped: () -> Unit)`

- [ ] **Step 1: Implement `AssistantScreen.kt`**

Create `mobile/app/src/main/java/com/jarvis/os/ui/screens/AssistantScreen.kt`:
```kotlin
package com.jarvis.os.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.os.overlay.OverlayUiState
import com.jarvis.os.ui.components.ArcReactorVisualizer
import com.jarvis.os.ui.theme.CyberBorder
import com.jarvis.os.ui.theme.CyberSurface
import com.jarvis.os.ui.theme.ElectricCyan
import com.jarvis.os.ui.theme.MatrixGreen
import com.jarvis.os.ui.theme.ObsidianDark
import com.jarvis.os.ui.theme.StandbyAmber
import com.jarvis.os.ui.theme.TextMuted
import com.jarvis.os.ui.theme.TextWhite

@Composable
fun AssistantScreen(
    standbyActive: Boolean,
    voiceStatus: String,
    executionStatus: String,
    hasVoiceKey: Boolean,
    onToggleStandby: () -> Unit,
    onOpenSetup: () -> Unit,
    onTalkTapped: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.fillMaxWidth()
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            // Subtitle Guidance
            Text(
                text = if (standbyActive) "Listening for “Hey Jarvis”" else "Voice Standby is Paused",
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium,
                color = if (standbyActive) ElectricCyan else TextMuted,
                letterSpacing = 0.5.sp
            )

            Spacer(modifier = Modifier.height(28.dp))

            // Living Arc Reactor
            ArcReactorVisualizer(
                state = OverlayUiState.Idle,
                size = 230.dp,
                onClick = onTalkTapped
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Status Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(containerColor = CyberSurface),
                border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
            ) {
                Column(
                    modifier = Modifier.padding(18.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = if (voiceStatus.isNotBlank()) voiceStatus else "Ready · Say “Hey Jarvis” to start",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = TextWhite,
                        textAlign = TextAlign.Center
                    )

                    Spacer(modifier = Modifier.height(10.dp))

                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(12.dp))
                            .background(Color(0x2200F2FE))
                            .padding(horizontal = 12.dp, vertical = 6.dp)
                    ) {
                        Text(
                            text = executionStatus.ifBlank { "Phone · Connect PC to share execution" },
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium,
                            color = ElectricCyan,
                            textAlign = TextAlign.Center
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Text(
                        text = "Say “on my phone” or “on my PC” to choose where an action executes.",
                        fontSize = 11.sp,
                        color = TextMuted,
                        textAlign = TextAlign.Center
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Action Controls (Bottom Dock)
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            if (!hasVoiceKey) {
                Button(
                    onClick = onOpenSetup,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = StandbyAmber)
                ) {
                    Text(
                        text = "CONFIGURE GEMINI API KEY",
                        color = ObsidianDark,
                        fontWeight = FontWeight.Bold,
                        fontSize = 13.sp
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))
            } else {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Button(
                        onClick = onToggleStandby,
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (standbyActive) CyberSurface else ElectricCyan
                        ),
                        border = if (standbyActive) androidx.compose.foundation.BorderStroke(1.dp, CyberBorder) else null
                    ) {
                        Text(
                            text = if (standbyActive) "PAUSE STANDBY" else "ENABLE HEY JARVIS",
                            color = if (standbyActive) TextWhite else ObsidianDark,
                            fontWeight = FontWeight.Bold,
                            fontSize = 13.sp
                        )
                    }

                    Button(
                        onClick = onTalkTapped,
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0077FE))
                    ) {
                        Text(
                            text = "🎙️ TAP TO TALK",
                            color = TextWhite,
                            fontWeight = FontWeight.Bold,
                            fontSize = 13.sp
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}
```

- [ ] **Step 2: Verify compilation**

Run: `cd mobile && ./gradlew compileDebugKotlin`  
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 3: Commit**

```bash
git add mobile/app/src/main/java/com/jarvis/os/ui/screens/AssistantScreen.kt
git commit -m "feat(ui): implement AssistantScreen composable"
```

---

### Task 5: Devices & Actions Screen

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/ui/screens/DevicesScreen.kt`

**Interfaces:**
- Consumes: `isPaired`, `pairingInfo`, `overlayGranted`, `hasVoiceKey`, onScanPc, onManualPair, onSyncMemory, onOpenOverlay, onOpenAccessibility, onOpenBrightness.
- Produces:
  - `@Composable fun DevicesScreen(context: Context, isPaired: Boolean, pairingInfo: PairingPayload?, overlayGranted: Boolean, onScanPc: () -> Unit, onManualPair: () -> Unit, onSyncMemory: () -> Unit, onOpenOverlay: () -> Unit, onOpenAccessibility: () -> Unit, onOpenBrightness: () -> Unit)`

- [ ] **Step 1: Implement `DevicesScreen.kt`**

Create `mobile/app/src/main/java/com/jarvis/os/ui/screens/DevicesScreen.kt`:
```kotlin
package com.jarvis.os.ui.screens

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.os.sync.PairingPayload
import com.jarvis.os.ui.theme.CyberBorder
import com.jarvis.os.ui.theme.CyberSurface
import com.jarvis.os.ui.theme.ElectricCyan
import com.jarvis.os.ui.theme.MatrixGreen
import com.jarvis.os.ui.theme.ObsidianDark
import com.jarvis.os.ui.theme.StandbyAmber
import com.jarvis.os.ui.theme.TextMuted
import com.jarvis.os.ui.theme.TextWhite

@Composable
fun DevicesScreen(
    context: Context,
    isPaired: Boolean,
    pairingInfo: PairingPayload?,
    overlayGranted: Boolean,
    onScanPc: () -> Unit,
    onManualPair: () -> Unit,
    onSyncMemory: () -> Unit,
    onOpenOverlay: () -> Unit,
    onOpenAccessibility: () -> Unit,
    onOpenBrightness: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Spacer(modifier = Modifier.height(12.dp))

        // SECTION 1: DESKTOP PC LINK MATRIX
        Text(
            text = "DESKTOP PC LINK MATRIX",
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            color = ElectricCyan,
            letterSpacing = 1.sp
        )
        Spacer(modifier = Modifier.height(8.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(containerColor = CyberSurface),
            border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
        ) {
            Column(modifier = Modifier.padding(18.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = if (isPaired) (pairingInfo?.deviceId ?: "JARVIS Desktop") else "No Desktop Paired",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = TextWhite
                        )
                        Text(
                            text = if (isPaired) "Shared execution active" else "Connect PC to run commands remotely",
                            fontSize = 12.sp,
                            color = TextMuted
                        )
                    }

                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(if (isPaired) MatrixGreen else StandbyAmber)
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Button(
                        onClick = onScanPc,
                        modifier = Modifier
                            .weight(1f)
                            .height(44.dp),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan)
                    ) {
                        Text(
                            text = if (isPaired) "Re-Scan QR" else "Scan PC QR",
                            color = ObsidianDark,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp
                        )
                    }

                    OutlinedButton(
                        onClick = onManualPair,
                        modifier = Modifier
                            .weight(1f)
                            .height(44.dp),
                        shape = RoundedCornerShape(10.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
                    ) {
                        Text(text = "Paste JSON", color = TextWhite, fontSize = 12.sp)
                    }
                }

                if (isPaired) {
                    Spacer(modifier = Modifier.height(10.dp))
                    OutlinedButton(
                        onClick = onSyncMemory,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(42.dp),
                        shape = RoundedCornerShape(10.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x3300F2FE))
                    ) {
                        Text(text = "⚡ Sync Cloud Memory Now", color = ElectricCyan, fontSize = 12.sp)
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // SECTION 2: SYSTEM PERMISSIONS & CONTROLS
        Text(
            text = "SYSTEM PERMISSIONS & CONTROLS",
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            color = ElectricCyan,
            letterSpacing = 1.sp
        )
        Spacer(modifier = Modifier.height(8.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(containerColor = CyberSurface),
            border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
        ) {
            Column(modifier = Modifier.padding(18.dp)) {
                PermissionItem(
                    title = "Floating Siri HUD Overlay",
                    subtitle = "Draw glowing orb & dynamic island over apps",
                    isGranted = overlayGranted,
                    actionLabel = if (overlayGranted) "Active" else "Grant",
                    onClick = onOpenOverlay
                )

                Spacer(modifier = Modifier.height(14.dp))

                PermissionItem(
                    title = "Voice App Navigation",
                    subtitle = "Accessibility service to automate app taps",
                    isGranted = false,
                    actionLabel = "Open Settings",
                    onClick = onOpenAccessibility
                )

                Spacer(modifier = Modifier.height(14.dp))

                PermissionItem(
                    title = "System Brightness Control",
                    subtitle = "Modify display brightness via voice commands",
                    isGranted = false,
                    actionLabel = "Configure",
                    onClick = onOpenBrightness
                )
            }
        }

        Spacer(modifier = Modifier.height(24.dp))
    }
}

@Composable
private fun PermissionItem(
    title: String,
    subtitle: String,
    isGranted: Boolean,
    actionLabel: String,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(text = title, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = TextWhite)
            Text(text = subtitle, fontSize = 11.sp, color = TextMuted)
        }
        Spacer(modifier = Modifier.width(8.dp))
        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(8.dp))
                .background(if (isGranted) Color(0x2200E676) else Color(0x2200F2FE))
                .border(1.dp, if (isGranted) MatrixGreen else CyberBorder, RoundedCornerShape(8.dp))
                .padding(horizontal = 10.dp, vertical = 6.dp)
        ) {
            Text(
                text = actionLabel,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = if (isGranted) MatrixGreen else ElectricCyan
            )
        }
    }
}
```

- [ ] **Step 2: Verify compilation**

Run: `cd mobile && ./gradlew compileDebugKotlin`  
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 3: Commit**

```bash
git add mobile/app/src/main/java/com/jarvis/os/ui/screens/DevicesScreen.kt
git commit -m "feat(ui): implement DevicesScreen composable"
```

---

### Task 6: Settings & Intelligence Screen

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/ui/screens/SettingsScreen.kt`

**Interfaces:**
- Consumes: `hasVoiceKey`, `credentialSource`, `onConfigureKeys`, `context`.
- Produces:
  - `@Composable fun SettingsScreen(context: Context, hasVoiceKey: Boolean, credentialSource: String, onConfigureKeys: () -> Unit)`

- [ ] **Step 1: Implement `SettingsScreen.kt` with OTA update checker**

Create `mobile/app/src/main/java/com/jarvis/os/ui/screens/SettingsScreen.kt`:
```kotlin
package com.jarvis.os.ui.screens

import android.content.Context
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.os.ui.theme.CyberBorder
import com.jarvis.os.ui.theme.CyberSurface
import com.jarvis.os.ui.theme.ElectricCyan
import com.jarvis.os.ui.theme.ObsidianDark
import com.jarvis.os.ui.theme.TextMuted
import com.jarvis.os.ui.theme.TextWhite
import com.jarvis.os.update.MobileUpdater
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    context: Context,
    hasVoiceKey: Boolean,
    credentialSource: String,
    onConfigureKeys: () -> Unit,
    modifier: Modifier = Modifier
) {
    val coroutineScope = rememberCoroutineScope()
    var updateBusy by remember { mutableStateOf(false) }
    var updateStatus by remember { mutableStateOf("") }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Spacer(modifier = Modifier.height(12.dp))

        // SECTION 1: AI & CREDENTIALS VAULT
        Text(
            text = "AI INTELLIGENCE & CREDENTIALS",
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            color = ElectricCyan,
            letterSpacing = 1.sp
        )
        Spacer(modifier = Modifier.height(8.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(containerColor = CyberSurface),
            border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
        ) {
            Column(modifier = Modifier.padding(18.dp)) {
                Text(
                    text = if (hasVoiceKey) "Gemini 2.0 Flash / Live Active" else "API Key Missing",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextWhite
                )
                Text(
                    text = if (!hasVoiceKey) "Setup required for voice synthesis and reasoning"
                    else if (credentialSource == "pc") "Credential Source: Synchronized from PC"
                    else "Credential Source: Personal API Key",
                    fontSize = 12.sp,
                    color = TextMuted
                )

                Spacer(modifier = Modifier.height(14.dp))

                Button(
                    onClick = onConfigureKeys,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(44.dp),
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan)
                ) {
                    Text(
                        text = if (hasVoiceKey) "MANAGE API KEYS" else "CONFIGURE API KEY",
                        color = ObsidianDark,
                        fontWeight = FontWeight.Bold,
                        fontSize = 12.sp
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // SECTION 2: OTA SOFTWARE UPDATES
        Text(
            text = "SOFTWARE & UPDATES",
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            color = ElectricCyan,
            letterSpacing = 1.sp
        )
        Spacer(modifier = Modifier.height(8.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(containerColor = CyberSurface),
            border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
        ) {
            Column(modifier = Modifier.padding(18.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(text = "Current Build", fontSize = 14.sp, color = TextWhite)
                    Text(text = "v1.2.3 (Debug)", fontSize = 13.sp, color = ElectricCyan, fontWeight = FontWeight.Bold)
                }

                Spacer(modifier = Modifier.height(10.dp))
                Text(
                    text = "Updates download directly over Wi-Fi or mobile data from GitHub releases.",
                    fontSize = 11.sp,
                    color = TextMuted
                )

                Spacer(modifier = Modifier.height(14.dp))

                OutlinedButton(
                    onClick = {
                        coroutineScope.launch {
                            updateBusy = true
                            try {
                                updateStatus = MobileUpdater(context).update { updateStatus = it }
                            } catch (_: Exception) {
                                updateStatus = "Update check failed. Check network connection."
                            } finally {
                                updateBusy = false
                            }
                        }
                    },
                    enabled = !updateBusy,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(44.dp),
                    shape = RoundedCornerShape(10.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
                ) {
                    Text(
                        text = if (updateBusy) "Checking Releases…" else "CHECK FOR UPDATES",
                        color = TextWhite,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }

                if (updateStatus.isNotBlank()) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(text = updateStatus, fontSize = 11.sp, color = TextMuted)
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // SECTION 3: AUDIO TELEMETRY
        Text(
            text = "HARDWARE & AUDIO TELEMETRY",
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            color = ElectricCyan,
            letterSpacing = 1.sp
        )
        Spacer(modifier = Modifier.height(8.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(containerColor = CyberSurface),
            border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
        ) {
            Column(modifier = Modifier.padding(18.dp)) {
                TelemetryRow("Sampling Rate", "16,000 Hz Mono PCM")
                Spacer(modifier = Modifier.height(8.dp))
                TelemetryRow("Echo Cancellation", "Hardware AEC Active")
                Spacer(modifier = Modifier.height(8.dp))
                TelemetryRow("Wake Engine", "Vosk Gated KWS")
                Spacer(modifier = Modifier.height(8.dp))
                TelemetryRow("Standby Power Mode", "Zero-Allocation VAD")
            }
        }

        Spacer(modifier = Modifier.height(24.dp))
    }
}

@Composable
private fun TelemetryRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = label, fontSize = 13.sp, color = TextMuted)
        Text(text = value, fontSize = 12.sp, color = TextWhite, fontWeight = FontWeight.Medium)
    }
}
```

- [ ] **Step 2: Verify compilation**

Run: `cd mobile && ./gradlew compileDebugKotlin`  
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 3: Commit**

```bash
git add mobile/app/src/main/java/com/jarvis/os/ui/screens/SettingsScreen.kt
git commit -m "feat(ui): implement SettingsScreen composable"
```

---

### Task 7: Refactor `MainActivity.kt` with Cybernetic Shell & Bottom Navigation

**Files:**
- Modify: `mobile/app/src/main/java/com/jarvis/os/ui/MainActivity.kt`

**Interfaces:**
- Consumes: `JarvisCyberTheme`, `TopTelemetryBar`, `CyberBottomNav`, `AssistantScreen`, `DevicesScreen`, `SettingsScreen`, `QrScannerDialog`, `ApiKeySetupDialog`.
- Replaces: Monolithic stacked column with tabbed navigation shell while maintaining full lifecycle, service actions, and dialog integration.

- [ ] **Step 1: Refactor `MainActivity.kt` to bind the 3 tabs and theme**

Update `mobile/app/src/main/java/com/jarvis/os/ui/MainActivity.kt` to:
1. Wrap root with `JarvisCyberTheme`.
2. Introduce `var selectedTab by remember { mutableStateOf(0) }`.
3. Display `TopTelemetryBar` at top.
4. Render selected screen (`AssistantScreen`, `DevicesScreen`, `SettingsScreen`) in animated `Box`.
5. Render `CyberBottomNav` at bottom.
6. Preserve all permission requests, pairing logic, and service intents.

- [ ] **Step 2: Verify compilation and tests**

Run: `cd mobile && ./gradlew testDebugUnitTest assembleDebug`  
Expected: 100% tests pass, build succeeds.

- [ ] **Step 3: Commit**

```bash
git add mobile/app/src/main/java/com/jarvis/os/ui/MainActivity.kt
git commit -m "feat(ui): refactor MainActivity into modern 3-tab cybernetic layout"
```

---

### Task 8: Verification & Device Testing

**Files:**
- Test: `mobile/app/src/test/java/com/jarvis/os/audio/AudioPcmTest.kt`

- [ ] **Step 1: Run unit tests**

Run: `cd mobile && ./gradlew testDebugUnitTest`  
Expected: `BUILD SUCCESSFUL`

- [ ] **Step 2: Verify APK compilation**

Run: `cd mobile && ./gradlew assembleDebug`  
Expected: `app-debug.apk` built successfully.

- [ ] **Step 3: Install on connected test device**

Run: `adb -s 10.167.177.68:5555 install -r mobile/app/build/outputs/apk/debug/app-debug.apk`  
Expected: `Success`

- [ ] **Step 4: Launch and verify UI on device**

Run: `adb -s 10.167.177.68:5555 shell am start -n com.jarvis.os/.ui.MainActivity`  
Expected: Activity starts cleanly without runtime crash.
