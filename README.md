# astrbot_plugin_yushu_core

雨舒 Core 是一个面向 AstrBot 的 owner 私聊陪练插件。v0.1.0 MVP 聚焦安全可回滚的最小能力：owner 私聊提示词注入、短记忆摘要、复盘模式、手动记忆管理，以及 WebUI 管理页面。

## 功能

- owner 私聊 live 提示词注入：只追加 `system_prompt`，不修改用户消息。
- 记忆摘要注入：只在 owner 私聊中注入少量短记忆，不注入群聊。
- coach_review 复盘模式：owner 私聊命中触发词进入复盘，命中退出词回到角色内。
- 手动记忆命令：支持新增、查看、编辑、删除、置顶、导出、清理预览/确认。
- 中文记忆类型别名：如 `偏好`、`个人资料`、`边界` 等，内部仍保存英文类型。
- Memory Console：WebUI 插件页面中管理记忆。
- Yushu Console：WebUI 总览、健康检查、命令速查。
- 只读诊断：`/ys doctor`、`/ys config audit`、`/ys config diff`。

## 安装

1. 将本目录放入 AstrBot 插件目录，例如：

   ```text
   AstrBot/data/plugins/astrbot_plugin_yushu_core
   ```

2. 在 AstrBot WebUI 中重载或启用插件。
3. 在插件配置页设置 `owner_user_ids`。
4. 按推荐配置检查开关。

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

## 常用命令

```text
/ys status
/ys doctor
/ys help
/ys config audit
/ys config diff
/ys injection status
/ys memory status
/ys memory list
/ys memory add 偏好 <内容>
/ys memory export md
/ys memory prune dry-run
```

## WebUI 页面

- 雨舒总览：`#/plugin-page/yushu_core/console`
- 记忆管理：`#/plugin-page/yushu_core/memory-console`

Memory Console 通过 AstrBot WebUI 登录态访问，不应作为公网裸页面暴露。

## 边界

- 群聊不注入 owner 私聊记忆。
- owner 在群聊发消息也不注入私聊记忆。
- 默认不接管 proactive_chat。
- 默认不接管 SpectreCore。
- 不自动保存完整聊天记录。
- SQLite 记忆库位于插件运行数据目录，发布包不包含任何运行数据。

## 记忆类型

内部类型保持英文，命令可使用中文别名：

- `profile`：个人资料
- `preference`：偏好
- `boundary`：边界
- `open_thread`：未完话题
- `skill_goal`：练习目标
- `relationship`：关系线索
- `fact`：事实
- `group_rule`：群规

## 验证

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile main.py core/*.py
python3 -m json.tool _conf_schema.json >/tmp/yushu_release_schema_check.json
```

## 未完成项

- proactive reason gate
- 状态机正式启用
- proactive_chat / SpectreCore 适配器
- 模型自动评测 runner
