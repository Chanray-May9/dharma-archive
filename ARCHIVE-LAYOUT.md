# 完整恢复布局

完整数据集来自多个位置，但恢复后使用同一个普通文件目录。

```text
archive/
  RECOVERY.txt
  verify.py
  RESTORE.py
  manifest-sha256.txt
  data/
    catalog.json               JSON 分片目录入口
    catalog.csv                通用文献目录
    catalog/                   JSON / JSONL 目录分片
    packages/                  741 个独立 ZIP / BagIt 恢复包
    sources/                   来源版本、原始声明和结构定义
    upstream/                  完整 Bilara 源快照的原始字节分片
    recovery/                  PAR2 索引和恢复块、破坏恢复测试回执
    toolkit/                   PAR2 实现源码与 Windows 工具
    mirrors.json               GitHub 文件路径与分片仓库对应表
```

`upstream/bilara-full-source.tar.gz.part-*` 按清单顺序直接拼接即可得到原始 `.tar.gz`；拼接前检查各片 SHA-256，拼接后检查 `bilara-full-source-parts.json` 记载的整体 SHA-256。分片没有私有封装或加密。

恢复顺序：先补齐文件，必要时执行 PAR2 修复，再做完整 SHA-256 与包内清单校验，最后用 `RESTORE.py` 解出原始 XML/JSON/TXT 和阅读文本。不要把仅有目录、网站截图或账号登录成功算作数据备份。

本次 PAR2 实测在隔离副本中移除了一个 15,995,637 字节的恢复包，并破坏另一包的一段内容；修复后对全部 821 个受保护文件重新哈希，全部一致。测试未改动原始档案。

镜像的实际上传与读回状态另外记录在 `DEPLOYMENT.json`，归档快照内的 pending/prepared 状态表示构建时的状态，不是实时监控结果。
