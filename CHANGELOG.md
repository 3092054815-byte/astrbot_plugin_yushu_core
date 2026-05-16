# Changelog

## v0.1.1 - 2026-05-16

### Added

- 新增 `coach_review_no_history_enabled` 配置，默认开启。
- 复盘模式注入成功后记录 live mode 标记，并在 `on_agent_done` 阶段将本轮复盘 assistant 回复标记为临时消息。
- `/ys injection status`、`/ys doctor`、配置审计和配置差异中展示“复盘不进历史”状态。
- 复盘提示词明确说明复盘内容只作为当轮建议，不作为长期事实、偏好或关系状态。

### Fixed

- 修正候选包中 MVP 验证文档测试写死旧绝对路径的问题，继续使用仓库内 `docs/mvp_validation_checklist.md`。

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
