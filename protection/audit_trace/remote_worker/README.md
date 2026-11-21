# HSW远端二次改写：Windows Controller / MUSA Worker

这是R19的独立、显式开启工程模块。导入不会连接API/SSH、加载模型、下载权重或修改历史算法。生产 `src/` 与R16–R18未改。

## 当前状态

- Windows任务、幂等账本、SSH/SFTP提交/回传、公开文本检测与内部KGW参考适配已准备，需以本地测试结果为准。
- `preflight`只读检查已提供服务器；没有安装软件、上传Worker、写远端任务、加载Qwen或生成。
- 已准备的推理分支是Transformers＋torch_musa、FP16、单请求，尚未经过远端模型验收。
- vLLM-MUSA V1具有不同的批处理LogitsProcessor API，必须按实际安装版本另行验证。当前没有把逐请求回调冒称为V1适配器。
- HF参考引擎并发能力为1。独立请求有独立KGW状态；并发隔离的本地控制不等于真实2/4/8并发GPU吞吐通过。

## 分工

Windows通过 `source_api.generate_original` 显式调用原文API，每次最多一个HTTP尝试，绝不把API凭据传给Worker。人工质量审核PASS并锁定后，`controller.make_task` 将原文、契约、审核、模型和消息绑定至SHA。
`Controller`使用本地SQLite记录 REGISTERED → SUBMITTED_OR_UNKNOWN → COMPLETED/FAILED。传输异常后只查询已有结果，绝不自动重发生成。相同ID不同输入拒绝；同一结果重复回收只计一次。源材料/审核/最终分数保存在Windows。

Worker只接收审核原文进行CLEAN/KGW改写。`JobStore`以独占claim防止重复执行，崩溃后RUNNING_OR_UNKNOWN须人工核对；完整结果已落盘但控制端失联时可直接回收。FAILED不会自动重试，恢复不等于重复采样。

## 命令

在Windows项目根目录运行只读预检（无模型生成）：

```powershell
python -B -m protection.audit_trace.remote_worker.preflight --host HOST --port PORT --username USER --output var/results/hsw_remote_musa_20261102_r19/new_preflight.json
```

密码使用无回显getpass，不存入文件/参数/环境。首次SSH连接只在会话内记录TOFU指纹，已有known_hosts冲突会拒绝；首次信任不是带外身份认证。后续 `SSHTransport` 必须匹配固定指纹。

Worker离线验证任务（默认不执行推理）：

```sh
python3 -B -m protection.audit_trace.remote_worker.worker --task TASK.json --spool JOB_ROOT --model-dir MODEL_DIR --model-manifest MANIFEST.json
```

只有未来另行授权后才加 `--execute`；当前配置明确0次生成。远端inbox、工作目录、依赖及模型必须事先经批准提供，提交器不会自动mkdir、安装或下载。
`config.example.json`是模板，不能直接当已验收配置。

## 算法与结果验收

gamma=.25、delta=2、window=4、词表151643、原key承诺、CPU SHA256/PCG64绿表及37911索引保持不变；禁止用torch/MUSA随机排列替代原PRF。GPU只执行同一组索引加2。输入是完整真实chat prefix＋生成历史，内部回调读取末4个真实ID。缓存有硬上限，默认16个上下文。

CLEAN/KGW共用消息和采样配置，greedy无温度采样、无惩罚、无占位符或后处理修复。FP16权重来自独立HF资产清单，不能把旧GGUF文件直接塞进HF加载器；也不能将GGUF反量化称为原始FP16模型。模型/tokenizer/所有相关配置逐文件hash固定，不允许隐式PEFT或联网fallback。

Windows先锁知识审核，再仅以最终公开文本和同一Tokenizer/key进行j≥4、count_all、严格z>3的独立计分。之后才核查私有生成IDs、上下文和偏置。重分词不一致时保留失败，不拿内部高分替换。收到COMPLETED只表示执行结束；知识、公开对齐和水印是否通过仍由Controller审核，不计作自动科学成功。

## 验证与限制

```powershell
run.cmd test protection/audit_trace/remote_worker/tests -q
```

标准库/NumPy测试在`.venv-langgraph`运行；若该环境没有torch，内部回调CPU张量测试会明确SKIP，可使用已有研究Python补充执行，不安装新依赖。所有本地测试都是工程控制，不是MTT生成、速度或水印质量结果。

远端当前Python为3.10，Windows CogniGuard要求3.12；本模块源码采用3.10兼容语法。未来可按受控源代码bundle执行Worker，不要求在远端安装整个3.12框架，更不自动升级系统Python。依赖安装、模型来源、容器或驱动变更均须另行审批。

## 关卡和回退

1. 硬件及已安装推理环境；只识别GPU不等于整个Gate1通过。
2. 现有7B、CLEAN短改写。
3. 真实设备内部绿表加2／历史／独立请求隔离。
4. Windows公开检测与轨迹逐位置对齐。
5. 相同数值模型与设置的内部/HTTP路径对比；FP16对Q4_K_M只能标非严格比较。

全部关卡PASS后才开放2/4/8并发计划。`benchmark.throughput_plan`只输出计划，不启动推理。
回退保留Windows R18 GGUF逐Token HTTP运行器和固定检测器；回退不能自动补写本轮样本或掩盖失败，也不保证KGW检出。
