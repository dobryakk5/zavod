# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Content Factory (Zavod) - A Django/Wagtail-based AI-powered social media content management and scheduling platform with multi-tenancy support. The system automatically collects fresh content on specified topics, generates new materials (text, images, video) using AI, allows editors to review and approve content via web interface, then publishes on schedule to social networks.

**Tech Stack**: Django 5.2, Wagtail 7.2, Celery, Redis, SQLite (dev), Python 3.13

**Planned AI Stack**: OpenAI GPT (text), Stability AI (images), Runway ML (video generation)

## Common Commands

All commands assume you're in the `backend/` directory with the virtual environment activated.

```bash
# Environment setup
python3 -m venv venv
source venv/bin/activate  # or `. venv/bin/activate`
pip install -r requirements.txt

# Database
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser

# Development server
python manage.py runserver

# Run Celery (in separate terminals)
celery -A config worker -l info
celery -A config beat -l info

# Testing
python manage.py test                    # All tests
python manage.py test core               # Specific app
python manage.py test core.tests.TestCase  # Specific test

# Static files
python manage.py collectstatic

# Docker
docker build -t content-factory .
docker run -p 8000:8000 content-factory
```

## Architecture

### System Pipeline

The complete content generation and publishing pipeline consists of four main stages:

1. **Content Aggregation** - Automated collection of fresh content from external sources
   - RSS/Atom feeds parsing (using `feedparser`)
   - News aggregator APIs (NewsAPI, Google News)
   - Social trends (Google Trends via `pytrends`)
   - Video metadata (YouTube Data API)
   - Web scraping when necessary (`requests` + `BeautifulSoup4` or `Scrapy`)

2. **AI Content Generation** - Creating original content from collected materials
   - **Text generation**: OpenAI GPT-4/GPT-3.5 via official SDK
   - **Image generation**: Stability AI (Stable Diffusion) via REST API
   - **Video generation**: Runway ML Gen-2/Gen-3 API for short-form video
   - All generation happens asynchronously via Celery tasks

3. **Moderation (CMS)** - Human review and editing interface
   - Web interface for reviewing generated content
   - Edit text, regenerate images/video, approve or reject
   - Schedule publications with specific timing per platform
   - (Note: Current implementation uses Wagtail/Django admin; Next.js frontend is planned)

4. **Automated Publishing** - Scheduled delivery to social platforms
   - **Instagram**: Graph API (2-step: create media container → publish)
   - **Telegram**: Bot API (`python-telegram-bot` library)
   - **YouTube**: Data API v3 with `publishAt` scheduling support
   - Celery Beat schedules tasks, workers execute API calls

**Data Flow**: External sources → Raw content DB → AI generation → Draft content (needs moderation) → Approved content → Scheduled tasks → Published to platforms

### Settings Structure

Uses split settings pattern:
- `config/settings/base.py` - Shared configuration
- `config/settings/dev.py` - Development (default)
- `config/settings/production.py` - Production with ManifestStaticFilesStorage

Set environment: `DJANGO_SETTINGS_MODULE=config.settings.production`

### Multi-Tenancy Model

The platform uses a client-based tenancy system where all content is scoped to a `Client`:

- **Client** - Top-level tenant entity
- **UserTenantRole** - Maps users to clients with roles (owner/editor/viewer)
- **SocialAccount** - Social media credentials per client
- **Post** - Content items linked to client
- **Schedule** - Publishing schedules linked to posts

**Key principle**: Most models should have a `client` ForeignKey. Always filter queries by client to maintain tenant isolation.

### Status-Based Workflow

**Post statuses**: `draft` → `ready` → `approved` → `scheduled` → `published`
**Schedule statuses**: `pending` → `in_progress` → `published`/`failed`

Status transitions are enforced in the models and should be respected when creating features.

### Async Task System

Celery tasks are in `core/tasks.py`:
- `process_due_schedules()` - Periodic task that finds and processes pending schedules
- `publish_schedule(schedule_id)` - Publishes content to social media platforms

Currently these are stubs. When implementing, ensure proper error handling and status updates.

### Admin Interfaces

- **Wagtail Admin**: `/admin/` - CMS interface
- **Django Admin**: `/django-admin/` - Model management

Project name is `config` (not `backend`) - this affects imports and WSGI configuration.

### Code Conventions

- Mix of Russian and English comments (Russian is common)
- Project root is `config/` instead of typical project name
- Empty `api/` directory exists for future REST API implementation
- Empty `core/tasks/` directory for additional task modules

### Key Technical Details

**Content Aggregation**:
- Celery tasks run on schedule (via Celery Beat) to collect fresh content
- Each source type (RSS, API, scraping) is a separate task
- Collected data stored with metadata: source, timestamp, topic/keywords
- Deduplication via hashing/ID tracking to avoid re-collecting old content

**AI Generation Orchestration**:
- Text → Image → Video (sequential or parallel via Celery chains)
- Each generation step is a separate task for independent scaling
- Long-running tasks (especially video) handled asynchronously
- Generated media stored in object storage (planned: S3/MinIO) with URLs in DB

**Database Schema**:
- **Content** table: title, text, image_url, video_url, status, topic, timestamps
- **SourceData** (optional): raw collected data for transparency
- **PublishQueue** or status fields: track scheduled publications per platform
- PostgreSQL recommended for production (JSONB support for AI metadata)

**Publishing Strategy**:
- Instagram: Two-step process (upload media → publish), no native scheduling
- Telegram: Direct bot API calls at scheduled time
- YouTube: Upload with `publishAt` parameter (platform handles timing)
- Celery tasks created with ETA for precise timing
- Idempotent tasks with retry logic and status tracking

**Scaling Considerations**:
- Separate Celery queues: `ai` (generation), `publish` (posting), `scrape` (collection)
- GPU workers for AI tasks, lightweight workers for API calls
- Redis for broker (Celery), PostgreSQL for data, S3 for media
- Containerization via Docker, orchestration via Docker Compose or Kubernetes

## Important Notes

### Security Issues to Address

- `SECRET_KEY` is hardcoded as "change-me" in `base.py` - should use environment variable
- `ALLOWED_HOSTS = ["*"]` in base settings - should be restricted in production
- `DEBUG = True` in base settings - ensure it's False in production

### Known Issues

- `Dockerfile` references `backend.wsgi:application` but should be `config.wsgi:application` (will cause deployment failure)

### Feature Completeness

**Currently Implemented**:
- Basic Django/Wagtail setup with multi-tenancy models
- Celery + Redis configuration
- Core data models (Client, Post, SocialAccount, Schedule)

**In Development** (per architecture document):
- Content aggregation module (RSS, Google Trends, News APIs)
- AI content generation (OpenAI, Stability AI, Runway ML integrations)
- Social media publishing implementations (Instagram Graph API, Telegram Bot API, YouTube Data API)
- Next.js moderation frontend

**Current Stubs**:
- `publish_schedule()` in `core/tasks.py` - needs platform-specific implementations
- API directory exists but is empty
- `core/tasks/` directory ready for additional task modules

## Testing Notes

Uses Wagtail's `WagtailPageTestCase` for page tests. Example in `home/tests.py`. When writing tests for core functionality, use Django's standard `TestCase` with proper client isolation.