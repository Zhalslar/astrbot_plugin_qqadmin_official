from __future__ import annotations

from typing import Any

from botpy import Client


class QQMessageSender:
    """Send QQ Official messages used by the administration plugin."""

    def __init__(self, bot: Client):
        self.bot = bot

    async def send_group_markdown(
        self,
        group_openid: str,
        content: str,
        keyboard: dict[str, Any] | None = None,
        msg_id: str | None = None,
        msg_seq: int = 1,
    ) -> None:
        await self.bot.api.post_group_message(
            group_openid=group_openid,
            msg_type=2,
            markdown={"content": content},
            keyboard=keyboard,
            msg_id=msg_id,
            msg_seq=msg_seq,
        )
