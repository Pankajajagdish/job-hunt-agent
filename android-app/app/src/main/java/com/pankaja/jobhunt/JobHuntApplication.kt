package com.pankaja.jobhunt

import android.app.Application
import com.pankaja.jobhunt.notifications.NotificationHelper
import com.pankaja.jobhunt.sync.JobSyncWorker

class JobHuntApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        NotificationHelper.ensureChannel(this)
        JobSyncWorker.schedule(this)
    }
}
