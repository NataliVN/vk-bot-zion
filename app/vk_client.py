from __future__ import annotations

import os
import requests
import vk_api

from app.config import settings

class VKClient:
    def __init__(self) -> None:
        self.session = vk_api.VkApi(token=settings.vk_group_token)
        self.api = self.session.get_api()

    def send_message(self, peer_id: int, text: str, keyboard: str | None = None) -> None:
        params = {"peer_id": peer_id, "message": text, "random_id": self._random_id()}
        if keyboard:
            params["keyboard"] = keyboard
        self.api.messages.send(**params)

    def answer_message_event(self, event_id: str, user_id: int, peer_id: int, payload: dict | None = None) -> None:
        self.api.messages.sendMessageEventAnswer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            event_data=payload or {},
        )

    def download_photo(self, url: str, save_path: str) -> str:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(r.content)
        return save_path

    def upload_wall_photo(self, file_path: str) -> str:
        upload_server = self.api.photos.getWallUploadServer(group_id=settings.vk_group_id)
        with open(file_path, "rb") as f:
            resp = requests.post(upload_server["upload_url"], files={"photo": f}, timeout=60)
        data = resp.json()
        saved = self.api.photos.saveWallPhoto(
            group_id=settings.vk_group_id,
            photo=data["photo"],
            server=data["server"],
            hash=data["hash"],
        )
        photo = saved[0]
        return f"photo{photo['owner_id']}_{photo['id']}"

    def upload_wall_photos(self, file_paths: list[str]) -> list[str]:
        return [self.upload_wall_photo(path) for path in file_paths]

    def schedule_wall_post(self, message: str, attachments: list[str] | None, publish_date: int) -> dict:
        params = {
            "owner_id": -settings.vk_group_id,
            "from_group": 1,
            "message": message,
            "publish_date": publish_date,
            "random_id": self._random_id(),
            "v": settings.vk_api_version,
        }
        if attachments:
            params["attachments"] = ",".join(attachments)
        return self.api.wall.post(**params)

    @staticmethod
    def _random_id() -> int:
        return int.from_bytes(os.urandom(4), "little")
