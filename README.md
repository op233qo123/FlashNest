# FlashNest

iOS Flash 模拟器，基于 Ruffle。支持从「文件」导入文件夹、ZIP 或 SWF，保留多 SWF 项目及相对路径资源，并选择入口文件。

- 平台：iOS 17+，iPhone / iPad；仅开发 iOS 应用，不提供桌面版或网页产品。
- 下载：[1.1 构建产物](https://github.com/op233qo123/FlashNest/actions/runs/40298962271/artifacts/12640550413)（临时下载，保留至 2026-11-02，可能需要登录 GitHub）。未签名 IPA 需要自行签名后安装。
- 1.1：新图标、中英文界面、递归文件夹选择与导入进度。iPhoneOS 构建及 24 项模拟器测试通过；用户反馈实体设备文件夹导入仍无响应，正在排查；真实游戏尚未验证。Flash 兼容性取决于 Ruffle。
- 构建与测试：[说明](scripts/README.md)。不附带第三方游戏。
- 协议：项目原创代码采用 [MIT](LICENSE)；依赖保留各自协议，见 [第三方声明](THIRD_PARTY_NOTICES.md)。
