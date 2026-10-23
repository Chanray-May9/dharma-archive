# 来源登记与扩充路线

收录状态以生成的 `public/data/sources.json` 和 `public/data/status.json` 为准；此表中的待处理来源不计入已备份数量。

| 来源 | 范围 | 本阶段处理 |
| --- | --- | --- |
| [CBETA](https://github.com/cbeta-org/xml-p5) | 汉文经律论、多种藏经与近代文献 | 当前快照全部 5,017 份 XML、26 个有文件的集合已收录 |
| [SuttaCentral Bilara](https://github.com/suttacentral/bilara-data) | 原典与多语译文 | 四种原典语言与全部 translation JSON 共 21,845 份；完整上游源文件快照另存 |
| [Esukhia 甘珠尔](https://github.com/Esukhia/derge-kangyur) | 德格甘珠尔电子文本 | 已收录 text/ 下全部 103 个文件；上游所缺原书目录不伪造补齐 |
| [Esukhia 丹珠尔](https://github.com/Esukhia/derge-tengyur) | 德格丹珠尔电子文本 | 已收录 text/ 下全部 213 个文件 |
| [BDRC / BUDA](https://library.bdrc.io/) | 以藏文为主的扫描、目录及多语佛典 | 待按开放访问范围获取目录与 IIIF 清单；图像需容量规划，不把目录当作经文副本 |
| [OpenPecha](https://github.com/OpenPecha) | 藏文数字文本、OCR、文本层与校勘 | 待按仓库核实文本层、来源、许可和质量；保留 OCR 与原图的关联 |
| [84000](https://84000.co/) | 藏传佛典译本 | 待核实逐部版本与批量再传播条件 |
| [GRETIL](https://gretil.sub.uni-goettingen.de/) | 梵文及相关语言电子文献 | 已收录 225 份佛教 TEI 原件，保留筛选目录、各原始文件头和来源 |
| [DSBC](https://www.dsbcproject.org/) | 梵文佛典数字语料 | 待核实批量接口、版本与再传播条件 |
| [SAT](https://21dzk.l.u-tokyo.ac.jp/SAT/) | 大正藏检索及相关图像 | 作为版本对照候选；不以网页可访问推定图像可批量镜像 |
| [BDK](https://www.bdkamerica.org/) | 英译佛典 | 待逐出版物核实下载和分发条件 |
| [Internet Archive](https://archive.org/) | 多语古籍扫描及现代出版物 | 待按具体条目标识和权利状态收录；不批量复制受限借阅文件 |
| [Wikisource](https://wikisource.org/) | 多语言公有领域及开放文本 | 待按语言站点、作品版本、导出方式建立快照 |

完整性不是通过搜索引擎结果数量判断。后续应建立“作品—译本—版本—卷册—文件—来源”关系；保留平行版本，不按同名去重。扫描本的 OCR、图像和校勘文本须分层保存，不能用 OCR 替代图像原件。

尚未数字化或仅存私人收藏的文献，无法通过网上抓取获得；需要与持藏机构合作。相同经藏在不同整理平台的副本也不能自动视为所有历史版本。
