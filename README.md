# FlashNest

iPhone / iPad 离线 Flash 播放器，基于 Ruffle，支持 iOS 17+。

**[下载 1.5 未签名 IPA](https://github.com/op233qo123/FlashNest/actions/runs/40346370319/artifacts/12663010141)**：登录 GitHub，下载 ZIP 后取出 IPA 自行签名。更新请使用相同签名覆盖安装，勿先卸载。Actions 下载限时保留。

- 导入完整文件夹、ZIP 或 SWF，递归保留子目录，再选择主 SWF。
- 备用导入：复制完整游戏文件夹到「文件 → 我的 iPhone → FlashNest → Import」，返回应用刷新。
- 全屏播放；触控按键可隐藏、调整透明度和位置，并支持改键。
- 每个游戏独立存档，统一位于 `Documents/save/<游戏 UUID>/`；支持命名备份、JSON 导入/导出及导入前备份。
- 删除游戏仅移除应用内游戏副本和临时缓存，保留原始文件及存档；已删除游戏的存档仍可导出。
- 中文、English、跟随系统；不附带第三方游戏。

存档保存的是游戏写入的数据，不是模拟器即时状态。退出或进入后台会尝试保存；重新打开从游戏已写入的进度继续。无法保证强制结束时尚未保存的进度，游戏兼容性因 Ruffle 而异。

[1.5 构建：89 项测试通过](https://github.com/op233qo123/FlashNest/actions/runs/40346370319) · [对应源码](https://github.com/op233qo123/FlashNest/commit/432a139610dcf462b1ea34133369f8abb704fa60) · [构建与校验](scripts/README.md) · [MIT 协议](LICENSE) · [第三方协议](THIRD_PARTY_NOTICES.md)
