# 部署资料

`image_watermark/` 是图像水印服务的 Linux/GPU 部署说明、环境变量示例与资产哈希清单。
它属于应用部署配置，不是临时输出。

当前调用方包括：

- `scripts/server/start_image_watermark_api.sh`：默认读取本目录的资产清单。
- `scripts/server/image_watermark_benchmark.sbatch`：正式基准使用同一清单。
- `protection/supporting/image_watermark/experiments/paper_benchmark.py`：把相关部署配置纳入运行来源记录。

具体运行步骤见 [image_watermark/README.md](image_watermark/README.md)。
新增其他服务部署时使用 `deploy/<service>/`，实际启动脚本放 `scripts/server/`。
