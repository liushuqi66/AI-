import { useState, useRef, useCallback, useEffect } from "react";
import { analyzeResume, checkHealth, clearCache, getCacheStats } from "./api";

// ── Constants ──────────────────────────────────────

const STEP_LABELS = ["上传简历", "智能解析", "信息提取", "匹配评分"];

// ── Helpers ────────────────────────────────────────

function getScoreClass(score) {
  if (score >= 75) return "high";
  if (score >= 50) return "medium";
  return "low";
}

function getRecommendationClass(rec) {
  if (!rec) return "";
  if (rec.includes("推荐") && !rec.includes("不")) return "recommend";
  if (rec.includes("可以")) return "consider";
  return "not-recommend";
}

function formatScoreLabel(score) {
  if (score >= 75) return "优秀";
  if (score >= 50) return "良好";
  return "待提升";
}

// ── Toast ──────────────────────────────────────────

function Toast({ message, type, onClose }) {
  if (!message) return null;
  return (
    <div className={`toast ${type}`} onClick={onClose}>
      {message}
    </div>
  );
}

// ── Header ─────────────────────────────────────────

function Header({ backendStatus, aiConfigured, onRefresh }) {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-brand">
          <div className="header-logo">RA</div>
          <div>
            <h1>AI 智能简历分析系统</h1>
            <div className="header-subtitle">Resume Analysis Powered by AI</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {aiConfigured && (
            <span className="ai-badge">🤖 AI 已启用</span>
          )}
          <div className="status-indicator">
            <span className={`status-dot ${backendStatus === "online" ? "" : "offline"}`} />
            {backendStatus === "online" ? "后端运行中" : "检查连接..."}
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={onRefresh}
            title="刷新状态"
            style={{ color: "white", borderColor: "rgba(255,255,255,0.3)", background: "rgba(255,255,255,0.1)" }}
          >
            🔄
          </button>
        </div>
      </div>
    </header>
  );
}

// ── Steps Indicator ────────────────────────────────

function StepsIndicator({ currentStep }) {
  return (
    <div className="steps-container">
      {STEP_LABELS.map((label, i) => {
        let cls = "";
        if (i < currentStep) cls = "completed";
        else if (i === currentStep) cls = "active";
        return (
          <div key={i} className={`step ${cls}`}>
            <span className="step-number">{i < currentStep ? "✓" : i + 1}</span>
            {label}
          </div>
        );
      })}
    </div>
  );
}

// ── Upload Card ────────────────────────────────────

function UploadCard({ file, onFileSelect, onAnalyze, loading }) {
  const [dragOver, setDragOver] = useState(false);
  const [jobDesc, setJobDesc] = useState("");
  const fileInputRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f && f.type === "application/pdf") {
      onFileSelect(f);
    }
  }, [onFileSelect]);

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };
  const handleDragLeave = () => setDragOver(false);

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f) onFileSelect(f);
  };

  const handleAnalyze = () => {
    if (file) onAnalyze(file, jobDesc);
  };

  return (
    <div className="card">
      <div className="card-title">
        <span className="card-title-icon upload">📄</span>
        上传简历 & 岗位匹配
      </div>

      {/* Upload zone */}
      <div
        className={`upload-zone ${dragOver ? "dragover" : ""}`}
        onClick={() => fileInputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <span className="upload-icon">{file ? "📑" : "📁"}</span>
        <div className="upload-text">
          {file ? "点击重新选择文件" : "拖拽 PDF 简历到此处或点击上传"}
        </div>
        <div className="upload-hint">仅支持 .pdf 格式，最大 16 MB</div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />
      </div>

      {/* Selected file info */}
      {file && (
        <div className="file-info">
          <div className="file-info-text">
            <span className="file-info-icon">✅</span>
            <span>
              {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => onFileSelect(null)}>
            移除
          </button>
        </div>
      )}

      {/* Job description */}
      <div style={{ marginTop: 20 }}>
        <label style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 8, color: "var(--text)" }}>
          📋 岗位需求描述
          <span style={{ color: "var(--text-muted)", fontWeight: 400, marginLeft: 6 }}>（可选，用于匹配评分）</span>
        </label>
        <textarea
          value={jobDesc}
          onChange={(e) => setJobDesc(e.target.value)}
          placeholder={"请粘贴岗位需求描述，例如：\n招聘高级前端工程师，要求精通 React、TypeScript，3年以上工作经验，本科以上学历..."}
          rows={4}
        />
      </div>

      {/* Action buttons */}
      <div className="btn-group">
        <button
          className="btn btn-primary"
          disabled={!file || loading}
          onClick={handleAnalyze}
        >
          {loading ? (
            <>
              <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
              分析中...
            </>
          ) : (
            <>🚀 开始智能分析</>
          )}
        </button>
        {file && !loading && (
          <button className="btn btn-secondary" onClick={() => { onFileSelect(null); setJobDesc(""); }}>
            重置
          </button>
        )}
      </div>
    </div>
  );
}

// ── Extracted Info Card ────────────────────────────

function ExtractedInfoCard({ extractedInfo }) {
  if (!extractedInfo) return null;

  const { basic_info, job_info, background } = extractedInfo;

  return (
    <div className="card">
      <div className="card-title">
        <span className="card-title-icon extract">🔍</span>
        关键信息提取
      </div>

      {/* Basic Info */}
      <SectionHeader icon="📌" title="基本信息" />
      <div className="info-grid">
        {[
          ["姓名", basic_info?.name],
          ["电话", basic_info?.phone],
          ["邮箱", basic_info?.email],
          ["地址", basic_info?.address],
        ].map(([label, val]) => (
          <div className="info-item" key={label}>
            <div className="info-label">{label}</div>
            <div className={`info-value ${val ? "" : "null"}`}>
              {val || "未识别"}
            </div>
          </div>
        ))}
      </div>

      {/* Job Info */}
      <SectionHeader icon="💼" title="求职信息" />
      <div className="info-grid">
        {[
          ["求职意向", job_info?.job_intention],
          ["期望薪资", job_info?.expected_salary],
        ].map(([label, val]) => (
          <div className="info-item" key={label}>
            <div className="info-label">{label}</div>
            <div className={`info-value ${val ? "" : "null"}`}>
              {val || "未识别"}
            </div>
          </div>
        ))}
      </div>

      {/* Background */}
      <SectionHeader icon="🎓" title="背景信息" />
      <div className="info-grid">
        {[
          ["工作年限", background?.work_years],
          ["学历背景", background?.education],
        ].map(([label, val]) => (
          <div className="info-item" key={label}>
            <div className="info-label">{label}</div>
            <div className={`info-value ${val ? "" : "null"}`}>
              {val || "未识别"}
            </div>
          </div>
        ))}
      </div>

      {/* Project Experience */}
      {background?.project_experience?.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <SectionHeader
            icon="🛠️"
            title={`项目经历 (${background.project_experience.length})`}
          />
          {background.project_experience.map((proj, i) => (
            <div key={i} className="info-item" style={{ marginBottom: 8 }}>
              <div className="info-label">{proj.project_name || proj.name || `项目 ${i + 1}`}</div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>
                {proj.description || proj.desc || "无描述"}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SectionHeader({ icon, title }) {
  return (
    <h4
      style={{
        fontSize: 13,
        color: "var(--text-muted)",
        margin: "20px 0 12px",
        textTransform: "uppercase",
        letterSpacing: "0.5px",
        fontWeight: 600,
      }}
    >
      {icon} {title}
    </h4>
  );
}

// ── Match Score Card ───────────────────────────────

function MatchScoreCard({ matchResult }) {
  if (!matchResult) return null;

  const score = matchResult.total_score || 0;
  const cls = getScoreClass(score);

  const dimensions = [
    { label: "技能匹配", value: matchResult.skill_score ?? 0, max: 40 },
    { label: "经验相关", value: matchResult.experience_score ?? 0, max: 30 },
    { label: "学历匹配", value: matchResult.education_score ?? 0, max: 15 },
    { label: "项目契合", value: matchResult.project_score ?? 0, max: 15 },
  ];

  return (
    <div className="card">
      <div className="card-title">
        <span className="card-title-icon match">🎯</span>
        匹配度评分
      </div>

      {/* Big score circle */}
      <div className="score-section">
        <div className={`score-circle ${cls}`}>{score}</div>
        <div style={{ fontSize: 16, fontWeight: 600 }}>{formatScoreLabel(score)}</div>
        <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>满分 100 分</div>
      </div>

      {/* Dimension scores */}
      <div className="score-grid">
        {dimensions.map((d) => (
          <div className="score-item" key={d.label}>
            <div className="score-item-label">{d.label}</div>
            <div className="score-item-value">{d.value}</div>
            <div className="score-item-max">/ {d.max}</div>
            <div className="progress-bar">
              <div
                className={`progress-fill ${getScoreClass((d.value / d.max) * 100)}`}
                style={{ width: `${Math.min(100, (d.value / d.max) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Recommendation badge */}
      {matchResult.recommendation && (
        <div style={{ textAlign: "center" }}>
          <span className={`recommendation ${getRecommendationClass(matchResult.recommendation)}`}>
            {matchResult.recommendation}
          </span>
        </div>
      )}

      {/* AI Analysis */}
      {matchResult.analysis && (
        <div className="analysis-text">
          <strong>💡 分析：</strong>{matchResult.analysis}
        </div>
      )}

      {/* Strengths & Weaknesses */}
      <div className="two-column" style={{ marginTop: 20 }}>
        {matchResult.strengths?.length > 0 && (
          <div>
            <h4 style={{ fontSize: 14, color: "#065f46", marginBottom: 8 }}>✅ 优势</h4>
            <ul className="strengths-list">
              {matchResult.strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        )}
        {matchResult.weaknesses?.length > 0 && (
          <div>
            <h4 style={{ fontSize: 14, color: "#991b1b", marginBottom: 8 }}>⚠️ 待提升</h4>
            <ul className="weaknesses-list">
              {matchResult.weaknesses.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Keyword tags */}
      {(matchResult.matched_keywords?.length > 0 || matchResult.job_keywords?.length > 0) && (
        <div style={{ marginTop: 20 }}>
          <h4
            style={{
              fontSize: 13,
              color: "var(--text-muted)",
              marginBottom: 8,
              textTransform: "uppercase",
              letterSpacing: "0.5px",
              fontWeight: 600,
            }}
          >
            🏷️ 关键词匹配
            <span style={{ fontWeight: 400, marginLeft: 8 }}>
              ({matchResult.matched_keywords?.length || 0}/{matchResult.job_keywords?.length || 0})
            </span>
          </h4>
          <div className="tag-list">
            {matchResult.job_keywords?.map((kw, i) => {
              const matched = matchResult.matched_keywords?.includes(kw);
              return (
                <span key={i} className={`tag ${matched ? "matched" : "unmatched"}`}>
                  {matched ? "✓ " : "✗ "}{kw}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Raw Text Card ──────────────────────────────────

function RawTextCard({ text, metadata }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="card">
      <div className="card-title">
        <span className="card-title-icon result">📝</span>
        简历文本预览
      </div>

      {metadata && (
        <div className="meta-row">
          <span className="meta-item">页数: <strong>{metadata.page_count}</strong></span>
          <span className="meta-item">大小: <strong>{metadata.file_size_kb} KB</strong></span>
          <span className="meta-item">字符数: <strong>{text?.length || 0}</strong></span>
        </div>
      )}

      <div className="raw-text-box" style={{ maxHeight: expanded ? "none" : 200 }}>
        {text || "无文本内容"}
      </div>

      {text?.length > 500 && (
        <button
          className="btn btn-secondary btn-sm"
          style={{ marginTop: 12 }}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "收起" : "展开全部"}
        </button>
      )}
    </div>
  );
}

// ── JSON Result Card ───────────────────────────────

function JsonResultCard({ result }) {
  return (
    <div className="card">
      <div className="card-title">
        <span className="card-title-icon result">📊</span>
        完整 JSON 结果
      </div>
      <div className="json-preview">
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </div>
    </div>
  );
}

// ── Empty State ────────────────────────────────────

function EmptyState() {
  return (
    <div className="card" style={{ textAlign: "center", padding: "48px 24px" }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
      <h3 style={{ fontSize: 18, marginBottom: 8 }}>欢迎使用 AI 智能简历分析系统</h3>
      <p style={{ color: "var(--text-muted)", fontSize: 14, maxWidth: 500, margin: "0 auto", lineHeight: 1.7 }}>
        上传 PDF 简历文件，系统将自动利用 AI 模型提取关键信息，
        并可结合岗位需求进行智能匹配评分，帮助您快速筛选候选人。
      </p>
      <div className="score-grid" style={{ maxWidth: 600, margin: "24px auto 0" }}>
        {[
          { icon: "📄", title: "PDF 解析", desc: "兼容多页简历文本提取" },
          { icon: "🧠", title: "AI 提取", desc: "智能识别关键字段信息" },
          { icon: "🎯", title: "精准匹配", desc: "多维评分与关键词分析" },
          { icon: "⚡", title: "缓存加速", desc: "双层缓存避免重复计算" },
        ].map((f, i) => (
          <div className="score-item" key={i}>
            <div style={{ fontSize: 28 }}>{f.icon}</div>
            <div className="score-item-label" style={{ marginTop: 8 }}>{f.title}</div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Performance Info ───────────────────────────────

function PerformanceBar({ totalTimeMs, aiUsed, fromCache }) {
  return (
    <div className="card" style={{ padding: "12px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", fontSize: 13, color: "var(--text-secondary)" }}>
        <span>⏱️ 总耗时: <strong>{totalTimeMs} ms</strong></span>
        <span>🤖 分析模式: <strong>{aiUsed ? "AI 智能" : "基础匹配"}</strong></span>
        <span>💾 缓存: <strong>{fromCache ? "命中 ✅" : "计算 🔄"}</strong></span>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════
//  Main App
// ════════════════════════════════════════════════════

export default function App() {
  const [backendStatus, setBackendStatus] = useState("checking");
  const [aiConfigured, setAiConfigured] = useState(false);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  const [showJson, setShowJson] = useState(false);
  const [history, setHistory] = useState([]);

  // ── Health check on mount ──
  useEffect(() => {
    refreshHealth();
  }, []);

  async function refreshHealth() {
    try {
      const data = await checkHealth();
      setBackendStatus(data?.status === "ok" ? "online" : "offline");
      if (data?.ai_configured) {
        setAiConfigured(true);
        showToast("✅ AI 模型已启用 (" + (data?.ai_model || "LLM") + ")", "success");
      } else {
        setAiConfigured(false);
        showToast("⚠️ AI 模型未配置，使用基础匹配模式", "info");
      }
    } catch {
      setBackendStatus("offline");
      showToast("❌ 无法连接后端服务", "error");
    }
  }

  function showToast(msg, type = "info") {
    setToast({ message: msg, type });
    setTimeout(() => setToast(null), 4000);
  }

  async function handleAnalyze(selectedFile, jobDescription) {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await analyzeResume(selectedFile, jobDescription);
      setResult(data);

      // Save to history
      setHistory((prev) => [
        {
          id: data.resume_id,
          fileName: data.file_name,
          score: data.match_result?.total_score ?? null,
          name: data.extracted_info?.basic_info?.name ?? "未知",
          time: new Date().toLocaleString(),
        },
        ...prev.slice(0, 9), // Keep last 10
      ]);

      const name = data.extracted_info?.basic_info?.name;
      const score = data.match_result?.total_score;
      showToast(
        `✅ 分析完成！${name ? `候选人: ${name}` : ""}${score != null ? ` | 匹配度: ${score}分` : ""}`,
        "success"
      );
    } catch (err) {
      const msg = err.message || "分析失败";
      setError(msg);
      showToast(`❌ ${msg}`, "error");
    } finally {
      setLoading(false);
    }
  }

  // Determine current step
  let currentStep = 0;
  if (result) {
    if (result.match_result) currentStep = 3;
    else if (result.extracted_info) currentStep = 2;
    else if (result.cleaned_text) currentStep = 1;
  }

  const isFromCache = result?.match_result?.from_cache || result?.from_cache;

  return (
    <div className="app-container">
      <Header
        backendStatus={backendStatus}
        aiConfigured={aiConfigured}
        onRefresh={refreshHealth}
      />

      <main className="main-content">
        <StepsIndicator currentStep={currentStep} />

        {/* Upload */}
        <UploadCard
          file={file}
          onFileSelect={setFile}
          onAnalyze={handleAnalyze}
          loading={loading}
        />

        {/* Error */}
        {error && (
          <div className="card" style={{ borderColor: "var(--danger)", background: "#fef2f2" }}>
            <div style={{ color: "var(--danger)", fontWeight: 500 }}>
              ❌ {error}
            </div>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="card">
            <div className="loading-overlay">
              <div className="spinner" />
              <div className="loading-text">AI 正在分析简历，请稍候...</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                正在解析 PDF → 提取关键信息 → 智能匹配评分
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {result && !loading && (
          <>
            {/* Performance bar */}
            <PerformanceBar
              totalTimeMs={result.total_time_ms}
              aiUsed={result.ai_used}
              fromCache={isFromCache}
            />

            {/* Extracted Info */}
            <ExtractedInfoCard extractedInfo={result.extracted_info} />

            {/* Match Score */}
            {result.match_result && <MatchScoreCard matchResult={result.match_result} />}

            {/* Raw text */}
            <RawTextCard text={result.cleaned_text} metadata={result.metadata} />

            {/* JSON toggle */}
            <div style={{ textAlign: "center", margin: "20px 0" }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setShowJson(!showJson)}
              >
                {showJson ? "隐藏" : "查看"}完整 JSON 响应
              </button>
            </div>
            {showJson && <JsonResultCard result={result} />}
          </>
        )}

        {/* History (after first analysis) */}
        {history.length > 0 && !loading && (
          <div className="card" style={{ padding: "20px" }}>
            <div className="card-title" style={{ marginBottom: 12, fontSize: 16 }}>
              <span className="card-title-icon upload">📋</span>
              分析历史
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {history.map((h) => (
                <div
                  key={h.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "8px 12px",
                    background: "var(--bg)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: 13,
                  }}
                >
                  <span>
                    <strong>{h.name}</strong> — {h.fileName}
                  </span>
                  <span style={{ display: "flex", gap: 16, color: "var(--text-muted)" }}>
                    {h.score != null && (
                      <span style={{ color: h.score >= 75 ? "var(--success)" : h.score >= 50 ? "var(--warning)" : "var(--danger)", fontWeight: 600 }}>
                        {h.score}分
                      </span>
                    )}
                    <span>{h.time}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!file && !loading && !result && <EmptyState />}
      </main>

      <Toast
        message={toast?.message}
        type={toast?.type}
        onClose={() => setToast(null)}
      />
    </div>
  );
}
