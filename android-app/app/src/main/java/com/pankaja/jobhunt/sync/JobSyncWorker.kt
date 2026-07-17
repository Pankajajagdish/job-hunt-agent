package com.pankaja.jobhunt.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.pankaja.jobhunt.data.ApiClient
import com.pankaja.jobhunt.notifications.NotificationHelper
import java.util.concurrent.TimeUnit

class JobSyncWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        return try {
            val prefs = applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val apiBase = prefs.getString(KEY_API_BASE, null)
                ?: com.pankaja.jobhunt.BuildConfig.DEFAULT_API_BASE
            ApiClient.setBaseUrl(apiBase)

            val knownIds = prefs.getStringSet(KEY_KNOWN_IDS, emptySet()) ?: emptySet()
            val poll = ApiClient.api.pollJobs(minScore = 35, knownIds = knownIds.joinToString(","))

            val newJobs = poll.new_jobs
            if (newJobs.isNotEmpty()) {
                NotificationHelper.notifyNewJobs(applicationContext, newJobs)
                val updated = knownIds.toMutableSet()
                newJobs.forEach { updated.add(it.id) }
                prefs.edit()
                    .putStringSet(KEY_KNOWN_IDS, updated)
                    .putLong(KEY_LAST_SYNC, System.currentTimeMillis())
                    .apply()
            }

            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }

    companion object {
        const val PREFS = "jobhunt"
        const val KEY_API_BASE = "api_base"
        const val KEY_KNOWN_IDS = "known_job_ids"
        const val KEY_LAST_SYNC = "last_sync_ms"
        private const val WORK_NAME = "job_sync"

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<JobSyncWorker>(15, TimeUnit.MINUTES)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )
        }
    }
}
