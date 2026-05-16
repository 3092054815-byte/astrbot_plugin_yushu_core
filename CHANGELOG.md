# Changelog

## v0.1.0 - 2026-05-16

MVP release.

### Added

- owner 私聊 live 提示词注入。
- owner 私聊短记忆摘要注入。
- `coach_review` 复盘触发与退出。
- 手动记忆命令：查看、新增、编辑、删除、置顶、导出、清理。
- 中文记忆类型别名，内部仍保存英文 type。
- Memory Console WebUI 页面：查看、编辑、删除、置顶、导出、清理记忆。
- Yushu Console WebUI 页面：总览、健康检查、命令速查。
- 只读诊断命令：`/ys doctor`、`/ys config audit`、`/ys config diff`。
- 面向日常使用的插件配置页中文说明。
- MVP 验证清单文档。

### Safety

- 群聊不注入 owner 私聊记忆。
- 不修改 `request.prompt`，live 注入只追加 `system_prompt`。
- live 注入失败时回退为不注入。
- 默认不接管 `proactive_chat`。
- 默认不接管 `SpectreCore`。
- 发布包不包含运行数据、SQLite 数据库、导出文件或缓存。

### Known incomplete work

- proactive reason gate。
- 状态机正式启用。
- proactive_chat / SpectreCore 适配器。
- 模型自动评测 runner。