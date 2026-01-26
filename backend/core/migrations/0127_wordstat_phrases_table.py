from django.db import migrations, models
import django.db.models.deletion


def forwards_fill_wordstat_phrases(apps, schema_editor):
    SemanticPhrase = apps.get_model("core", "SemanticPhrase")
    WordstatPhrase = apps.get_model("core", "WordstatPhrase")

    def _normalize(value: str) -> str:
        return " ".join(str(value or "").strip().split()).lower()

    phrases_map: dict[str, int | None] = {}
    for phrase_text, lemma, frequency in SemanticPhrase.objects.values_list(
        "phrase", "lemma", "frequency"
    ):
        raw_value = (lemma or phrase_text or "").strip()
        if not raw_value:
            continue
        normalized = _normalize(raw_value)
        if not normalized:
            continue
        current = phrases_map.get(normalized)
        if current is None:
            phrases_map[normalized] = frequency
        elif frequency is not None and current is not None and frequency > current:
            phrases_map[normalized] = frequency

    if phrases_map:
        WordstatPhrase.objects.bulk_create(
            [WordstatPhrase(phrase=phrase_value, frequency=frequency) for phrase_value, frequency in phrases_map.items()],
            ignore_conflicts=True,
        )

        existing_rows = WordstatPhrase.objects.filter(phrase__in=list(phrases_map.keys()))
        updates: list[WordstatPhrase] = []
        for row in existing_rows:
            desired = phrases_map.get(row.phrase)
            if desired is None:
                continue
            if row.frequency is None or desired > row.frequency:
                row.frequency = desired
                updates.append(row)
        if updates:
            WordstatPhrase.objects.bulk_update(updates, ["frequency", "updated_at"])

    phrase_id_map = {row.phrase: row.id for row in WordstatPhrase.objects.all().only("id", "phrase")}

    batch: list[SemanticPhrase] = []
    for row in SemanticPhrase.objects.all().iterator():
        raw_value = (getattr(row, "lemma", "") or getattr(row, "phrase", "") or "").strip()
        normalized = _normalize(raw_value)
        if not normalized:
            continue
        row.wordstat_phrase_id = phrase_id_map.get(normalized)
        batch.append(row)
        if len(batch) >= 1000:
            SemanticPhrase.objects.bulk_update(batch, ["wordstat_phrase"])
            batch = []
    if batch:
        SemanticPhrase.objects.bulk_update(batch, ["wordstat_phrase"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0126_semantic_phrase_comment"),
    ]

    operations = [
        migrations.CreateModel(
            name="WordstatPhrase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phrase", models.TextField(unique=True)),
                ("frequency", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "wordstat_phrases",
                "ordering": ("phrase", "id"),
                "verbose_name": "Wordstat Phrase",
                "verbose_name_plural": "Wordstat Phrases",
            },
        ),
        migrations.AddField(
            model_name="semanticphrase",
            name="wordstat_phrase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="semantic_phrases",
                to="core.wordstatphrase",
            ),
        ),
        migrations.RunPython(forwards_fill_wordstat_phrases, reverse_code=migrations.RunPython.noop),
        migrations.RemoveField(model_name="semanticphrase", name="lemma"),
        migrations.RemoveField(model_name="semanticphrase", name="frequency"),
        migrations.RemoveField(model_name="semanticphrase", name="phrase"),
        migrations.RenameField(model_name="semanticphrase", old_name="wordstat_phrase", new_name="phrase"),
        migrations.AlterField(
            model_name="semanticphrase",
            name="phrase",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="semantic_phrases",
                to="core.wordstatphrase",
            ),
        ),
    ]
