import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YADISK_TOKEN")
HEADERS = {"Authorization": f"OAuth {TOKEN}"}


def safe_request(req_func, *args, retries: int = 5, backoff: int = 2, **kwargs):
    """
    Выполнить запрос с ретраями на 423 Locked (часто бывает у Я.Диска при параллельных аплоадах).

    Возвращает объект Response, как requests.*.
    """
    for i in range(retries):
        try:
            response = req_func(*args, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 423 and i < retries - 1:
                wait = backoff * (i + 1)
                print(f"⚠️ Locked, retry in {wait}s…")
                time.sleep(wait)
                continue
            raise


def create_folder(disk_path: str):
    """
    Создать папку на Яндекс.Диске.

    Важно: API не всегда создаёт промежуточные директории автоматически, поэтому
    создаём путь по частям.
    """
    disk_path = (disk_path or "").strip().strip("/")
    if not disk_path:
        return

    url = "https://cloud-api.yandex.net/v1/disk/resources"
    parts = [p for p in disk_path.split("/") if p]
    current = ""
    for part in parts:
        current = f"{current}/{part}" if current else part
        params = {"path": current}
        try:
            safe_request(requests.put, url, headers=HEADERS, params=params)
        except requests.exceptions.HTTPError as e:
            # 409 = папка уже существует (не ошибка)
            if getattr(getattr(e, "response", None), "status_code", None) != 409:
                raise


def get_upload_link(disk_path: str) -> str:
    url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    params = {"path": disk_path, "overwrite": "true"}
    r = safe_request(requests.get, url, headers=HEADERS, params=params)
    return r.json()["href"]


def upload_file(
    local_path: str,
    disk_path: str,
    logger=print,
    *,
    retries: int = 5,
    backoff: int = 2,
):
    folder = os.path.dirname(disk_path)
    if folder:
        create_folder(folder)

    if retries < 1:
        retries = 1

    for attempt in range(retries):
        upload_url = get_upload_link(disk_path)
        try:
            with open(local_path, "rb") as f:
                r = requests.put(upload_url, files={"file": f})
                r.raise_for_status()
            if logger:
                logger(f"Файл загружен: {disk_path}")
            return
        except requests.exceptions.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 404 and attempt < retries - 1:
                wait = 1
                print(f"⚠️ 404 upload-target, получаем новую ссылку (попытка {attempt + 1}), жду {wait}s…")
                time.sleep(wait)
                continue
            if status == 423 and attempt < retries - 1:
                wait = backoff * (attempt + 1)
                print(f"⚠️ Locked, retry in {wait}s…")
                time.sleep(wait)
                continue
            raise

    raise RuntimeError(f"Не удалось загрузить файл на Я.Диск после {retries} попыток: {disk_path}")


if __name__ == "__main__":
    with open("test_upload.txt", "w", encoding="utf-8") as f:
        f.write("Hello from Python!\nТест Яндекс.Диск API")

    upload_file(
        local_path="test_upload.txt",
        disk_path="python_tests/test_upload.txt"
    )
