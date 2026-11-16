# T6 运行顺序

使用本目录对应的独立工作树和冻结输入。原文、模型、密钥、运行日志和盲评包留在本机。已完成的阶段保持原样。

1. `t6_sources.py` 写题干与公开清单。提交清单和 T6_GENERATION_FREEZE.json 后，运行 `t6_generate.py`。
2. 提交 T6_EMBED_FREEZE.json 后执行 `stage_c_embed.py`。它按已写入的逐源记录续跑。用 `prepare_t6_next.py union` 核对并冻结 KGW／Unigram 队列，提交生成的三个阶段 C 证据后运行 `t6_model_arms.py baseline`。
3. `t6_controls.py human` 导出本机空白人工表单，`rc` 运行旧随机对照，`background` 执行生产密钥与 1000 个诊断密钥误报。盲评映射与参考清单分开保存。
4. 用 T6_POSTMARK_FREEZE.json 准备 PostMark 固定资产。在隔离进程设置 `HF_MODULES_CACHE` 指向本次运行目录，执行 `t6_postmark.py calibrate`。提交 `prepare_t6_next.py postmark` 写出的开发阈值后运行 `t6_postmark.py generate`。
5. 用 `t6_registry.py` 建立评测清单，运行 `prepare_t6_next.py variants` 并提交冻结。使用 EVAL-03 的 OCR 虚拟环境运行 `t6_ocr.py`。对同一清单运行 `t6_model_arms.py compress`，再用 `t6_metrics.py variants` 计算变体检出及来源归属。若只做第一批固定主方法，清单和 OCR、指标入口使用 `--primary`，输出独立归档。
6. `t6_metrics.py public_gate` 完成改写基线的全文公开检出准入。随后 `t6_frequency.py` 产生离线 P1 文本。运行 `prepare_t6_next.py p1` 并提交输入哈希后才能用 `t6_metrics.py frequency` 评分。
7. `t6_metrics.py baseline_fpr` 计算 KGW、Unigram 与可用 PostMark 的冻结阈值误报。运行 `report_t6.py` 得到完整汇总。仅在分阶段交付时用 `--checkpoint`，它保留尚未完成的阶段状态。

通用 Python 使用 EVAL-04 隔离运行环境，GPU 模型阶段使用旧 llama.cpp 运行库及回环地址。保持实验进程自己的端口与日志。保留首次失败或中断产生的记录。
