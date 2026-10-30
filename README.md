# tvbox-hub · TVBox/影视仓 线路中枢

[![CI](https://github.com/guxia66898/tvbox-hub/actions/workflows/hub.yml/badge.svg)](https://github.com/guxia66898/tvbox-hub/actions/workflows/hub.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)

把散落在 TVBox/影视仓 社区的公开接口线路，做成一条**可持续运行的流水线**：
`种子线路 + 聚合页采集 → 全生态配置解析 → L1 线路验活 → L2 站点抽样 → 排名去重 → 三个订阅产物 + 历史趋势体检面板`。

> **English**: tvbox-hub is a self-hosted pipeline for TVBox / YingShiCang config sources.
> It harvests public config URLs, parses every known config format (lenient JSON, image steganography,
> CatVod `2423` AES, Base64), probes line and site availability, merges them into a single-warehouse
> config with per-site `jar` allocation, and publishes three subscription artifacts plus a static
> health dashboard. Availability checking only — no content is stored or redistributed. See [README.en.md](README.en.md).

> 源起：分析桌面版《影视仓接口助手_1.0.apk》（WebView 单文件版）后，把它的核心能力
> （内置线路 + 聚合页搜寻 + 多仓递归展开 + 测速导出）服务端化，并融合
> [yz8023/ysc-helper-android](https://github.com/yz8023/ysc-helper-android)（同源原生版，2423 AES/图片隐写协议）、
> [zhuzhuyule/juhe-subhub](https://github.com/zhuzhuyule/juhe-subhub)（订阅检测拼装）、
> [fish2018/tvbox](https://github.com/fish2018/tvbox)（去重私有化）、
> [lyrhub/tvbox-checker-app](https://github.com/lyrhub/tvbox-checker-app)（站点级验证思路）的功能互补点。
> 仅做**可用性检测与汇总**，不存储、不分发任何影视内容。


## 🌐 在线地址（本仓库每日自动更新）

| 用途 | 地址 |
|---|---|
| 体检面板 | https://guxia66898.github.io/tvbox-hub/dist/ |
| 多仓订阅（影视仓） | `https://guxia66898.github.io/tvbox-hub/dist/merged.json` |
| 精选订阅（仅种子源） | `https://guxia66898.github.io/tvbox-hub/dist/curated.json` |
| 单仓配置（FongMi/TVBox） | `https://guxia66898.github.io/tvbox-hub/dist/tvbox.json` |

由 GitHub Actions 每天 UTC 21:30（北京时间 05:30）自动跑一遍并提交结果。

## 目录

```
tvbox-hub/
├── run.py                     # 入口：python run.py --config config.json
├── config.example.json        # 配置模板（复制为 config.json 后可改）
├── requirements.txt           # 仅 pycryptodome（2423 AES 解密用）
├── seeds/lines.json           # 125 条种子线路（v1.0 APK 照录 56 + GitHub 仓库/聚合订阅/多仓镜像 69）+ 18 个聚合页
│   ├── scan_repos.py          #    扫描 GitHub 高星配置仓库（jsDelivr 文件树，无 API 限流）
│   ├── verify_cands*.py       #    候选种子实测（抓取+解析）后再入库
│   ├── mine_readme.py         #    从仓库 README 里挖它们自己引用的配置链接
│   ├── discovered.json        #    子代理广度发现并逐条验证的 40 条新来源
│   └── merge_discovered.py    #    合并发现清单到种子池（语义去重）
├── tvbox_config_parser/       # ① 统一配置解析库（独立可用）
│   ├── parser.py              #    明文/带注释 JSON 解析 + 类型分类
│   ├── crypto.py              #    CatVod 2423 ($#key#$) AES-128-CBC Hex 解密
│   ├── stego.py               #    图片伪装接口（二进制末尾 ** + Base64）
│   ├── harvest.py             #    聚合页 URL 抽取（关键词过滤）
│   └── utils.py               #    URL 规范化 / 代理前缀剥离
├── hub/                       # ② 线路中枢流水线
│   ├── fetch.py               #    抓取（SSRF 防护 / 中文域名 IDNA / gzip / TTFB）
│   ├── probe.py               #    L1 递归验活 + L2 站点 API 抽样
│   ├── rank.py                #    打分排序与汇总
│   ├── merge.py               #    单仓配置合并引擎（spider 投票 + per-site jar 分配）
│   ├── discover.py            #    自动发现新仓库（索引页 / Codeberg / GitHub / jsDelivr）
│   ├── promote.py             #    采集子线自动晋升（连续 N 轮可用 → 转正为种子）
│   ├── jarcheck.py            #    jar 可达性探测（type:3 站点的硬依赖）
│   ├── publish.py             #    产物写盘 + 历史快照
│   ├── panel.py               #    单文件体检面板（无外部依赖）
│   └── run.py                 #    CLI 编排
├── tests/                     # 离线测试（无需外网）
│   ├── test_parser.py         #    解析库：容错 JSON / 2423 AES / 隐写 / Base64
│   ├── test_merge.py          #    合并引擎：spider 投票 / per-site jar / 脏数据清洗
│   ├── test_hub_offline.py    #    产物写盘 / 面板生成 / 差异检测
│   └── test_discover.py       #    自动发现：四通道 / 实测拦截 / 健康计数淘汰
├── tools/                     # 运维与诊断工具
│   ├── audit.py               #    产物体检（结构/一致性/快照完整性）
│   ├── check_panel.py         #    面板结构与内嵌数据校验
│   ├── analyze_source.py      #    分析「新线路从哪来」（快照演推 + 来源拆解）
│   ├── diff_merge.py          #    对比合并引擎新旧效果
│   ├── scan_repos.py          #    扫描 GitHub 仓库找候选配置
│   ├── verify_candidates.py   #    候选种子实测模板（复制后填 URL 即可）
│   └── merge_discovered.py    #    把发现清单合入种子池
├── Dockerfile
└── .github/workflows/hub.yml  # 每日定时跑 + 自动提交产物
```

## 快速开始

### 本地运行

```bash
cd tvbox-hub
pip install pycryptodome
python run.py --config config.example.json          # 全流程：采集+发现+L1+L2
python run.py --no-harvest --no-l2                  # 只验种子线路（L1）
python run.py --max-depth 2 --l2-max-sites 8        # 控制规模
```

**跑之前先自检**（全部离线、不需网络，约 2 秒）：

```bash
python tests/test_parser.py        # 解析库：容错 JSON / 2423 AES / 图片隐写 / Base64
python tests/test_merge.py         # 合并引擎：spider 投票 / per-site jar / 去重 / 脏数据清洗
python tests/test_hub_offline.py   # 产物写盘 / 面板生成 / 差异检测
python tests/test_discover.py      # 自动发现：四通道 / 实测拦截 / 健康计数淘汰
```

四项均输出 `ALL PASS` 才说明环境与代码正常。跑完真实流水线后，可再执行
`python tools/audit.py` 对产物做体检（结构合法性 / 数据一致性 / 快照完整性）。

产物在 `dist/`，历史在 `history/`；面板直接用浏览器打开 `dist/index.html`。

### GitHub Actions（推荐：fork 即用，零服务器）

仓库自带 `.github/workflows/hub.yml`：每天 UTC 21:30（北京时间 05:30）自动运行，
产物（dist/ + history/）自动提交回仓库——用 GitHub Pages 指向 `dist/` 即得到一个
**每日更新的订阅地址 + 在线体检面板**。

### Docker

```bash
docker build -t tvbox-hub .
docker run --rm -v $PWD/config.json:/app/config.json -v $PWD/dist:/app/dist \
           -v $PWD/history:/app/history tvbox-hub
```

## 产物说明（2026-10-30 架构变更）

### 为什么不再推荐大合并

之前发布的 `tvbox.json` 是 6418 个站点的合并配置——258 个 jar 混装，靠 per-site `jar`
字段区分来源。**实测结果：能导入，但能播放的没几个，远不如「饭太硬」这类单一配置。**

根因有三条：

| 问题 | 影响 |
|---|---|
| per-site `jar` 不是所有客户端都支持（影视仓部分版本忽略） | 一旦忽略，5637/6418 个 type:3 站点（**88%**）全部报废 |
| 22.5% 的 jar 已失效 | 混装后无法定位是哪一家拖垮整体 |
| 不同作者站点质量差异极大 | 合并把好源和死源混为一谈 |

### 现在的做法：单源直出

**不做大合并，直接给出若干「自洽单仓」**——一个配置 + 一个 jar，由同一作者维护，
站点与 jar 严格配套。这正是「饭太硬」好用的原因，也是生态里的事实标准形态。

判定「自洽」的三个条件：
1. 有全局 `spider`；
2. ≥90% 的 type:3 站点**不带自己的 `jar`**（全部靠全局 spider）；
3. jar 实测可达且 >20KB。

| 产物 | 内容 | 用法 |
|---|---|---|
| **`dist/best.json`** | 评分最高的**一个**自洽源 | **默认推荐**，直接把里面的 `url` 填进客户端 |
| **`dist/sources.json`** | 全部通过验证的自洽源清单（含站点数、jar 大小、L2 通过率） | 想换源时从这里挑一条 |
| `dist/merged.json` | 149 条子仓地址（多仓） | 影视仓想自己管理多个源的场景 |
| `dist/curated.json` | 同上，只含人工种子 | 想要更短更稳的列表 |
| `dist/tvbox.json` | 大合并配置（**默认不再生成**） | 需要时加 `--merge` |
| `dist/report.json` / `index.html` | 探测报告 / 体检面板 | 诊断用 |

实测数据（2026-10-30）：294 个可用单仓里 **190 个结构自洽**，
其中 **169 个 jar 可达**——这些才是真正能播放的。

```bash
python run.py --config config.example.json        # 默认：单源直出
python run.py --merge                             # 额外生成大合并配置
python run.py --sources-limit 120                 # 多验证一些源
```

### 一个关键认知纠正

`spider: "./jar/pg.jar;md5;..."` 这类**相对路径不是坏地址**——客户端会以配置 URL
为基准自动解析。我最初把它当 URL 直接用，误杀了 69 个能正常播放的源。
现在 `hub/singlesource.resolve_jar()` 严格按客户端语义处理：
绝对地址原样、相对路径基于配置 URL、`csp_/py_/js_` 类名引用返回空。

## 解析库单独使用（tvbox_config_parser）

```python
from tvbox_config_parser import parse_payload, extract_urls, clean_source_url

payload = parse_payload(resp_bytes)      # 任何 TVBox/影视仓 配置响应体
payload.kind        # 'single' | 'multi_storehouse' | 'multi_urls' | 'unknown'
payload.format      # 'plain_json' | 'json_relaxed' | 'image_stego' | 'aes_hex' | 'base64_json'
payload.site_count  # sites 数量
payload.sub_entries # 多仓子线路 [(name, url)...]
payload.raw_obj     # 解析后的原始 dict
```

覆盖协议：明文 JSON；`//` 与 `/* */` 注释 + 尾逗号（词法状态机，不误伤字符串）；
图片伪装接口（PNG/JPG 末尾 `**` + Base64）；CatVod `2423`（`$#key#$`，AES-128-CBC，
兼容 13 位时间戳 IV 与 16 字节 IV）；纯 Base64。零第三方依赖（AES 需 pycryptodome，懒加载）。

## 三层验活口径

- **L1 线路级**（本仓库核心）：配置 URL 可达、可解析、类型可识别；多仓递归展开（默认深度 2-3、每仓 ≤40-100 子线、总节点上限 800）；TTFB/总时长/体积中位数测速，分级 快<500ms / 中<2s / 慢<5s。
- **L2 站点级**：对可用单仓的 `sites` 抽样（type 0/1 的 CMS API，优先可搜索站点，默认每仓 ≤8-20 个），按响应特征判定可用，产出通过率。
- **L3 播放级**（路线图）：详情→播放链接→m3u8 有效性，参考 tvbox-checker-app 的做法。

## 安全设计

- **SSRF 防护**：默认解析 DNS 并拦截私网/回环/链路本地/CGNAT/保留地址（含 IPv4-mapped IPv6），`--allow-private` 仅供本机调试；
- 响应体大小硬上限（默认 4MB），防超大流/炸弹；
- 配置里明文 `http://` 的 spider jar 会在节点上标记 `has_cleartext_spider`，供面板/报告提示供应链风险；
- 历史快照只存 URL/指标，不落任何内容数据。

## 与同类项目的关系（互补点）

| 项目 | 它做的 | tvbox-hub 吸收了什么 |
|---|---|---|
| 影视仓接口助手 v1.0 APK（本会话解包） | 端上搜集+验活+导出 | 种子表 56 线路+18 聚合页、递归展开/测速口径、导出多仓格式 |
| yz8023/ysc-helper-android | 同源原生正式版 | 2423 AES / 图片隐写 / 注释剥离的精确实现、SSRF 防护清单 |
| juhe-subhub | 服务端订阅检测拼装 | 三产物（聚合/精选/单仓）+ 体检面板 + 每日一轮思路 |
| fish2018/tvbox | 接口私有化去重 | normalize 去重、代理前缀剥离（jar 全量私有化留作路线图） |
| lyrhub/tvbox-checker-app | 站点级连通/搜索测速 | L2 抽样设计（本仓库实现 type 0/1，spider/drpy 留作路线图） |
| Guovin/iptv-api | 直播源采集测速 | 流水线形态与 Actions 模式 |
| **tengxiaobao/tvbox-source-aggregator**（Gitee；[GitHub 镜像 riowang88](https://github.com/riowang88/tvbox-source-aggregator)） | 多源合并服务：站点级去重、**Spider JAR 智能分配**、管理后台、CF Worker/Docker 部署 | **`hub/merge.py` 的算法蓝本**：相对路径转绝对、全局 spider 投票制、per-site `jar` 字段分配（type:3 站点共存）、`key\|api` 去重 + key 冲突加后缀、parses 按 `url\|type` / lives 按 url 去重、rules 按 host 合并、本地地址清洗 |

## 试运行记录（2026-10-29，本机真实网络）

实测三次端到端运行（`run-demo.log` / `dist/report.json`）：

- **规模**：56 条种子 + 18 个聚合页（3 页存活、抽取 31 条候选）→ 去重后 76 条顶层线路 → 多仓展开后 334 个节点，全程 **50.7 秒**；
- **L1 验活**：可用 58（单仓 39 + 多仓 19），平均响应 637.8ms，Top 线路：小马线路（szyyds.cn）、菜妮丝、香雅晴、王二小等；
- **L2 抽样**：39 个可用单仓全部有 l2 数据，其中 13 个含 type 0/1 CMS 站点被实际抽样（其余为 type 3 csp_* 爬虫型，按设计标「未抽样」）；
- **产物**：merged.json 38 条 / curated.json 9 条 / tvbox.json 合并 135 站点（含 spider/lives/parses）；
- **差异检测**：与上一轮快照相比自动报出 新增可用 1 条 / 失效 1 条（社区线路日流失率可见）；
- **面板**：`dist/index.html` 已在浏览器实测渲染（汇总卡片、趋势折线、差异 chips、334 行明细+筛选）。

结论：流水线端到端可用；两次中途崩溃（DNS 异常未兜底、argparse 布尔 flag 默认值覆盖配置文件）均已修复并加入离线回归（`tests/test_hub_offline.py`）。

### 种子池扩充轮（2026-10-29）

把 GitHub 高星配置仓库接入种子池（用 `tools/scan_repos.py` 经 jsDelivr 文件树扫描、`tools/verify_candidates.py` 实测解析后入库 8 条：2hacc、noimank 多仓、Dong-learn9×2、hackyjso、youhunwl×2、juhe-subhub 每日自动聚合订阅），前后对比：

| 指标 | 扩充前 | 扩充后 |
|---|---|---|
| 顶层线路 / 节点 | 76 / 334 | **84 / 436** |
| 可用（单仓/多仓） | 58（39/19） | **89（65/23）** |
| L2 抽样节点 | 13 | **25** |
| merged / curated / tvbox 站点 | 38 / 9 / 135 | **64 / 15 / 199** |
| 差异检测 | — | 新增可用 28 / 失效 0 |

耗时 73.1s。qist/tvbox、cluntop、kimwang1978、niubihu1 等仓库经扫描疑似已删除/改名，自动排除。

### 全量扩充轮（2026-10-29，种子池 125 条）

三路并挖（jsDelivr 文件树深挖 18 仓库 / 青柠 README 索引 76 链接验证 / 子代理广度发现 40 条），全部实测解析通过后入库；多份「聚合的聚合」订阅（juhe-subhub、liu673cn-BOX、zblog-xh2、ztha-GYCK、xhztv、iyouhun 等）带来持续更新的多仓子线：

| 指标 | 初始 56 种子 | 扩充轮 64 | **全量轮 125** |
|---|---|---|---|
| 顶层线路 / 节点 | 76 / 334 | 84 / 436 | **145 / 1006** |
| 可用（单仓/多仓） | 58（39/19） | 89（65/23） | **221（174/45）** |
| L2 抽样 | 13 | 25 | **74 仓·平均通过率 77%** |
| merged / curated / tvbox 站点 | 38 / 9 / 135 | 64 / 15 / 199 | **168 / 65 / 375** |
| 耗时 | 50.7s | 73.1s | 189.3s（并发16可调） |

vs 上一轮差异：新增可用 122 / 失效 3。所有候选坚持「先实测解析再入库」，猜测路径全部被过滤（404）。

### 合并引擎移植轮（2026-10-29）

参考 tengxiaobao/tvbox-source-aggregator（GitHub 镜像 riowang88，同一项目）的 merger/parser/dedup 实现，新增 `hub/merge.py` 重写单仓合并，`dist/tvbox.json` 前后对比：

| 项 | 旧（仅 type 0/1） | 新（完整合并引擎） |
|---|---|---|
| 站点总数 | 375 | **6685** |
| 其中 type:3 爬虫站 | 35（几乎全丢） | **6130** |
| 带 per-site jar 的站点 | 13 | **5979** |
| 不同 jar 数 | 1 | **272** |
| parses / lives / hosts / doh | 590 / 3 / 0 / 0 | 296 / 284 / 14 / 16 |

质量抽检：缺 key/api 0 个、key 100% 唯一、随机 8 个 jar 全部 200 可达。相对路径转绝对、spider 投票、per-site jar 分配、`key\|api` 去重、本地地址清洗均已有离线测试覆盖（`tests/test_merge.py`）。

## 自动发现新仓库（闭环）

轮流水线会自动扫新源，无需人工维护列表。四条通道按可靠性排序：

| 通道 | 实现 | 需要授权 |
|---|---|---|
| 索引页挖掘 | 抄 awesome 清单/聚合仓库 README，抽其中的配置链接 | 无 |
| Codeberg 公开搜索 | Gitea REST API（`/api/v1/repos/search`），搜 tvbox 仓库并枚举配置 | 无 |
| GitHub 仓库搜索 | 仅当设置 `GITHUB_TOKEN` 时启用（匿名 60 次/小时极易耗尽，宁可不贪） | 可选 |
| jsDelivr 文件树 | 对上两路发出现的仓库枚举根目录配置文件 | 无 |

**三道安全闸**：
1. **实测拦截**——候选必须抓取成功且 `parse_payload` 能识别为单仓/多仓且有内容，才入库；实测数据显示 96 条索引页候选里只有 1~3 条真新源，其余是已存在/死链；
2. **代理归一化判重**——`ghproxy.net/https://raw...` 与 `https://raw...` 视为同一条（`clean_source_url` 后比较），避免同一源多代理形态重复入库；
3. **与人工种子隔离**——自动发现的写入 `seeds/auto.json`（带 `first_seen`/`last_ok`/`ok`/`fail` 健康计数），**永不污染人工策展的 `seeds/lines.json`**；连续失败达 3 次的条目自动淘汰。

```bash
python run.py --no-discover      # 关闭自动发现
python run.py --discover-max 80  # 加大候选验证量
$env:GITHUB_TOKEN='ghp_xxx'; python run.py   # 启用 GitHub 搜索通道
```

1. **GitHub 配置仓库**：改 `tools/scan_repos.py` 的 REPOS 列表 → 跑扫描 → 把输出的 raw URL 加进 `tools/verify_candidates.py` 实测 → 解析通过的写进 `seeds/lines.json` 的 `base_lines`。选仓库时优先多仓（`storeHouse`/`urls`），一条多仓展开后就是几十条线；
2. **聚合的聚合**（性价比最高）：juhe-subhub 这类每日自动检测拼装的订阅（如 `https://ofind.cn/juhe-subhub/merged.json`）本身就是活水，会自己发现新线路；
3. **多仓镜像站**：`52bsj.vip:98`、`tvbox.lltv8.top`、jihulab/gitlab 的 dcang 系列已在池内，同类镜像出现时照方抓药；
4. **聚合页**：现 18 个存活率低（3/18，下载站多为 JS 渲染），可补充 FlowUs/Notion 分享页、Telegram 频道备份页等静态页；
5. 每轮运行后看面板「今日新增可用」——采集到的多仓子线若持续可用，值得提升为显式种子。

## 采集子线自动晋升（闭环）

多仓展开出的子线（一个聚合仓里往往有几十条）以前每轮都靠父仓“重新发现”，父仓一挂就全丢。
`hub/promote.py` 用长期可用性把它们**转正**：

- 每轮为每条可探到的**叶子单仓**累计 `ok_streak`（连续可用轮数）/ `fail_streak`；
- 连续可用达 `promote_after` 轮（默认 3）→ 写 `seeds/promote.json` 并标 `promoted`，下一轮起作为**顶层种子**直接探测，不再依赖父仓；
- 晋升后连续失败达 `promote_prune_fails` 轮（默认 5）→ 自动淘汰；
- 已在 `lines.json` / `auto.json` 里的线路不重复收录；多仓父节点不晋升（不可直接订阅）；完全隔离于人工种子表。

实测（连跑三轮真实网络）：第 1/2 轮无变化，**第 3 轮晋升 84 条**（东篱/周J/饭太硬镜像/小盒子/潇洒等）。

```bash
python run.py --no-promote        # 关闭晋升
python run.py --promote-after 2   # 两轮可用即转正（激进）
```

## jar 可达性检查

type:3 站点必须由客户端加载 jar 才能用。聚合产物里有 270+ 个不同 jar，抽样发现约 15% 已失效，
这些站点在 L1 层看不出来（配置能下、JSON 能解），但客户端必然报错。

每次合并后并发探测全部 jar（只取前 2KB），结果写 `dist/jar_health.json`，
指向失效 jar 的站点被打上 `"jar_dead": true`（**不直接删**——jar 可能临时抽风，交用户判断）。

```bash
python run.py --no-jar-check      # 跳过（省 30~60 秒）
```

## 已知边界（诚实说明）

- **L2 只覆盖 type 0/1**：社区主流是 type:3 爬虫站（需客户端加载 jar 才能验），所以面板上大量「未抽样」不代表不可用；
- **type:3 共存依赖 per-site jar 分配**：共 269 个 jar 中抽样实测约 85% 可达，剩余是上游已删或代理失效；
- **自动发现增速有限**：不设 `GITHUB_TOKEN` 时只有索引页 + Codeberg 两个通道，本机实测每轮新增 1~3 条；
- **晋升需要累积轮次**：默认连续 3 轮可用才转正，首次部署后前两天看不到晋升；
- **jar_dead 只是标记**：不自动删除站点，因为 jar 可能临时抽风；
- **上游源会跑路**：任何公开接口都有随时失效的可能，这正是需要每天跑的原因；历史快照可看出衰减趋势。

### 闭环轮（2026-10-29，自动发现 + 晋升 + jar 检查）

连跑多轮真实网络，验证三条自维持机制：

| 机制 | 实测结果 |
|---|---|
| 采集子线自动晋升 | 第 1/2 轮无变化 → **第 3 轮晋升 84 条**；下一轮作为顶层种子加载（84 条）并继续新晋升 7 条；现有 102 条在册、91 条已晋升 |
| jar 可达性检查 | **274 个 jar 中 220 可达 / 54 失效（19.7%）**；**763 个站点（11.0%）被标记 `jar_dead`** |
| 自动发现新仓库 | 每轮新增 1~3 条真新源（索引页挖出 96 条候选，绝大部分是已收录/死链） |

规模：顶层 236 条（含 84 条晋升种子）、节点 546、可用 233（单仓 185 / 多仓 46）、L2 抽样 77。
合并产物：**6936 站点 / 274 jar**，结构合法性审计 0 缺陷。

## 路线图

- L3 播放链路验证（详情→m3u8）；
- spider jar 去重落地与域名替换镜像（fish2018/hl128k 思路）；
- 线路死亡自动顶替 + IM 告警（订阅守护）；
- **采集子线自动晋升**：把面板上连续 N 轮可用的多仓子线回写为显式种子（当前只记录不晋升）；
- 解析库发 PyPI / npm，并提供 MCP server 供 AI 助手调用；
- 2423 密钥库：对失败解密的线路做社区密钥聚合。


## 致谢与许可合规

这个项目站在 TVBox / 影视仓 社区很多人的成果之上。完整的三方声明见 [NOTICE](NOTICE)。

### 代码级参考

| 项目 | 许可 | 本项目用到什么 |
|---|---|---|
| [yz8023/ysc-helper-android](https://github.com/yz8023/ysc-helper-android) | 仓库无 LICENSE 文件（保留所有权利） | **CatVod 2423 AES 解密方案、图片隐写提取、注释剥离状态机、SSRF 拦截分类**。这些是生态内公开的**传输格式约定**，本项目用 Python 独立重写（命名、结构、错误处理均为自有），**未逐行复制 Kotlin 源码**。若作者认为不妥，相关模块可仅依据格式规范重写。 |
| [tengxiaobao/tvbox-source-aggregator](https://gitee.com/tengxiaobao/tvbox-source-aggregator)（[GitHub 镜像](https://github.com/riowang88/tvbox-source-aggregator)） | 仓库无 LICENSE 文件 | **`hub/merge.py` 的算法蓝本**：全局 spider 投票、per-site `jar` 分配、相对路径解析、`key\|api` 去重加后缀。仅借鉴思路并用 Python 重实现，**未复制任何 TypeScript 源码，也未再分发其文件**。 |
| [zhuzhuyule/juhe-subhub](https://github.com/zhuzhuyule/juhe-subhub) | **MIT** | 三产物结构（聚合/精选/单仓）＋每日一轮＋体检面板的运营模型。 |

### 设计思路参考

| 项目 | 许可 | 借鉴点 |
|---|---|---|
| [fish2018/tvbox](https://github.com/fish2018/tvbox) | 无 LICENSE | 接口去重策略、GitHub 代理前缀剥离 |
| [lyrhub/tvbox-checker-app](https://github.com/lyrhub/tvbox-checker-app) | 无 LICENSE | L2 站点级抽样设计（type 0/1 CMS API 探测） |
| [Guovin/iptv-api](https://github.com/Guovin/iptv-api) | **AGPL-3.0** | 仅流水线形态启发（采集→校验→测速→发布）。**不含任何 AGPL 代码**，本项目为 MIT。 |
| [FongMi/TV](https://github.com/FongMi/TV) | **GPL-3.0** | 仅用于理解 TVBox 配置 JSON 结构（数据格式不受版权保护），**不含其代码**。 |

### 数据来源与索引页

流水线默认会抓取以下社区维护者的索引页来发现新配置（`hub/discover.py`）。它们的整理工作省了大量时间：

- [Zhou-Li-Bin/Tvbox-QingNing](https://github.com/Zhou-Li-Bin/Tvbox-QingNing) — README 本身就是 76 条链接的配置索引
- [laoma528/awesome-zhuiju-free](https://github.com/laoma528/awesome-zhuiju-free) — **CC-BY-4.0**，按其要求在此署名
- [youhunwl/TVAPP](https://github.com/youhunwl/TVAPP) — **Apache-2.0**
- [dongyubin/IPTV](https://github.com/dongyubin/IPTV)、[wuxierj/TVBox](https://github.com/wuxierj/TVBox)、[youhunwl/TVBox](https://github.com/youhunwl/TVBox)

`seeds/lines.json` 的种子表源自「影视仓接口助手」v1.0 的内置线路表，以及上述仓库中逐条实测通过的条目。

### 上游配置维护者

每条被探测的配置 URL 都由独立的社区维护者发布。生成的产物里保留了他们起的名字（`name` 字段）——本项目不主张对任何内容的所有权，也不对其可用性负责。

> **关于无 LICENSE 的项目**：默认版权下「无许可证 = 保留所有权利」。本项目的处理方式是：只重写**公开的格式约定**与**算法思路**，不复制源码文件、不再分发其代码；同时在 [NOTICE](NOTICE) 中明确标注来源与用途。如果你是其作者并希望调整署名方式，欢迎提 issue。


## 合规声明

本项目只对公开接口做**可用性检测、测速与格式转换**，不抓取、不存储、不分发任何影视内容；
请遵守所在地区法律法规，勿将产物用于商业用途。
