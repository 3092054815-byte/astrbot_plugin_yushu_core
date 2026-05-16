# yushu_core MVP Validation Checklist

## 推荐配置

- `prompt_injection_enabled=true`
- `memory_injection_enabled=true`
- `coach_review_enabled=true`
- `debug_mode=false`
- `state_machine_enabled=false`
- `proactive_enabled=false`
- `yushu_group_enabled=false`
- `proactive_chat_integration_enabled=false`
- `spectrecore_integration_enabled=false`

## WebUI 验证步骤

- 打开雨舒总览页面，确认基础状态、健康检查、命令速查可见。
- 打开记忆管理页面，确认列表、详情和单条操作可见。
- 确认页面不显示完整 owner id、session id、数据库路径或敏感内容。

## 私聊验证步骤

- owner 私聊普通消息应使用 normal 模式。
- owner 私聊复盘触发词应进入 coach_review。
- 退出词应回到角色内普通聊天。

## 群聊隔离验证步骤

- 群聊继续作为普通 bot 使用。
- 群聊不注入 owner 私聊记忆。
- owner 在群聊发消息也不注入私聊记忆。

## 记忆管理验证步骤

- `/ys memory list` 与 Memory Console 记忆条数一致。
- 导出和清理流程先预览再确认。
- 敏感内容显示为 `<hidden>` 或被拒存。

## 回滚方式

- WebUI 禁用 yushu_core 插件。
- 保留或备份插件运行数据目录。
- 如需恢复配置，按 WebUI 配置页手动调整。
- 不动 proactive_chat / SpectreCore 数据。

## 未完成项

- proactive reason gate
- 状态机正式启用
- proactive_chat / SpectreCore 适配器
- 模型评测 runner
