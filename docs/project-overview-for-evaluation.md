# General Medical Services — Project Overview for Technical Evaluation

> GitHub: https://github.com/hrafael2011/general-medical-services.git
> Evaluated: 2026-05-29 | Branch: `bot-dev`

---

## 1. Project Summary

**General Medical Services** is a full-stack military hospital shift scheduling and notification system. It automates the assignment of doctors to service areas (Emergency, Runway, On-Call) through constraint-based calendar generation, manages medical missions, and delivers notifications/confirmations via WhatsApp (Meta Cloud API) and Telegram (AI-powered conversational bot).

**Users:** Hospital administrators ("encargados", "admins", "superadmins") who manage doctors, calendars, missions, and notifications.

---

## 2. Tech Stack

### Backend

| Category | Technology | Version |
|----------|-----------|---------|
| Language | Python | 3.12 |
| Framework | FastAPI | 0.115.6 |
| ASGI Server | Uvicorn | 0.34.0 |
| ORM | SQLAlchemy | 2.0.36 |
| Database | PostgreSQL | — |
| DB Driver | psycopg[binary] | 3.2.3 |
| Migrations | Alembic | — |
| Validation | Pydantic v2 | — |
| Settings | pydantic-settings | 2.7.1 |
| Auth | JWT (python-jose) + bcrypt/passlib | — |
| HTTP Client | httpx | ≥0.27.0 |

### AI / LLM

| Category | Technology | Version |
|----------|-----------|---------|
| LLM Provider | DeepSeek (`deepseek-chat`) | — |
| LLM SDK | openai (compatibility layer) | ≥1.0.0 |
| Vector Store | sqlite-vec | ≥0.1.0 |
| Embeddings | scikit-learn (TfidfVectorizer) | ≥1.5.0 |
| Numerical | numpy | ≥2.0.0 |

### Messaging & Notifications

| Category | Technology | Version |
|----------|-----------|---------|
| WhatsApp | PyWa (Meta Cloud API v22.0) | ≥3.0.0 |
| Telegram | Raw HTTP to Bot API (no library) | — |
| Scheduler | APScheduler | ≥3.10.0 |

### PDF & Reports

| Category | Technology | Version |
|----------|-----------|---------|
| HTML→PDF | WeasyPrint | ≥68.0 |
| PDF Generation | ReportLab | ≥4.2 |
| Excel | openpyxl | 3.1.5 |
| Templates | Jinja2 | ≥3.1 |

### Frontend

| Category | Technology | Version |
|----------|-----------|---------|
| Framework | React | 19 |
| Language | TypeScript | — |
| Build Tool | Vite | — |
| Routing | react-router-dom | 7 |
| State/Server | @tanstack/react-query | 5 |
| HTTP Client | ky + custom apiFetch wrapper | — |
| Icons | lucide-react | — |
| Testing | Vitest + @testing-library/react | — |

### Infrastructure

| Category | Technology |
|----------|-----------|
| Backend Hosting | Railway |
| Frontend Hosting | Vercel |
| Database | Railway PostgreSQL |
| CI/CD | Vercel Git Integration + Railway GitHub Integration |
| Containerization | Docker + docker-compose |
| Version Control | Git + GitHub |

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    FRONTEND (Vercel)                      │
│  React 19 + TypeScript + Vite + react-router + react-query│
│  • Admin dashboard • Doctor management • Calendar views   │
│  • Mission management • Audit log • Notifications panel   │
│  • User management with granular permissions              │
│  • Confirmation management panel                          │
│  • Telegram links admin                                   │
└──────────────────────┬───────────────────────────────────┘
                       │ REST API (JSON)
                       ▼
┌──────────────────────────────────────────────────────────┐
│                   BACKEND (Railway)                       │
│              FastAPI + SQLAlchemy + PostgreSQL             │
│                                                          │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Calendar   │  │ Doctor       │  │ Mission         │  │
│  │ Engine     │  │ Management   │  │ Management      │  │
│  │ (backtrack)│  │              │  │                 │  │
│  └────────────┘  └──────────────┘  └─────────────────┘  │
│                                                          │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Notification│  │ Confirmation │  │ Audit           │  │
│  │ Service    │  │ Service      │  │ System          │  │
│  │ (PyWa)     │  │ (WhatsApp)   │  │                 │  │
│  └────────────┘  └──────────────┘  └─────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ TELEGRAM BOT (Conversational AI)                    │  │
│  │ • NLU Engine (DeepSeek LLM)                        │  │
│  │ • 14 tools with JSON schemas                       │  │
│  │ • Semantic Layer (15 hand-written business metrics)│  │
│  │ • SQL Agent (NL→SQL multi-turn, up to 3 iterations)│  │
│  │ • Few-shot RAG (sqlite-vec + TF-IDF)               │  │
│  │ • Session memory with follow-up support            │  │
│  │ • 30+ pre-registered SQL query templates           │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ APScheduler│  │ Permissions  │  │ PDF / Excel     │  │
│  │ (4 jobs)   │  │ System (JSON)│  │ Reports         │  │
│  └────────────┘  └──────────────┘  └─────────────────┘  │
└──────────────────────┬───────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌──────────┐ ┌──────────┐ ┌──────────────┐
   │ Meta     │ │ Telegram │ │ PostgreSQL   │
   │ Cloud API│ │ Bot API  │ │ (Railway)    │
   │(WhatsApp)│ │          │ │              │
   └──────────┘ └──────────┘ └──────────────┘
```

---

## 4. Feature Inventory

### 4.1 Core Domain
- **Doctor Management**: CRUD with WhatsApp phone, rank, department, sex, availability mode (monthly/daily), service areas, monthly limits, mission participation
- **Catalog Management**: Service areas (Emergency, Runway, On-Call), military ranks, departments — each with configurable weights and start hours
- **Calendar Generation**: Backtracking constraint engine that auto-assigns doctors to service areas based on availability, load balancing, and area requirements
- **Calendar Approval**: Week-by-week approval workflow with WhatsApp notifications to assigned doctors
- **Mission Management**: Medical mission creation, doctor candidate ranking, confirmation flow

### 4.2 Notification System
- **WhatsApp (Meta Cloud API)**: Initial assignment notifications, 12h pre-service reminders, confirmation via "1" reply, escalation to managers
- **APScheduler Jobs**: Queue processing (30s), pre-service reminders (5min), escalation checks (15min), overdue confirmations (10min)
- **Notification Log**: Full audit trail of every notification sent, with status tracking and retry logic

### 4.3 Telegram AI Bot
- **Natural Language Understanding**: Single LLM call for intent classification, entity extraction, and tool selection (14 tools)
- **Deterministic Query Layer**: 15 business metrics with hand-written SQL (zero hallucination risk)
- **NL→SQL Fallback**: Multi-turn SQL agent with self-correction (schema linking → generation → execution → verification → refinement, up to 3 iterations)
- **Few-Shot RAG**: Local vector store (sqlite-vec + TF-IDF) for similar query retrieval
- **Conversational Features**: Session memory, follow-up context merging, mission contextual follow-ups
- **Export**: PDF and Excel generation from any query, sent as Telegram documents
- **Authentication**: Deep-link `/start <token>` flow linking Telegram users to system accounts
- **Admin Panel**: Web UI for managing Telegram user links and viewing interaction logs

### 4.4 Security & Access Control
- **JWT Authentication**: Token-based auth with refresh support
- **Granular Permissions**: JSON column on User model (12 permissions: manage_doctors, manage_calendars, manage_missions, manage_users, view_audit, view_notifications, manage_alerts, receive_escalation_alerts, export_reports, manage_trash, manage_catalogs, manage_admins)
- **Roles**: encargado (permission-based), admin (full access), superadmin (admin creation)
- **Rate Limiting**: Configurable per-endpoint rate limiting
- **Webhook Security**: Secret token validation for both Telegram and WhatsApp webhooks
- **SQL Injection Prevention**: Multi-layer SQL validation in the NL→SQL pipeline

### 4.5 Reporting & Audit
- **PDF Reports**: Institutional military hospital formats via WeasyPrint + Jinja2 HTML templates
- **Excel Exports**: Via openpyxl
- **Audit Log**: Complete action trail with actor, action, target, and metadata

### 4.6 Frontend Features
- **Responsive Dashboard**: Sidebar navigation with role-based menu items
- **Welcome Toast**: Professional greeting with spring animation on login
- **User Avatar**: Color-hash avatar with initials in sidebar footer
- **Doctor Views**: List with search/filter, detail profiles, by-day calendar view
- **Calendar Management**: Monthly/daily views, generation, approval workflow
- **Mission Views**: Candidate ranking, manual participant assignment, status tracking
- **Notifications Panel**: Filterable log with status badges
- **Confirmation Panel**: Track doctor confirmations with status and escalation info
- **User Management**: Create/edit users with permission checkboxes grouped by category
- **Audit Log**: Filterable activity feed with date range and action type filters

---

## 5. Codebase Statistics

| Metric | Count |
|--------|-------|
| Backend Python files | ~120+ |
| Frontend TypeScript/TSX files | ~60+ |
| Database migrations | ~41 |
| Test files (backend) | ~55+ |
| Test files (frontend) | ~10+ |
| Telegram bot specific files | ~32 |
| SQL Agent subsystem files | 10 |
| Semantic Layer files | 5 |
| Backend dependencies | ~30 |
| Frontend dependencies | ~25 |

### Lines of Code (approximate)

| Layer | LOC |
|-------|-----|
| Backend application logic | ~15,000 |
| Backend tests | ~10,000 |
| Frontend components & pages | ~8,000 |
| Frontend styles | ~2,500 |
| Database migrations | ~1,500 |
| Configuration & DevOps | ~500 |
| **Total** | **~37,500** |

---

## 6. Integration Points

| Integration | Protocol | Purpose |
|-------------|----------|---------|
| Meta Cloud API (v22.0) | REST + Webhooks | WhatsApp messaging & confirmation replies |
| Telegram Bot API | REST + Webhooks | AI conversational bot |
| DeepSeek API | REST (OpenAI-compatible) | LLM for NLU, NLG, SQL generation |
| Railway | Platform | Backend + PostgreSQL hosting |
| Vercel | Platform | Frontend hosting + preview deployments |

---

## 7. Operational Characteristics

- **Multi-environment**: Development (local), Staging (Railway + Vercel preview), Production (master)
- **Feature flags**: `FEATURE_TELEGRAM`, `FEATURE_NOTIFICATIONS` — modules can be disabled per environment
- **Background jobs**: 4 APScheduler jobs running in the FastAPI process (no separate worker)
- **Session persistence**: Telegram conversation sessions survive server restarts via PostgreSQL
- **Idempotency**: Notification queue uses idempotency keys to prevent duplicate sends
- **Retry logic**: Notification service retries failed sends; webhook handler retries once on failure
- **Graceful degradation**: When LLM or Telegram token is missing, system uses Fake providers (in-memory) instead of crashing

---

## 8. Key Technical Decisions

1. **No `python-telegram-bot` library** — raw HTTP to avoid dependency weight and have full control
2. **No langchain/llamaindex** — custom lightweight NLU pipeline keeps latency low and costs predictable
3. **LLM never touches the database directly** — all data access goes through deterministic SQL templates or validated SQL generation
4. **Hybrid NLU architecture** — LLM for understanding, deterministic code for execution (no hallucination in data responses)
5. **APScheduler in-process** — no Redis/Celery dependency, keeps infrastructure simple
6. **JSON permissions column** — flexible permission model without join tables
7. **Feature flags via env vars** — modules can be toggled without code changes
