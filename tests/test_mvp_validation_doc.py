from __future__ import annotations

import unittest
from pathlib import Path


class MvpValidationDocTest(unittest.TestCase):
    def test_mvp_validation_checklist_exists_and_covers_rollout(self) -> None:
        doc_path = Path(__file__).resolve().parents[1] / "docs" / "mvp_validation_checklist.md"
        self.assertTrue(doc_path.exists())

        text = doc_path.read_text(encoding="utf-8")

        self.assertIn("推荐配置", text)
        self.assertIn("WebUI 验证步骤", text)
        self.assertIn("私聊验证步骤", text)
        self.assertIn("群聊隔离验证步骤", text)
        self.assertIn("记忆管理验证步骤", text)
        self.assertIn("回滚方式", text)
        self.assertIn("禁用 yushu_core 插件", text)
        self.assertIn("proactive reason gate", text)
        self.assertIn("SpectreCore 适配器", text)
        self.assertIn("模型评测 runner", text)


if __name__ == "__main__":
    unittest.main()
