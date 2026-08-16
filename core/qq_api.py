from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from botpy.http import Route

from astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter import (
    botClient,
)


class QQOfficialAPI:
    """Convenience wrapper for QQ Official group management APIs."""

    def __init__(self, bot: botClient):
        """Initialize the group API wrapper.

        Args:
            bot: QQ Official bot client.
        """
        self.bot = bot
        self.api = self.bot.api
        self.http = self.bot.api._http

    async def _request(
        self,
        method: str,
        path: str,
        path_params: dict[str, str],
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Send a request to a QQ Official group management endpoint.

        Args:
            method: HTTP method.
            path: API path template.
            path_params: Values for path template parameters.
            payload: Optional JSON request body.

        Returns:
            The decoded QQ API response.
        """
        route = Route(method, path, **path_params)
        if self.http is None:
            raise RuntimeError("QQ Official API client is not initialized")
        if payload is None:
            return await self.http.request(route)
        return await self.http.request(route, json=payload)

    async def get_group_info(self, group_openid: str) -> dict[str, Any]:
        """Get basic information about a QQ group.

        Args:
            group_openid: QQ group OpenID.

        Returns:
            Group information returned by QQ.
        """
        return await self._request(
            "GET",
            "/v2/groups/{group_openid}/info",
            {"group_openid": group_openid},
        )

    async def get_bot_state(self, group_openid: str) -> dict[str, Any]:
        """Get the bot's state in a QQ group.

        Args:
            group_openid: QQ group OpenID.

        Returns:
            Bot group state returned by QQ.
        """
        return await self._request(
            "GET",
            "/v2/groups/{group_openid}/bot_state",
            {"group_openid": group_openid},
        )

    async def get_mute_status(self, group_openid: str) -> dict[str, Any]:
        """Get current group-wide and member mute states.

        Args:
            group_openid: QQ group OpenID.

        Returns:
            Mute status returned by QQ.
        """
        return await self._request(
            "GET",
            "/v2/groups/{group_openid}/restrict_chat_setting",
            {"group_openid": group_openid},
        )

    async def set_member_mute(
        self,
        group_openid: str,
        member_openids: list[str],
        operation: str,
        seconds: int | None = None,
        mute_expire_at: str | None = None,
    ) -> Any:
        """Set, update, or remove member mute state.

        Args:
            group_openid: QQ group OpenID.
            member_openids: Member OpenIDs, with at most 10 members.
            operation: Operation type: ``add``, ``update``, or ``del``.
            seconds: Mute duration in seconds for ``add`` or ``update``.
            mute_expire_at: RFC3339 expiration time for ``add`` or ``update``.

        Returns:
            The decoded QQ API response.

        Raises:
            ValueError: If operation, member count, or mute duration is invalid.
        """
        if operation not in {"add", "update", "del"}:
            raise ValueError("operation must be add, update, or del")
        if not member_openids or len(member_openids) > 10:
            raise ValueError("member_openids must contain between 1 and 10 members")
        if operation in {"add", "update"}:
            if mute_expire_at is None:
                if seconds is None or not 1 <= seconds <= 2592000:
                    raise ValueError("seconds must be between 1 and 2592000")
                mute_expire_at = (
                    datetime.now(timezone.utc) + timedelta(seconds=seconds)
                ).isoformat(timespec="seconds")
        else:
            mute_expire_at = ""
        return await self._request(
            "POST",
            "/v2/groups/{group_openid}/restrict_chat_setting",
            {"group_openid": group_openid},
            {
                "members": [
                    {
                        "op": operation,
                        "member_openid": member_openid,
                        "mute_expire_at": mute_expire_at,
                    }
                    for member_openid in member_openids
                ]
            },
        )

    async def list_join_requests(
        self, group_openid: str, cursor: str = "", limit: int = 20
    ) -> dict[str, Any]:
        """List pending requests to join a QQ group.

        Args:
            group_openid: QQ group OpenID.
            cursor: Pagination cursor from the previous response.
            limit: Number of requests to return, from 1 to 100.

        Returns:
            Join request list and pagination cursor.

        Raises:
            ValueError: If limit is outside the QQ API range.
        """
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return await self._request(
            "GET",
            "/v2/groups/{group_openid}/join_request_list",
            {"group_openid": group_openid},
            {"cursor": cursor, "limit": limit},
        )

    async def list_join_approval_strategies(
        self, cursor: str = "", limit: int = 20
    ) -> dict[str, Any]:
        """List active automatic join approval strategies.

        Args:
            cursor: Pagination cursor from the previous response.
            limit: Number of strategies to return, from 1 to 100.

        Returns:
            Strategy list and pagination cursor.

        Raises:
            ValueError: If limit is outside the QQ API range.
        """
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return await self._request(
            "GET",
            "/v2/groups/join_approval_strategy",
            {},
            {"cursor": cursor, "limit": limit},
        )

    async def create_join_approval_strategy(
        self,
        group_openids: list[str] | None = None,
        group_ids: list[int] | None = None,
        is_enable: str = "on",
        expire_at: str = "",
        remark: str = "",
    ) -> dict[str, Any]:
        """Create an automatic join approval strategy.

        Args:
            group_openids: Group OpenIDs, mutually exclusive with group_ids.
            group_ids: Numeric QQ group IDs, mutually exclusive with group_openids.
            is_enable: Strategy state, either ``on`` or ``off``.
            expire_at: Strategy expiration time in RFC3339 format.
            remark: Optional strategy remark.

        Returns:
            Created strategy information.

        Raises:
            ValueError: If group identifiers or strategy state are invalid.
        """
        has_group_openids = bool(group_openids)
        has_group_ids = bool(group_ids)
        if has_group_openids == has_group_ids:
            raise ValueError("provide exactly one of group_openids or group_ids")
        if len(group_openids or group_ids or []) > 100:
            raise ValueError("a strategy can contain at most 100 groups")
        if is_enable not in {"on", "off"}:
            raise ValueError("is_enable must be on or off")

        payload: dict[str, Any] = {"is_enable": is_enable}
        if has_group_openids:
            payload["group_openids"] = group_openids
        else:
            payload["group_ids"] = group_ids
        if expire_at:
            payload["expire_at"] = expire_at
        if remark:
            payload["remark"] = remark
        return await self._request(
            "POST",
            "/v2/groups/join_approval_strategy",
            {},
            payload,
        )

    async def update_join_approval_strategy(
        self,
        strategy_id: str,
        is_enable: str | None = None,
        expire_at: str | None = None,
        group_action: dict[str, Any] | None = None,
        remark: str | None = None,
    ) -> dict[str, Any]:
        """Update an automatic join approval strategy.

        Args:
            strategy_id: Strategy ID.
            is_enable: Optional strategy state, either ``on`` or ``off``.
            expire_at: Optional expiration time in RFC3339 format.
            group_action: Optional group add/remove action from the API schema.
            remark: Optional strategy remark.

        Returns:
            Updated strategy information.

        Raises:
            ValueError: If no fields are supplied or strategy state is invalid.
        """
        payload: dict[str, Any] = {}
        if is_enable is not None:
            if is_enable not in {"on", "off"}:
                raise ValueError("is_enable must be on or off")
            payload["is_enable"] = is_enable
        if expire_at is not None:
            payload["expire_at"] = expire_at
        if group_action is not None:
            payload["group_action"] = group_action
        if remark is not None:
            payload["remark"] = remark
        if not payload:
            raise ValueError("at least one strategy field is required")
        return await self._request(
            "PATCH",
            "/v2/groups/join_approval_strategy/{strategy_id}",
            {"strategy_id": strategy_id},
            payload,
        )

    async def delete_join_approval_strategy(self, strategy_id: str) -> Any:
        """Delete an automatic join approval strategy.

        Args:
            strategy_id: Strategy ID.

        Returns:
            The decoded QQ API response.
        """
        return await self._request(
            "DELETE",
            "/v2/groups/join_approval_strategy/{strategy_id}",
            {"strategy_id": strategy_id},
        )

    async def execute_join_approval_strategy(self, strategy_id: str) -> Any:
        """Execute an automatic join approval strategy immediately.

        Args:
            strategy_id: Strategy ID.

        Returns:
            The decoded QQ API response.
        """
        return await self._request(
            "POST",
            "/v2/groups/join_approval_strategy/{strategy_id}/execute",
            {"strategy_id": strategy_id},
            {},
        )

    async def update_join_approval_whitelist(
        self, strategy_id: str, operation: str, whitelist_users: list[str]
    ) -> dict[str, Any]:
        """Add or remove users from an approval strategy whitelist.

        Args:
            strategy_id: Strategy ID.
            operation: Whitelist operation, either ``add`` or ``del``.
            whitelist_users: QQ numbers, with at most 10000 users per request.

        Returns:
            Updated whitelist summary.

        Raises:
            ValueError: If the operation or user list is invalid.
        """
        if operation not in {"add", "del"}:
            raise ValueError("operation must be add or del")
        if not whitelist_users or len(whitelist_users) > 10000:
            raise ValueError("whitelist_users must contain between 1 and 10000 users")
        return await self._request(
            "POST",
            "/v2/groups/join_approval_strategy/{strategy_id}/whitelist_users",
            {"strategy_id": strategy_id},
            {"op": operation, "whitelist_users": whitelist_users},
        )

    async def approve_join_request(
        self,
        group_openid: str,
        member_openid: str,
        join_request_id: str = "",
    ) -> Any:
        """Approve a QQ group join request.

        Args:
            group_openid: QQ group OpenID.
            member_openid: Applicant member OpenID.
            join_request_id: Join request ID when provided by QQ.

        Returns:
            The decoded QQ API response.
        """
        return await self._handle_join_request(
            group_openid,
            member_openid,
            "approve",
            join_request_id,
        )

    async def decline_join_request(
        self,
        group_openid: str,
        member_openid: str,
        join_request_id: str = "",
        reject_reason: str = "",
        add_to_member_blacklist: bool = False,
    ) -> Any:
        """Decline a QQ group join request.

        Args:
            group_openid: QQ group OpenID.
            member_openid: Applicant member OpenID.
            join_request_id: Join request ID when provided by QQ.
            reject_reason: Reason shown when the request is declined.
            add_to_member_blacklist: Whether to add the applicant to the blacklist.

        Returns:
            The decoded QQ API response.
        """
        return await self._handle_join_request(
            group_openid,
            member_openid,
            "decline",
            join_request_id,
            reject_reason,
            add_to_member_blacklist,
        )

    async def _handle_join_request(
        self,
        group_openid: str,
        member_openid: str,
        operation: str,
        join_request_id: str = "",
        reject_reason: str = "",
        add_to_member_blacklist: bool = False,
    ) -> Any:
        """Submit an approval decision for a join request."""
        if operation not in {"approve", "decline"}:
            raise ValueError("operation must be approve or decline")
        payload: dict[str, Any] = {"op": operation}
        if join_request_id:
            payload["join_request_id"] = join_request_id
        if operation == "decline":
            if reject_reason:
                payload["reject_reason"] = reject_reason
            if add_to_member_blacklist:
                payload["add_to_member_blacklist"] = True
        return await self._request(
            "POST",
            "/v2/groups/{group_openid}/approval_join_request/{member_openid}",
            {"group_openid": group_openid, "member_openid": member_openid},
            payload,
        )
