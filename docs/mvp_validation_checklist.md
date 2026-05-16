# yushu_core MVP v0.1.0 验证清单

本文档用于发布前和部署后的人工验收。

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

## 自动验证

在插件目录运行：

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile main.py core/*.py
python3 -m json.tool _conf_schema.json >/tmp/yushu_release_schema_check.json
```

预期：测试通过，Python 编译通过，配置 schema 是合法 JSON。

## WebUI 验证步骤

1. 打开 AstrBot WebUI 插件配置页。
2. 确认配置说明为日常中文文案，没有开发阶段提示。
3. 打开雨舒总览：`#/plugin-page/yushu_core/console`。
4. 确认可看到总览、健康检查、复盘触发词、命令速查。
5. 确认页面不显示完整 owner id、session id、数据库路径或敏感内容。

## 记忆管理验证步骤

1. 打开记忆管理：`#/plugin-page/yushu_core/memory-console`。
2. 确认可查看、编辑、删除、置顶、导出和清理记忆。
3. 确认导出和清理操作需要明确触发，不会自动写入或删除记忆。

## 私聊验证步骤

在 owner 私聊中运行：

```text
/ys doctor
/ys help
/ys config diff
/ys memory add 偏好 喜欢简短直接的回复
/ys memory list
/ys injection preview normal
/ys injection preview coach
```

预期：

- `/ys doctor` 显示推荐配置符合或给出只读建议。
- `/ys help` 显示中文命令帮助。
- `/ys memory add 偏好 ...` 可写入，内部 type 为 `preference`。
- `/ys memory list` 显示中文字段和中文类型。
- 注入预览只显示短记忆摘要，不显示数据库细节。

## 群聊隔离验证步骤

1. 在群聊中进行普通对话。
2. 确认群聊不会注入 owner 私聊记忆。
3. 确认群聊不会进入 owner 私聊陪练状态。
4. owner 在群聊发言也不注入 owner 私聊 memory。

## 回滚方式

- 在 AstrBot WebUI 中禁用 yushu_core 插件。
- 保留或备份：`/root/astrbot/data/plugin_data/astrbot_plugin_yushu_core/`。
- 如需清理导出文件，优先在 Memory Console 中先做清理预览。
- 不删除或修改 `proactive_chat` / `SpectreCore` 数据。

## 未完成项

- proactive reason gate。
- 状态机正式启用。
- proactive_chat / SpectreCore 适配器。
- 模型评测 runner。
