from django.db import migrations, models


def forwards(apps, schema_editor):
    Article = apps.get_model("core", "Article")
    Article.objects.filter(status="draft").update(status="wordstat")
    Article.objects.filter(status="options_ready").update(status="context_suggested")


def backwards(apps, schema_editor):
    Article = apps.get_model("core", "Article")
    Article.objects.filter(status="wordstat").update(status="draft")
    Article.objects.filter(status="context_suggested").update(status="options_ready")
    Article.objects.filter(status="context_selected").update(status="options_ready")
    Article.objects.filter(status="article_ready").update(status="outline_ready")
    Article.objects.filter(status="result_edited").update(status="outline_ready")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0092_article_result_html"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="status",
            field=models.CharField(
                choices=[
                    ("wordstat", "Wordstat"),
                    ("context_suggested", "Context Suggested"),
                    ("context_selected", "Context Selected"),
                    ("outline_ready", "Outline Ready"),
                    ("article_ready", "Article Ready"),
                    ("result_edited", "Result Edited"),
                    ("failed", "Failed"),
                ],
                default="wordstat",
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
