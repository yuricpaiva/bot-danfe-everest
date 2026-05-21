from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from config import TelegramSettings


LOGGER = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, settings: TelegramSettings) -> None:
        self._token = settings.token
        self._chat_id = settings.chat_id

    @property
    def enabled(self) -> bool:
        return bool(self._token and self._chat_id)

    def send(self, message: str) -> None:
        if not self.enabled:
            LOGGER.warning("Telegram nao configurado. Pulando envio de notificacao.")
            return

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = json.dumps(
            {
                "chat_id": self._chat_id,
                "text": message,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            LOGGER.exception("Falha ao enviar notificacao para o Telegram: %s", exc)
