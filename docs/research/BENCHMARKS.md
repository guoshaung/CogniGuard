# A 档格子的候选公开基准

只记录这次能核对到的事实。对不上的写「待核实」。没有为了填表去跑这些基准。

格子编号按 Lin et al. 2026（arXiv 2606.23075）摘要里的顺序推出来：五个模块 Brain、Cognitive Resource、Execution、Self-Design、Collective，五个阶段 Bootstrap、Propose、Evaluate、Commit、Serve，从 1 起按行计数。任务书里已经点名的格子和这个数法一致，例如 #7 是 Cognitive Resource × Propose，#12 是 Execution × Propose，#22 是 Collective × Propose。按同一数法，#5 是 Brain × Serve，#10 是 Cognitive Resource × Serve，#25 是 Collective × Serve。论文正文里的编号表我没有逐格核对，若正式表不是这个顺序，下面三格的名字要改。

## #5 Brain × Serve

待核实。没有找到一份我能确认是专门测「已部署模型在服务阶段被改坏」的公开基准，因而不编一个名字凑数。

## #7 Cognitive Resource × Propose

**InjecAgent**（Zhan et al., ACL Findings 2024）

- 下载：<https://github.com/uiuc-kang-lab/InjecAgent>。论文页 <https://arxiv.org/abs/2403.02691>。
- 许可证：仓库标明 MIT。
- 规模：1,054 个测试，17 个用户工具，62 个攻击工具。
- 离线：用例是仓库里的 JSON，读数据可以离线。
- 付费 API：论文评估用了 GPT-4。只读数据不用付费；按论文方式打分需要模型接口。

**AgentDojo**（Debenedetti et al., 2024）

- 下载：<https://github.com/ethz-spylab/agentdojo>。论文 <https://arxiv.org/abs/2406.13352>。项目页 <https://agentdojo.spylab.ai/>。
- 许可证：MIT。
- 规模：论文写 97 个用户任务、629 个安全测试、4 个环境。
- 离线：任务环境是本地模拟的。模型推理是否离线取决于所选模型。
- 付费 API：仓库示例用 `gpt-4o-2024-05-13`。换成本地模型是否被官方脚本完整支持，待核实。

## #9 Cognitive Resource × Commit

**AgentPoison**（Chen et al., NeurIPS 2024）

- 下载：<https://github.com/AI-secure/AgentPoison>。项目页 <https://billchan226.github.io/AgentPoison.html>。
- 许可证：仓库 README 写 MIT。
- 规模：项目页写向 Agent-Driver 注入 20 条、ReAct 4 条、EHRAgent 2 条毒化记录。整个检索库有多大，待核实。
- 离线：待核实。论文设置要跑智能体和检索器。
- 付费 API：论文用了 GPT-3.5，也用了 LLaMA。GPT-3.5 那条需要付费接口。

**Misevolution**（Shao et al., arXiv 2509.26354）

- 下载：<https://github.com/ShaoShuai0605/Misevolution>。论文 <https://arxiv.org/abs/2509.26354>。
- 许可证：待核实。仓库首页片段没有给出许可证。
- 规模：论文按 model、memory、tool、workflow 四条演化路径做实验。memory 路径的样本数，待核实。仓库写着 Getting Started 仍是 Coming soon。
- 离线：待核实。
- 付费 API：论文结果包含 Gemini-2.5-Pro，那一部分需要付费接口。其余路径是否可以只用本地模型，待核实。

## #10 Cognitive Resource × Serve

**AgentPoison**。毒化的是记忆或知识库，攻击发生在检索、服务的时候。下载、许可证、规模、离线和付费 API 见 #9。

第二份专门针对「服务阶段才触发」的公开基准：待核实。

## #12 Execution × Propose

**InjecAgent** 和 **AgentDojo**。两者都是工具调用时的间接提示注入。事实见 #7。

## #14 Execution × Commit

**Misevolution** 的 tool 路径，看工具演化之后有害行为是否留下来。仓库、论文、许可证和付费 API 见 #9。这一条自己的样本数，待核实。

第二份能单独衡量「工具权限逐代扩大并在提交后保留」的公开基准：待核实。

## #17 Self-Design × Propose

**Misevolution** 的 workflow 路径。事实见 #9。样本数待核实。

第二份公开基准：待核实。

## #19 Self-Design × Commit

仍是 **Misevolution**。它讨论自我演化之后有害行为留下来。没有另一份我能确认是「连续多代改写受保护策略」的公开基准。样本数、许可证、能否离线，见 #9，未单独核实的仍是待核实。

## #22 Collective × Propose

**AgentLeak**（arXiv 2602.11510）

- 下载：<https://github.com/Privatris/AgentLeak>。论文 <https://arxiv.org/abs/2602.11510>。
- 许可证：仓库写 MIT。
- 规模：论文评估 1,000 个场景，7 个通道，4 个领域。
- 离线：场景数据可以随仓库拿到。复现论文数字需要跑多智能体。
- 付费 API：论文评了 GPT-4o、Claude、Gemini、Llama、Mistral。闭源模型那一部分需要付费接口。

**The Sum Leaks More Than Its Parts**（Patil, Stengel-Eskin, Bansal；arXiv 2509.14284）

- 下载：论文 <https://arxiv.org/abs/2509.14284>。独立的官方代码仓库地址，待核实。本仓库实验用的 JSON 在本地 `cogniguard_raw/sumleaks/`，那是一份拷贝，不是这次确认过的发布页。
- 许可证：待核实。
- 规模：待核实。
- 离线：已下载的场景 JSON 可以离线读。论文里的防御实验需要模型。
- 付费 API：待核实。论文比较里出现了 Gemini-2.5-pro。

## #25 Collective × Serve

**Sum Leaks**（arXiv 2509.14284）。风险是多段看起来无害的回答合在一起之后才泄露。下载和许可证见 #22，未确认的仍是待核实。

**AgentLeak** 的最终输出通道。下载、许可证和规模见 #22。
