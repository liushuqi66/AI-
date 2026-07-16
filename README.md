# 🤖 AI 智能简历分析系统

> AI-Powered Intelligent Resume Analysis System — 基于 AI 的简历自动解析、信息提取与岗位匹配评分系统。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 目录

- [项目简介](#项目简介)
- [功能模块](#功能模块)
- [技术架构](#技术架构)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [API 接口文档](#api-接口文档)
- [评分标准说明](#评分标准说明)
- [部署指南](#部署指南)
- [环境变量配置](#环境变量配置)
- [Git 提交规范](#git-提交规范)

---

## 项目简介

在招聘流程中，快速筛选和分析大量简历是一项耗时的工作。本系统能够：

- **自动解析** PDF 格式简历，兼容多页文档
- **AI 驱动提取** 关键信息（姓名、联系方式、学历、项目经历等）
- **智能匹配评分** 将简历与岗位需求进行多维对比，输出匹配度评分
- **缓存加速** Redis + 本地 LRU 双层缓存，避免重复计算

## 功能模块

| 模块 | 功能说明 | 状态 |
|:---|:---|:---:|
| **模块一** | 简历上传与 PDF 解析 — 支持拖拽上传、多页解析、文本清洗 | ✅ |
| **模块二** | AI 关键信息提取 — 姓名/电话/邮箱/地址 + 求职意向/薪资/学历/项目 | ✅ |
| **模块三** | 简历评分与匹配 — 4 维评分（技能40+经验30+学历15+项目15=100分） | ✅ |
| **模块四** | 结果返回与缓存 — JSON 结构化输出 + Redis/本地双层缓存 | ✅ |
| **模块五** | 前端交互页面 — React 19 + 响应式设计 + GitHub Pages 部署 | ✅ |

### 加分项实现

- 🎯 **多 AI 模型支持**：OpenAI / DeepSeek / 通义千问 等兼容 API
- 📊 **雷达图可视化**：评分维度雷达图（计划中）
- ⚡ **双层缓存架构**：Redis（分布式）+ 内存 LRU（本地降级）
- 🔄 **请求速率限制**：防止 API 滥用
- 📝 **请求日志与性能监控**：每个请求记录耗时和状态
- 🌐 **GitHub Actions CI/CD**：自动化测试与部署

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (React 19 + Vite)               │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ 上传组件 │ │ 信息展示  │ │ 评分仪表盘 │ │ JSON 预览   │ │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └──────┬──────┘ │
└───────┼───────────┼────────────┼───────────────┼────────┘
        │           │            │               │
   ┌────▼───────────▼────────────▼───────────────▼────────┐
   │              后端 (Flask RESTful API)                  │
   │  ┌───────────┐ ┌──────────────┐ ┌──────────────────┐ │
   │  │ PDF 解析   │ │ AI 信息提取   │ │ 智能匹配评分      │ │
   │  │ (PyMuPDF) │ │ (DeepSeek)   │ │ (多维评分模型)    │ │
   │  └───────────┘ └──────────────┘ └──────────────────┘ │
   │  ┌──────────────────────────────────────────────────┐ │
   │  │        缓存层 (Redis + In-Memory LRU)             │ │
   │  └──────────────────────────────────────────────────┘ │
   └──────────────────────────────────────────────────────┘
```

## 项目结构

```
resume-analyzer/
├── .github/workflows/              # CI/CD 自动化部署
│   ├── deploy-backend.yml          # 后端部署到阿里云 FC
│   └── deploy-frontend.yml         # 前端部署到 GitHub Pages
├── backend/                        # Python Flask 后端
│   ├── app.py                      # 主应用 & API 路由（8个端点）
│   ├── config.py                   # 配置管理（dataclass + .env）
│   ├── utils.py                    # 公共工具（AI客户端、响应格式化、校验）
│   ├── middleware.py               # 中间件（日志、限流、错误处理）
│   ├── pdf_parser.py               # 模块一：PDF 解析与文本清洗
│   ├── resume_extractor.py         # 模块二：AI 关键信息提取
│   ├── resume_matcher.py           # 模块三：简历评分与匹配
│   ├── cache_manager.py            # 模块四：Redis + LRU 双层缓存
│   ├── index.py                    # 阿里云 FC 入口适配器
│   ├── serverless.yml              # Serverless 部署配置
│   ├── pyproject.toml              # Python 项目配置
│   ├── requirements.txt            # Python 依赖
│   └── .env.example                # 环境变量模板
├── frontend/                       # React 19 + Vite 前端
│   ├── src/
│   │   ├── App.jsx                 # 主应用（完整交互流程）
│   │   ├── api.js                  # API 调用封装（Axios）
│   │   ├── main.jsx                # React 入口
│   │   └── index.css               # 现代化响应式 UI
│   ├── public/favicon.svg          # 网站图标
│   ├── index.html                  # HTML 入口
│   ├── vite.config.js              # Vite 配置（含 GitHub Pages 路径）
│   └── package.json                # 前端依赖
├── .gitignore
└── README.md
```

## 快速开始

### 环境要求

- **Python** 3.10+
- **Node.js** 18+
- **Redis** (可选，未安装时自动使用内存 LRU 缓存)
- **AI API Key** (DeepSeek / OpenAI 兼容)

### 1. 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 AI API Key

# 启动服务
python app.py
```

服务运行在 `http://localhost:5000`

### 2. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 本地开发（热更新）
npm run dev

# 构建生产版本
npm run build
```

### 3. 一键启动脚本

```bash
# 终端1 - 后端
cd backend && python app.py

# 终端2 - 前端
cd frontend && npm run dev
```

打开 `http://localhost:3000/resume-analyzer/` 即可使用。

## API 接口文档

### 通用响应格式

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": { ... }
}
```

### 接口列表

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/api/health` | 健康检查 & 系统状态 |
| `POST` | `/api/resume/upload` | 上传并解析 PDF 简历 |
| `POST` | `/api/resume/extract` | AI 提取简历关键信息 |
| `POST` | `/api/resume/analyze` | **一键全流程分析（推荐）** |
| `POST` | `/api/resume/match` | 简历与岗位匹配评分 |
| `GET` | `/api/cache/stats` | 缓存统计信息 |
| `POST` | `/api/cache/clear` | 清除所有缓存 |

### 示例：一键分析

```bash
curl -X POST http://localhost:5000/api/resume/analyze \
  -F "file=@resume.pdf" \
  -F "job_description=招聘高级前端工程师，要求精通 React、TypeScript，3年以上经验"
```

### 示例响应

```json
{
  "success": true,
  "data": {
    "resume_id": "uuid-xxxx",
    "file_name": "resume.pdf",
    "metadata": { "page_count": 2, "file_size_kb": 45.3 },
    "extracted_info": {
      "basic_info": {
        "name": "张三",
        "phone": "13800138000",
        "email": "zhangsan@example.com",
        "address": "北京市朝阳区"
      },
      "job_info": {
        "job_intention": "高级前端工程师",
        "expected_salary": "25K-35K"
      },
      "background": {
        "work_years": "5年",
        "education": "本科",
        "project_experience": [...]
      }
    },
    "match_result": {
      "total_score": 85,
      "skill_score": 34,
      "experience_score": 25,
      "education_score": 13,
      "project_score": 13,
      "analysis": "...",
      "strengths": ["React 熟练", "项目经验丰富"],
      "weaknesses": ["缺少 TypeScript 经验"],
      "recommendation": "推荐面试",
      "matched_keywords": ["React", "JavaScript", "Vue.js"],
      "job_keywords": ["React", "TypeScript", "JavaScript", ...]
    },
    "total_time_ms": 3245.67,
    "ai_used": true,
    "ai_model": "deepseek-chat"
  }
}
```

## 评分标准说明

简历匹配采用 **100 分制 4 维度评分模型**：

| 维度 | 满分 | 评分依据 |
|:---|:---:|:---|
| **技能匹配度** | 40分 | 技术栈、工具、框架与岗位需求的匹配程度 |
| **工作经验相关性** | 30分 | 工作年限、行业经验与岗位的相关程度 |
| **学历匹配度** | 15分 | 学历背景是否符合岗位要求 |
| **项目经验匹配度** | 15分 | 项目经历与岗位需求的契合度 |
| **总分** | **100分** | |

### 推荐等级

- 🟢 **≥75 分** — 推荐面试
- 🟡 **50-74 分** — 可以面试
- 🔴 **<50 分** — 暂不推荐

### AI 模式 vs 基础模式

| 特性 | AI 模式 | 基础模式 |
|:---|:---|:---|
| 信息提取 | 基于 LLM 深度理解 | 正则表达式匹配 |
| 匹配评分 | LLM 综合分析与评分 | 关键词计数 + 规则打分 |
| 分析报告 | 自然语言综合分析 | 关键词匹配率统计 |
| 准确度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 速度 | 2-5秒 | <0.5秒 |
| 配置要求 | 需 API Key | 开箱即用 |

## 部署指南

### 前端：GitHub Pages

推送到 `main` 分支后，GitHub Actions 自动构建并部署：

```bash
git push origin main
# 自动触发 .github/workflows/deploy-frontend.yml
```

部署后访问：`https://<username>.github.io/resume-analyzer/`

### 后端：阿里云函数计算 FC

```bash
# 1. 安装 Serverless Devs
npm install -g @serverless-devs/s

# 2. 配置阿里云凭证
s config add

# 3. 部署
cd backend
s deploy
```

### 环境变量（FC 控制台配置）

在阿里云 FC 控制台设置以下环境变量：

- `OPENAI_API_KEY` — AI 模型 API Key
- `OPENAI_BASE_URL` — API 端点地址
- `AI_MODEL` — 模型名称
- `REDIS_HOST` — Redis 地址（可选）

## 环境变量配置

| 变量 | 说明 | 默认值 |
|:---|:---|:---|
| `OPENAI_API_KEY` | AI API Key（必填以启用 AI 模式） | - |
| `OPENAI_BASE_URL` | API 端点地址 | `https://api.openai.com/v1` |
| `AI_MODEL` | 模型名称 | `gpt-4o-mini` |
| `REDIS_HOST` | Redis 主机地址 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `REDIS_PASSWORD` | Redis 密码 | - |
| `REDIS_DB` | Redis 数据库编号 | `0` |
| `FLASK_PORT` | Flask 服务端口 | `5000` |
| `FLASK_ENV` | 运行环境 (`development`/`production`) | `production` |
| `MAX_CONTENT_LENGTH` | 最大上传文件大小（字节） | `16777216` (16MB) |

### 支持的 AI 模型

| 模型 | BASE_URL | 说明 |
|:---|:---|:---|
| **DeepSeek** | `https://api.deepseek.com/v1` | 高性价比，中文友好 |
| **OpenAI** | `https://api.openai.com/v1` | GPT-4o / GPT-4o-mini |
| **通义千问** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里云模型 |
| **其他兼容** | 自定义 | 支持 OpenAI 兼容 API |

## Git 提交规范

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
feat:     新功能
fix:      修复 Bug
docs:     文档更新
refactor: 代码重构（不改变功能）
style:    代码格式调整（不影响逻辑）
test:     测试相关
chore:    构建/工具链/依赖更新
perf:     性能优化
ci:       CI/CD 相关
```

示例：
```
feat: 添加双层缓存机制（Redis + LRU）
fix: 修复多页 PDF 解析时文本丢失的问题
docs: 更新 API 文档，添加响应示例
refactor: 提取公共工具函数到 utils.py
```

---

**Built with ❤️ using Flask + React + AI**
