# 蒸馏与 LoRA 独立训练准备

CPU 已分别完成一次真实反向传播、AdamW 更新和 checkpoint 重载前向。两条路径各用 2 条合成序列和 5 个目标 token。蒸馏路径更新 3,632 个参数，损失 1.7275。LoRA 更新 128 个参数，损失 3.4494。烟测验证入口和保存格式，任务效用与水印指标仍需正式样本。 [CPU_SMOKE.json](CPU_SMOKE.json)

复用官方 C4 训练文件的 160,000 条记录，按 Unicode NFKC、大小写和空白规范化后有 159,993 条唯一文本。与全部 10,000 条官方 C4 测试文本、预注册的 24 条原生能力样本，以及 38 条已验收 OpenStax 教学文本的规范化全文交集均为 0。该检查未覆盖近似复用或同一网页的不同片段。官方 C4 缓存缺少可靠上游文档 ID，因此全文审计不支持跨文档来源独立性的结论。原生实验的前 8 条校准、后 16 条测试行号已另存。 [DATA_AUDIT.json](DATA_AUDIT.json) · [native_holdout_ids.json](native_holdout_ids.json)

目前可复用的冻结文档涵盖公开 Qwen 演示和原生 C4 复测。正式蒸馏与 LoRA 批次还需要锁定教师和学生快照、包含 `source_id` 的提示和目标清单、训练参数、独立知识与效用标签。正式数据划分以文档来源为单元，同一来源的不同文本版本进入相同分区。已有历史 STOP 结论沿用原文件。 [原生预注册](../NATIVE_PREREG.md)

## 可执行入口

Windows 烟测使用现有 PyTorch 环境，PEFT 单独安装到工作区的 `var/rkw-training/extra`，通过 PYTHONPATH 导入。独立环境版本见清单。CPU 烟测使用线程数 1、seed 61126、随机初始化的一层 Llama，并将 CUDA 对进程隐藏。训练脚本的正式入口要求传入已冻结的参数，示例中的文件名仅表示输入位置。 [requirements.txt](requirements.txt)

```powershell
$env:CUDA_VISIBLE_DEVICES = ''
$env:PYTHONPATH = (Resolve-Path var/rkw-training/extra).Path
$py = 'D:/pycharm/CogniGuard/.venv/Scripts/python.exe'
& $py experiments/rkw_official_multibit/training/train.py distill var/rkw-training/distill-smoke-new --smoke
& $py experiments/rkw_official_multibit/training/train.py lora var/rkw-training/lora-smoke-new --smoke
```

准备程序输入 JSON 数组或 JSONL。样本字段为 `id`、`source_id`、`source_text`、`prompt`、`target`，来源分配表字段为 `source_id` 和 `split`，评估排除文件读取 `text`。程序拒绝跨分区重复、训练与冻结评估全文重叠并保存 SHA-256 清单。正式训练入口只读取训练分区。蒸馏使用同词表教师的 token KL 和学生目标 token 交叉熵。LoRA 路径仅训练已配置的适配器，以目标 token 交叉熵更新。提示 token 屏蔽。超长样本返回带 ID 的错误，避免训练目标静默截断。

```powershell
& $py experiments/rkw_official_multibit/training/prepare_data.py prepare `
  examples.jsonl source_assignments.json var/rkw-training/formal-split --exclude c4-test.json OpenStax-ACCEPTED.json
& $py experiments/rkw_official_multibit/training/train.py distill var/rkw-training/distill-formal --spec frozen_distill.json --split var/rkw-training/formal-split
& $py experiments/rkw_official_multibit/training/train.py lora var/rkw-training/lora-formal --spec frozen_lora.json --split var/rkw-training/formal-split
```

参数文件包含 `student_snapshot`、`seed`、`max_length`、`batch_size`、`epochs`、`learning_rate`。蒸馏另需 `teacher_snapshot`、`temperature`、`kl_weight`。LoRA 另需以 `lora` 保存 PEFT 配置，如 `r`、`lora_alpha`、`target_modules`。两臂都保存 checkpoint 和训练收据。

## 两臂评估口径

- **水印继承**以冻结解码器对同一分区上的带码、无水印及错码样本分别计算位准确率、固定长度完整载荷恢复率、接受率和缺位率。
- **来源识别**以冻结来源候选和规范化文档来源标注计算正确归因率，分别保留拒绝、缺字段和并列。
- **误归因**单列无水印文本接受率和带水印文本错误来源接受率，各自使用对应样本分母。
- **知识保真**使用 OpenStax 已验收事实、参考计算和独立复核记录专名、数值、单位、条件及否定关系。
- **任务效用**使用同一独立题集、同一生成预算与同一评分规则比较基座和两个训练产物。按任务报告准确率、格式失败、超长与拒绝。

组间比较需要先固定候选来源、解码器阈值、效用评分和评估样本，再让原基座、蒸馏、LoRA 逐条共用这些输入。仅检出水印的文本单列为继承证据。来源归因还需要对应真实来源标注通过独立核验。
