package com.jarvis.os.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.jarvis.os.overlay.HaloOrb
import com.jarvis.os.overlay.OverlayUiState
import com.jarvis.os.service.JarvisVoiceService
import com.jarvis.os.sync.CloudMemorySyncWorker
import com.jarvis.os.sync.QrPairingScanner

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            JarvisMobileScreen(
                context = this,
                onStartDaemon = { startVoiceDaemon() },
                onStopDaemon = { stopVoiceDaemon() },
                onRequestOverlay = { requestOverlayPermission() }
            )
        }
    }

    private fun startVoiceDaemon() {
        val intent = Intent(this, JarvisVoiceService::class.java).apply {
            action = JarvisVoiceService.ACTION_START
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        Toast.makeText(this, "JARVIS Voice Daemon started", Toast.LENGTH_SHORT).show()
    }

    private fun stopVoiceDaemon() {
        val intent = Intent(this, JarvisVoiceService::class.java).apply {
            action = JarvisVoiceService.ACTION_STOP
        }
        startService(intent)
        Toast.makeText(this, "JARVIS Voice Daemon stopped", Toast.LENGTH_SHORT).show()
    }

    private fun requestOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivity(intent)
        }
    }
}

@Composable
fun JarvisMobileScreen(
    context: Context,
    onStartDaemon: () -> Unit,
    onStopDaemon: () -> Unit,
    onRequestOverlay: () -> Unit
) {
    var isPaired by remember { mutableStateOf(QrPairingScanner.isPaired(context)) }
    var pairingInfo by remember { mutableStateOf(QrPairingScanner.getPairingPayload(context)) }
    var showPairDialog by remember { mutableStateOf(false) }
    var pairInputText by remember { mutableStateOf("") }
    var overlayGranted by remember {
        mutableStateOf(
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) Settings.canDrawOverlays(context) else true
        )
    }

    // Permission Request Launcher
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { _ ->
        // Refreshed on return
    }

    LaunchedEffect(Unit) {
        val permissions = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        permissionLauncher.launch(permissions.toTypedArray())
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = Color(0xFF090A0E)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp, vertical = 32.dp)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Header
            Text(
                text = "JARVIS OS",
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White,
                letterSpacing = 2.sp
            )
            Text(
                text = "Mobile Voice Companion • Siri Ambient HUD",
                fontSize = 12.sp,
                color = Color(0xFF00F2FE),
                modifier = Modifier.padding(top = 4.dp)
            )

            Spacer(modifier = Modifier.height(36.dp))

            // Ambient Halo Orb
            HaloOrb(
                size = 180.dp,
                state = OverlayUiState.Listening(rms = 2500f)
            )

            Spacer(modifier = Modifier.height(36.dp))

            // System Status Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF14161E)),
                border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x3300F2FE))
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(
                        text = "SYSTEM STATUS",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color.Gray,
                        letterSpacing = 1.sp
                    )

                    Spacer(modifier = Modifier.height(14.dp))

                    StatusRow(
                        title = "Desktop Pairing",
                        value = if (isPaired) "Paired (${pairingInfo?.deviceId})" else "Not Paired",
                        active = isPaired
                    )

                    Spacer(modifier = Modifier.height(10.dp))

                    StatusRow(
                        title = "Overlay Permission",
                        value = if (overlayGranted) "Granted" else "Requires Setup",
                        active = overlayGranted
                    )

                    Spacer(modifier = Modifier.height(10.dp))

                    StatusRow(
                        title = "Cloud Memory Sync",
                        value = "jarvis-os-508612 (Firestore/GCS)",
                        active = isPaired
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Actions Section
            Button(
                onClick = { onStartDaemon() },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00F2FE))
            ) {
                Text(
                    text = "START AMBIENT DAEMON",
                    color = Color.Black,
                    fontWeight = FontWeight.Bold
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            OutlinedButton(
                onClick = { onStopDaemon() },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = Color.White)
            ) {
                Text(text = "STOP DAEMON")
            }

            Spacer(modifier = Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = { showPairDialog = true },
                    modifier = Modifier
                        .weight(1f)
                        .height(46.dp),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(text = "Pair Desktop", fontSize = 13.sp)
                }

                OutlinedButton(
                    onClick = {
                        CloudMemorySyncWorker.schedule(context)
                        Toast.makeText(context, "Memory sync dispatched", Toast.LENGTH_SHORT).show()
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(46.dp),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(text = "Sync Cloud", fontSize = 13.sp)
                }
            }

            if (!overlayGranted) {
                Spacer(modifier = Modifier.height(12.dp))
                Button(
                    onClick = {
                        onRequestOverlay()
                        overlayGranted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                            Settings.canDrawOverlays(context)
                        } else true
                    },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF9B51E0))
                ) {
                    Text(text = "Enable Floating Siri Overlay", color = Color.White)
                }
            }
        }
    }

    // Pairing Dialog
    if (showPairDialog) {
        AlertDialog(
            onDismissRequest = { showPairDialog = false },
            title = { Text(text = "Pair with JARVIS Desktop") },
            text = {
                Column {
                    Text(
                        text = "Run 'jarvis pair' on your desktop and paste the terminal JSON payload below:",
                        fontSize = 13.sp
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    OutlinedTextField(
                        value = pairInputText,
                        onValueChange = { pairInputText = it },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { Text("{\"v\":1,\"pid\":\"jarvis-os-508612\"...}") },
                        maxLines = 4
                    )
                }
            },
            confirmButton = {
                Button(onClick = {
                    val payload = QrPairingScanner.processScanResult(context, pairInputText.trim())
                    if (payload != null) {
                        isPaired = true
                        pairingInfo = payload
                        showPairDialog = false
                        Toast.makeText(context, "Successfully paired with ${payload.deviceId}!", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(context, "Invalid pairing payload", Toast.LENGTH_SHORT).show()
                    }
                }) {
                    Text("Pair Now")
                }
            },
            dismissButton = {
                TextButton(onClick = { showPairDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }
}

@Composable
fun StatusRow(title: String, value: String, active: Boolean) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = title, color = Color.White, fontSize = 14.sp)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(if (active) Color(0xFF00F2FE) else Color(0xFFFF5252))
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = value,
                color = if (active) Color(0xFFE0E0E0) else Color.Gray,
                fontSize = 13.sp
            )
        }
    }
}
