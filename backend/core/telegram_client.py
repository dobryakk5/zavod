"""
Утилиты для работы с Telegram через Telethon.

Этот модуль предоставляет функции для:
1. Сбора контента из Telegram каналов по ключевым словам
2. Публикации постов в Telegram каналы
"""

import asyncio
import re
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import GetFullChannelRequest
from django.conf import settings
import os

logger = logging.getLogger(__name__)


class TelegramContentCollector:
    """
    Класс для сбора контента из Telegram каналов.
    """

    def __init__(self, api_id: str, api_hash: str, session_name: str = "session_content_collector"):
        """
        Инициализация клиента.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            session_name: Имя файла сессии
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None

    async def connect(self):
        """Подключиться к Telegram."""
        # Создаем директорию для сессий, если её нет
        sessions_dir = os.path.join(settings.BASE_DIR, 'telegram_sessions')
        os.makedirs(sessions_dir, exist_ok=True)

        session_path = os.path.join(sessions_dir, self.session_name)
        session_file = f"{session_path}.session"

        if not os.path.exists(session_file):
            raise RuntimeError(
                f"Telegram сессия '{session_file}' не найдена. "
                "Создайте её через python backend/scripts/authorize_telegram.py "
                "или следуйте инструкции в docs/TELEGRAM_SETUP.md."
            )

        self.client = TelegramClient(session_path, self.api_id, self.api_hash)
        await self.client.start()

        me = await self.client.get_me()
        if getattr(me, 'bot', False):
            await self.client.disconnect()
            self.client = None
            raise RuntimeError(
                "Эта Telegram сессия авторизована как бот. "
                "Для сбора трендов необходима Telegram User API сессия. "
                "Создайте её через python backend/scripts/authorize_telegram.py --session-type collector "
                "или следуйте инструкции в docs/TELEGRAM_SETUP.md."
            )

        logger.info(f"Telegram клиент подключен (сессия: {self.session_name})")

    async def disconnect(self):
        """Отключиться от Telegram."""
        if self.client:
            await self.client.disconnect()
            logger.info("Telegram клиент отключен")

    async def search_in_channel(
        self,
        channel: str,
        keywords: List[str],
        limit: int = 100,
        last_message_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Поиск сообщений в канале по ключевым словам.

        Args:
            channel: Username канала (например, '@rian_ru') или ID
            keywords: Список ключевых слов для поиска
            limit: Максимальное количество сообщений для проверки
            last_message_id: ID последнего обработанного сообщения (для инкрементального сбора)

        Returns:
            Список найденных сообщений в формате словарей
        """
        if not self.client:
            raise RuntimeError("Клиент не подключен. Вызовите connect() сначала.")

        # Создаем регулярное выражение для поиска
        pattern = re.compile(
            r'\b(' + '|'.join(re.escape(k) for k in keywords) + r')\b',
            flags=re.IGNORECASE
        )

        found_messages = []

        try:
            # Получаем сообщения из канала
            async for msg in self.client.iter_messages(channel, limit=limit):
                if not msg:
                    continue

                # Если есть last_message_id, пропускаем старые сообщения
                if last_message_id is not None and msg.id <= last_message_id:
                    break

                # Получаем текст сообщения
                text = msg.message or ''

                # Проверяем совпадение с ключевыми словами
                if pattern.search(text):
                    message_data = {
                        'id': msg.id,
                        'text': text,
                        'date': msg.date,
                        'channel': channel,
                        'url': f"https://t.me/{channel.lstrip('@')}/{msg.id}",
                        'views': getattr(msg, 'views', 0) or 0,
                        'forwards': getattr(msg, 'forwards', 0) or 0,
                        # Дополнительная информация
                        'has_media': msg.media is not None,
                        'media_type': type(msg.media).__name__ if msg.media else None,
                    }
                    found_messages.append(message_data)

            logger.info(f"Найдено {len(found_messages)} сообщений в {channel} по ключевым словам {keywords}")

        except errors.ChannelPrivateError:
            logger.error(f"Нет доступа к каналу {channel} (приватный или заблокирован)")
        except errors.ChannelInvalidError:
            logger.error(f"Неверный канал: {channel}")
        except ValueError as e:
            logger.error(f"Некорректный канал {channel}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при поиске в канале {channel}: {e}", exc_info=True)

        return found_messages

    async def get_channel_messages(
        self,
        channel_username: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Получить последние сообщения из канала (без фильтрации).

        Args:
            channel_username: Username канала (например, '@my_channel')
            limit: Количество сообщений для получения (по умолчанию 20)

        Returns:
            Список сообщений в формате словарей
        """
        if not self.client:
            raise RuntimeError("Клиент не подключен. Вызовите connect() сначала.")

        messages = []

        try:
            # Получаем последние сообщения из канала
            async for msg in self.client.iter_messages(channel_username, limit=limit):
                if not msg:
                    continue

                # Получаем текст сообщения
                text = msg.message or ''

                # Формируем данные сообщения
                message_data = {
                    'id': msg.id,
                    'text': text,
                    'date': msg.date,
                    'channel': channel_username,
                    'url': f"https://t.me/{channel_username.lstrip('@')}/{msg.id}",
                    'views': getattr(msg, 'views', 0) or 0,
                    'forwards': getattr(msg, 'forwards', 0) or 0,
                    'has_media': msg.media is not None,
                    'media_type': type(msg.media).__name__ if msg.media else None,
                }
                messages.append(message_data)

            logger.info(f"Получено {len(messages)} сообщений из канала {channel_username}")

        except errors.ChannelPrivateError:
            logger.error(f"Нет доступа к каналу {channel_username} (приватный или заблокирован)")
        except errors.ChannelInvalidError:
            logger.error(f"Неверный канал: {channel_username}")
        except ValueError as e:
            logger.error(f"Некорректный канал {channel_username}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений из канала {channel_username}: {e}", exc_info=True)

        return messages

    async def get_channel_info(self, channel_username: str) -> Dict:
        """
        Получить базовую информацию о канале.

        Args:
            channel_username: Username канала (например, '@my_channel')

        Returns:
            dict: Информация о канале
        """
        if not self.client:
            raise RuntimeError("Клиент не подключен. Вызовите connect() сначала.")

        try:
            entity = await self.client.get_entity(channel_username)
            full_info = await self.client(GetFullChannelRequest(entity))

            return {
                'id': getattr(entity, 'id', None),
                'title': getattr(entity, 'title', '') or '',
                'username': getattr(entity, 'username', '') or channel_username,
                'subscribers': getattr(full_info.full_chat, 'participants_count', 0) or 0,
                'about': getattr(full_info.full_chat, 'about', '') or '',
                'photo': getattr(entity, 'photo', None),
            }
        except errors.ChannelPrivateError:
            logger.error(f"Нет доступа к каналу {channel_username} (приватный или заблокирован)")
            raise
        except errors.ChannelInvalidError:
            logger.error(f"Неверный канал: {channel_username}")
            raise
        except ValueError as e:
            logger.error(f"Некорректный канал {channel_username}: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении информации о канале {channel_username}: {e}", exc_info=True)
            raise

    async def search_in_channels(
        self,
        channels: List[str],
        keywords: List[str],
        limit: int = 100,
        last_message_ids: Optional[Dict[str, int]] = None
    ) -> Dict[str, List[Dict]]:
        """
        Поиск в нескольких каналах.

        Args:
            channels: Список каналов
            keywords: Список ключевых слов
            limit: Лимит сообщений на канал
            last_message_ids: Словарь {канал: last_message_id}

        Returns:
            Словарь {канал: [список сообщений]}
        """
        results = {}
        last_ids = last_message_ids or {}

        for channel in channels:
            last_id = last_ids.get(channel)
            messages = await self.search_in_channel(channel, keywords, limit, last_id)
            results[channel] = messages

        return results


class TelegramPublisher:
    """
    Класс для публикации контента в Telegram каналы.
    """

    def __init__(self, api_id: str, api_hash: str, session_name: str = "session_publisher", bot_token: Optional[str] = None):
        """
        Инициализация клиента.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            session_name: Имя файла сессии
            bot_token: Токен бота (если используется Bot API вместо User API)
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.bot_token = bot_token
        self.client = None

    async def connect(self):
        """Подключиться к Telegram."""
        sessions_dir = os.path.join(settings.BASE_DIR, 'telegram_sessions')
        os.makedirs(sessions_dir, exist_ok=True)

        session_path = os.path.join(sessions_dir, self.session_name)

        self.client = TelegramClient(session_path, self.api_id, self.api_hash)

        # Если есть bot_token, используем Bot API (не требует интерактивной авторизации)
        if self.bot_token:
            await self.client.start(bot_token=self.bot_token)
            logger.info(f"Telegram publisher подключен как бот (сессия: {self.session_name})")
        else:
            # Используем User API (требует предварительной авторизации сессии)
            # Файл сессии должен быть создан заранее через скрипт authorize_telegram.py
            if not os.path.exists(session_path + '.session'):
                raise RuntimeError(
                    f"Сессия {session_path}.session не найдена. "
                    "Создайте сессию командой: python backend/scripts/authorize_telegram.py --client-id <id> --session-type publisher"
                )
            await self.client.start()
            logger.info(f"Telegram publisher подключен (User API, сессия: {self.session_name})")

    async def disconnect(self):
        """Отключиться от Telegram."""
        if self.client:
            await self.client.disconnect()
            logger.info("Telegram publisher отключен")

    def _split_text(self, text: str, max_length: int) -> List[str]:
        """
        Разделить длинный текст на части, не превышающие max_length.
        Старается разделять по границам предложений/абзацев.

        Args:
            text: Исходный текст
            max_length: Максимальная длина одной части

        Returns:
            Список частей текста
        """
        if len(text) <= max_length:
            return [text]

        parts = []
        current_part = ""

        # Разделяем по абзацам
        paragraphs = text.split('\n\n')

        for paragraph in paragraphs:
            # Если абзац сам по себе слишком длинный
            if len(paragraph) > max_length:
                # Разделяем по предложениям
                sentences = paragraph.replace('! ', '!|').replace('? ', '?|').replace('. ', '.|').split('|')

                for sentence in sentences:
                    # Если даже предложение слишком длинное, разделяем по словам
                    if len(sentence) > max_length:
                        words = sentence.split()
                        temp = ""
                        for word in words:
                            # Если слово само по себе длиннее лимита, режем принудительно
                            if len(word) > max_length:
                                # Сохраняем накопленное
                                if temp:
                                    parts.append(temp.strip())
                                    temp = ""
                                # Режем длинное слово на части
                                for i in range(0, len(word), max_length):
                                    parts.append(word[i:i+max_length])
                            elif len(temp) + len(word) + 1 <= max_length:
                                temp += (word + " ")
                            else:
                                if temp:
                                    parts.append(temp.strip())
                                temp = word + " "
                        if temp:
                            if current_part and len(current_part) + len(temp) <= max_length:
                                current_part += temp
                            else:
                                if current_part:
                                    parts.append(current_part.strip())
                                current_part = temp
                    else:
                        # Предложение помещается
                        if len(current_part) + len(sentence) + 1 <= max_length:
                            current_part += sentence + " "
                        else:
                            if current_part:
                                parts.append(current_part.strip())
                            current_part = sentence + " "
            else:
                # Абзац помещается
                if len(current_part) + len(paragraph) + 2 <= max_length:
                    current_part += paragraph + "\n\n"
                else:
                    if current_part:
                        parts.append(current_part.strip())
                    current_part = paragraph + "\n\n"

        if current_part:
            parts.append(current_part.strip())

        return parts

    async def publish_post(
        self,
        channel: str,
        text: str,
        image_path: Optional[str] = None,
        video_path: Optional[str] = None
    ) -> Dict:
        """
        Опубликовать пост в канал.

        Args:
            channel: Username канала (например, '@my_channel') или ID
            text: Текст сообщения
            image_path: Путь к изображению (опционально)
            video_path: Путь к видео (опционально)

        Returns:
            Словарь с результатом: {'success': bool, 'message_id': int, 'error': str}
        """
        if not self.client:
            raise RuntimeError("Клиент не подключен. Вызовите connect() сначала.")

        # Telegram ограничения
        MAX_CAPTION_LENGTH = 1024  # Максимальная длина подписи к медиа
        MAX_MESSAGE_LENGTH = 4096  # Максимальная длина текстового сообщения

        try:
            message = None
            message_ids = []

            # Публикация с медиа (приоритет видео над изображением)
            if image_path or video_path:
                media_path = video_path or image_path
                media_type = "видео" if video_path else "изображением"

                # Если текста нет, отправляем только медиа
                if not text or text.strip() == "":
                    logger.info(f"Публикация поста с {media_type} в {channel} (без текста)")
                    message = await self.client.send_file(channel, media_path)
                    message_ids.append(message.id)
                # Если текст слишком длинный для caption, разделяем
                elif len(text) > MAX_CAPTION_LENGTH:
                    logger.info(f"Текст ({len(text)} символов) превышает лимит caption ({MAX_CAPTION_LENGTH}). Разделяем на два сообщения.")

                    # 1. Отправляем медиа с коротким caption
                    caption = text[:MAX_CAPTION_LENGTH]
                    remaining_text = text[MAX_CAPTION_LENGTH:].strip()

                    logger.info(f"Публикация поста с {media_type} в {channel} (caption: {len(caption)} символов)")
                    message = await self.client.send_file(
                        channel,
                        media_path,
                        caption=caption
                    )
                    message_ids.append(message.id)

                    # 2. Отправляем остальной текст как отдельное сообщение
                    # Разделяем на части, если нужно
                    text_parts = self._split_text(remaining_text, MAX_MESSAGE_LENGTH)
                    for part in text_parts:
                        logger.info(f"Отправка продолжения текста ({len(part)} символов)")
                        text_message = await self.client.send_message(channel, part)
                        message_ids.append(text_message.id)
                else:
                    # Текст помещается в caption
                    logger.info(f"Публикация поста с {media_type} в {channel}")
                    message = await self.client.send_file(
                        channel,
                        media_path,
                        caption=text
                    )
                    message_ids.append(message.id)
            else:
                # Публикация только текста
                logger.info(f"Публикация текстового поста в {channel} ({len(text)} символов)")

                # Если текст слишком длинный, разделяем
                if len(text) > MAX_MESSAGE_LENGTH:
                    text_parts = self._split_text(text, MAX_MESSAGE_LENGTH)
                    logger.info(f"Текст разделен на {len(text_parts)} частей")
                    for i, part in enumerate(text_parts):
                        logger.info(f"Отправка части {i+1}/{len(text_parts)} ({len(part)} символов)")
                        msg = await self.client.send_message(channel, part)
                        message_ids.append(msg.id)
                        message = msg  # Сохраняем последнее сообщение
                else:
                    message = await self.client.send_message(channel, text)
                    message_ids.append(message.id)

            if message:
                main_message_id = message_ids[0]
                logger.info(f"Пост успешно опубликован в {channel}, ID: {main_message_id}")
                if len(message_ids) > 1:
                    logger.info(f"  + {len(message_ids) - 1} дополнительных сообщений")

                return {
                    'success': True,
                    'message_id': main_message_id,
                    'url': f"https://t.me/{channel.lstrip('@')}/{main_message_id}",
                    'total_messages': len(message_ids)
                }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось отправить сообщение'
                }

        except errors.ChannelPrivateError:
            error_msg = f"Нет доступа к каналу {channel} (приватный или заблокирован)"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        except errors.ChannelInvalidError:
            error_msg = f"Неверный канал: {channel}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f"Ошибка при публикации в {channel}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'error': error_msg}


def run_async_task(coro):
    """
    Вспомогательная функция для запуска асинхронных задач из синхронного кода.

    Args:
        coro: Корутина для выполнения

    Returns:
        Результат выполнения корутины
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def normalize_telegram_channel_identifier(value: str) -> str:
    """
    Преобразовать URL или @username в валидный username канала.

    Args:
        value: Строка с URL или именем канала

    Returns:
        str: Username в формате '@channel'
    """
    if not value:
        return ""

    candidate = value.strip()
    candidate = candidate.replace('https://', '').replace('http://', '')

    if candidate.startswith('t.me/') or candidate.startswith('telegram.me/'):
        candidate = candidate.split('/', 1)[1]

    if '://' in candidate or '/' in candidate:
        parsed = urlparse(candidate if '://' in candidate else f"https://{candidate}")
        path = parsed.path.lstrip('/')
        if path:
            candidate = path.split('/')[0]
        else:
            candidate = parsed.netloc

    candidate = candidate.replace('t.me/', '').replace('telegram.me/', '')
    candidate = candidate.replace('joinchat/', '').split('?')[0]
    candidate = candidate.strip('@').strip('/')

    if not candidate:
        return ""

    return candidate if candidate.startswith('@') else f"@{candidate}"
