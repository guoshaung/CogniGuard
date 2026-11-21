# 保护算法

现行模块只有三个：

- `student_profile/`：学生画像的最小披露。
- `teacher_resource/`：教师材料的授权查找、受控返回和暴露记账。
- `audit_trace/`：讲解文本的水印与溯源。

`legacy/layers/` 存放旧的 `Layer1_fopd_c2rag`、`Layer2_c2rag`、`Layer2_hsw_st_minimal`。旧导入名仍指向这里。
`supporting/image_watermark/` 是图像水印，`supporting/cg_guardrails/` 是 NeMo 配置。新功能不要写进这些目录。

调用关系见 [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)。
