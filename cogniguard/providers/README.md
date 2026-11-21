# 模型提供方适配

`mimo.py` 提供 MiMo 的 HTTP/流式客户端及配置读取，不决定画像权限、版权返回模式或预算。
真实调用由应用和 CGC 授权后触发；测试使用假响应，不自动调用付费模型。
原 `cogniguard.agents.mimo_client` 是同一模块的兼容导入。
