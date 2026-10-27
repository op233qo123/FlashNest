# FlashNest

iPhone / iPad 离线 Flash 播放器，基于 Ruffle，支持 iOS 17+。

**[下载最新已交付版本：1.5.4（build 17）未签名测试 IPA](https://github.com/op233qo123/FlashNest/actions/runs/40499842236/artifacts/12733536242)**。登录 GitHub，下载 ZIP 后取出 IPA 自行签名。更新请使用相同签名覆盖安装，勿先卸载；Actions 下载限时保留。

该包对应[源码 `a09ccefc`](https://github.com/op233qo123/FlashNest/commit/a09ccefc4513b617a88898a3d1e4dfb6eaea91f9)，[113 项核心测试通过](https://github.com/op233qo123/FlashNest/actions/runs/40499842236)。iOS 18.2 专项验证为原生 17/18、界面 6/7，**并非全绿或全面稳定版本**。内含实验性 AVM2 排队跳帧修补，来源和限制见[引擎说明](App/Resources/Web/Ruffle-MODIFICATIONS.md)及[供应包记录](vendor/README.md)。

- 导入完整文件夹、ZIP 或 SWF，递归保留子目录，再选择主 SWF。
- 备用导入：复制完整游戏文件夹到「文件 → 我的 iPhone → FlashNest → Import」，返回应用刷新。
- 全屏播放；触控按键可隐藏、调整透明度和位置，并支持改键。
- 每个游戏独立存档，统一位于 `Documents/save/<游戏 UUID>/`；支持命名备份、JSON 导入/导出及导入前备份。
- 删除游戏仅移除应用内游戏副本和临时缓存，保留原始文件及存档；已删除游戏的存档仍可导出。
- 中文、English、跟随系统；不附带第三方游戏。

保存可选择直接复制游戏已写入的存档并保留场景，或保存后清理临时缓存并重新打开同一游戏。普通切换应用只暂停和保留页面，不主动重启。存档不是即时状态：未写入的进度及被系统终止后的场景无法保证恢复。

## 主分支开发中（尚无新 IPA）

外部打开导入、原始 SOL 导入、归档存档删除及存档列表元数据优化已进入主分支。导入/删除专项已通过原生 8 项、界面 2 项，见[验证记录](https://github.com/op233qo123/FlashNest/actions/runs/40544544877)；这不等于完整发布验证或游戏内存下降。内存与兼容性问题仍在排查，**多个低采样档位、音频修补尚未发布**。

[构建与校验](scripts/README.md) · [MIT 协议](LICENSE) · [第三方协议](THIRD_PARTY_NOTICES.md)
