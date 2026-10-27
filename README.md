# FlashNest

iPhone / iPad 离线 Flash 播放器，基于 Ruffle，支持 iOS 17+。

1.5.4（build 17）是含实验性引擎修补的候选版本：修补 AVM2 嵌套跳帧时过早消耗排队跳转的问题。该引擎在此前隔离构建中的原始小型复现、相邻回归及一次 iOS 18.2 原生/保存/界面流程已通过；1.5.4 完整应用验证另行进行，不代表全部游戏、Adobe 行为或间歇性 WebKit 崩溃均已修复。确切引擎、来源和限制见 `vendor/README.md` 与 `App/Resources/Web/Ruffle-MODIFICATIONS.md`。

**[下载 1.5.2 未签名测试 IPA](https://github.com/op233qo123/FlashNest/actions/runs/40435351644/artifacts/12704167540)**：登录 GitHub，下载 ZIP 后取出 IPA 自行签名。更新请使用相同签名覆盖安装，勿先卸载。Actions 下载限时保留。

- 导入完整文件夹、ZIP 或 SWF，递归保留子目录，再选择主 SWF。
- 备用导入：复制完整游戏文件夹到「文件 → 我的 iPhone → FlashNest → Import」，返回应用刷新。
- 全屏播放；触控按键可隐藏、调整透明度和位置，并支持改键。
- 每个游戏独立存档，统一位于 `Documents/save/<游戏 UUID>/`；支持命名备份、JSON 导入/导出及导入前备份。
- 删除游戏仅移除应用内游戏副本和临时缓存，保留原始文件及存档；已删除游戏的存档仍可导出。
- 中文、English、跟随系统；不附带第三方游戏。

1.5.2 提供两种保存操作：直接复制游戏已写入的存档并保留场景，或保存后清理临时缓存并重新打开同一游戏。普通切换应用只暂停和保留页面，不再主动重启。

存档不是模拟器即时状态。未写入的进度及被系统终止后的场景无法保证恢复。内存占用、长时间运行崩溃及部分游戏兼容性仍待改进；模拟器 UI 自动化尚未全绿，详见验证记录。

[1.5.2 构建：105 项核心测试通过](https://github.com/op233qo123/FlashNest/actions/runs/40435351644) · [对应源码](https://github.com/op233qo123/FlashNest/commit/d8bd5746fb8be08640abe6224bec2884a51d2f9e) · [构建与校验](scripts/README.md) · [MIT 协议](LICENSE) · [第三方协议](THIRD_PARTY_NOTICES.md)
