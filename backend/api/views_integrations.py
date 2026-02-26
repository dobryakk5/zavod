from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import string
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import tasks
from core.generation_events import record_generation_event
from core.audience_profiles import merge_audience_profiles
from core.models import (
    Client,
    ChannelAnalysis,
    GenerationEvent,
    ProjectChannelAnalysisRun,
    ProjectChannelPostStat,
    VkIntegration,
    WeeklySourceBatch,
    WeeklySourceReport,
)

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .serializers import (
    ChannelAnalysisDetailSerializer,
    ChannelAnalysisListSerializer,
    ProjectChannelAnalysisRunDetailSerializer,
    ProjectChannelAnalysisRunListSerializer,
    VkIntegrationSerializer,
    WeeklySourceBatchListSerializer,
    WeeklySourceBatchSerializer,
    WeeklySourceReportSerializer,
)
from .utils import enforce_generation_limit, get_active_client

VK_SCOPE = "wall photos groups messages"
VK_TIMEOUT = 15
VK_ID_AUTHORIZE_URL = "https://id.vk.ru/authorize"
VK_ID_TOKEN_URL = "https://id.vk.ru/oauth2/auth"

logger = logging.getLogger(__name__)

class VkApiError(Exception):
    """Raised when VK API responds with an error."""

    def __init__(self, message: str, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload or {}


def _missing_vk_settings() -> list[str]:
    missing: list[str] = []
    if not getattr(settings, "VK_CLIENT_ID", ""):
        missing.append("VK_CLIENT_ID")
    if not getattr(settings, "VK_REDIRECT_URI", ""):
        missing.append("VK_REDIRECT_URI")
    return missing


def _popup_response(message: str, *, success: bool = True, title: str = "VK интеграция"):
    """
    Returns a minimal plain-text page (no scripts) per VK ID redirect_uri requirements.
    """
    status_value = "Успех" if success else "Ошибка"
    content = f"{title}: {status_value}\n\n{message}\n\nОкно можно закрыть."
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Referrer-Policy"] = "no-referrer"
    return response


def _generate_vk_state(length: int = 36) -> str:
    alphabet = string.ascii_letters + string.digits + "_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _generate_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def _vk_id_token_request(payload: dict) -> dict:
    try:
        response = requests.post(VK_ID_TOKEN_URL, data=payload, timeout=VK_TIMEOUT)
        data = response.json()
    except requests.RequestException as exc:
        raise VkApiError("Не удалось связаться с VK ID") from exc
    except ValueError as exc:
        raise VkApiError("VK ID вернул некорректный ответ") from exc

    if "error" in data:
        message = data.get("error_description") or data.get("error") or "Ошибка VK ID"
        raise VkApiError(message, data)
    return data


def _vk_api_request(method: str, *, access_token: str, params: dict | None = None,
                    http_method: str = "get"):
    url = f"https://api.vk.com/method/{method}"
    payload = dict(params or {})
    payload.setdefault("access_token", access_token)
    payload.setdefault("v", getattr(settings, "VK_API_VERSION", "5.131"))

    if http_method.lower() == "post":
        response = requests.post(url, data=payload, timeout=VK_TIMEOUT)
    else:
        response = requests.get(url, params=payload, timeout=VK_TIMEOUT)

    data = response.json()
    if "error" in data:
        raise VkApiError(data["error"].get("error_msg", "VK API error"), data["error"])
    return data.get("response")


def _normalize_group_identifier(value: str) -> str:
    slug = value.strip()
    slug = slug.replace("https://vk.com/", "").replace("http://vk.com/", "")
    slug = slug.replace("vk.com/", "")
    slug = slug.lstrip("@")
    for prefix in ("public", "club"):
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
    if slug.startswith("-"):
        slug = slug[1:]
    return slug


def _fetch_admin_groups(access_token: str, user_id: int | None) -> list[dict]:
    params = {
        "extended": 1,
        "filter": "admin",
        "fields": "screen_name,type,members_count",
    }
    if user_id:
        params["user_id"] = user_id
    response = _vk_api_request("groups.get", access_token=access_token, params=params)
    if isinstance(response, dict):
        items = response.get("items", [])
    else:
        items = response or []
    return [item for item in items if item.get("is_admin")]


def _fetch_single_group(access_token: str, identifier: str) -> dict:
    response = _vk_api_request(
        "groups.getById",
        access_token=access_token,
        params={"group_id": identifier, "fields": "is_admin,screen_name,type,members_count"},
    )
    if not response:
        raise VkApiError("Группа не найдена")
    group = response[0]
    if not group.get("is_admin"):
        raise VkApiError("У вас нет прав администратора этой группы")
    return group


def _save_vk_integration(
    client: Client,
    owner,
    group_data: dict,
    access_token: str,
    user_id: int | None,
    token_meta: dict | None = None,
):
    group_id = int(group_data.get("id"))
    integration, _created = VkIntegration.objects.get_or_create(
        client=client,
        group_id=group_id,
        defaults={
            "owner": owner,
            "group_name": group_data.get("name", ""),
            "screen_name": group_data.get("screen_name", ""),
        },
    )

    extra = integration.extra or {}
    extra.update({
        "type": group_data.get("type"),
        "members_count": group_data.get("members_count"),
    })

    token_meta = token_meta or {}
    if token_meta.get("refresh_token"):
        extra["refresh_token"] = token_meta["refresh_token"]
    if token_meta.get("device_id"):
        extra["device_id"] = token_meta["device_id"]
    if token_meta.get("id_token"):
        extra["id_token"] = token_meta["id_token"]
    if token_meta.get("scope"):
        extra["scope"] = token_meta["scope"]

    expires_in = token_meta.get("expires_in")
    if expires_in:
        try:
            expires_seconds = int(expires_in)
            if expires_seconds > 0:
                expires_at = timezone.now() + timedelta(seconds=expires_seconds)
                extra["access_token_expires_at"] = expires_at.isoformat()
        except (TypeError, ValueError):
            pass

    integration.owner = owner
    integration.group_name = group_data.get("name", "")
    integration.screen_name = group_data.get("screen_name", "")
    integration.access_token = access_token
    integration.user_id = user_id
    integration.status = VkIntegration.STATUS_ACTIVE
    integration.extra = extra
    integration.save(
        update_fields=[
            "owner",
            "group_name",
            "screen_name",
            "access_token",
            "user_id",
            "status",
            "extra",
            "updated_at",
        ]
    )


def _refresh_vk_access_token_if_needed(integration: VkIntegration) -> None:
    extra = integration.extra or {}
    refresh_token = extra.get("refresh_token")
    device_id = extra.get("device_id")
    expires_at_raw = extra.get("access_token_expires_at")

    if not refresh_token or not device_id:
        return

    expires_at = None
    if expires_at_raw:
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
            if timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at)
        except (TypeError, ValueError):
            expires_at = None

    if expires_at and (expires_at - timezone.now()) > timedelta(seconds=60):
        return

    refresh_payload = {
        "client_id": settings.VK_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "device_id": device_id,
        "state": _generate_vk_state(32),
    }
    token_data = _vk_id_token_request(refresh_payload)

    new_expires_in = token_data.get("expires_in")
    if new_expires_in:
        try:
            expires_seconds = int(new_expires_in)
            if expires_seconds > 0:
                expires_at = timezone.now() + timedelta(seconds=expires_seconds)
                extra["access_token_expires_at"] = expires_at.isoformat()
        except (TypeError, ValueError):
            pass

    extra["refresh_token"] = token_data.get("refresh_token") or refresh_token
    extra["device_id"] = device_id
    if token_data.get("scope"):
        extra["scope"] = token_data["scope"]
    if token_data.get("id_token"):
        extra["id_token"] = token_data["id_token"]

    integration.access_token = token_data.get("access_token") or integration.access_token
    integration.extra = extra
    integration.save(update_fields=["access_token", "extra", "updated_at"])



class VkIntegrationViewSet(mixins.ListModelMixin,
                           mixins.DestroyModelMixin,
                           viewsets.GenericViewSet):
    """List or delete VK integrations for the active client."""

    permission_classes = [IsTenantOwnerOrEditor]
    serializer_class = VkIntegrationSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            VkIntegration.objects.filter(client=client)
            .select_related("owner")
            .order_by("-updated_at")
        )


class VkConnectView(APIView):
    """Starts VK ID OAuth PKCE flow and redirects user to VK."""

    permission_classes = [IsTenantOwnerOrEditor]

    def get(self, request):
        # Ensure current user has an active client (raises if not)
        get_active_client(request.user)

        target_group = (request.query_params.get("group_id") or "").strip()
        if not target_group:
            return _popup_response(
                "Укажите ссылку или ID группы VK для подключения.",
                success=False,
            )

        missing = _missing_vk_settings()
        if missing:
            msg = (
                "VK ID OAuth не настроен. Укажите переменные "
                f"{', '.join(missing)} на сервере."
            )
            return _popup_response(msg, success=False)

        state = _generate_vk_state()
        code_verifier, code_challenge = _generate_pkce_pair()
        request.session["vk_oauth_state"] = state
        request.session["vk_code_verifier"] = code_verifier
        request.session["vk_target_group"] = target_group
        request.session.modified = True

        params = {
            "client_id": settings.VK_CLIENT_ID,
            "redirect_uri": settings.VK_REDIRECT_URI,
            "scope": VK_SCOPE,
            "response_type": "code",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        auth_url = f"{VK_ID_AUTHORIZE_URL}?" + urlencode(params)
        return redirect(auth_url)


class VkCallbackView(APIView):
    """Handles VK ID callback, exchanges code for tokens and saves integrations."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        missing = _missing_vk_settings()
        if missing:
            msg = (
                "VK ID OAuth не настроен. Обратитесь к администратору: "
                f"{', '.join(missing)}"
            )
            return _popup_response(msg, success=False)

        payload_raw = request.GET.get("payload")
        payload_data: dict = {}
        if payload_raw:
            try:
                payload_data = json.loads(payload_raw)
            except ValueError:
                return _popup_response("Некорректный payload авторизации VK ID", success=False)

        provided_state = payload_data.get("state") or request.GET.get("state")
        saved_state = request.session.pop("vk_oauth_state", None)
        if not provided_state or provided_state != saved_state:
            return _popup_response("Некорректный ответ авторизации VK ID (state mismatch)", success=False)

        code_verifier = request.session.pop("vk_code_verifier", None)
        if not code_verifier:
            return _popup_response("Не удалось подтвердить PKCE для VK ID", success=False)

        code = payload_data.get("code") or request.GET.get("code")
        device_id = payload_data.get("device_id") or request.GET.get("device_id")
        if not code:
            error_description = request.GET.get("error_description") or "VK не вернул код авторизации"
            return _popup_response(error_description, success=False)
        if not device_id:
            return _popup_response("VK ID не вернул device_id", success=False)

        try:
            client = get_active_client(request.user)
        except PermissionDenied:
            return _popup_response("Пользователь не привязан к клиенту", success=False)

        token_params = {
            "client_id": settings.VK_CLIENT_ID,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
            "device_id": device_id,
            "code": code,
            "redirect_uri": settings.VK_REDIRECT_URI,
            "state": provided_state,
        }
        try:
            token_data = _vk_id_token_request(token_params)
        except VkApiError as exc:
            logger.warning("VK ID token exchange failed: %s", exc)
            return _popup_response(f"Ошибка VK ID OAuth: {exc}", success=False)

        access_token = token_data.get("access_token")
        user_id = token_data.get("user_id")
        if not access_token:
            return _popup_response("VK ID не вернул access_token", success=False)

        target_group = request.GET.get("group_id") or request.session.pop("vk_target_group", None)
        if not target_group:
            return _popup_response(
                "Не указана группа VK для подключения. Вернитесь в настройки и выберите группу.",
                success=False,
            )

        groups: list[dict]
        try:
            identifier = _normalize_group_identifier(str(target_group))
            groups = [_fetch_single_group(access_token, identifier)]
        except VkApiError as exc:
            logger.warning("VK group fetch error: %s", exc)
            return _popup_response(str(exc), success=False)
        except requests.RequestException as exc:
            logger.exception("VK group fetch failed: %s", exc)
            return _popup_response("Не удалось получить список групп VK", success=False)

        if not groups:
            return _popup_response("VK не нашёл групп, где вы администратор.", success=False)

        token_meta = {
            "refresh_token": token_data.get("refresh_token"),
            "id_token": token_data.get("id_token"),
            "expires_in": token_data.get("expires_in"),
            "scope": token_data.get("scope"),
            "device_id": device_id,
        }
        for group in groups:
            _save_vk_integration(client, request.user, group, access_token, user_id, token_meta)

        message = "Группа успешно подключена." if len(groups) == 1 else f"Подключено групп: {len(groups)}."
        return _popup_response(f"{message} Это окно можно закрыть.")


class VkPublishView(APIView):
    """Publishes a post with optional images to VK."""

    permission_classes = [IsTenantOwnerOrEditor]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        client = get_active_client(request.user)

        integration_id = request.data.get("integration_id")
        if not integration_id:
            return Response({"success": False, "error": "Не указана интеграция VK"}, status=status.HTTP_400_BAD_REQUEST)

        integration = get_object_or_404(VkIntegration, id=integration_id, client=client)
        message = (request.data.get("message") or "").strip()
        images = request.FILES.getlist("images")

        if not message and not images:
            return Response(
                {"success": False, "error": "Добавьте текст или изображение для публикации"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            _refresh_vk_access_token_if_needed(integration)
        except VkApiError as exc:
            integration.status = VkIntegration.STATUS_ERROR
            integration.save(update_fields=["status"])
            return Response(
                {"success": False, "error": f"Не удалось обновить токен VK ID: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            attachments = self._upload_images(integration, images) if images else []
            params = {
                "owner_id": -abs(int(integration.group_id)),
                "from_group": 1,
                "message": message,
            }
            if attachments:
                params["attachments"] = ",".join(attachments)
            vk_response = _vk_api_request(
                "wall.post",
                access_token=integration.access_token,
                params=params,
                http_method="post",
            )
        except (VkApiError, ValueError) as exc:
            logger.warning("VK publish error: %s", exc)
            integration.status = VkIntegration.STATUS_ERROR
            integration.save(update_fields=["status"])
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except requests.RequestException as exc:
            logger.exception("VK publish request failed: %s", exc)
            integration.status = VkIntegration.STATUS_ERROR
            integration.save(update_fields=["status"])
            return Response(
                {"success": False, "error": "Не удалось отправить данные в VK"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        integration.status = VkIntegration.STATUS_ACTIVE
        integration.last_published_at = timezone.now()
        integration.save(update_fields=["status", "last_published_at"])

        return Response({"success": True, "vk_response": vk_response})

    def _upload_images(self, integration: VkIntegration, files):
        attachments: list[str] = []
        for upload_file in files:
            server_info = _vk_api_request(
                "photos.getWallUploadServer",
                access_token=integration.access_token,
                params={"group_id": integration.group_id},
            )
            upload_url = server_info.get("upload_url")
            if not upload_url:
                raise VkApiError("VK не вернул адрес загрузки изображений")

            upload_file.seek(0)
            try:
                upload_response = requests.post(
                    upload_url,
                    files={"photo": (upload_file.name, upload_file.read(), upload_file.content_type or "image/jpeg")},
                    timeout=VK_TIMEOUT,
                )
                upload_data = upload_response.json()
            except requests.RequestException as exc:
                raise VkApiError("Не удалось загрузить изображение в VK") from exc
            except ValueError as exc:
                raise VkApiError("VK вернул некорректный ответ при загрузке изображения") from exc

            save_response = _vk_api_request(
                "photos.saveWallPhoto",
                access_token=integration.access_token,
                params={
                    "group_id": integration.group_id,
                    "photo": upload_data.get("photo"),
                    "server": upload_data.get("server"),
                    "hash": upload_data.get("hash"),
                },
                http_method="post",
            )
            for item in save_response or []:
                attachments.append(f"photo{item['owner_id']}_{item['id']}")
        return attachments



class ChannelAnalysisViewSet(mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    """Expose stored channel analysis records."""

    permission_classes = [IsTenantMember]
    pagination_class = None

    def get_object(self):
        share_token = self.request.query_params.get("share_token")
        if self.action == "retrieve" and share_token:
            lookup_value = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
            return get_object_or_404(
                ChannelAnalysis,
                **{
                    self.lookup_field: lookup_value,
                    "share_token": share_token,
                    "share_enabled": True,
                },
            )
        return super().get_object()

    def get_permissions(self):
        if self.action == "destroy":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            ChannelAnalysis.objects.filter(client=client)
            .select_related("client")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ChannelAnalysisListSerializer
        return ChannelAnalysisDetailSerializer

    def _issue_share_token(self) -> str:
        for _ in range(5):
            token = secrets.token_urlsafe(24)
            if not ChannelAnalysis.objects.filter(share_token=token).exists():
                return token
        raise RuntimeError("Failed to generate unique share token")

    @action(detail=True, methods=["post"], url_path="share", permission_classes=[IsTenantOwnerOrEditor])
    def share(self, request, pk=None):
        """Enable external sharing by issuing a one-time token."""
        analysis = self.get_object()

        if not analysis.share_enabled:
            analysis.share_token = self._issue_share_token()
        elif not analysis.share_token:
            analysis.share_token = self._issue_share_token()

        analysis.share_enabled = True
        analysis.save(update_fields=["share_token", "share_enabled", "updated_at"])

        return Response({"success": True, "share_token": analysis.share_token})

    @action(detail=True, methods=["post"], url_path="unshare", permission_classes=[IsTenantOwnerOrEditor])
    def unshare(self, request, pk=None):
        """Disable external sharing for this report."""
        analysis = self.get_object()
        analysis.share_enabled = False
        analysis.save(update_fields=["share_enabled", "updated_at"])
        return Response({"success": True})

    @action(
        detail=True,
        methods=["post"],
        url_path="merge_audience",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def merge_audience(self, request, pk=None):
        """Добавить описание ЦА из анализа канала в профиль клиента."""
        client = get_active_client(request.user)
        analysis = self.get_object()

        if analysis.client_id != client.id:
            return Response({"success": False, "error": "Анализ не принадлежит текущему клиенту"}, status=status.HTTP_403_FORBIDDEN)

        if analysis.status != ChannelAnalysis.STATUS_COMPLETED:
            return Response({"success": False, "error": "Анализ ещё не завершён"}, status=status.HTTP_400_BAD_REQUEST)

        result = analysis.result if isinstance(analysis.result, dict) else {}
        profile = result.get("audience_profile")

        def _has_text(value) -> bool:
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, (list, tuple)):
                return any(_has_text(item) for item in value)
            if isinstance(value, dict):
                return any(_has_text(item) for item in value.values())
            return bool(value)

        if not isinstance(profile, dict) or not any(_has_text(value) for value in profile.values()):
            return Response(
                {"success": False, "error": "Для этого анализа нет описания целевой аудитории"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_profile = {
            "avatar": client.avatar or "",
            "pains": client.pains or "",
            "desires": client.desires or "",
            "objections": client.objections or "",
        }

        merged_profile = merge_audience_profiles(current_profile, profile)
        for field, value in merged_profile.items():
            setattr(client, field, value)
        client.save(update_fields=["avatar", "pains", "desires", "objections"])

        return Response(
            {
                "success": True,
                "message": "Описание целевой аудитории обновлено в настройках клиента",
                "client_profile": merged_profile,
            }
        )


class ProjectChannelAnalysisRunView(APIView):
    """Запуск анализа каналов проекта клиента."""

    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request):
        client = get_active_client(request.user)

        channels = [
            ("telegram", client.project_telegram_channel or ""),
            ("instagram", client.project_instagram_channel or ""),
            ("youtube", client.project_youtube_channel or ""),
        ]
        has_any = any(value.strip() for _, value in channels)
        if not has_any:
            return Response(
                {"success": False, "error": "Добавьте хотя бы один канал проекта перед запуском анализа."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_CHANNEL_ANALYSIS)
        if limit_response:
            return limit_response

        run = ProjectChannelAnalysisRun.objects.create(
            client=client,
            status=ProjectChannelAnalysisRun.STATUS_PENDING,
        )
        task = tasks.analyze_project_channels_task.delay(run.id)
        run.task_id = task.id
        run.save(update_fields=["task_id", "updated_at"])

        record_generation_event(
            client,
            GenerationEvent.EVENT_CHANNEL_ANALYSIS,
            meta={"source": "project"},
        )
        return Response({"success": True, "task_id": task.id, "run_id": run.id})


class ProjectChannelAnalysisRunViewSet(viewsets.ReadOnlyModelViewSet):
    """Просмотр запусков анализа каналов проекта."""

    permission_classes = [IsTenantMember]
    pagination_class = None

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return ProjectChannelAnalysisRun.objects.filter(client=client).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return ProjectChannelAnalysisRunListSerializer
        return ProjectChannelAnalysisRunDetailSerializer

    @action(detail=False, methods=["get"], url_path="timeseries")
    def timeseries(self, request):
        client = get_active_client(request.user)
        runs = list(
            ProjectChannelAnalysisRun.objects.filter(
                client=client,
                status=ProjectChannelAnalysisRun.STATUS_COMPLETED,
            ).order_by("created_at")
        )
        if not runs:
            return Response({"runs": [], "channels": []})

        run_map = {run.id: run for run in runs}
        stats_rows = (
            ProjectChannelPostStat.objects.filter(run_id__in=run_map.keys())
            .values("run_id", "channel_type", "channel_identifier", "run__created_at")
            .annotate(
                posts_count=Count("id"),
                views=Sum("views"),
                reactions=Sum("reactions"),
                comments=Sum("comments"),
            )
            .order_by("run__created_at")
        )

        def resolve_channel_meta(run, channel_type: str, channel_identifier: str):
            result = run.result if isinstance(run.result, dict) else {}
            channels = result.get("channels") if isinstance(result.get("channels"), list) else []
            for channel in channels:
                if not isinstance(channel, dict):
                    continue
                if (
                    channel.get("channel_type") == channel_type
                    and channel.get("channel_identifier") == channel_identifier
                ):
                    summary = channel.get("summary") if isinstance(channel.get("summary"), dict) else {}
                    label = (
                        (summary or {}).get("channel_name")
                        or channel.get("channel_url")
                        or channel_identifier
                    )
                    url = (summary or {}).get("profile_url") or channel.get("channel_url") or ""
                    subscribers = summary.get("subscribers")
                    return label, url, int(subscribers or 0)
            return channel_identifier, "", 0

        runs_payload = {
            run.id: {
                "run_id": run.id,
                "created_at": run.created_at.isoformat(),
                "channels": [],
            }
            for run in runs
        }
        channel_meta_map = {}

        for row in stats_rows:
            run = run_map.get(row["run_id"])
            if not run:
                continue
            channel_type = row["channel_type"]
            channel_identifier = row["channel_identifier"]
            key = f"{channel_type}:{channel_identifier}"
            label, url, subscribers = resolve_channel_meta(run, channel_type, channel_identifier)
            channel_meta_map.setdefault(
                key,
                {
                    "key": key,
                    "channel_type": channel_type,
                    "channel_identifier": channel_identifier,
                    "channel_label": label,
                    "channel_url": url,
                },
            )
            runs_payload[row["run_id"]]["channels"].append(
                {
                    "key": key,
                    "channel_type": channel_type,
                    "channel_identifier": channel_identifier,
                    "channel_label": label,
                    "channel_url": url,
                    "totals": {
                        "posts_count": int(row["posts_count"] or 0),
                        "views": int(row["views"] or 0),
                        "reactions": int(row["reactions"] or 0),
                        "comments": int(row["comments"] or 0),
                        "subscribers": subscribers,
                    },
                }
            )

        ordered_runs = [runs_payload[run.id] for run in runs]
        return Response({"runs": ordered_runs, "channels": list(channel_meta_map.values())})

    @action(detail=False, methods=["get"], url_path="latest")
    def latest(self, request):
        client = get_active_client(request.user)
        latest_run = (
            ProjectChannelAnalysisRun.objects.filter(client=client)
            .order_by("-created_at")
            .first()
        )
        if not latest_run:
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = ProjectChannelAnalysisRunDetailSerializer(latest_run)
        return Response(serializer.data)


class WeeklySourceReportViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only доступ к еженедельным отчетам по источникам."""

    permission_classes = [IsTenantMember]
    serializer_class = WeeklySourceReportSerializer
    pagination_class = None

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            WeeklySourceReport.objects.filter(client=client)
            .order_by("-week_start", "source_type", "-created_at")
        )


class WeeklySourceRunView(APIView):
    """Запуск еженедельной аналитики по всем источникам клиента."""

    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request):
        client = get_active_client(request.user)
        week_start = timezone.now().date() - timedelta(days=timezone.now().weekday())

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_WEEKLY_COLLECTION)
        if limit_response:
            return limit_response

        batch = WeeklySourceBatch.objects.create(
            client=client,
            week_start=week_start,
            status=WeeklySourceReport.STATUS_PENDING,
        )
        task = tasks.run_weekly_sources_for_client.delay(client.id, batch.id)

        record_generation_event(
            client,
            GenerationEvent.EVENT_WEEKLY_COLLECTION,
            meta={"week_start": str(week_start)},
        )
        return Response(
            {
                "success": True,
                "task_id": task.id,
                "week_start": str(week_start),
                "batch_id": batch.id,
            }
        )


class WeeklySourceBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Подборки по неделям."""

    permission_classes = [IsTenantMember]
    pagination_class = None

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return WeeklySourceBatch.objects.filter(client=client).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return WeeklySourceBatchListSerializer
        return WeeklySourceBatchSerializer
