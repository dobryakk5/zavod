# Content Factory API Documentation

## Overview

This document describes the REST API endpoints for the Content Factory (Zavod) platform. All endpoints use JWT authentication via cookies.

## Base URL

```
http://localhost:8000/api/
```

## Authentication

All API endpoints (except auth endpoints) require JWT authentication. Tokens are stored in HttpOnly cookies (`access_token`, `refresh_token`).

### Endpoints

#### `POST /api/auth/telegram`
Authenticate via Telegram

**Request Body:**
```json
{
  "id": "123456789",
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe",
  "photo_url": "https://..."
}
```

**Response:** Sets cookies and returns user data

---

#### `PUT /api/auth/telegram`
Dev mode login (DEBUG=True only)

**Response:** Logs in as `dev_user` connected to `zavod` client

---

#### `POST /api/auth/logout/`
Logout (clear cookies)

---

## Client Endpoints

#### `GET /api/client/info/`
Get current client info and user role

**Response:**
```json
{
  "client": {
    "id": 1,
    "name": "My Client",
    "slug": "123456789"
  },
  "role": "owner"
}
```

---

#### `GET /api/client/summary/`
Get client statistics

**Response:**
```json
{
  "total_posts": 42,
  "posts_scheduled": 10,
  "posts_published": 25,
  "by_platform": [
    {"platform": "telegram", "count": 15},
    {"platform": "instagram", "count": 10}
  ]
}
```

---

#### `GET /api/client/settings/`
Get client settings (excludes id and name)

#### `PATCH /api/client/settings/`
Update client settings

---

## Posts API

### `GET /api/posts/`
List all posts for current client

**Query Parameters:**
- `status` - Filter by status (draft, ready, approved, scheduled, published)
- `platform` - Filter by platform

**Response:**
```json
[
  {
    "id": 1,
    "title": "My Post",
    "status": "draft",
    "created_at": "2025-12-01T10:00:00Z",
    "platforms": ["telegram", "instagram"]
  }
]
```

---

### `GET /api/posts/{id}/`
Get detailed post information

**Response:**
```json
{
  "id": 1,
  "title": "My Post",
  "text": "Post content...",
  "image": "http://localhost:8000/media/post_images/image.jpg",
  "video": null,
  "status": "draft",
  "tags": ["#ai", "#content"],
  "source_links": ["https://example.com"],
  "publish_text": true,
  "publish_image": true,
  "publish_video": false,
  "story": null,
  "episode_number": null,
  "generated_by": "grok-4.1-fast",
  "regeneration_count": 0,
  "created_at": "2025-12-01T10:00:00Z",
  "updated_at": "2025-12-01T10:00:00Z"
}
```

---

### `POST /api/posts/`
Create a new post

**Request Body:**
```json
{
  "title": "My New Post",
  "text": "Content...",
  "status": "draft"
}
```

---

### `PATCH /api/posts/{id}/`
Update a post

---

### `DELETE /api/posts/{id}/`
Delete a post

---

### `POST /api/posts/{id}/generate_image/`
Generate image for post using AI

**Request Body:**
```json
{
  "model": "pollinations"  // pollinations, nanobanana, huggingface, flux2
}
```

**Response:**
```json
{
  "success": true,
  "message": "Image generation started with model: pollinations",
  "task_id": "abc-123"
}
```

---

### `POST /api/posts/{id}/generate_video/`
Generate video from post image

**⚠️ Requires:** Dev mode (`DEBUG=True`) OR zavod client

**Response:**
```json
{
  "success": true,
  "message": "Video generation started",
  "task_id": "def-456"
}
```

---

### `POST /api/posts/{id}/regenerate_text/`
Regenerate post text using AI

---

### `POST /api/posts/{id}/quick_publish/`
Quick publish post to a social account

**Request Body:**
```json
{
  "social_account_id": 1
}
```

---

## Topics API

### `GET /api/topics/`
List all topics

### `GET /api/topics/{id}/`
Get topic details (includes `enabled_sources`)

### `POST /api/topics/`
Create a new topic

**Request Body:**
```json
{
  "name": "AI News",
  "keywords": ["artificial intelligence", "machine learning"],
  "is_active": true,
  "use_google_trends": true,
  "use_telegram": true,
  "use_rss": false,
  "use_youtube": false,
  "use_instagram": false,
  "use_vkontakte": false
}
```

### `PATCH /api/topics/{id}/`
Update a topic

### `DELETE /api/topics/{id}/`
Delete a topic

### `POST /api/topics/{id}/discover_content/`
Discover new content (trends) from enabled sources

**Response:**
```json
{
  "success": true,
  "message": "Content discovery started for topic: AI News",
  "task_id": "ghi-789"
}
```

### `POST /api/topics/{id}/generate_posts/`
Generate posts from all unused trends for this topic

### `POST /api/topics/{id}/generate_seo/`
Generate SEO keywords for this topic

---

## Trends API

### `GET /api/trends/`
List all trends

**Query Parameters:**
- `topic` - Filter by topic ID
- `unused` - Show only unused trends (true/false)

### `GET /api/trends/{id}/`
Get trend details

### `DELETE /api/trends/{id}/`
Delete a trend

### `POST /api/trends/{id}/generate_post/`
Generate a single post from this trend

### `POST /api/trends/{id}/generate_story/`
Generate a story (mini-series) from this trend

**Request Body:**
```json
{
  "episode_count": 3
}
```

---

## Stories API

### `GET /api/stories/`
List all stories

### `GET /api/stories/{id}/`
Get story details (includes episodes array)

### `POST /api/stories/`
Create a new story

### `PATCH /api/stories/{id}/`
Update a story

### `DELETE /api/stories/{id}/`
Delete a story

### `POST /api/stories/{id}/generate_posts/`
Generate posts from story episodes

---

## Templates API

### `GET /api/templates/`
List all content templates

### `GET /api/templates/{id}/`
Get template details

### `POST /api/templates/`
Create a new template

**⚠️ Note:** Basic fields (`type`, `tone`, `length`, `language`) are **read-only** after creation

### `PATCH /api/templates/{id}/`
Update a template (only advanced fields can be edited)

### `DELETE /api/templates/{id}/`
Delete a template

---

## Schedules API

### `GET /api/schedules/`
List all schedules

### `GET /api/schedules-manage/{id}/`
Get schedule details

### `POST /api/schedules-manage/`
Create a new schedule

### `PATCH /api/schedules-manage/{id}/`
Update a schedule

### `DELETE /api/schedules-manage/{id}/`
Delete a schedule

### `POST /api/schedules-manage/{id}/publish_now/`
Publish this schedule immediately

---

## Social Accounts API

### `GET /api/social-accounts/`
List all social accounts for current client

### `GET /api/social-accounts/{id}/`
Get social account details

### `POST /api/social-accounts/`
Add a new social account

**Request Body:**
```json
{
  "platform": "telegram",
  "name": "My Channel",
  "access_token": "token...",
  "extra": {
    "channel_id": "@mychannel"
  }
}
```

### `PATCH /api/social-accounts/{id}/`
Update a social account

### `DELETE /api/social-accounts/{id}/`
Delete a social account

---

## Frontend Usage Examples

### Using API Client

```typescript
import { postsApi, topicsApi, useCanGenerateVideo, useRole } from '@/lib';

// List posts
const posts = await postsApi.list({ status: 'draft' });

// Get post details
const post = await postsApi.get(1);

// Generate image
await postsApi.generateImage(1, 'pollinations');

// Generate video (requires permission)
await postsApi.generateVideo(1);

// Create topic
const topic = await topicsApi.create({
  name: 'AI News',
  keywords: ['AI', 'ML'],
  is_active: true,
  use_google_trends: true,
});

// Discover content
await topicsApi.discoverContent(topic.id);
```

### Using Hooks

```typescript
import { useCanGenerateVideo, useRole, useClient } from '@/lib/hooks';

function PostActions({ postId }: { postId: number }) {
  const { canGenerateVideo, loading } = useCanGenerateVideo();
  const { canEdit } = useRole();
  const { data: clientInfo } = useClient();

  return (
    <div>
      {canEdit && (
        <Button onClick={() => postsApi.generateImage(postId, 'pollinations')}>
          Generate Image
        </Button>
      )}

      <Button
        disabled={!canGenerateVideo || loading}
        onClick={() => postsApi.generateVideo(postId)}
      >
        {canGenerateVideo ? 'Generate Video' : 'Generate Video (Dev only)'}
      </Button>

      <p>Client: {clientInfo?.client.name}</p>
      <p>Your role: {clientInfo?.role}</p>
    </div>
  );
}
```

---

## Permissions

### Roles

- **owner** - Full access to all operations
- **editor** - Can create, edit, delete content and trigger generation
- **viewer** - Read-only access

### Special Permissions

- **Video Generation**: Only available in `DEBUG=True` mode OR for `zavod` client (slug='zavod')
- **Template Basic Fields**: `type`, `tone`, `length`, `language` are read-only and cannot be edited

---

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK` - Success
- `201 Created` - Resource created
- `204 No Content` - Success with no response body
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Permission denied
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

Error response format:
```json
{
  "detail": "Error message here"
}
```
