package com.pankaja.jobhunt.data

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*

data class Job(
    val id: String,
    val title: String,
    val company: String,
    val location: String,
    val description: String,
    val url: String,
    val source: String,
    val posted_at: String,
    val match_score: Int = 0,
    val matched_skills: List<String>? = null,
    val match_reason: String? = null
)

data class JobsResponse(val count: Int, val jobs: List<Job>)

data class LiveJobsResponse(
    val count: Int,
    val live: Boolean,
    val sources: List<String>? = null,
    val jobs: List<Job>
)

data class PollResponse(
    val updated_at: String,
    val total_cached: Int,
    val new_count: Int,
    val new_jobs: List<Job>,
    val all_jobs: List<Job>? = null
)

data class DashboardResponse(
    val daily_goal: Int,
    val applied_today: Int,
    val remaining_today: Int,
    val total_applied: Int,
    val progress_percent: Double,
    val message: String,
    val recent: List<Map<String, Any>>? = null
)

data class ApplyAssistRequest(
    val job_id: String,
    val title: String,
    val company: String,
    val url: String,
    val description: String
)

data class QuickApplyRequest(
    val job_id: String,
    val title: String,
    val company: String,
    val url: String,
    val description: String,
    val mark_applied: Boolean = false
)

data class QuickApplyResponse(
    val resume_file: String,
    val download_url: String,
    val cover_letter: String,
    val apply_url: String,
    val tailored_summary: String,
    val message: String
)

data class ApplyAssistResponse(
    val resume_file: String,
    val download_url: String,
    val tailored_summary: String,
    val tailored_bullets: List<String>? = null,
    val cover_letter: String,
    val apply_url: String,
    val note: String,
    val tracked: Boolean? = null
)

data class LogApplyRequest(
    val job_id: String,
    val title: String,
    val company: String,
    val url: String,
    val status: String = "applied",
    val resume_file: String = ""
)

interface JobHuntApi {
    @GET("api/dashboard")
    suspend fun dashboard(): DashboardResponse

    @GET("api/jobs/live")
    suspend fun liveJobs(
        @Query("min_score") minScore: Int = 35,
        @Query("refresh") refresh: Boolean = true
    ): LiveJobsResponse

    @GET("api/jobs/poll")
    suspend fun pollJobs(
        @Query("min_score") minScore: Int = 35,
        @Query("known_ids") knownIds: String = ""
    ): PollResponse

    @POST("api/jobs/seen")
    suspend fun markSeen(@Body jobIds: List<String>): Map<String, Any>

    @GET("api/jobs/search")
    suspend fun searchJobs(@Query("min_score") minScore: Int = 35): JobsResponse

    @POST("api/jobs/quick-apply")
    suspend fun quickApply(@Body body: QuickApplyRequest): QuickApplyResponse

    @POST("api/jobs/apply-assist")
    suspend fun applyAssist(@Body body: ApplyAssistRequest): ApplyAssistResponse

    @POST("api/tracker/log")
    suspend fun logApply(@Body body: LogApplyRequest): Map<String, Any>

    @GET("api/health")
    suspend fun health(): Map<String, String>
}

object ApiClient {
    private var baseUrl: String = com.pankaja.jobhunt.BuildConfig.DEFAULT_API_BASE

    fun getBaseUrl(): String = baseUrl.trimEnd('/')

    fun setBaseUrl(url: String) {
        baseUrl = if (url.endsWith("/")) url else "$url/"
        retrofit = buildRetrofit(baseUrl)
        api = retrofit.create(JobHuntApi::class.java)
    }

    private fun buildRetrofit(url: String): Retrofit = Retrofit.Builder()
        .baseUrl(url)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    private var retrofit: Retrofit = buildRetrofit(baseUrl)
    var api: JobHuntApi = retrofit.create(JobHuntApi::class.java)
}
