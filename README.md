
<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_qqAdmin_official?name=astrbot_plugin_qqAdmin_official&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_qqadmin_official

_✨ QQ官方群管 ✨_  

[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.0%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)

</div>

## 🤝 介绍

适用于QQ官方bot的群管插件，功能包括：禁言、进群审批

## 📦 安装

在astrbot的插件市场搜索astrbot_plugin_qqadmin_official，点击安装即可  

## ⌨️ 使用说明

- `禁言 @成员`：按插件配置中的默认时长禁言成员。
- `禁言 60 @成员`：禁言 60 秒。
- `解禁 @成员`：解除成员禁言；不 @ 时解除当前发送者的禁言。
- `群信息`：查询当前群的基本信息。
- `禁言状态`：查询当前群的禁言状态。
- `入群申请`：查询待处理的入群申请。
- `同意入群 <成员OpenID> [申请ID]`：同意入群申请。
- `拒绝入群 <成员OpenID> [申请ID]`：拒绝入群申请。
- 单次最多可禁言 10 名普通成员。

命令仅能在 QQ 官方机器人群聊中使用。机器人必须拥有群管理员身份；命令发送者必须是群主、群管理员或 AstrBot 管理员。

插件也提供群管理 API 适配层，外部功能可直接复用：

```python
from .core.qq_group_api import QQOfficialGroupAPI

group_api = QQOfficialGroupAPI(event.bot)
group_info = await group_api.get_group_info(group_openid)
```

## 🤝 配置

进入 AstrBot 插件设置页后，可直接使用本插件自带的前端配置面板进行管理。

## 📌 注意事项

- 想第一时间得到反馈的可以来作者的插件反馈群（QQ群）：460973561（不点star不给进）

## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码
