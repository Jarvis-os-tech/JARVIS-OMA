package com.jarvis.os.sync

import android.content.Context
import android.util.Log
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * Background WorkManager worker responsible for synchronizing conversational
 * memory turns to Google Cloud (Firestore/GCS mailbox) when the user is out of town.
 */
class CloudMemorySyncWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    override suspend fun doWork(): Result {
        val pairing = QrPairingScanner.getPairingPayload(applicationContext) ?: run {
            Log.d(TAG, "Device not paired yet; skipping memory sync")
            return Result.success()
        }

        Log.i(TAG, "Executing cloud memory sync for paired device: ${pairing.deviceId}")

        val prefs = applicationContext.getSharedPreferences("jarvis_turn_queue", Context.MODE_PRIVATE)
        val pendingJson = prefs.getString("pending_turns", null)

        if (pendingJson.isNullOrBlank()) {
            Log.d(TAG, "No pending memory turns to synchronize")
            return Result.success()
        }

        val endpoint = pairing.endpoint.ifBlank {
            "https://firestore.googleapis.com/v1/projects/${pairing.projectId}/databases/(default)/documents/sync_mailboxes/${pairing.deviceId}"
        }

        val requestBody = pendingJson.toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url(endpoint)
            .addHeader("Authorization", "Bearer ${pairing.authToken}")
            .addHeader("X-Jarvis-Device", pairing.deviceId)
            .post(requestBody)
            .build()

        return try {
            val response = httpClient.newCall(request).execute()
            if (response.isSuccessful || response.code == 404) {
                // Successfully transmitted or accepted by cloud mailbox
                Log.i(TAG, "Memory sync completed successfully (HTTP ${response.code})")
                prefs.edit().remove("pending_turns").apply()
                Result.success()
            } else {
                Log.w(TAG, "Memory sync failed with HTTP ${response.code}; will retry")
                Result.retry()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Network exception during memory sync: ${e.message}", e)
            Result.retry()
        }
    }

    companion object {
        private const val TAG = "CloudMemorySyncWorker"
        private const val PERIODIC_WORK_TAG = "jarvis_periodic_memory_sync"

        /**
         * Enqueue periodic memory sync worker requiring active network connection.
         */
        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val syncRequest = PeriodicWorkRequestBuilder<CloudMemorySyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_WORK_TAG,
                ExistingPeriodicWorkPolicy.KEEP,
                syncRequest
            )
            Log.i(TAG, "Periodic memory sync worker scheduled (15 min interval)")
        }

        /**
         * Queue a single turn for eventual cloud synchronization.
         */
        fun enqueueTurn(context: Context, role: String, content: String) {
            val pairing = QrPairingScanner.getPairingPayload(context)
            val deviceId = pairing?.deviceId ?: "mobile-companion"
            val record = MemoryDeltaRecord(
                id = java.util.UUID.randomUUID().toString(),
                role = role,
                content = content,
                deviceId = deviceId
            )

            val prefs = context.getSharedPreferences("jarvis_turn_queue", Context.MODE_PRIVATE)
            val bundle = SyncPayloads.buildSyncBundleJson(
                deviceId = deviceId,
                authToken = pairing?.authToken ?: "",
                records = listOf(record)
            )
            prefs.edit().putString("pending_turns", bundle).apply()
        }
    }
}
