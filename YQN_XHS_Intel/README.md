# 运去哪·小红书市场情报助手

这是 Ryan 为运去哪准备的第一阶段 demo。

## 稳定分享

- GitHub 仓库：https://github.com/zherong0603-web/yqn-xhs-intel
- GitHub Pages 展示版：https://zherong0603-web.github.io/yqn-xhs-intel/
- Render 真实 API 版一键部署：https://render.com/deploy?repo=https://github.com/zherong0603-web/yqn-xhs-intel

说明：

- GitHub Pages 展示版免费、稳定，适合给朋友或老板看效果。
- GitHub Pages 不能运行 Python 后端，所以不能真实调用 TikHub。
- 真实 API、费用保护、Excel 实时生成，需要部署 Render 版。

## 打开方法

双击项目根目录里的：

`启动YQN小红书市场情报助手.command`

打开后会自动出现中文网页。

## 本地保存

- API Key：当前浏览器 localStorage
- 原始数据：`YQN_XHS_Intel/data/raw/`
- Excel：`YQN_XHS_Intel/outputs/`
- 缓存数据库：`YQN_XHS_Intel/data/state.db`

这些运行数据默认不上传 GitHub。

朋友模式下，服务器不保存 API Key。每个使用者都在自己的浏览器里保存自己的 Key。
