# astrbot_plugin_yushu_core

雨舒 Core 是一个面向 AstrBot 的 owner 私聊陪练插件。v0.1.0 MVP 聚焦“可控、可回滚、可管理”的最小可用能力：owner 私聊提示词注入、短记忆摘要、复盘模式、手动记忆管理，以及 AstrBot WebUI 管理页面。

> 设计边界：雨舒只在配置的 owner 私聊中启用陪练能力；群聊保持普通 bot/群友型行为，不注入 owner 私聊记忆。

## 快速开始

1. 下载 `astrbot_plugin_yushu_core-v0.1.0.tar.gz`，解压到 `AstrBot/data/plugins/astrbot_plugin_yushu_core`。
2. 在 AstrBot WebUI 中加载或重载插件，并在插件配置页填写 `owner_user_ids`。
3. 在 owner 私聊中运行 `/ys doctor` 和 `/ys config diff`，确认配置符合推荐状态。

## 兼容性

- 已在 AstrBot v4.24.2 验证。
- 需要 AstrBot 支持 Plugin Pages，用于暴露 WebUI 管理页面。
- 需要 AstrBot 支持 `on_llm_request`，用于在 LLM 请求前追加 owner 私聊提示词上下文。
- 插件元数据声明 `astrbot_version: ">=4.24.2,<5"`。

## 功能概览

- owner 私聊 live 提示词注入：只追加 `system_prompt`，不修改用户消息。
- 记忆摘要注入：只在 owner 私聊注入少量短记忆，不注入群聊。
- 复盘模式：owner 私聊命中触发词后进入 `coach_review`，命中退出词后回到角色内。
- 手动记忆命令：支持查看、新增、编辑、删除、置顶、导出、清理预览/确认。
- 中文记忆类型别名：命令可用中文类型，内部仍保存英文 type，方便机器读取。
- Memory Console：在 WebUI 中查看、编辑、删除、置顶、导出和清理记忆。
- Yushu Console：WebUI 总览、健康检查、命令速查。
- 只读诊断：`/ys doctor`、`/ys config audit`、`/ys config diff`。

## 安装

1. 将本目录或 release 压缩包解压后的目录放入 AstrBot 插件目录，例如：

   ```text
   AstrBot/data/plugins/astrbot_plugin_yushu_core
   ```

2. 在 AstrBot WebUI 中加载或重载插件。
3. 在插件配置页设置 `owner_user_ids`。
4. 按推荐配置检查关键开关。

## 推荐配置

```text
prompt_injection_enabled=true
memory_injection_enabled=true
coach_review_enabled=true
debug_mode=false
state_machine_enabled=false
proactive_enabled=false
yushu_group_enabled=false
proactive_chat_integration_enabled=false
spectrecore_integration_enabled=false
```

可以在私聊中运行：

```text
/ys config diff
/ys doctor
```

确认当前配置是否符合推荐状态。

## 常用命令

```text
/ys status                         查看基础状态
/ys doctor                         运行 MVP 只读诊断
/ys help                           查看命令帮助
/ys config audit                   查看当前配置风险提示
/ys config diff                    查看当前值到推荐值的配置差异
/ys injection status               查看注入相关开关
/ys injection preview normal       预览普通模式注入片段
/ys injection preview coach        预览复盘模式注入片段
/ys memory status                  查看记忆功能状态和容量限制
/ys memory list                    查看当前 owner 私聊记忆列表
/ys memory add 偏好 <内容>          手动新增一条偏好记忆
/ys memory export md               导出当前记忆为 Markdown
/ys memory prune dry-run           预览可清理项目，不会真的删除
```

## WebUI 页面

- 雨舒总览：`#/plugin-page/yushu_core/console`
- 记忆管理：`#/plugin-page/yushu_core/memory-console`

Memory Console 继承 AstrBot WebUI 登录态，不应该作为公网裸页面暴露。

## 记忆类型

内部类型保持英文，命令可使用中文别名。

| 英文 type | 中文名 | 用途 |
| --- | --- | --- |
| `profile` | 个人资料 | 稳定身份或背景摘要 |
| `preference` | 偏好 | 回复风格或互动偏好 |
| `boundary` | 边界 | 不希望被怎样对待，或需要避开的表达 |
| `open_thread` | 未完话题 | 下次可接上的开放话题 |
| `skill_goal` | 练习目标 | 表达、边界、邀约、降焦虑等训练目标 |
| `relationship` | 关系线索 | 现实关系中的阶段、氛围、注意点 |
| `fact` | 事实 | 普通事实信息，避免敏感隐私 |
| `group_rule` | 群规 | 群聊层面的公开规则，不用于 owner 私聊亲密记忆 |

示例：

```text
/ys memory add 偏好 喜欢简短直接的回复
/ys memory add 边界 不喜欢被催促
/ys memory add 练习目标 练习表达清晰
```

## 安全边界

- 群聊不注入 owner 私聊记忆。
- owner 在群聊发消息也不注入私聊记忆。
- 默认不接管 `proactive_chat`。
- 默认不接管 `SpectreCore`。
- 不自动保存完整聊天记录。
- 不保存 token、cookie、密码、密钥等敏感信息。
- 发布包不包含运行数据、SQLite 数据库、导出文件或缓存。

## 验证

在插件目录运行：

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile main.py core/*.py
python3 -m json.tool _conf_schema.json >/tmp/yushu_release_schema_check.json
```

## 未完成项

以下能力留给后续版本：

- proactive reason gate
- 状态机正式启用
- proactive_chat / SpectreCore 适配器
- 模型自动评测 runner

## 许可证

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
