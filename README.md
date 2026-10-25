# 经藏 · 佛典留存计划

面向长期保存的开放佛典档案与阅读入口。欢迎下载、复制、传播；版本、整理机构与原始授权条款随档案保留。

这是持续扩充的档案，不是“世界全部佛经已备份”的声明。文件数包括经文分段、不同版本及论律资料，不能当成独立佛经部数。

## 本次收录

- CBETA XML P5：当前固定提交版本中的全部 26 个有 XML 文件的藏经集合，逐文件保留原始条件，不统一重贴授权标签。
- SuttaCentral Bilara：四种原典语言及全部 `translation/` 文件；另保存完整上游源文件快照。
- Esukhia：德格《甘珠尔》和《丹珠尔》的全部现有电子文本卷册。
- GRETIL：从固定原始 TEI 快照提取的 225 份佛教文献，保留筛选目录与原始文件头。
- 每个文件记录固定的上游 Git 提交版本、路径、原件 SHA-256 及阅读副本 SHA-256。
- 其他版本、扫描图像、尚未纳入的译本及未数字化手稿继续登记扩充。没有用生成文字补缺。

准确数量和覆盖范围见 `public/data/status.json`；具体来源版本见 `public/data/sources.json`。

## 不依赖前端的访问

- GitHub 仓库：<https://github.com/Chanray-May9/dharma-archive>
- GitHub Pages：<https://chanray-may9.github.io/dharma-archive/>
- Codeberg 公版 / CC0 原典子集：<https://codeberg.org/chanray-dharma-archive/buddhist-public-domain-texts>
- Internet Archive 分片快照：<https://archive.org/details/chanray-dharma-archive-buddhist-texts-20261023>；公开入库与读回核验结果以部署回执为准。
- Cloudflare 地址以 `DEPLOYMENT.json` 的实际部署回执为准。
- 不运行网页：直接打开 `public/RECOVERY.txt`、`public/data/catalog.csv`，解压 `public/data/packages/*.zip`；纯文本位于包内 `data/reading/`。
- 每个分包自身含原件、阅读副本、来源说明和 SHA-256 清单，可单独恢复。

正文没有数据库依赖、登录依赖、临时签名地址或 Git LFS 指针。GitHub 数据分片仓库保存真实 ZIP 字节；Cloudflare 保存完整静态镜像，Worker 只提供只读目录 API。Pages 只托管前端与目录，以避免其 1 GiB 网站体积限制；Pages 并非完整数据副本。

GitHub 数据分片：

- <https://github.com/Chanray-May9/dharma-archive-data-001>
- <https://github.com/Chanray-May9/dharma-archive-data-002>
- <https://github.com/Chanray-May9/dharma-archive-recovery>

下载主仓库和三个分片后，把分片中的 `data/` 合并到主仓库 `public/data/`，即可用全部离线工具。也可用 `tools/mirror.py` 从主仓库 Raw 地址开始恢复；它会读取 `data/mirrors.json` 并按路径访问分片。

## 格式

原件保留 XML TEI P5 / JSON / TXT 原始字节。阅读副本采用 UTF-8 纯文本并保存在 ZIP 内，目录分片使用 JSON 和 JSONL，同时提供 CSV。ZIP 使用通用 DEFLATE 压缩，分包有 BagIt 1.0 标识和 SHA-256 清单。`RFC3629-UTF8.txt`、授权全文及 CBETA 结构定义随包保存。网页可按字节范围读取 ZIP 中的单份阅读副本，不需要数据库。

XML 阅读副本保留正文、注释和异读的文本标记；复杂版面、字形、定位和完整校勘结构以原始 XML 为准。无法映射的缺字保留 `[CBxxxx]` 标识，可查原件中的 `charDecl`。不声称派生 TXT 是校勘定本。

## 离线校验与恢复

Python 3 标准库即可，无需联网安装依赖：

```sh
python tools/verify.py public --deep
python tools/verify.py public/data/packages/cbeta-T08-001.zip
```

目录校验会检查全部载荷文件集合和 SHA-256，深度校验还逐一检查 ZIP 内部文件。源文件下载另外对照固定 Git 树的 blob 哈希和文件长度，防止传输截断或下载错误页。

从一份公开镜像恢复：

```sh
python tools/mirror.py download --base https://YOUR-MIRROR/ --output restored --manifest-sha256 EXPECTED_MANIFEST_HASH
python tools/verify.py restored --deep
```

`tools/mirror.py check` 默认只核验指定镜像，不能用其他平台的正确副本掩盖当前平台的文件丢失或损坏。核验 GitHub 主仓库与三个分片的联合布局时显式添加 `--allow-shards`；下载恢复模式自动使用已登记的备用位置。

Internet Archive 使用标准 TAR 的原始字节分片，不是另一种私有压缩格式。按照 `DISTRIBUTION.json` 列出的顺序拼接各片，即可用通用 TAR 工具解出完整目录；分片清单 SHA-256 为 `247c7656d3432e4148b9f5f7602372015f880d57dc14e4c5d03b4a036ec44acd`。不应使用文本模式拼接二进制分片。

校验发现损坏，PAR2 纠错数据用于重建丢失或损坏的块。本档案额外生成约 35% 的 Reed–Solomon 恢复数据，位于 `public/data/recovery/`。使用全部恢复块时，修复能力按块计算，不能简单理解为任意 35% 文件；源块和恢复块同时丢失会降低能力。实际创建参数和“整包丢失＋另一包损坏”的实测结果见 `PROTECTION.json`。恢复工具源码随档案保存。

```sh
par2 repair -Bpublic public/data/recovery/dharma.par2
python public/verify.py public --deep
python public/RESTORE.py public --output recovered
```

## 扩充与预算

`SOURCES.md` 列出发现的来源；`MIRRORS.md` 区分已部署、可配置和缺少账号的平台。脚本不会自动注册账号、开启计费或上传到未经配置的账户。R2 不会自动启用，因为其免费额度属于按量计费订阅，并非硬性零费用上限。

本次 Worker 静态资源按免费上限检查：少于 19,500 文件、每文件少于 24 MiB。动态接口额度依账户方案而定；经文静态访问独立于 Worker API。后续超过阈值必须拆成新的归档分片及仓库，不覆盖旧快照。

`.github/workflows/audit-replicas.yml` 每月独立读回 GitHub、Cloudflare 与 Internet Archive 的全部归档载荷，也可手动运行。检查失败会让对应任务失败；GitHub 的失败通知取决于账号通知设置。核验回执与 Actions 临时 artifact 不是额外的长期数据副本。免费平台可能调整条款、停用账号或停止服务，仍需异地离线副本与持续的维护人交接。

## 重建

从官方固定 Git 树抓取文件，失败后可续传：

```sh
python tools/fetch_snapshot.py --repository cbeta-org/xml-p5 --tree cbeta-tree.json --output cbeta --prefix T/ --prefix X/ --prefix J/ --prefix N/ --prefix schema/
python tools/fetch_snapshot.py --repository suttacentral/bilara-data --tree bilara-tree.json --output bilara --prefix root/pli/ --prefix root/lzh/ --prefix root/san/ --prefix root/pra/
python tools/build_archive.py --cbeta cbeta --bilara bilara --cbeta-tree cbeta-tree.json --bilara-tree bilara-tree.json --notices notices --output NEW-SNAPSHOT
```

固定 Git 树、下载说明和上游辅助文件应与下载目录共同保存。构建器拒绝覆盖已有目录，须为新快照指定新输出路径。发布前必须重新检查授权范围、完整性、体积和恢复测试。

## 运行与部署

```sh
python -m http.server 8080 --directory public
node --test tests/worker.test.mjs
npx wrangler deploy
```

GitHub Pages 工作流部署 `public/`。`public/config.js` 指向独立 Cloudflare API，所有本地路径兼容 GitHub Pages 仓库子路径。后端 API 不可用时目录可回退到同站 JSON，原件始终能直接下载。

实际 Pages 部署目录由 `tools/stage_pages.py` 生成，只含前端、目录和恢复说明；大数据留在独立 Git 仓库及 Cloudflare。所有仓库用 `.gitattributes` 禁止换行自动转换，避免破坏归档校验值。

遇到网络对大请求断开时，`tools/batch_push.py` 用小批次 Git 提交与推送续传；`tools/wrangler_resilient.cjs` 在本进程内把资产上传调整为单文件顺序请求，不修改已安装的 Wrangler。传输适配不会改变归档内容、账户方案或纠错参数。

## 千年留存的实际条件

没有现有云平台承诺存续数千年。目标应通过不同机构共同持有、至少三份副本、至少两类介质、至少一份异地离线副本来推进。每年校验、抽样恢复；约每 3–5 年评估介质迁移，具体以介质状态为准；保留多代版本、接续维护人和资金来源。不可把域名续费或单个账号当成永久保存机制。
