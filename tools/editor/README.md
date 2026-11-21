# 编辑器工作区

在 VS Code 或兼容编辑器中选择“从文件打开工作区”，打开
[`CogniGuard.code-workspace`](CogniGuard.code-workspace)。

工作区的 `folders[0].path` 为 `../..`，相对于此文件解析到仓库根目录，
因此仍能浏览完整源码。常见依赖、构建和缓存目录在资源管理器中隐藏；
这些显示设置不会移动或删除文件。

测试设置统一放在根目录 `pyproject.toml` 的 `[tool.pytest.ini_options]` 中。
旧 `pytest.ini` 已保留至本地 `var/cache/maintenance/pytest.before.ini`，
作为迁移前的维护备份；pytest 不会从该位置加载配置。
