import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from botpy.interaction import Interaction
from botpy.types.inline import (
    Action,
    Button,
    Keyboard,
    KeyboardRow,
    Permission,
    RenderData,
)
from botpy.types.message import KeyboardPayload, MarkdownPayload

from astrbot import logger
from astrbot.core.platform.sources.qqofficial.qqofficial_message_event import (
    QQOfficialMessageEvent,
)

from .config import PluginConfig
from .models import (
    QQGroupContext,
    QQGroupJoinRequest,
)
from .qq_service import QQOfficialService


class JoinHandler:
    def __init__(self, cfg: PluginConfig, service: QQOfficialService):
        self.cfg = cfg
        self.service = service

    @staticmethod
    def format_iso_datetime(iso_str: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            dt_utc = dt.astimezone(timezone.utc)
            return dt_utc.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return iso_str

    def _build_approve_content(self, request: QQGroupJoinRequest) -> str:
        lines = ["### 【进群申请】请审批："]
        lines.append(f"昵称：{request.username}")
        if request.apply_at:
            apply_at = self.format_iso_datetime(request.apply_at)
            lines.append(f"时间：{apply_at}")
        if request.apply_source:
            apply_source = {
                "self_apply": "主动申请",
                "invited": "被邀请",
            }.get(request.apply_source, request.apply_source)
            lines.append(f"来源：{apply_source}")
        if request.invited_by:
            lines.append(f"邀请人：{request.invited_by}")
        if request.bot:
            lines.append("人机：是")
        if request.risk_tips:
            lines.append(f"提示：{request.risk_tips}")

        verify_info = request.verify_info
        if verify_info.verify_message:
            lines.append(f"验证：{verify_info.verify_message}")
        if verify_info.review_qa_list:
            for _, review_qa in enumerate(verify_info.review_qa_list, 1):
                if review_qa.question:
                    lines.append(f"问题：{review_qa.question}")
                if review_qa.answer:
                    lines.append(f"回答：{review_qa.answer}")
        return "\n".join(lines)

    def _build_approve_keyboard(self, request: QQGroupJoinRequest) -> Keyboard:
        approve_data = json.dumps(
            {
                "action": "approve",
                "member_openid": request.member_openid,
                "join_request_id": request.join_request_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        decline_data = json.dumps(
            {
                "action": "decline",
                "member_openid": request.member_openid,
                "join_request_id": request.join_request_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        button1 = Button(
            id="qqadmin_join_request_approve",
            render_data=RenderData(label="批准", visited_label="已批准", style=2),
            action=Action(
                type=1,
                permission=Permission(type=1, specify_role_ids=[], specify_user_ids=[]),
                click_limit=1,
                data=approve_data,
                at_bot_show_channel_list=True,
            ),
        )
        button2 = Button(
            id="qqadmin_join_request_decline",
            render_data=RenderData(label="驳回", visited_label="已驳回", style=2),
            action=Action(
                type=1,
                permission=Permission(type=1, specify_role_ids=[], specify_user_ids=[]),
                click_limit=1,
                data=decline_data,
                at_bot_show_channel_list=True,
            ),
        )
        row1 = KeyboardRow(buttons=[button1, button2])
        return Keyboard(rows=[row1])

    async def _get_join_requests(
        self, event: QQOfficialMessageEvent, limit: int = 100
    ) -> list[QQGroupJoinRequest] | str:
        ctx = QQGroupContext.from_event(event)
        result = await self.service.list_join_requests(ctx.group_openid, limit=limit)
        if error := result.get("error"):
            return error
        requests = [
            QQGroupJoinRequest.from_dict(item)
            for item in result.get("list", [])
            if isinstance(item, dict)
        ]
        if not requests:
            return "暂无入群申请"

        return requests

    async def get_join_requests_content(
        self, event: QQOfficialMessageEvent, limit: int = 100
    ) -> str:
        result = await self._get_join_requests(event, limit)
        if isinstance(result, str):
            return result
        return "\n".join(self._build_approve_content(request) for request in result)

    async def send_join_request(
        self, event: QQOfficialMessageEvent, limit: int = 100
    ) -> str | None:
        source = event.message_obj.raw_message
        group_openid = getattr(source, "group_openid", "")
        message_id = getattr(source, "id", "")
        result = await self._get_join_requests(event, limit)
        if isinstance(result, str):
            await event.bot.api.post_group_message(group_openid, content=result)
            return
        for index, request in enumerate(result, 1):
            markdown = MarkdownPayload(content=self._build_approve_content(request))
            keyboard = KeyboardPayload(content=self._build_approve_keyboard(request))
            await event.bot.api.post_group_message(
                group_openid,
                msg_type=2,
                markdown=markdown,
                keyboard=keyboard,  # type: ignore
                msg_id=message_id,
                msg_seq=index,
            )

    async def handle_group_join_request(self, event: Any) -> bool:
        raw_data = getattr(event, "raw_data", None)
        if not isinstance(raw_data, dict):
            return False
        if raw_data.get("auto_approved"):
            return True

        request = QQGroupJoinRequest.from_dict(raw_data)
        if not request.group_openid or not request.join_request_id:
            logger.warning("Ignore incomplete QQ group join request event")
            return True
        markdown = MarkdownPayload(content=self._build_approve_content(request))
        keyboard = KeyboardPayload(content=self._build_approve_keyboard(request))
        await self.service.bot.api.post_group_message(
            request.group_openid,
            msg_type=2,
            markdown=markdown,
            keyboard=keyboard,  # type: ignore
        )
        return True

    async def handle_interaction(
        self,
        interaction: Interaction,
    ) -> bool:
        """Handle an inline keyboard interaction owned by the join handler.

        Args:
            interaction: The QQ inline keyboard interaction.

        Returns:
            Whether the interaction belongs to this handler.
        """
        resolved = interaction.data.resolved
        button_id = getattr(resolved, "button_id", "")
        button_data = getattr(resolved, "button_data", "") or ""
        try:
            decoded_payload = json.loads(button_data)
        except (json.JSONDecodeError, TypeError):
            decoded_payload = {}
        payload = decoded_payload if isinstance(decoded_payload, dict) else {}

        if button_id == "qqadmin_interaction_button":
            await interaction._api.on_interaction_result(interaction.id, 0)
            return True

        if button_id not in {
            "qqadmin_join_request_approve",
            "qqadmin_join_request_decline",
        } and payload.get("action") not in {"approve", "decline"}:
            return False

        await interaction._api.on_interaction_result(interaction.id, 0)
        group_openid = str(
            getattr(interaction, "group_openid", "")
            or getattr(resolved, "group_openid", "")
            or ""
        )
        if not group_openid:
            return True

        asyncio.create_task(
            self._handle_join_request_button(
                interaction,
                group_openid,
                payload,
            )
        )
        return True

    async def _handle_join_request_button(
        self,
        interaction: Interaction,
        group_openid: str,
        payload: dict[str, Any],
    ) -> None:
        member_openid = str(payload.get("member_openid") or "")
        join_request_id = str(payload.get("join_request_id") or "")
        action = payload.get("action")
        if (
            not member_openid
            or not join_request_id
            or action not in {"approve", "decline"}
        ):
            return

        ctx = QQGroupContext(
            group_openid=group_openid,
            sender_openid=interaction.group_member_openid,
            member_role="admin",
            target_member_openids=[],
            message_str="",
            referenced_message_str="",
        )
        if action == "approve":
            error = await self.service.approve_join_request(
                ctx,
                True,
                member_openid,
                join_request_id,
            )
            logger.debug("Approve join request: %s", error or "Success")
        else:
            error = await self.service.decline_join_request(
                ctx,
                True,
                member_openid,
                join_request_id,
            )
            logger.debug("Decline join request: %s", error or "Success")
