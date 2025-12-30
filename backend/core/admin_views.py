from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.db.models import Case, IntegerField, When

from .models import Client, ContentTemplate


MAX_POSTS_PER_RUN = 99


class ContentTemplateChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: ContentTemplate) -> str:
        prefix = "[Системный] " if obj.is_system else ""
        return f"{prefix}{obj.name} — {obj.type} / {obj.tone}"


class CustomPostGeneratorForm(forms.Form):
    client = forms.ModelChoiceField(
        label="Клиент",
        queryset=Client.objects.exclude(slug=Client.SYSTEM_SLUG).order_by("name"),
        required=True,
    )
    template = ContentTemplateChoiceField(
        label="Контент-шаблон",
        queryset=ContentTemplate.objects.none(),
        required=False,
    )
    posts_count = forms.IntegerField(
        label="Количество постов",
        min_value=1,
        max_value=MAX_POSTS_PER_RUN,
        initial=5,
        required=True,
    )
    videos_per_post = forms.IntegerField(
        label="Видео на пост",
        min_value=1,
        max_value=5,
        initial=1,
        required=True,
        help_text="Каждое видео генерируется как ролик из 3 сцен.",
    )
    task = forms.CharField(
        label="Задача",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text="Опишите, какие посты нужно сгенерировать (тема, цель, формат, ограничения).",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        client = None
        if self.is_bound:
            raw_client_id = self.data.get(self.add_prefix("client"))
            try:
                client_id = int(raw_client_id)
            except (TypeError, ValueError):
                client_id = None
            if client_id:
                client = Client.objects.filter(id=client_id).first()
        else:
            client = self.initial.get("client")
            if isinstance(client, int):
                client = Client.objects.filter(id=client).first()

        if not client:
            return

        templates = list(ContentTemplate.objects.for_client(client).select_related("client").order_by("name"))
        templates.sort(key=lambda tpl: (0 if tpl.client_id == client.id else 1, tpl.name.lower()))

        ordered_ids = [tpl.id for tpl in templates]
        order_by_case = Case(
            *[When(id=template_id, then=pos) for pos, template_id in enumerate(ordered_ids)],
            output_field=IntegerField(),
        )
        self.fields["template"].queryset = (
            ContentTemplate.objects.filter(id__in=ordered_ids)
            .select_related("client")
            .order_by(order_by_case)
        )

        # template is optional: do not auto-select a default


def custom_generator_view(request: HttpRequest) -> HttpResponse:
    if not request.user.has_perm("core.add_post"):
        raise PermissionDenied

    initial = dict(request.session.get("custom_generator_settings") or {})
    if not initial.get("template"):
        initial.pop("template", None)
    if request.method == "GET":
        raw_client_id = request.GET.get("client")
        try:
            client_id = int(raw_client_id) if raw_client_id else None
        except (TypeError, ValueError):
            client_id = None
        if client_id:
            initial["client"] = client_id

    form = CustomPostGeneratorForm(data=request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        client: Client = form.cleaned_data["client"]
        template: ContentTemplate | None = form.cleaned_data["template"]
        posts_count: int = form.cleaned_data["posts_count"]
        videos_per_post: int = form.cleaned_data["videos_per_post"]
        task: str = (form.cleaned_data["task"] or "").strip()

        session_settings = {
            "client": client.id,
            "posts_count": posts_count,
            "videos_per_post": videos_per_post,
            "task": task,
        }
        if template:
            session_settings["template"] = template.id
        request.session["custom_generator_settings"] = session_settings
        request.session.modified = True

        messages.success(
            request,
            "Настройки сохранены.",
        )
        return HttpResponseRedirect(request.path)

    context = admin.site.each_context(request)
    context.update(
        {
            "title": "Custom",
            "form": form,
            "max_posts": MAX_POSTS_PER_RUN,
        }
    )
    return TemplateResponse(request, "admin/custom_generator.html", context)
