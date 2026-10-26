# FlashNest

iOS 17+ Flash 模拟器，基于 Ruffle，适用于 iPhone / iPad。仅开发 iOS 应用。

- [下载 1.4 未签名 IPA](https://github.com/op233qo123/FlashNest/actions/runs/40320819875/artifacts/12649975485)：需登录 GitHub，下载 ZIP 后取出 IPA；Actions 产物为限时保留。安装前需自行签名。覆盖更新请保持相同签名，勿先卸载，以保留已导入内容。
- 导入完整文件夹、ZIP 或 SWF；递归保留所有子目录和相对路径资源，再选择主 SWF。
- 备用导入：把完整游戏文件夹复制到「文件 → 我的 iPhone → FlashNest → Import」，在应用内选择「从应用文件夹导入」并刷新。
- 提供中文、English 和跟随系统选项。不附带第三方游戏。
- 1.3 真机文件夹导入已由用户确认成功；此前 iOS 18.2 的 2 项跨应用选择界面测试通过。
- 1.4 修正文件系统路径别名造成的错误 SWF 相对路径；仅在完整文件清单可唯一验证时修复旧清单，保留真实的 `content/` 子目录。已通过 38 项测试，包括路径别名、清单恢复及 44 MiB Unicode 路径资源在真实 WebKit／播放器配置中的完整传输。用户实际游戏的真机播放仍待确认，不代表所有 Flash 游戏兼容。
- [本次构建与测试记录](https://github.com/op233qo123/FlashNest/actions/runs/40320819875) · [对应源码 `ca617e6`](https://github.com/op233qo123/FlashNest/commit/ca617e604d9d4c2d93a21f024372e6ee494e9c86)
- IPA：14,975,812 字节；SHA-256：`909be9f01af5bf10730f609d145d508b5cacc2495c3779db8b812bf1754a86dd`。
- [构建说明](scripts/README.md) · [MIT 协议](LICENSE) · [完整第三方协议与声明](THIRD_PARTY_NOTICES.md)
