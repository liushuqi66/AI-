/**
 * API client for the Resume Analysis System.
 *
 * Provides typed wrappers around all backend API endpoints
 * with proper error handling and timeout configuration.
 */

import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

const api = axios.create({
  baseURL: API_BASE,
  timeout: 180000, // 3 min timeout for AI calls
  headers: { "Content-Type": "application/json" },
});

// ── Response Interceptor ──────────────────────────────

api.interceptors.response.use(
  (response) => {
    // Unwrap standardized response envelope
    const body = response.data;
    if (body && typeof body === "object" && "success" in body) {
      if (!body.success) {
        const err = new Error(body.error?.message || "Unknown error");
        err.code = body.error?.code;
        err.response = response;
        return Promise.reject(err);
      }
      // Return the data portion
      return { ...response, data: body.data ?? body };
    }
    return response;
  },
  (error) => {
    if (error.response) {
      const body = error.response.data;
      if (body && body.error) {
        const msg = body.error.message || error.message;
        const err = new Error(msg);
        err.code = body.error.code;
        err.status = error.response.status;
        return Promise.reject(err);
      }
    }
    if (error.code === "ECONNABORTED") {
      return Promise.reject(new Error("请求超时，请稍后重试"));
    }
    if (!error.response) {
      return Promise.reject(new Error("无法连接到后端服务，请检查服务是否运行"));
    }
    return Promise.reject(error);
  }
);

// ── API Methods ───────────────────────────────────────

/**
 * Check backend health and configuration status.
 * @returns {Promise<Object>} Health status with AI/cache info
 */
export async function checkHealth() {
  const { data } = await api.get("/health");
  return data;
}

/**
 * Upload and parse a PDF resume file.
 * @param {File} file - PDF file to upload
 * @returns {Promise<Object>} Parsed resume data with text and metadata
 */
export async function uploadResume(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/resume/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/**
 * Extract key information from resume text using AI.
 * @param {string} resumeText - Cleaned resume text
 * @param {string} [resumeId] - Optional resume identifier
 * @returns {Promise<Object>} Structured resume information
 */
export async function extractInfo(resumeText, resumeId) {
  const { data } = await api.post("/resume/extract", {
    resume_text: resumeText,
    resume_id: resumeId,
  });
  return data;
}

/**
 * Full pipeline: upload + parse + extract + match.
 * This is the recommended single-call endpoint.
 *
 * @param {File} file - PDF resume file
 * @param {string} [jobDescription] - Job requirements text for matching
 * @returns {Promise<Object>} Complete analysis results
 */
export async function analyzeResume(file, jobDescription) {
  const formData = new FormData();
  formData.append("file", file);
  if (jobDescription) {
    formData.append("job_description", jobDescription);
  }
  const { data } = await api.post("/resume/analyze", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 300000, // 5 min for full pipeline
  });
  return data;
}

/**
 * Match pre-extracted resume info against a job description.
 * @param {Object} resumeInfo - Extracted resume info object
 * @param {string} jobDescription - Job requirements text
 * @returns {Promise<Object>} Match scoring details
 */
export async function matchResume(resumeInfo, jobDescription) {
  const { data } = await api.post("/resume/match", {
    resume_info: resumeInfo,
    job_description: jobDescription,
  });
  return data;
}

/**
 * Get cache statistics for monitoring.
 * @returns {Promise<Object>} Cache stats including hit rates
 */
export async function getCacheStats() {
  const { data } = await api.get("/cache/stats");
  return data;
}

/**
 * Clear all cached analysis results.
 * @returns {Promise<Object>} Clear confirmation
 */
export async function clearCache() {
  const { data } = await api.post("/cache/clear");
  return data;
}
