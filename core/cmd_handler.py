from datetime import datetime

import botpy.message
from botpy.http import Route

from astrbot.core.platform.sources.qqofficial.qqofficial_message_event import (
    QQOfficialMessageEvent,
)

from .config import PluginConfig
from .models import (
    QQGroupContext,
    QQGroupInfo,
    QQGroupMuteStatus,
)
from .qq_service import QQOfficialService


class CmdHandler:
    def __init__(self, cfg: PluginConfig, service: QQOfficialService):
        self.cfg = cfg
        self.service = service

    @staticmethod
    def _format_duration(seconds: int) -> str:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")

        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, remaining_seconds = divmod(remainder, 60)

        parts: list[str] = []
        if days:
            parts.append(f"{days}天")
        if hours:
            parts.append(f"{hours}小时")
        if minutes:
            parts.append(f"{minutes}分")
        if remaining_seconds or not parts:
            parts.append(f"{remaining_seconds}秒")
        return "".join(parts)

    async def get_group_info(self, event: QQOfficialMessageEvent) -> str:
        ctx = QQGroupContext.from_event(event)
        result = await self.service.get_group_info(ctx.group_openid)
        if error := result.get("error"):
            return error
        info = QQGroupInfo.from_dict(result)
        lines = []
        if info.group_name:
            lines.append(f"群名称：{info.group_name}")
        if info.group_finger_memo:
            lines.append(f"群简介：{info.group_finger_memo}")
        if info.group_class_text:
            lines.append(f"群分类：{info.group_class_text}")
        if info.group_tags:
            lines.append(f"群标签：{'、'.join(info.group_tags)}")
        if info.group_member_num is not None:
            lines.append(f"成员数：{info.group_member_num}")
        return "\n".join(lines)

    async def get_mute_status(self, event: QQOfficialMessageEvent) -> str:
        ctx = QQGroupContext.from_event(event)
        result = await self.service.get_mute_status(ctx.group_openid)
        if error := result.get("error"):
            return error
        status = QQGroupMuteStatus.from_dict(result)
        mode_names = {
            "schedule": "定时禁言",
            "always": "全员禁言",
            "none": "未开启禁言",
        }
        mode = mode_names.get(status.global_rule.mode, status.global_rule.mode)
        lines = []
        if mode:
            lines.append(f"禁言类型：{mode}")

        active_schedule_rules = [
            rule for rule in status.global_rule.schedule_rules if rule.enabled
        ]
        if active_schedule_rules:
            schedule_lines = []
            for rule in active_schedule_rules:
                start_at = ""
                if rule.start_at:
                    try:
                        start_at = datetime.fromisoformat(
                            rule.start_at.replace("Z", "+00:00")
                        ).strftime("%Y年%m月%d日 %H:%M")
                    except ValueError:
                        start_at = rule.start_at
                end_at = ""
                if rule.end_at:
                    try:
                        end_at = datetime.fromisoformat(
                            rule.end_at.replace("Z", "+00:00")
                        ).strftime("%Y年%m月%d日 %H:%M")
                    except ValueError:
                        end_at = rule.end_at
                schedule = " ~ ".join(value for value in (start_at, end_at) if value)
                if schedule:
                    schedule_lines.append(f"- {schedule}")
            if schedule_lines:
                lines.append("定时规则：")
                lines.extend(schedule_lines)

        weekday_names = {
            1: "周一",
            2: "周二",
            3: "周三",
            4: "周四",
            5: "周五",
            6: "周六",
            7: "周日",
        }
        active_recurring_rules = [
            rule for rule in status.global_rule.recurring_rules if rule.enabled
        ]
        if active_recurring_rules:
            recurring_lines = []
            for rule in active_recurring_rules:
                weekdays = "、".join(
                    weekday_names.get(day, str(day)) for day in rule.weekdays
                )
                time_range = " ~ ".join(
                    value for value in (rule.start_time, rule.end_time) if value
                )
                recurring_rule = " ".join(
                    value for value in (weekdays, time_range) if value
                )
                if recurring_rule:
                    recurring_lines.append(f"- {recurring_rule}")
            if recurring_lines:
                lines.append("周期规则：")
                lines.extend(recurring_lines)

        if status.members:
            lines.append("")
            lines.append(f"被禁成员：{len(status.members)} 人")
            for member in status.members:
                expire_at = datetime.fromisoformat(
                    member.mute_expire_at.replace("Z", "+00:00")
                )
                remaining_seconds = int(
                    (expire_at - datetime.now(expire_at.tzinfo)).total_seconds()
                )
                remaining = f"剩余{self._format_duration(remaining_seconds)}"
                lines.append(f"- {member.username}（{remaining}）")
        return "\n".join(lines)

    async def set_mute_member(
        self, event: QQOfficialMessageEvent, seconds: int | None = None
    ) -> str:
        ctx = QQGroupContext.from_event(event)
        is_admin = event.is_admin()
        return await self.service.set_member_mute(ctx, seconds, is_admin)

    async def _recall_qqofficial_message(
        self, event: QQOfficialMessageEvent, message_id: str
    ) -> None:
        source = event.message_obj.raw_message
        route_path = None
        route_params = {}

        if isinstance(source, botpy.message.GroupMessage):
            route_path = "/v2/groups/{group_openid}/messages/{message_id}"
            route_params["group_openid"] = source.group_openid
        elif isinstance(source, botpy.message.C2CMessage):
            route_path = "/v2/users/{openid}/messages/{message_id}"
            route_params["openid"] = source.author.user_openid
        elif isinstance(source, botpy.message.DirectMessage):
            route_path = "/dms/{guild_id}/messages/{message_id}"
            route_params["guild_id"] = source.guild_id
        elif isinstance(source, botpy.message.Message):
            await event.bot.api.recall_message(
                channel_id=source.channel_id,
                message_id=message_id,
            )
            return

        if route_path:
            await event.bot.api._http.request(
                Route(
                    "DELETE",
                    route_path,
                    message_id=message_id,
                    **route_params,
                )
            )
