import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YADISK_TOKEN")
HEADERS = {"Authorization": f"OAuth {TOKEN}"}


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
        r = requests.put(url, headers=HEADERS, params=params)

        if r.status_code not in (201, 409):  # 409 = папка уже есть
            r.raise_for_status()


def get_upload_link(disk_path: str) -> str:
    url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    params = {"path": disk_path, "overwrite": "true"}
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()["href"]


def upload_file(local_path: str, disk_path: str):
    folder = os.path.dirname(disk_path)
    if folder:
        create_folder(folder)

    upload_url = get_upload_link(disk_path)

    with open(local_path, "rb") as f:
        r = requests.put(upload_url, files={"file": f})
        r.raise_for_status()

    print(f"Файл загружен: {disk_path}")


if __name__ == "__main__":
    with open("test_upload.txt", "w", encoding="utf-8") as f:
        f.write("Hello from Python!\nТест Яндекс.Диск API")

    upload_file(
        local_path="test_upload.txt",
        disk_path="python_tests/test_upload.txt"
    )
