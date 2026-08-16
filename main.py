from types import SimpleNamespace

from botpy.interaction import Interaction

from astrbot import logger
from astrbot.api import llm_tool
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core import AstrBotConfig
from astrbot.core.platform.sources.qqofficial.qqofficial_message_event import (
    QQOfficialMessageEvent,
)
from astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter import (
    QQOfficialPlatformAdapter,
)

from .core.cmd_handler import CmdHandler
from .core.config import PluginConfig
from .core.join_handler import JoinHandler
from .core.qq_api import QQOfficialAPI
from .core.qq_service import QQOfficialService


class QQAdminOfficialPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.cfg = PluginConfig(config)
        self.qq_service: QQOfficialService
        self.cmd_handlers: CmdHandler
        self.join_handler: JoinHandler

    async def initialize(self) -> None:
        """Initialize handlers from the first QQ Official platform instance."""
        if hasattr(self, "qq_service"):
            return

        platforms = [
            platform
            for platform in self.context.platform_manager.get_insts()
            if isinstance(platform, QQOfficialPlatformAdapter)
        ]
        if not platforms:
            return
        index = min(max(0, self.cfg.bot_index - 1), len(platforms) - 1)
        platform = platforms[index]
        client = platform.get_client()
        intents = getattr(client, "intents", None)
        if isinstance(intents, int):
            client.intents = intents | (1 << 25) | (1 << 26)
        elif intents is not None:
            intents.interaction = True

        logger.info(
            "[QQAdmin] installing GROUP_JOIN_REQUEST hook: intents=%s",
            client.intents,
        )
        previous_bot_login = client._bot_login

        async def bot_login(token, previous_handler=previous_bot_login):
            await previous_handler(token)

            def parse_group_join_request(payload):
                data = payload.get("d", {})
                if not isinstance(data, dict):
                    data = {}
                event = SimpleNamespace(
                    _api=client.api,
                    event_id=payload.get("id"),
                    raw_data=data,
                    **data,
                )
                logger.info(
                    "[QQAdmin] received GROUP_JOIN_REQUEST: group_openid=%s, "
                    "member_openid=%s",
                    data.get("group_openid"),
                    data.get("member_openid"),
                )
                client._connection.state._dispatch("group_join_request", event)  # type: ignore

            client._connection.state.parsers["group_join_request"] = (  # type: ignore
                parse_group_join_request
            )
            logger.info("[QQAdmin] registered GROUP_JOIN_REQUEST parser")

        client._bot_login = bot_login

        self.qq_service = QQOfficialService(QQOfficialAPI(client))
        self.cmd_handlers = CmdHandler(self.cfg, self.qq_service)
        self.join_handler = JoinHandler(self.cfg, self.qq_service)

        previous_handler = getattr(client, "on_interaction_create", None)
        previous_join_request_handler = getattr(client, "on_group_join_request", None)
        join_handler = self.join_handler

        async def on_group_join_request(
            request,
            previous_handler=previous_join_request_handler,
        ):
            if await join_handler.handle_group_join_request(request):
                return
            if previous_handler is not None:
                await previous_handler(request)

        setattr(client, "on_group_join_request", on_group_join_request)

        async def on_interaction_create(
            interaction: Interaction,
            previous_handler=previous_handler,
        ):
            if await join_handler.handle_interaction(interaction):
                return
            if previous_handler is not None:
                await previous_handler(interaction)

        setattr(client, "on_interaction_create", on_interaction_create)

    async def terminate(self) -> None:
        pass

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """Initialize the plugin after platform instances become available."""
        await self.initialize()

    @filter.command("群信息")
    @filter.platform_adapter_type(filter.PlatformAdapterType.QQOFFICIAL)
    async def get_group_info(self, event: QQOfficialMessageEvent):
        """查询当前群的基本信息"""
        msg = await self.cmd_handlers.get_group_info(event)
        yield event.plain_result(msg)

    @filter.command("禁言状态")
    @filter.platform_adapter_type(filter.PlatformAdapterType.QQOFFICIAL)
    async def mute_status(self, event: QQOfficialMessageEvent):
        """展当前群的禁言状态"""
        msg = await self.cmd_handlers.get_mute_status(event)
        yield event.plain_result(msg)

    @filter.command("禁言")
    @filter.platform_adapter_type(filter.PlatformAdapterType.QQOFFICIAL)
        """禁言 <秒数> <@成员>"""
        seconds = seconds if isinstance(seconds, int) else 60
        msg = await self.cmd_handlers.set_mute_member(event, seconds)
        yield event.plain_result(msg)
        event.stop_event()

    @filter.command("解禁")
    @filter.platform_adapter_type(filter.PlatformAdapterType.QQOFFICIAL)
    async def unmute_member(self, event: QQOfficialMessageEvent):
        """解禁 <@成员>"""
        msg = await self.cmd_handlers.set_mute_member(event, None)
        yield event.plain_result(msg)
        event.stop_event()

    @filter.command("进群申请", alias={"入群申请"})
    @filter.platform_adapter_type(filter.PlatformAdapterType.QQOFFICIAL)
    async def join_requests(self, event: QQOfficialMessageEvent, limit: int = 100):
        """查询进群申请列表"""
        await self.join_handler.send_join_request(event, limit=limit)
        event.stop_event()

    @llm_tool()
    async def get_qq_group_info(self, event: QQOfficialMessageEvent) -> str:
        """查询当前 QQ 群的基本信息"""
        return await self.cmd_handlers.get_group_info(event)

    @llm_tool()
    async def get_qq_group_mute_status(self, event: QQOfficialMessageEvent) -> str:
        """查询当前 QQ 群的全员和成员禁言状态。"""
        return await self.cmd_handlers.get_mute_status(event)

    @llm_tool()
    async def mute_qq_group_members(
        self, event: QQOfficialMessageEvent, seconds: int = 60
    ) -> str:
        """在群聊中禁言/解禁某用户，被禁言的用户在禁言期间将无法发送消息。

        Args:
            seconds(number): 禁言持续时间（秒），范围为0~2592000, 0表示取消禁言
        """
        return await self.cmd_handlers.set_mute_member(event, seconds)

    @llm_tool()
    async def list_qq_group_join_requests(self, event: QQOfficialMessageEvent) -> str:
        """查询当前 QQ 群的入群申请列表"""
        return await self.join_handler.get_join_requests_content(event)
