# 旁路材料

这一层不是三个现行资产算法。

- `image_watermark/`：图像水印。导入名 `protection.supporting.image_watermark`。
- `cg_guardrails/`：保留的 NeMo 配置，执行开关是关的。

路径常量在 `core/paths.py` 的 `IMAGE_WATERMARK_DIR` 和 `CG_GUARDRAILS_DIR`。
旧名字 `protection.image_watermark` 和 `dfg_locguard` 由工具目录改写成上面的导入名。
旧记录里的 `protection/image_watermark/api_jobs` 仍翻译到 `var/outputs/sce_locguard_api_jobs`。
