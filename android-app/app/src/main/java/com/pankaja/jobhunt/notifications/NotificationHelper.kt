package com.pankaja.jobhunt.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.pankaja.jobhunt.MainActivity
import com.pankaja.jobhunt.R
import com.pankaja.jobhunt.data.Job

object NotificationHelper {
    const val CHANNEL_ID = "new_jobs"
    private const val CHANNEL_NAME = "New matching jobs"
    private var notificationId = 1000

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Alerts when new DevSecOps / Cloud jobs match your profile"
            }
            context.getSystemService(NotificationManager::class.java)
                .createNotificationChannel(channel)
        }
    }

    fun notifyNewJobs(context: Context, jobs: List<Job>) {
        if (jobs.isEmpty()) return
        ensureChannel(context)

        val openApp = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        if (jobs.size == 1) {
            val job = jobs.first()
            show(
                context,
                title = "New job: ${job.title}",
                text = "${job.company} · ${job.match_score}% match",
                pendingIntent = openApp
            )
        } else {
            val top = jobs.take(3).joinToString("\n") { "• ${it.title} @ ${it.company}" }
            show(
                context,
                title = "${jobs.size} new matching jobs",
                text = top,
                pendingIntent = openApp
            )
        }
    }

    private fun show(
        context: Context,
        title: String,
        text: String,
        pendingIntent: PendingIntent
    ) {
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        NotificationManagerCompat.from(context).notify(notificationId++, notification)
    }
}
