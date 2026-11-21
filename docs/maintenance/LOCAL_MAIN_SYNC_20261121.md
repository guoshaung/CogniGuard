# 本地源码与main同步检查

本次从GitHub main 29a14a7139a5f90820ce748b035ca2417496c502建立独立同步分支，整理D:/pycharm/CogniGuard主目录现行源码。

主要差异是尚未提交的目录重构：backend→cogniguard、frontend→visualization，配置/文档/脚本分组，以及公共治理、教育集成与LangGraph工作流入口。保留本地已提交的MM-FOPD Gate0证据。独立水印和C²-RAG工作树的研究进展不自动合入main。

包括源码、配套小型配置、测试、依赖清单、文档与前端锁文件。未打包本地3.66GB未跟踪内容：2GB迁移tar、模型权重、第三方目录、数据集缓存、var运行输出、私钥/环境文件均未进入此提交。历史实验目录不改名，研究源码保留原路径；模型或历史数据依赖仍按模块说明自行准备。

发现并修复默认NeMo配置路径仍指向旧protection/cg_guardrails，现指向protection/supporting/cg_guardrails；五个新增API文件完成格式化。本地源文件同步了这项修复和格式变化，其余未提交内容及9项媒体删除暂存保持原样。

验证：主目录既有.venv-langgraph运行隔离同步树的scripts/run_tests.py，cogniguard/tests与tests共372通过、21跳过（可选依赖）、2警告。API与runtime/mode.py Ruff lint通过，24个文件格式检查通过。visualization执行npm ci与npm run build成功，构建有大于500kB分包提示。不下载/调用真实模型或重跑正式实验。

GitHub远程引用已刷新，本地main引用已对齐origin/main。源主目录当前分支仍是资源测溯源返还；由于已有暂存媒体删除，直接合并被Git拒绝，无文件丢失。本同步分支经PR审查后再更新main，不用reset覆盖源目录。
