# 镜像与存储目标

已发现平台不等于已完成备份。只有实际上传并通过读回校验的目标，才记为已核验。当前部署回执和核验范围见 `DEPLOYMENT.json`。

| 平台 | 适用方式 | 状态 / 限制 |
| --- | --- | --- |
| 本地 | 完整目录、独立 ZIP 分包 | 构建后逐文件校验；单台电脑不属于异地副本 |
| GitHub | 独立公共仓库保存实际 ZIP/TXT 文件，Pages 提供访问 | 本阶段目标；不使用 LFS 指针，不依赖 Actions 临时 artifact |
| Cloudflare Workers Static Assets | 完整静态镜像及只读目录后端 | 本阶段目标；不启用付费资源，检查 20,000 文件 / 25 MiB 单文件限制 |
| GitLab / Codeberg | 完整 Git 镜像或分片仓库 | 待提供相应账号授权并核实服务容量与用途政策 |
| Hugging Face Datasets | 公开数据集保存分包和目录 | 待账号授权和用途、存储政策核实 |
| Internet Archive | 分经藏 / 快照条目，上传原件包及元数据 | 待 Archive.org 账号与 S3 key；网页抓取不算完整经文备份 |
| Zenodo | 适合有版本的研究数据快照和 DOI | 待账号授权、配额和收录政策核实 |
| OSF | 可引用研究项目与数据快照 | 待账号授权及配额核实 |
| Wikimedia Commons / Wikisource | 符合开放许可与收录要求的文献 | 非通用免费网盘；部分非商业许可不满足其收录条件 |
| Google Drive / OneDrive / Dropbox / Box | 异地云盘副本 | 待用户账号连接；按各账号剩余额度分批，不能假定所有平台可用 |
| Backblaze B2 / S3 / Wasabi / R2 | 对象存储镜像 | 待账号、配额、费用与硬性限制确认；本阶段不启用计费订阅 |
| IPFS | 内容地址分发与多节点持有 | 本地添加或得到 CID 不等于持久备份；须独立长期 pin、可用性核验及持有人交接 |
| Filecoin / Arweave | 合约型或预付分布式存储 | 有费用和技术限制，不属于本阶段免费落地范围，也不承诺万年存在 |
| 离线硬盘 / 光盘 / 磁带 | 异地、离线及机构交接 | 应由不同地点的持有人保管、定期巡检迁移；不能由云端副本代替 |

## 配置其他平台

可使用 rclone 配置云盘或对象存储，再复制完整 `public/` 目录。不要在聊天、仓库或日志里粘贴密钥。

```sh
rclone config
rclone copy public YOUR_REMOTE:dharma-archive/SNAPSHOT --immutable
rclone check public YOUR_REMOTE:dharma-archive/SNAPSHOT --download --one-way
```

`--immutable` 防止已有路径被覆盖。`rclone check --download` 会下载并比较内容；校验完成后保存本次结果、时间、文件数和失败项。仅“上传成功”回执不足以证明可恢复。

应把每个平台账号归属、恢复方式和费用责任交接给维护人，使用独立账号或权限边界。多个同公司服务或同一账号中的副本不算完全独立的故障域。
