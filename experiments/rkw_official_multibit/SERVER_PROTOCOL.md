# 5090 原生演示执行记录与协议

以作者公开 Qwen 版本为本轮运行对象。冻结上游 `7439ecee` 及检查点公开 revision 见 `CONFIG.json`。句界、两编码器 token logits 选择、top-50 采样、逐句 value head 和 Best-of-4 评分沿用上游。种子 61124。两个官方输入各生成一批四个候选，每候选最多 512 个新增 token。输出保留全部候选、结束状态、逐句分数和最终选择。可在后续独立预注册增加 C4、负例和扰动。两例演示不对 AUC 或误接受作统计推断。

BF16 先加载两套编码器进行生成。优先两张卡各放一个模型。5090 单卡模式把编码器 0 放在 CUDA，编码器 1 使用 Accelerate GPU 11 GiB 和 CPU 的自动设备放置。生成与核验为两个进程，第二阶段加载解码器和官方 MPNet。报告记录软件和设备放置。这是作者 Qwen 发布版的运行适配。官方 sampler 的 `synced_gpus=False` 约束针对分布式同步，原函数在普通跨设备路径已把输入分别移到模型设备并把第二套 logits 移回主卡。双分支每个 token 都做前向，发送到两台机器的多进程分布式并非当前运行方式。

权重下载使用固定 revision、分片与可续传文件。运行前逐片核对 HF 元数据中的大小和 SHA-256，value head 核对固定 Git 资产哈希。Tokenizer 固定 Qwen2.5-7B-Instruct revision `a09a35458c702b33eeacc393d103063234e8bc28`，MPNet 固定 `e8c3b32edf5434bc2275fc9bab85f82640a19130`。服务器基础 Torch 2.5.1+cu124 的实际 BF16 开机检查失败，隔离环境使用 Torch 2.7.1 cu128。上游生成代码保留其默认全前缀前向和不启用 KV 缓存设置。
