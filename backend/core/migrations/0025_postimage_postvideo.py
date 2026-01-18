from django.db import migrations, models
import django.db.models.deletion


def copy_post_media(apps, schema_editor):
    Post = apps.get_model("core", "Post")
    PostImage = apps.get_model("core", "PostImage")
    PostVideo = apps.get_model("core", "PostVideo")

    for post in Post.objects.all():
        image_field = getattr(post, "image", None)
        if image_field and image_field.name:
            PostImage.objects.create(
                post=post,
                image=image_field.name,
                order=0,
            )

        video_field = getattr(post, "video", None)
        if video_field and video_field.name:
            PostVideo.objects.create(
                post=post,
                video=video_field.name,
                order=0,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0024_client_telegram_client_channel"),
    ]

    operations = [
        migrations.CreateModel(
            name="PostImage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="post_images/")),
                ("alt_text", models.CharField(blank=True, max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="core.post")),
            ],
            options={
                "ordering": ("order", "id"),
                "verbose_name": "Post Image",
                "verbose_name_plural": "Post Images",
            },
        ),
        migrations.CreateModel(
            name="PostVideo",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("video", models.FileField(upload_to="post_videos/")),
                ("caption", models.CharField(blank=True, max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="videos", to="core.post")),
            ],
            options={
                "ordering": ("order", "id"),
                "verbose_name": "Post Video",
                "verbose_name_plural": "Post Videos",
            },
        ),
        migrations.RunPython(copy_post_media, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="post",
            name="image",
        ),
        migrations.RemoveField(
            model_name="post",
            name="video",
        ),
    ]
