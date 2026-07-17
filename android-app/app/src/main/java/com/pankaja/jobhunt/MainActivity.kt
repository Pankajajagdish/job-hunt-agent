package com.pankaja.jobhunt

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.pankaja.jobhunt.data.*
import com.pankaja.jobhunt.notifications.NotificationHelper
import com.pankaja.jobhunt.sync.JobSyncWorker
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val requestNotificationPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* optional */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                JobFeedScreen()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobFeedScreen() {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val prefs = context.getSharedPreferences(JobSyncWorker.PREFS, Context.MODE_PRIVATE)

    var apiBase by remember {
        mutableStateOf(prefs.getString(JobSyncWorker.KEY_API_BASE, BuildConfig.DEFAULT_API_BASE)
            ?: BuildConfig.DEFAULT_API_BASE)
    }
    var showSettings by remember { mutableStateOf(false) }
    var dashboard by remember { mutableStateOf<DashboardResponse?>(null) }
    var jobs by remember { mutableStateOf<List<Job>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var applyingId by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var lastUpdated by remember { mutableStateOf("") }

    fun knownIds(): Set<String> =
        prefs.getStringSet(JobSyncWorker.KEY_KNOWN_IDS, emptySet()) ?: emptySet()

    fun saveKnownIds(ids: Set<String>) {
        prefs.edit().putStringSet(JobSyncWorker.KEY_KNOWN_IDS, ids).apply()
    }

    fun refreshAll(showToast: Boolean = false) {
        scope.launch {
            loading = true
            try {
                ApiClient.setBaseUrl(apiBase)
                prefs.edit().putString(JobSyncWorker.KEY_API_BASE, apiBase).apply()

                dashboard = ApiClient.api.dashboard()
                val live = ApiClient.api.liveJobs(minScore = 35, refresh = true)
                jobs = live.jobs
                lastUpdated = live.count.toString()
                error = null

                val poll = ApiClient.api.pollJobs(minScore = 35, knownIds = knownIds().joinToString(","))
                if (poll.new_jobs.isNotEmpty()) {
                    NotificationHelper.notifyNewJobs(context, poll.new_jobs)
                    val updated = knownIds().toMutableSet()
                    poll.new_jobs.forEach { updated.add(it.id) }
                    saveKnownIds(updated)
                }
                if (showToast) {
                    Toast.makeText(context, "${live.count} live jobs loaded", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                error = "Start backend: cd job-hunt-agent/backend && start_backend.bat"
            }
            loading = false
        }
    }

    fun applyNow(job: Job) {
        scope.launch {
            applyingId = job.id
            try {
                val result = ApiClient.api.quickApply(
                    QuickApplyRequest(
                        job_id = job.id,
                        title = job.title,
                        company = job.company,
                        url = job.url,
                        description = job.description,
                        mark_applied = false
                    )
                )
                val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                cm.setPrimaryClip(ClipData.newPlainText("cover", result.cover_letter))

                val resumeUrl = if (result.download_url.startsWith("http")) {
                    result.download_url
                } else {
                    "${ApiClient.getBaseUrl()}${result.download_url}"
                }
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(resumeUrl)))
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(result.apply_url)))

                Toast.makeText(
                    context,
                    "Resume ready · Cover letter copied · Apply page opened",
                    Toast.LENGTH_LONG
                ).show()
                dashboard = ApiClient.api.dashboard()
                error = null
            } catch (e: Exception) {
                Toast.makeText(context, "Apply failed: ${e.message}", Toast.LENGTH_SHORT).show()
            }
            applyingId = null
        }
    }

    LaunchedEffect(apiBase) {
        refreshAll()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Job Hunt") },
                actions = {
                    IconButton(onClick = { showSettings = !showSettings }) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                    IconButton(onClick = { refreshAll(showToast = true) }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            if (error != null) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp).fillMaxWidth()
                ) {
                    Text(
                        error!!,
                        Modifier.padding(12.dp),
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        fontSize = 13.sp
                    )
                }
            }

            dashboard?.let { d ->
                Card(Modifier.padding(horizontal = 16.dp, vertical = 4.dp).fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("Today: ${d.applied_today}/${d.daily_goal}", fontWeight = FontWeight.Bold)
                            Text("${d.remaining_today} left", color = MaterialTheme.colorScheme.primary)
                        }
                        Spacer(Modifier.height(6.dp))
                        LinearProgressIndicator(
                            progress = { (d.progress_percent / 100).toFloat() },
                            modifier = Modifier.fillMaxWidth().height(8.dp)
                        )
                    }
                }
            }

            if (showSettings) {
                OutlinedTextField(
                    value = apiBase,
                    onValueChange = { apiBase = it },
                    label = { Text("Backend URL") },
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp).fillMaxWidth(),
                    singleLine = true,
                    trailingIcon = {
                        IconButton(onClick = { refreshAll(showToast = true) }) {
                            Icon(Icons.Default.Check, contentDescription = "Save")
                        }
                    }
                )
                Text(
                    "Emulator: http://10.0.2.2:8000 · Phone: http://PC_IP:8000",
                    fontSize = 11.sp,
                    modifier = Modifier.padding(horizontal = 16.dp)
                )
            }

            Row(
                Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    if (loading) "Fetching live jobs…" else "${jobs.size} matching jobs · real-time",
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f)
                )
                if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            }

            if (loading && jobs.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(jobs, key = { it.id }) { job ->
                        JobCard(
                            job = job,
                            applying = applyingId == job.id,
                            onApply = { applyNow(job) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun JobCard(job: Job, applying: Boolean, onApply: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top
            ) {
                Column(Modifier.weight(1f)) {
                    Text(job.title, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Text(job.company, color = MaterialTheme.colorScheme.primary, fontSize = 14.sp)
                    Text("${job.location} · ${job.source}", fontSize = 12.sp)
                }
                AssistChip(onClick = {}, label = { Text("${job.match_score}%") })
            }

            job.match_reason?.let {
                Spacer(Modifier.height(4.dp))
                Text(it, fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
            }

            Spacer(Modifier.height(10.dp))
            Button(
                onClick = onApply,
                modifier = Modifier.fillMaxWidth(),
                enabled = !applying
            ) {
                if (applying) {
                    CircularProgressIndicator(
                        Modifier.size(18.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                    Spacer(Modifier.width(8.dp))
                    Text("Preparing…")
                } else {
                    Icon(Icons.Default.Bolt, contentDescription = null, Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Apply Now")
                }
            }
            Text(
                "One tap: tailored resume + cover letter copied + apply page opens",
                fontSize = 10.sp,
                color = MaterialTheme.colorScheme.outline,
                modifier = Modifier.padding(top = 4.dp)
            )
        }
    }
}
