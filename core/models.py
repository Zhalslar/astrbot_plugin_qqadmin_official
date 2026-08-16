from __future__ import annotations

from dataclasses import dataclass, field

import botpy.message

from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Reply


@dataclass(slots=True)
class QQGroupContext:
    """Normalized QQ Official group message data for plugin features."""

    group_openid: str
    sender_openid: str
    member_role: str
    target_member_openids: list[str]
    message_str: str
    referenced_message_str: str

    @classmethod
    def from_event(cls, event: AstrMessageEvent) -> QQGroupContext:
        """Create a group context from an AstrBot event.

        Args:
            event: AstrBot message event containing a QQ Official message.

        Returns:
            A normalized group context, or None when the event is not a QQ
            Official group message.
        """
        raw_message = getattr(event.message_obj, "raw_message", None)
        if not isinstance(raw_message, botpy.message.GroupMessage):
            raise ValueError("Not a QQ Official group message")

        raw_data = getattr(raw_message, "raw_data", {})
        if not isinstance(raw_data, dict):
            raw_data = {}
        author_data = raw_data.get("author", {})
        if not isinstance(author_data, dict):
            author_data = {}

        target_member_openids: list[str] = []
        for mention in getattr(raw_message, "mentions", None) or []:
            if getattr(mention, "is_you", False) is True:
                continue
            member_openid = str(getattr(mention, "member_openid", None) or "")
            if member_openid and member_openid not in target_member_openids:
                target_member_openids.append(member_openid)

        referenced_message_str = ""
        for component in event.get_messages():
            if isinstance(component, Reply):
                referenced_message_str = str(
                    component.message_str or component.text or ""
                ).strip()
                break
        if not referenced_message_str:
            try:
                is_reply = int(getattr(raw_message, "message_type", 0) or 0) == 103
            except (TypeError, ValueError):
                is_reply = False
            if is_reply:
                for element in getattr(raw_message, "msg_elements", None) or []:
                    if isinstance(element, dict):
                        referenced_message_str = str(
                            element.get("content") or ""
                        ).strip()
                    else:
                        referenced_message_str = str(
                            getattr(element, "content", None) or ""
                        ).strip()
                    if referenced_message_str:
                        break
        return cls(
            group_openid=str(raw_message.group_openid or event.get_group_id()),
            sender_openid=event.get_sender_id(),
            member_role=str(
                author_data.get("member_role") or raw_data.get("member_role") or ""
            ).lower(),
            target_member_openids=target_member_openids,
            message_str=event.message_str,
            referenced_message_str=referenced_message_str,
        )


@dataclass(slots=True)
class QQGroupInfo:
    """Normalized QQ Official group information."""

    group_openid: str = ""
    group_name: str = ""
    group_finger_memo: str = ""
    group_class_text: str = ""
    group_tags: list[str] | None = None
    group_member_num: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> QQGroupInfo:
        """Create group information from a QQ API response.

        Args:
            data: QQ Official group information response.

        Returns:
            A normalized group information model.
        """
        tags = data.get("group_tags")
        if isinstance(tags, list):
            group_tags = [str(tag) for tag in tags]
        else:
            group_tags = None

        member_num = data.get("group_member_num")
        if not isinstance(member_num, int):
            member_num = None

        return cls(
            group_openid=str(data.get("group_openid") or ""),
            group_name=str(data.get("group_name") or ""),
            group_finger_memo=str(data.get("group_finger_memo") or ""),
            group_class_text=str(data.get("group_class_text") or ""),
            group_tags=group_tags,
            group_member_num=member_num,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert the model to a QQ API-compatible dictionary.

        Returns:
            Group information represented as a dictionary.
        """
        return {
            "group_openid": self.group_openid,
            "group_name": self.group_name,
            "group_finger_memo": self.group_finger_memo,
            "group_class_text": self.group_class_text,
            "group_tags": self.group_tags or [],
            "group_member_num": self.group_member_num,
        }


@dataclass(slots=True)
class QQJoinRequestReviewQA:
    """One question and answer from a join request review."""

    question: str = ""
    answer: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> QQJoinRequestReviewQA:
        """Create a review question and answer from QQ API data.

        Args:
            data: One review question and answer item.

        Returns:
            A normalized review question and answer model.
        """
        return cls(
            question=str(data.get("question") or ""),
            answer=str(data.get("answer") or ""),
        )

    def to_dict(self) -> dict[str, str]:
        """Convert the review question and answer to a dictionary.

        Returns:
            Review question and answer data represented as a dictionary.
        """
        return {"question": self.question, "answer": self.answer}


@dataclass(slots=True)
class QQJoinRequestVerifyInfo:
    """Verification information attached to a group join request."""

    method: str = ""
    verify_message: str = ""
    review_qa_list: list[QQJoinRequestReviewQA] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> QQJoinRequestVerifyInfo:
        """Create verification information from QQ API data.

        Args:
            data: Join request verification information.

        Returns:
            A normalized verification information model.
        """
        raw_review_qa_list = data.get("review_qa_list")
        review_qa_list = []
        if isinstance(raw_review_qa_list, list):
            review_qa_list = [
                QQJoinRequestReviewQA.from_dict(item)
                for item in raw_review_qa_list
                if isinstance(item, dict)
            ]
        return cls(
            method=str(data.get("method") or ""),
            verify_message=str(data.get("verify_message") or ""),
            review_qa_list=review_qa_list,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert verification information to a dictionary.

        Returns:
            Verification information represented as a dictionary.
        """
        return {
            "method": self.method,
            "verify_message": self.verify_message,
            "review_qa_list": [item.to_dict() for item in self.review_qa_list],
        }


@dataclass(slots=True)
class QQGroupJoinRequest:
    """Normalized QQ Official group join request."""

    group_openid: str = ""
    join_request_id: str = ""
    risk_tips: str = ""
    union_openid: str = ""
    member_openid: str = ""
    username: str = ""
    apply_at: str = ""
    apply_source: str = ""
    invited_by: str = ""
    bot: bool | None = None
    verify_info: QQJoinRequestVerifyInfo = field(
        default_factory=QQJoinRequestVerifyInfo
    )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> QQGroupJoinRequest:
        """Create a group join request from a QQ API response item.

        Args:
            data: One item from the QQ group join request list response.

        Returns:
            A normalized group join request model.
        """
        raw_verify_info = data.get("verify_info")
        if not isinstance(raw_verify_info, dict):
            raw_verify_info = {}
        raw_bot = data.get("bot")
        return cls(
            group_openid=str(data.get("group_openid") or ""),
            join_request_id=str(data.get("join_request_id") or ""),
            risk_tips=str(data.get("risk_tips") or ""),
            union_openid=str(data.get("union_openid") or ""),
            member_openid=str(data.get("member_openid") or ""),
            username=str(data.get("username") or ""),
            apply_at=str(data.get("apply_at") or ""),
            apply_source=str(data.get("apply_source") or ""),
            invited_by=str(data.get("invited_by") or ""),
            bot=raw_bot if isinstance(raw_bot, bool) else None,
            verify_info=QQJoinRequestVerifyInfo.from_dict(raw_verify_info),
        )

    def to_dict(self) -> dict[str, object]:
        """Convert the join request model to a dictionary.

        Returns:
            Join request data represented as a dictionary.
        """
        return {
            "group_openid": self.group_openid,
            "join_request_id": self.join_request_id,
            "risk_tips": self.risk_tips,
            "union_openid": self.union_openid,
            "member_openid": self.member_openid,
            "username": self.username,
            "apply_at": self.apply_at,
            "apply_source": self.apply_source,
            "invited_by": self.invited_by,
            "bot": self.bot,
            "verify_info": self.verify_info.to_dict(),
        }


@dataclass(slots=True)
class QQMuteScheduleRule:
    """One scheduled group-wide mute rule."""

    task_id: str = ""
    start_at: str = ""
    end_at: str = ""
    enabled: bool = False


@dataclass(slots=True)
class QQMuteRecurringRule:
    """One recurring group-wide mute rule."""

    task_id: str = ""
    weekdays: list[int] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    enabled: bool = False


@dataclass(slots=True)
class QQMuteGlobalRule:
    """Group-wide mute configuration."""

    mode: str = ""
    schedule_rules: list[QQMuteScheduleRule] = field(default_factory=list)
    recurring_rules: list[QQMuteRecurringRule] = field(default_factory=list)


@dataclass(slots=True)
class QQMutedMember:
    """One currently muted QQ group member."""

    member_openid: str = ""
    mute_expire_at: str = ""
    username: str = ""
    union_openid: str = ""


@dataclass(slots=True)
class QQGroupMuteStatus:
    """Normalized QQ Official group mute status."""

    global_rule: QQMuteGlobalRule = field(default_factory=QQMuteGlobalRule)
    members: list[QQMutedMember] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> QQGroupMuteStatus:
        """Create a mute status model from a QQ API response.

        Args:
            data: QQ Official mute status response.

        Returns:
            A normalized group mute status model.
        """
        global_data = data.get("global_rule")
        if not isinstance(global_data, dict):
            global_data = {}

        schedule_rules: list[QQMuteScheduleRule] = []
        raw_schedule_rules = global_data.get("schedule_rules")
        if isinstance(raw_schedule_rules, list):
            for rule in raw_schedule_rules:
                if not isinstance(rule, dict):
                    continue
                schedule_rules.append(
                    QQMuteScheduleRule(
                        task_id=str(rule.get("task_id") or ""),
                        start_at=str(rule.get("start_at") or ""),
                        end_at=str(rule.get("end_at") or ""),
                        enabled=rule.get("enabled") is True,
                    )
                )

        recurring_rules: list[QQMuteRecurringRule] = []
        raw_recurring_rules = global_data.get("recurring_rules")
        if isinstance(raw_recurring_rules, list):
            for rule in raw_recurring_rules:
                if not isinstance(rule, dict):
                    continue
                weekdays = rule.get("weekdays")
                recurring_rules.append(
                    QQMuteRecurringRule(
                        task_id=str(rule.get("task_id") or ""),
                        weekdays=(
                            [day for day in weekdays if isinstance(day, int)]
                            if isinstance(weekdays, list)
                            else []
                        ),
                        start_time=str(rule.get("start_time") or ""),
                        end_time=str(rule.get("end_time") or ""),
                        enabled=rule.get("enabled") is True,
                    )
                )

        members: list[QQMutedMember] = []
        raw_members = data.get("members")
        if isinstance(raw_members, list):
            for member in raw_members:
                if not isinstance(member, dict):
                    continue
                members.append(
                    QQMutedMember(
                        member_openid=str(member.get("member_openid") or ""),
                        mute_expire_at=str(member.get("mute_expire_at") or ""),
                        username=str(member.get("username") or ""),
                        union_openid=str(member.get("union_openid") or ""),
                    )
                )

        return cls(
            global_rule=QQMuteGlobalRule(
                mode=str(global_data.get("mode") or ""),
                schedule_rules=schedule_rules,
                recurring_rules=recurring_rules,
            ),
            members=members,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert the mute status model to a dictionary.

        Returns:
            Mute status represented as a dictionary.
        """
        return {
            "global_rule": {
                "mode": self.global_rule.mode,
                "schedule_rules": [
                    {
                        "task_id": rule.task_id,
                        "start_at": rule.start_at,
                        "end_at": rule.end_at,
                        "enabled": rule.enabled,
                    }
                    for rule in self.global_rule.schedule_rules
                ],
                "recurring_rules": [
                    {
                        "task_id": rule.task_id,
                        "weekdays": rule.weekdays,
                        "start_time": rule.start_time,
                        "end_time": rule.end_time,
                        "enabled": rule.enabled,
                    }
                    for rule in self.global_rule.recurring_rules
                ],
            },
            "members": [
                {
                    "member_openid": member.member_openid,
                    "mute_expire_at": member.mute_expire_at,
                    "username": member.username,
                    "union_openid": member.union_openid,
                }
                for member in self.members
            ],
        }
