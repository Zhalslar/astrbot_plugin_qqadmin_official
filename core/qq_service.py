from __future__ import annotations

from typing import Any

import botpy.errors

from astrbot.api import logger

from .models import QQGroupContext, QQGroupMuteStatus
from .qq_api import QQOfficialAPI


class QQOfficialService:
    """Implement reusable QQ Official group management features."""

    def __init__(self, api: QQOfficialAPI):
        self.api = api
        self.bot = self.api.bot

    async def get_group_info(self, group_openid: str) -> dict[str, Any]:
        try:
            return await self.api.get_group_info(group_openid)
        except Exception as exc:
            logger.error("get group info failed: group_openid=%s", group_openid)
            return {"error": self._api_error_message(exc, "获取群信息失败")}

    async def get_mute_status(self, group_openid: str) -> dict[str, Any]:
        try:
            return await self.api.get_mute_status(group_openid)
        except Exception as exc:
            logger.error("get mute status failed: group_openid=%s", group_openid)
            return {"error": self._api_error_message(exc, "获取禁言状态失败")}

    async def set_member_mute(
        self,
        ctx: QQGroupContext,
        seconds: int | None,
        is_astrbot_admin: bool,
        operation: str | None = None,
    ) -> str:
        if not is_astrbot_admin and ctx.member_role not in {"admin", "owner"}:
            return "你权限不足"

        operation = operation or ("add" if seconds else "del")
        target_ids = list(ctx.target_member_openids)

        try:
            if operation in {"add", "update"}:
                target_ids = target_ids[:10] or [ctx.sender_openid]
                duration = (
                    seconds
                    if isinstance(seconds, int) and 1 <= seconds <= 2592000
                    else 60
                )
                await self.api.set_member_mute(
                    ctx.group_openid,
                    target_ids,
                    operation,
                    seconds=duration,
                )
            else:
                if not target_ids:
                    mute_status = await self.api.get_mute_status(ctx.group_openid)
                    if not isinstance(mute_status, QQGroupMuteStatus):
                        mute_status = QQGroupMuteStatus.from_dict(mute_status)
                    target_ids = [
                        member.member_openid
                        for member in mute_status.members
                        if member.member_openid
                    ]
                    if not target_ids:
                        return "当前没有被禁言的成员"
                for offset in range(0, len(target_ids), 10):
                    await self.api.set_member_mute(
                        ctx.group_openid,
                        target_ids[offset : offset + 10],
                        "del",
                    )
        except botpy.errors.ForbiddenError:
            return "我没权限"
        except botpy.errors.AuthenticationFailedError:
            return "鉴权失败"
        except Exception as exc:
            logger.exception(
                "mute operation failed: operation=%s, group_openid=%s, targets=%s",
                operation,
                ctx.group_openid,
                target_ids,
            )
            return f"禁言失败：{exc}"

        return ""

    async def list_join_requests(
        self, group_openid: str, cursor: str = "", limit: int = 100
    ) -> dict[str, Any]:
        try:
            result = await self.api.list_join_requests(group_openid, cursor, limit)
            raw_requests = result.get("list", [])
            if not isinstance(raw_requests, list):
                return {"error": "获取的群组入群请求列表不是列表"}
            if not all(isinstance(x, dict) for x in raw_requests):
                return {"error": "群组入群请求列表中存在非字典元素"}
            return {"list": raw_requests}
        except Exception as exc:
            logger.exception("list join requests failed: group_openid=%s", group_openid)
            return {"error": self._api_error_message(exc, "获取入群申请失败")}

    async def approve_join_request(
        self,
        ctx: QQGroupContext,
        is_astrbot_admin: bool,
        member_openid: str,
        join_request_id: str = "",
    ) -> str | None:

        if not self._has_admin_permission(ctx, is_astrbot_admin):
            return "你权限不足"
        try:
            await self.api.approve_join_request(
                ctx.group_openid, member_openid, join_request_id
            )
        except Exception as exc:
            logger.exception(
                "approve join request failed: group_openid=%s, member_openid=%s",
                ctx.group_openid,
                member_openid,
            )
            return self._api_error_message(exc, "同意入群失败")
        return None

    async def decline_join_request(
        self,
        ctx: QQGroupContext,
        is_astrbot_admin: bool,
        member_openid: str,
        join_request_id: str = "",
        reject_reason: str = "",
        add_to_member_blacklist: bool = False,
    ) -> str | None:
        if not self._has_admin_permission(ctx, is_astrbot_admin):
            return "你权限不足"
        try:
            await self.api.decline_join_request(
                ctx.group_openid,
                member_openid,
                join_request_id,
                reject_reason,
                add_to_member_blacklist,
            )
        except Exception as exc:
            logger.exception(
                "decline join request failed: group_openid=%s, member_openid=%s",
                ctx.group_openid,
                member_openid,
            )
            return self._api_error_message(exc, "拒绝入群失败")
        return None

    def _has_admin_permission(
        self, ctx: QQGroupContext, is_astrbot_admin: bool
    ) -> bool:
        """Check QQ group administration permission."""
        return is_astrbot_admin or ctx.member_role in {"admin", "owner"}

    @staticmethod
    def _api_error_message(exc: Exception, action: str) -> str:
        """Convert a QQ API exception to a concise user-facing message."""
        if isinstance(exc, botpy.errors.ForbiddenError):
            return "我没权限"
        if isinstance(exc, botpy.errors.AuthenticationFailedError):
            return "鉴权失败"
        return f"{action}：{exc}"
