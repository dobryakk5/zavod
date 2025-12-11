# API Documentation

This document describes all available API endpoints in the Zavod project.

## Table of Contents

1. [Authentication](#authentication)
2. [Client Management](#client-management)
3. [Content Management](#content-management)
4. [Analytics](#analytics)
5. [Response Formats](#response-formats)
6. [Error Handling](#error-handling)

## Authentication

### POST /api/auth/telegram

Authenticate user via Telegram.

**Request Body:**
```json
{
  "id": 123456789,
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe",
  "photo_url": "https://t.me/i/userpic/320/username.jpg"
}
```

**Response:**
```json
{
  "user": {
    "telegramId": "123456789",
    "firstName": "John",
    "lastName": "Doe",
    "username": "johndoe",
    "photoUrl": "https://t.me/i/userpic/320/username.jpg",
    "authDate": "2024-01-01T00:00:00Z",
    "isDev": false
  }
}
```

### PUT /api/auth/telegram

Dev mode login - auto-create/login as dev user (DEBUG mode only).

**Response:**
```json
{
  "user": {
    "telegramId": "1",
    "firstName": "Dev",
    "lastName": "User",
    "username": "dev_user",
    "photoUrl": null,
    "authDate": "2024-01-01T00:00:00Z",
    "isDev": true
  }
}
```

### DELETE /api/auth/telegram

Logout user.

**Response:**
```json
{
  "success": true
}
```

### POST /api/auth/token/

Login with username/password.

**Request Body:**
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### POST /api/auth/refresh/

Refresh JWT token.

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### POST /api/auth/logout/

Logout user and clear cookies.

**Response:**
```json
{
  "success": true
}
```

## Client Management

### GET /api/client/info/

Get current client info and user role.

**Response:**
```json
{
  "client": {
    "id": 1,
    "name": "Client Name",
    "slug": "client-slug"
  },
  "role": "owner"
}
```

### GET /api/client/summary/

Get client summary statistics.

**Response:**
```json
{
  "total_posts": 150,
  "posts_scheduled": 25,
  "posts_published": 120,
  "by_platform": [
    {
      "platform": "instagram",
      "count": 50
    },
    {
      "platform": "telegram",
      "count": 75
    }
  ]
}
```

### GET /api/client/settings/

Get current client settings.

**Response:**
```json
{
  "slug": "client-slug",
  "timezone": "Europe/Helsinki",
  "avatar": "Портрет целевой аудитории...",
  "pains": "Проблемы и боли...",
  "desires": "Желания и цели...",
  "objections": "Страхи и возражения...",
  "telegram_api_id": "123456",
  "telegram_api_hash": "abcdef123456",
  "telegram_source_channels": "@channel1, @channel2",
  "rss_source_feeds": "https://example.com/rss",
  "youtube_api_key": "AIza...",
  "youtube_source_channels": "UC123, UC456",
  "instagram_access_token": "IGQ...",
  "instagram_source_accounts": "user1, user2",
  "vkontakte_access_token": "vk1...",
  "vkontakte_source_groups": "group1, group2"
}
```

### PATCH /api/client/settings/

Update client settings.

**Request Body:**
```json
{
  "timezone": "Europe/Moscow",
  "avatar": "Новый портрет ЦА",
  "pains": "Новые боли",
  "desires": "Новые желания",
  "objections": "Новые возражения"
}
```

**Response:**
```json
{
  "slug": "client-slug",
  "timezone": "Europe/Moscow",
  "avatar": "Новый портрет ЦА",
  "pains": "Новые боли",
  "desires": "Новые желания",
  "objections": "Новые возражения",
  // ... остальные поля
}
```

## Content Management

### Posts

#### GET /api/posts/

List all posts for the current client.

**Query Parameters:**
- `status` (optional): Filter by status (draft, ready, approved, scheduled, published)
- `platform` (optional): Filter by platform (instagram, telegram, youtube)

**Response:**
```json
[
  {
    "id": 1,
    "title": "Post Title",
    "status": "published",
    "created_at": "2024-01-01T00:00:00Z",
    "platforms": ["instagram", "telegram"]
  }
]
```

#### GET /api/posts/{id}/

Get detailed information about a post.

**Response:**
```json
{
  "id": 1,
  "title": "Post Title",
  "text": "Post content...",
  "status": "published",
  "tags": ["ai", "instagram"],
  "source_links": ["https://example.com"],
  "publish_text": true,
  "publish_image": true,
  "publish_video": false,
  "story": null,
  "episode_number": null,
  "generated_by": "openai",
  "regeneration_count": 0,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "images": [
    {
      "id": 1,
      "image": "https://example.com/image.jpg",
      "alt_text": "Image description",
      "order": 0
    }
  ],
  "videos": []
}
```

#### POST /api/posts/

Create a new post.

**Request Body:**
```json
{
  "title": "Post Title",
  "text": "Post content...",
  "status": "draft",
  "tags": ["ai", "instagram"],
  "source_links": ["https://example.com"],
  "publish_text": true,
  "publish_image": true,
  "publish_video": false,
  "story": null,
  "episode_number": null
}
```

**Response:**
```json
{
  "id": 1,
  "title": "Post Title",
  "text": "Post content...",
  // ... остальные поля
}
```

#### PATCH /api/posts/{id}/

Update an existing post.

**Request Body:**
```json
{
  "title": "Updated Title",
  "text": "Updated content..."
}
```

**Response:**
```json
{
  "id": 1,
  "title": "Updated Title",
  // ... остальные поля
}
```

#### DELETE /api/posts/{id}/

Delete a post.

**Response:**
```json
{}
```

#### POST /api/posts/{id}/generate_image/

Generate image for post using AI.

**Request Body:**
```json
{
  "model": "pollinations"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Image generation started with model: pollinations",
  "task_id": "task_123"
}
```

#### POST /api/posts/{id}/generate_video/

Generate video from post image.

**Request Body:**
```json
{
  "method": "wan",
  "source": "image"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Video generation started (wan/image)",
  "task_id": "task_456"
}
```

#### POST /api/posts/{id}/regenerate_text/

Regenerate post text using AI.

**Response:**
```json
{
  "success": true,
  "message": "Text regeneration started",
  "task_id": "task_789"
}
```

#### POST /api/posts/{id}/quick_publish/

Quick publish post to a social account.

**Request Body:**
```json
{
  "social_account_id": 1
}
```

**Response:**
```json
{
  "success": true,
  "message": "Publishing started",
  "schedule_id": 1,
  "task_id": "task_101"
}
```

### Topics

#### GET /api/topics/

List all topics for the current client.

**Response:**
```json
[
  {
    "id": 1,
    "name": "Topic Name",
    "keywords": ["keyword1", "keyword2"],
    "is_active": true,
    "use_google_trends": true,
    "use_telegram": false,
    "use_rss": false,
    "use_youtube": false,
    "use_instagram": false,
    "use_vkontakte": false,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### GET /api/topics/{id}/

Get detailed information about a topic.

**Response:**
```json
{
  "id": 1,
  "name": "Topic Name",
  "keywords": ["keyword1", "keyword2"],
  "is_active": true,
  "use_google_trends": true,
  "use_telegram": false,
  "use_rss": false,
  "use_youtube": false,
  "use_instagram": false,
  "use_vkontakte": false,
  "enabled_sources": ["google_trends"],
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### POST /api/topics/

Create a new topic.

**Request Body:**
```json
{
  "name": "New Topic",
  "keywords": ["keyword1", "keyword2"],
  "is_active": true,
  "use_google_trends": true,
  "use_telegram": false,
  "use_rss": false,
  "use_youtube": false,
  "use_instagram": false,
  "use_vkontakte": false
}
```

**Response:**
```json
{
  "id": 1,
  "name": "New Topic",
  // ... остальные поля
}
```

#### PATCH /api/topics/{id}/

Update an existing topic.

**Request Body:**
```json
{
  "name": "Updated Topic",
  "keywords": ["new_keyword1", "new_keyword2"]
}
```

**Response:**
```json
{
  "id": 1,
  "name": "Updated Topic",
  // ... остальные поля
}
```

#### DELETE /api/topics/{id}/

Delete a topic.

**Response:**
```json
{}
```

#### POST /api/topics/{id}/discover_content/

Discover new content (trends) for this topic from enabled sources.

**Response:**
```json
{
  "success": true,
  "message": "Content discovery started for topic: Topic Name",
  "task_id": "task_123"
}
```

#### POST /api/topics/{id}/generate_posts/

Generate posts from all unused trends for this topic.

**Response:**
```json
{
  "success": true,
  "message": "Post generation started for topic: Topic Name",
  "task_id": "task_456"
}
```

#### POST /api/topics/{id}/generate_seo/

Generate SEO keywords for this topic.

**Response:**
```json
{
  "success": true,
  "message": "SEO keyword generation started for client: Client Name",
  "task_id": "task_789"
}
```

### Trends

#### GET /api/trends/

List all trends for the current client.

**Query Parameters:**
- `topic` (optional): Filter by topic ID
- `unused` (optional): Filter unused trends only

**Response:**
```json
[
  {
    "id": 1,
    "topic": 1,
    "topic_name": "Topic Name",
    "source": "google_trends",
    "title": "Trend Title",
    "description": "Trend description...",
    "url": "https://example.com",
    "relevance_score": 100,
    "used_for_post": null,
    "used_for_post_title": null,
    "discovered_at": "2024-01-01T00:00:00Z"
  }
]
```

#### GET /api/trends/{id}/

Get detailed information about a trend.

**Response:**
```json
{
  "id": 1,
  "topic": 1,
  "topic_name": "Topic Name",
  "source": "google_trends",
  "title": "Trend Title",
  "description": "Trend description...",
  "url": "https://example.com",
  "relevance_score": 100,
  "extra": {},
  "used_for_post": null,
  "discovered_at": "2024-01-01T00:00:00Z"
}
```

#### DELETE /api/trends/{id}/

Delete a trend.

**Response:**
```json
{}
```

#### POST /api/trends/{id}/generate_post/

Generate a single post from this trend.

**Response:**
```json
{
  "success": true,
  "message": "Post generation started from trend: Trend Title",
  "task_id": "task_123"
}
```

#### POST /api/trends/{id}/generate_story/

Generate a story (mini-series) from this trend.

**Request Body:**
```json
{
  "episode_count": 3
}
```

**Response:**
```json
{
  "success": true,
  "message": "Story generation started with 3 episodes",
  "task_id": "task_456"
}
```

### Stories

#### GET /api/stories/

List all stories for the current client.

**Response:**
```json
[
  {
    "id": 1,
    "title": "Story Title",
    "trend_item": 1,
    "trend_title": "Trend Title",
    "template": 1,
    "template_name": "Template Name",
    "episode_count": 5,
    "status": "completed",
    "generated_by": "openai",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### GET /api/stories/{id}/

Get detailed information about a story.

**Response:**
```json
{
  "id": 1,
  "title": "Story Title",
  "trend_item": 1,
  "trend_title": "Trend Title",
  "template": 1,
  "template_name": "Template Name",
  "episode_count": 5,
  "episodes": [
    {
      "order": 1,
      "title": "Episode 1 Title"
    }
  ],
  "status": "completed",
  "generated_by": "openai",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### POST /api/stories/

Create a new story.

**Request Body:**
```json
{
  "title": "New Story",
  "trend_item": 1,
  "template": 1,
  "episode_count": 5
}
```

**Response:**
```json
{
  "id": 1,
  "title": "New Story",
  // ... остальные поля
}
```

#### PATCH /api/stories/{id}/

Update an existing story.

**Request Body:**
```json
{
  "title": "Updated Story",
  "episode_count": 7
}
```

**Response:**
```json
{
  "id": 1,
  "title": "Updated Story",
  // ... остальные поля
}
```

#### DELETE /api/stories/{id}/

Delete a story.

**Response:**
```json
{}
```

#### POST /api/stories/{id}/generate_posts/

Generate posts from story episodes.

**Response:**
```json
{
  "success": true,
  "message": "Generating posts from story: Story Title",
  "task_id": "task_123"
}
```

### Templates

#### GET /api/templates/

List all content templates for the current client.

**Response:**
```json
[
  {
    "id": 1,
    "name": "Template Name",
    "type": "selling",
    "tone": "professional",
    "length": "medium",
    "language": "ru",
    "seo_prompt_template": "SEO prompt...",
    "trend_prompt_template": "Trend prompt...",
    "additional_instructions": "Additional instructions...",
    "is_default": true,
    "include_hashtags": true,
    "max_hashtags": 5,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

#### GET /api/templates/{id}/

Get detailed information about a template.

**Response:**
```json
{
  "id": 1,
  "name": "Template Name",
  "type": "selling",
  "tone": "professional",
  "length": "medium",
  "language": "ru",
  "seo_prompt_template": "SEO prompt...",
  "trend_prompt_template": "Trend prompt...",
  "additional_instructions": "Additional instructions...",
  "is_default": true,
  "include_hashtags": true,
  "max_hashtags": 5,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### POST /api/templates/

Create a new content template.

**Request Body:**
```json
{
  "name": "New Template",
  "type": "selling",
  "tone": "professional",
  "length": "medium",
  "language": "ru",
  "seo_prompt_template": "SEO prompt...",
  "trend_prompt_template": "Trend prompt...",
  "additional_instructions": "Additional instructions...",
  "is_default": false,
  "include_hashtags": true,
  "max_hashtags": 5
}
```

**Response:**
```json
{
  "id": 1,
  "name": "New Template",
  // ... остальные поля
}
```

#### PATCH /api/templates/{id}/

Update an existing template.

**Request Body:**
```json
{
  "name": "Updated Template",
  "type": "expert",
  "tone": "friendly"
}
```

**Response:**
```json
{
  "id": 1,
  "name": "Updated Template",
  // ... остальные поля
}
```

#### DELETE /api/templates/{id}/

Delete a template.

**Response:**
```json
{}
```

### Schedules

#### GET /api/schedules/

List all schedules for the current client.

**Response:**
```json
[
  {
    "id": 1,
    "platform": "instagram",
    "post_title": "Post Title",
    "scheduled_at": "2024-01-01T00:00:00Z",
    "status": "pending"
  }
]
```

#### GET /api/schedules-manage/{id}/

Get detailed information about a schedule.

**Response:**
```json
{
  "id": 1,
  "platform": "instagram",
  "post_title": "Post Title",
  "scheduled_at": "2024-01-01T00:00:00Z",
  "status": "pending"
}
```

#### POST /api/schedules-manage/

Create a new schedule.

**Request Body:**
```json
{
  "post": 1,
  "social_account": 1,
  "scheduled_at": "2024-01-01T00:00:00Z",
  "status": "pending"
}
```

**Response:**
```json
{
  "id": 1,
  "platform": "instagram",
  "post_title": "Post Title",
  // ... остальные поля
}
```

#### PATCH /api/schedules-manage/{id}/

Update an existing schedule.

**Request Body:**
```json
{
  "scheduled_at": "2024-01-02T00:00:00Z",
  "status": "scheduled"
}
```

**Response:**
```json
{
  "id": 1,
  "platform": "instagram",
  "post_title": "Post Title",
  // ... остальные поля
}
```

#### DELETE /api/schedules-manage/{id}/

Delete a schedule.

**Response:**
```json
{}
```

#### POST /api/schedules-manage/{id}/publish_now/

Publish this schedule immediately.

**Response:**
```json
{
  "success": true,
  "message": "Publishing started",
  "task_id": "task_123"
}
```

### Social Accounts

#### GET /api/social-accounts/

List all social accounts for the current client.

**Response:**
```json
[
  {
    "id": 1,
    "platform": "instagram",
    "name": "Instagram Account",
    "username": "username",
    "is_active": true,
    "extra": {},
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### GET /api/social-accounts/{id}/

Get detailed information about a social account.

**Response:**
```json
{
  "id": 1,
  "platform": "instagram",
  "name": "Instagram Account",
  "username": "username",
  "is_active": true,
  "extra": {},
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### POST /api/social-accounts/

Add a new social account.

**Request Body:**
```json
{
  "platform": "instagram",
  "name": "New Account",
  "username": "newusername",
  "access_token": "token123",
  "refresh_token": "refreshtoken123",
  "extra": {}
}
```

**Response:**
```json
{
  "id": 1,
  "platform": "instagram",
  "name": "New Account",
  // ... остальные поля
}
```

#### PATCH /api/social-accounts/{id}/

Update an existing social account.

**Request Body:**
```json
{
  "name": "Updated Account",
  "is_active": false
}
```

**Response:**
```json
{
  "id": 1,
  "platform": "instagram",
  "name": "Updated Account",
  // ... остальные поля
}
```

#### DELETE /api/social-accounts/{id}/

Delete a social account.

**Response:**
```json
{}
```

### Post Types

#### GET /api/post-types/

List all post types.

**Response:**
```json
[
  {
    "id": 1,
    "value": "selling",
    "label": "Продающий",
    "is_default": true,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### POST /api/post-types/

Create a new post type.

**Request Body:**
```json
{
  "value": "custom_type",
  "label": "Custom Type"
}
```

**Response:**
```json
{
  "id": 2,
  "value": "custom_type",
  "label": "Custom Type",
  "is_default": false,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Post Tones

#### GET /api/post-tones/

List all post tones.

**Response:**
```json
[
  {
    "id": 1,
    "value": "professional",
    "label": "Профессиональный",
    "is_default": true,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### POST /api/post-tones/

Create a new post tone.

**Request Body:**
```json
{
  "value": "friendly",
  "label": "Дружественный"
}
```

**Response:**
```json
{
  "id": 2,
  "value": "friendly",
  "label": "Дружественный",
  "is_default": false,
  "created_at": "2024-01-01T00:00:00Z"
}
```

## Analytics

### POST /api/tg_channel/

Unified endpoint for Telegram channel operations.

**Request Body for Analysis:**
```json
{
  "action": "analyze",
  "channel_url": "https://t.me/example",
  "channel_type": "telegram"
}
```

**Request Body for Validation:**
```json
{
  "action": "validate",
  "channel_url": "https://t.me/example",
  "channel_type": "telegram"
}
```

**GET Request Body for Status:**
```json
{
  "action": "status",
  "task_id": "task_123"
}
```

**Response for Analysis:**
```json
{
  "success": true,
  "message": "Channel analysis started",
  "task_id": "mock_task_123"
}
```

**Response for Validation:**
```json
{
  "valid": true,
  "message": "Channel URL is valid"
}
```

**Response for Status:**
```json
{
  "task_id": "task_123",
  "status": "completed",
  "progress": 100,
  "result": {
    "channel_name": "Test Channel",
    "subscribers": 1000,
    "avg_views": 500,
    "avg_reach": 400,
    "avg_engagement": 8.5,
    "top_posts": [
      {
        "title": "Top Post 1",
        "views": 1000,
        "engagement": 12.5,
        "url": "https://t.me/test/1"
      }
    ],
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "topics": ["topic1", "topic2"],
    "content_types": ["photo", "video", "text"],
    "posting_schedule": [
      {"day": "Monday", "hour": 10, "posts_count": 2},
      {"day": "Tuesday", "hour": 14, "posts_count": 1}
    ]
  }
}
```

## Response Formats

### Success Response

Most endpoints return a success response with the following format:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "task_id": "optional_task_id"
}
```

### Data Response

For GET requests that return data:

```json
{
  "field1": "value1",
  "field2": "value2",
  // ... additional fields
}
```

### List Response

For endpoints that return lists:

```json
[
  {
    "id": 1,
    "field1": "value1",
    "field2": "value2"
  },
  {
    "id": 2,
    "field1": "value3",
    "field2": "value4"
  }
]
```

## Error Handling

### Error Response Format

All error responses follow this format:

```json
{
  "success": false,
  "error": "Error message describing what went wrong"
}
```

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `204` - No Content
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `500` - Internal Server Error

### Common Error Messages

- `"Authentication required"` - User not authenticated
- `"Insufficient permissions"` - User lacks required role
- `"channel_url and channel_type are required"` - Missing required fields
- `"Unknown action: {action}"` - Invalid action parameter
- `"Task not found"` - Task ID doesn't exist
- `"Post not found"` - Post ID doesn't exist
- `"Topic not found"` - Topic ID doesn't exist
- `"Trend not found"` - Trend ID doesn't exist
- `"Story not found"` - Story ID doesn't exist
- `"Template not found"` - Template ID doesn't exist
- `"Schedule not found"` - Schedule ID doesn't exist
- `"Social account not found"` - Social account ID doesn't exist

## Authentication Requirements

Most endpoints require authentication via JWT token. Include the token in the Authorization header:

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

Or use the cookie-based authentication by first logging in via `/api/auth/telegram`.

## Permissions

- **Owner**: Full access to all operations
- **Editor**: Can create, update, delete most resources (except client settings)
- **Viewer**: Read-only access to most resources

Some operations require specific permissions:
- Client settings: Owner or Editor only
- Post generation: Owner or Editor only
- Schedule publishing: Owner or Editor only
