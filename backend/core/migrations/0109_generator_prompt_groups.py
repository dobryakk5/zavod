from django.db import migrations, models


PROMPT_GROUPS = {
    "repair_json_structure": "service",
    "hook_title_ru": "posts",
    "hook_title_en": "posts",
    "hook_title_seo_keyword_line": "posts",
    "post_text_seo_base": "posts",
    "post_text_trend_base": "posts",
    "post_text_hashtags_block": "posts",
    "post_text_seo_block": "posts",
    "post_text_wordstat_block": "posts",
    "post_text_additional_block": "posts",
    "post_text_response_format_block": "posts",
    "refine_text_wordstat": "wordstat",
    "seo_keywords_pains": "seo",
    "seo_keywords_desires": "seo",
    "seo_keywords_objections": "seo",
    "seo_keywords_avatar": "seo",
    "seo_keywords_list": "seo",
    "book_recommendations": "posts",
    "product_requirements_prompt": "products",
    "product_block_prompt": "products",
    "story_episodes_prompt": "posts",
    "story_post_from_episode_prompt": "posts",
    "story_post_episode_first_line": "posts",
    "story_post_episode_last_line": "posts",
    "story_post_episode_middle_line": "posts",
    "image_prompt_base": "media",
    "image_prompt_admin_block": "media",
    "video_prompt_base_instructions": "media",
    "video_prompt_admin_block": "media",
    "video_prompt_main": "media",
    "video_prompt_fallback": "media",
    "seo_wordstat_seed_groups": "wordstat",
    "seo_wordstat_cluster": "wordstat",
    "seo_wordstat_cluster_existing_rules": "wordstat",
    "seo_wordstat_cluster_existing_clusters": "wordstat",
    "seo_text_analysis": "seo",
    "seo_text_rewrite_note_on": "seo",
    "seo_text_rewrite_note_off": "seo",
}


def assign_prompt_groups(apps, schema_editor):
    GeneratorPrompt = apps.get_model("core", "GeneratorPrompt")
    for code, group in PROMPT_GROUPS.items():
        GeneratorPrompt.objects.filter(code=code).update(group=group)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0108_update_wordstat_seed_prompt"),
    ]

    operations = [
        migrations.AddField(
            model_name="generatorprompt",
            name="group",
            field=models.CharField(
                choices=[
                    ("posts", "Посты"),
                    ("seo", "SEO"),
                    ("articles", "Статьи"),
                    ("wordstat", "Wordstat"),
                    ("products", "Продукты"),
                    ("media", "Медиа"),
                    ("service", "Служебные"),
                ],
                default="posts",
                max_length=20,
            ),
        ),
        migrations.RunPython(assign_prompt_groups, reverse_code=migrations.RunPython.noop),
    ]
