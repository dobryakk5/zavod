import asyncio
import base64
import logging
import os
import re
import shutil
import tempfile
import urllib.parse
from io import BytesIO
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

try:
    from gradio_client import Client as GradioClient, handle_file
    GRADIO_AVAILABLE = True
except ImportError:
    GradioClient = None
    handle_file = None
    GRADIO_AVAILABLE = False

try:
    from telethon import TelegramClient, events
    from telethon.errors import AuthKeyUnregisteredError
    TELETHON_AVAILABLE = True
except ImportError:
    TelegramClient = None
    events = None
    AuthKeyUnregisteredError = None
    TELETHON_AVAILABLE = False

WAN_NEGATIVE_PROMPT = (
    "色调艳丽, 过曝, 静态, 细节模糊不清, 字幕, 风格, 作品, 画作, 画面, 静止, 整体发灰, 最差质量, "
    "低质量, JPEG压缩残留, 丑陋的, 残缺的, 多余的手指, 画得不好的手部, 画得不好的脸部, 畸形的, 毁容的, "
    "形态畸形的肢体, 手指融合, 静止不动的画面, 杂乱的背景, 三条腿, 背景人很多, 倒着走"
)


def generate_image(
    prompt: str,
    output_path: str,
    model: str,
    api_key: Optional[str],
    api_url: str,
    hf_client: Any = None
) -> Dict[str, Any]:
    """
    Сгенерировать изображение выбранной моделью.
    """
    logger.info("Генерация изображения (%s)", model)

    if model == "nanobanana":
        return _generate_image_openrouter(prompt, output_path, api_key, api_url)
    if model == "huggingface":
        return _generate_image_huggingface(prompt, output_path, hf_client)
    if model == "flux2":
        return _generate_image_flux2(prompt, output_path)
    return _generate_image_pollinations(prompt, output_path)


def generate_video_from_image(
    image_path: str,
    prompt: str,
    method: str = "wan",
    negative_prompt: Optional[str] = None,
    **options: Any
) -> Dict[str, Any]:
    """
    Создать короткое видео по изображению.
    """
    method_name = (method or "wan").lower()
    if method_name == "veo":
        return _generate_video_veo(image_path, prompt, **options)
    return _generate_video_wan(
        image_path=image_path,
        prompt=prompt,
        negative_prompt=negative_prompt,
        **options
    )


def generate_video_from_text(
    prompt: str,
    method: str = "veo",
    **options: Any
) -> Dict[str, Any]:
    """
    Создать видео только по текстовому описанию (сейчас поддерживается VEO).
    """
    method_name = (method or "veo").lower()
    if method_name != "veo":
        return {
            "success": False,
            "error": f"Метод '{method}' не поддерживает генерацию видео из текста"
        }

    return _generate_video_veo(
        image_path=None,
        prompt=prompt,
        text_only=True,
        **options
    )


def _generate_image_pollinations(prompt: str, output_path: str) -> Dict[str, Any]:
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        logger.info("Pollinations запрос: %s", image_url)

        response = requests.get(image_url, timeout=60)
        if response.status_code != 200:
            logger.error("Ошибка Pollinations HTTP %s", response.status_code)
            return {"success": False, "error": f"HTTP error {response.status_code}"}

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        return {
            "success": True,
            "image_path": output_path,
            "image_url": image_url,
            "model": "pollinations"
        }
    except requests.exceptions.Timeout:
        logger.error("Таймаут Pollinations")
        return {"success": False, "error": "Request timeout"}
    except Exception as exc:
        logger.error("Ошибка Pollinations: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_image_openrouter(
    prompt: str,
    output_path: str,
    api_key: Optional[str],
    api_url: str
) -> Dict[str, Any]:
    if not api_key:
        return {"success": False, "error": "OPENROUTER_API_KEY не задан"}

    try:
        logger.info("Генерация через OpenRouter (google/gemini-2.5-flash-image)")
        response = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://zavod-content-factory.com",
                "X-Title": "Content Factory Image Generator"
            },
            json={
                "model": "google/gemini-2.5-flash-image",
                "messages": [{"role": "user", "content": f"Generate an image: {prompt}"}]
            },
            timeout=120
        )

        if response.status_code != 200:
            logger.error("OpenRouter ошибка %s: %s", response.status_code, response.text)
            return {
                "success": False,
                "error": f"API error {response.status_code}: {response.text}"
            }

        data = response.json()
        image_url = None
        image_base64 = None

        if data.get("choices"):
            message = data["choices"][0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "image_url" in item:
                        img_data = item["image_url"]
                        url_value = img_data.get("url") if isinstance(img_data, dict) else img_data
                        if isinstance(url_value, str):
                            if url_value.startswith("data:image"):
                                image_base64 = url_value
                            else:
                                image_url = url_value
            elif isinstance(content, str):
                if content.startswith("data:image"):
                    image_base64 = content
                else:
                    urls = re.findall(r'https?://[^\s<>"{}|\\^`[\]]+', content)
                    if urls:
                        image_url = urls[0]

            if not image_url and not image_base64 and "image_url" in message:
                image_url = message["image_url"]

        if image_base64:
            base64_data = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
            image_bytes = base64.b64decode(base64_data)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(image_bytes)
            return {
                "success": True,
                "image_path": output_path,
                "image_url": None,
                "model": "nanobanana"
            }

        if image_url:
            img_response = requests.get(image_url, timeout=60)
            if img_response.status_code != 200:
                logger.error("Ошибка скачивания изображения %s", img_response.status_code)
                return {
                    "success": False,
                    "error": f"Image download HTTP error {img_response.status_code}"
                }

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(img_response.content)

            return {
                "success": True,
                "image_path": output_path,
                "image_url": image_url,
                "model": "nanobanana"
            }

        logger.error("Не удалось извлечь изображение из ответа: %s", data)
        return {"success": False, "error": "No image URL or base64 data in response"}

    except requests.exceptions.Timeout:
        logger.error("Таймаут OpenRouter")
        return {"success": False, "error": "Request timeout"}
    except Exception as exc:
        logger.error("Ошибка OpenRouter: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_image_flux2(prompt: str, output_path: str) -> Dict[str, Any]:
    if not GRADIO_AVAILABLE:
        return {"success": False, "error": "gradio_client not installed. Run pip install gradio_client."}

    try:
        def _env_bool(name: str, default: bool) -> bool:
            value = os.getenv(name)
            if value is None:
                return default
            return value.strip().lower() in ("1", "true", "yes", "on")

        space_name = os.getenv("FLUX2_SPACE", "black-forest-labs/FLUX.2-dev")
        api_name = os.getenv("FLUX2_API_NAME", "/infer")
        width = int(os.getenv("FLUX2_WIDTH", "1024"))
        height = int(os.getenv("FLUX2_HEIGHT", "1024"))
        seed = float(os.getenv("FLUX2_SEED", "0"))
        randomize_seed = _env_bool("FLUX2_RANDOMIZE_SEED", True)
        steps = float(os.getenv("FLUX2_STEPS", "30"))
        guidance_scale = float(os.getenv("FLUX2_GUIDANCE", "4"))
        prompt_upsampling = _env_bool("FLUX2_PROMPT_UPSAMPLING", True)

        client = GradioClient(space_name)
        result = client.predict(
            prompt=prompt,
            input_images=[],
            seed=seed,
            randomize_seed=randomize_seed,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            prompt_upsampling=prompt_upsampling,
            api_name=api_name
        )

        image_entry: Optional[Dict[str, Any]] = None
        if isinstance(result, (list, tuple)) and result:
            candidate = result[0]
            if isinstance(candidate, dict):
                image_entry = candidate
        elif isinstance(result, dict):
            image_entry = result

        path_candidate = None
        url_candidate = None

        if image_entry:
            path_candidate = image_entry.get("path")
            url_candidate = image_entry.get("url")
            meta = image_entry.get("meta")
            if isinstance(meta, dict):
                url_candidate = url_candidate or meta.get("url")
            nested_image = image_entry.get("image")
            if isinstance(nested_image, dict):
                path_candidate = path_candidate or nested_image.get("path")
                url_candidate = url_candidate or nested_image.get("url")

        if isinstance(result, str) and not path_candidate:
            path_candidate = result

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        saved = False

        if path_candidate and os.path.exists(path_candidate):
            shutil.copyfile(path_candidate, output_path)
            saved = True
        else:
            download_url = None
            if path_candidate and str(path_candidate).startswith("http"):
                download_url = path_candidate
            elif url_candidate:
                download_url = url_candidate

            if download_url:
                response = requests.get(download_url, timeout=120)
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(response.content)
                saved = True

        if not saved:
            logger.error("FLUX.2 Space не вернуло путь или URL")
            return {"success": False, "error": "Unable to retrieve generated image from FLUX.2 space"}

        return {
            "success": True,
            "image_path": output_path,
            "image_url": url_candidate,
            "model": "flux2"
        }
    except Exception as exc:
        logger.error("Ошибка FLUX.2: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_image_huggingface(prompt: str, output_path: str, hf_client: Any) -> Dict[str, Any]:
    if not hf_client:
        return {
            "success": False,
            "error": "HuggingFace client not available. Install huggingface_hub and set HF_TOKEN."
        }

    try:
        image = hf_client.text_to_image(prompt=prompt)
        img_bytes = BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes = img_bytes.getvalue()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_bytes)

        return {
            "success": True,
            "image_path": output_path,
            "image_url": None,
            "model": "huggingface"
        }
    except Exception as exc:
        logger.error("Ошибка HuggingFace: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_video_wan(
    image_path: str,
    prompt: str,
    negative_prompt: Optional[str],
    **options: Any
) -> Dict[str, Any]:
    if not GRADIO_AVAILABLE or not handle_file:
        return {"success": False, "error": "gradio_client not installed. Run pip install gradio_client."}

    gradio_space = options.get("gradio_space") or os.getenv("WAN_VIDEO_SPACE", "zerogpu-aoti/wan2-2-fp8da-aoti-faster")
    api_name = options.get("api_name") or os.getenv("WAN_VIDEO_API", "/generate_video")
    steps = options.get("steps", int(os.getenv("WAN_VIDEO_STEPS", "6")))
    duration_seconds = options.get("duration_seconds", float(os.getenv("WAN_VIDEO_DURATION", "3.5")))
    guidance_scale = options.get("guidance_scale", float(os.getenv("WAN_VIDEO_GUIDANCE", "1")))
    guidance_scale_2 = options.get("guidance_scale_2", float(os.getenv("WAN_VIDEO_GUIDANCE_2", "1")))
    seed = options.get("seed", int(os.getenv("WAN_VIDEO_SEED", "42")))
    randomize_seed_opt = options.get("randomize_seed")
    if randomize_seed_opt is None:
        randomize_seed = os.getenv("WAN_VIDEO_RANDOMIZE_SEED", "true").lower() in ("1", "true", "yes", "on")
    else:
        randomize_seed = bool(randomize_seed_opt)

    negative_prompt = negative_prompt or WAN_NEGATIVE_PROMPT

    try:
        client = GradioClient(gradio_space)
        payload = {
            "input_image": handle_file(image_path),
            "prompt": prompt,
            "steps": steps,
            "negative_prompt": negative_prompt,
            "duration_seconds": duration_seconds,
            "guidance_scale": guidance_scale,
            "guidance_scale_2": guidance_scale_2,
            "seed": seed,
            "randomize_seed": randomize_seed,
            "api_name": api_name
        }

        result = client.predict(**payload)
        downloaded_temp_files: List[str] = []

        def _download_url_wrapper(url: str) -> Optional[str]:
            path = _download_url(url)
            if path:
                downloaded_temp_files.append(path)
            return path

        video_temp_path = _extract_video_path(result, _download_url_wrapper)

        if not video_temp_path or not os.path.exists(video_temp_path):
            logger.error("Не удалось получить путь к видео WAN")
            for tmp in downloaded_temp_files:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return {"success": False, "error": "Unable to retrieve WAN video result"}

        return {
            "success": True,
            "video_path": video_temp_path,
            "model": "wan",
            "cleanup_paths": downloaded_temp_files
        }
    except Exception as exc:
        logger.error("Ошибка WAN видео: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_video_veo(
    image_path: Optional[str],
    prompt: str,
    text_only: bool = False,
    **options: Any
) -> Dict[str, Any]:
    if not TELETHON_AVAILABLE:
        return {"success": False, "error": "telethon не установлен. Установите пакет telethon."}

    if not text_only and not image_path:
        return {"success": False, "error": "Для генерации по изображению нужен путь к файлу"}

    bot_username = options.get("bot_username") or os.getenv("VEO_BOT_USERNAME", "c_zv_bot")
    session_path = (
        options.get("session_path")
        or os.getenv("VEO_SESSION_PATH")
        or os.getenv("VEO_SESSION_FILE")
        or os.getenv("TELEGRAM_SESSION_PATH")
    )
    session_name_raw = options.get("session_name") or os.getenv("VEO_SESSION_NAME", "veo_generator")
    session_label = session_path or session_name_raw
    if session_path:
        expanded_path = os.path.abspath(os.path.expanduser(session_path))
        if expanded_path.endswith(".session"):
            session_name = expanded_path[:-8]
            session_file = expanded_path
        else:
            session_name = expanded_path
            session_file = expanded_path + ".session"
        session_label = session_file
        logger.info("Используется файл сессии Telethon: %s", session_file)
    else:
        session_name = session_name_raw
        session_file = f"{session_name}.session"
    session_dir = os.path.dirname(session_name)
    if session_dir and not os.path.exists(session_dir):
        os.makedirs(session_dir, exist_ok=True)
    timeout = options.get("timeout") or int(os.getenv("VEO_TIMEOUT", "600"))

    api_id = (
        options.get("api_id")
        or os.getenv("TELEGRAM_API_ID")
        or os.getenv("TG_API_ID")
        or os.getenv("API_ID")
    )
    api_hash = (
        options.get("api_hash")
        or os.getenv("TELEGRAM_API_HASH")
        or os.getenv("TG_API_HASH")
        or os.getenv("API_HASH")
    )

    if not api_id or not api_hash:
        return {
            "success": False,
            "error": "TELEGRAM_API_ID (или TG_API_ID/API_ID) и TELEGRAM_API_HASH (TG_API_HASH/API_HASH) обязательны для метода VEO"
        }

    try:
        api_id = int(api_id)
    except ValueError:
        return {"success": False, "error": "TELEGRAM_API_ID должен быть числом"}

    caption = prompt or options.get("fallback_prompt") or "Please animate this image"

    async def _veo_coroutine() -> Optional[str]:
        client = TelegramClient(session_name, api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError(
                    f"Telethon session '{session_label}' не авторизована. "
                    "Запустите backend/core/foto_video_gen.py (или scripts/authorize_telegram.py) и пройдите вход в Telegram."
                )

            try:
                bot = await client.get_entity(bot_username)
            except AuthKeyUnregisteredError as auth_err:
                raise RuntimeError(
                    f"Telethon session '{session_label}' требует повторной авторизации: {auth_err}. "
                    "Удалите файл сессии и выполните вход снова через backend/core/foto_video_gen.py или scripts/authorize_telegram.py."
                ) from auth_err
            except Exception:
                raise
            try:
                async with client.conversation(bot, timeout=timeout) as conv:
                    if text_only:
                        await conv.send_message(caption)
                    else:
                        await conv.send_file(bot, image_path, caption=caption)

                    try:
                        response = await conv.get_response()
                    except asyncio.TimeoutError:
                        logger.error("Бот VEO не ответил в течение %s секунд", timeout)
                        return None
            except asyncio.TimeoutError:
                logger.error("Бот VEO не ответил в течение %s секунд (conversation)", timeout)
                return None

            if response.media:
                fd, temp_path = tempfile.mkstemp(suffix=".mp4")
                os.close(fd)
                saved_path = await client.download_media(response.media, file=temp_path)
                return saved_path

            if response.raw_text:
                url_match = re.search(r'https?://\S+', response.raw_text)
                if url_match:
                    return _download_url(url_match.group(0))

            logger.error("Ответ бота VEO не содержит видео")
            return None
        finally:
            await client.disconnect()

    try:
        video_path = asyncio.run(_veo_coroutine())
    except Exception as exc:
        logger.error("Ошибка общения с ботом VEO: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}

    if not video_path or not os.path.exists(video_path):
        return {"success": False, "error": "Не удалось получить видео от VEO"}

    return {
        "success": True,
        "video_path": video_path,
        "model": "veo",
        "cleanup_paths": [video_path]
    }


def _download_url(url: str) -> Optional[str]:
    try:
        response = requests.get(url, timeout=180)
        response.raise_for_status()
        fd, temp_path = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(response.content)
        return temp_path
    except Exception as exc:
        logger.error("Не удалось скачать файл %s: %s", url, exc)
        return None


def _extract_video_path(value: Any, download_func) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, str):
        candidate = value.strip()
        if candidate.startswith("file="):
            candidate = candidate.split("file=", 1)[1].split(";", 1)[0]
        if candidate.startswith("http"):
            return download_func(candidate)
        if os.path.exists(candidate):
            return candidate
        return None

    if isinstance(value, (list, tuple)):
        for item in value:
            path = _extract_video_path(item, download_func)
            if path:
                return path
        return None

    if isinstance(value, dict):
        for key in ("video", "videos", "result", "data", "value", "output", "outputs"):
            if key in value:
                path = _extract_video_path(value[key], download_func)
                if path:
                    return path
        for nested in value.values():
            path = _extract_video_path(nested, download_func)
            if path:
                return path
        return None

    for attr in ("data", "value"):
        if hasattr(value, attr):
            path = _extract_video_path(getattr(value, attr), download_func)
            if path:
                return path

    return None
