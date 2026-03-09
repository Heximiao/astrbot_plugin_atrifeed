![:name](https://count.getloli.com/@astrbot_plugin_atrifeed?name=astrbot_plugin_atrifeed&theme=miku&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# AstrBot 亚托莉(ATRI) 投喂互动插件

基于AstrBot框架开发的高性能机器人互动插件。通过记录群内成员与亚托莉的互动数据，实现投喂、羁绊养成、黑名单惩罚等功能，并生成精美的个人羁绊名片。

目前还处于测试阶段，还有很多功能需要添加，有可能会发生较大变动。如发现问题或者有有趣的想法欢迎提issue！

请注意：2026.3.5号之前有使用此插件的更新会导致历史记录丢失。如果报错，请关闭bot删除数据库再重载插件

## ✨ 功能亮点

* **动态羁绊系统**：内置 SQLite 数据库，记录每位用户与亚托莉的好感度、投喂统计及原谅次数。
* **多样化投喂**：支持螃蟹、水果、主食等多种 emoji 投喂，每种食物均有独特的逻辑反馈与好感加成。
* **可视化名片**：基于 HTML 渲染引擎生成高清个人羁绊卡片，直观展示你与亚托莉的互动点滴。
* **智能黑名单**：严厉打击行为不端者（如发送 💩 或辱骂），好感度过低将触发拉黑逻辑，需诚恳道歉方可恢复（道歉恢复是有次数限制的）。
* **关键词路由**：内置自定义路由引擎，支持 **精确匹配**、**开头匹配** 或 **包含匹配**，让互动更自然。
* **兼容性处理**：自动适配不同版本的 AstrBot 数据路径，确保数据库与资源文件存放安全。

## 📂 文件架构

```text
astrbot_plugin_atrifeed/
├── main.py                # 插件入口：注册指令、分发事件、初始化数据库及路径
├── keyword_trigger.py     # 核心路由：支持正则/模糊/精确匹配关键词的引擎
├── metadata.yaml          # 插件元数据 (名称、作者、版本等)
├── _conf_schema.json      # 配置项定义 (开关、触发模式等)
├── README.md              # 项目说明文档
├── CHANGELOG.md           # 版本更新日志
├── LICENSE                # 项目许可证
├── logo.png               # 插件图标
├── src/                   # 核心逻辑目录
│   ├── __init__.py        # 模块初始化
│   ├── constants.py       # 存放默认关键词映射 (_DEFAULT_KEYWORD_ROUTES)
│   ├── database.py        # 数据库操作中心 (处理好感度、金币、签到、黑名单)
│   ├── utils.py           # 工具类 (is_group_allowed 群聊过滤等)
│   ├── ban.py             # 惩罚与道歉逻辑 (run_apology_logic)
│   └── command/           # 业务指令实现目录
│       ├── __init__.py    
│       ├── feeding.py     # 投喂逻辑 (螃蟹、水果等)
│       ├── abuse.py       # 辱骂检测与黑名单处罚逻辑
│       ├── help.py        # 帮助菜单渲染
│       ├── my_atri.py     # 羁绊/属性卡片渲染
│       ├── radish.py      # 萝卜子/飞舞萝卜子互动
│       ├── other_emoji.py # 针筒等表情互动
│       ├── sign_in.py     # 签到逻辑
│       ├── gig.py         # 打工逻辑
│       └── dice.py        # 骰子/博弈逻辑
├── pic/                   # 静态资源
│   ├── demo/              # README 使用的示例图 (帮助、卡片演示)
│   ├── emoji/             # 互动反馈表情包 (含子文件夹：angry, bad, radish 等)
│   ├── lihui/             # 角色立绘库 (含 gig 打工专属立绘)
│   ├── pictorial/         # 卡片背景素材
│   └── sign_in/           # 签到功能专用配图
├── template/              # HTML 渲染模板 (用于生成图片)
│   ├── atri_help.html     
│   ├── atri_sign_in.html  # 签到卡片模板
│   ├── gig.html           # 打工结算模板
│   └── my_atri1.html      # 羁绊卡片模板
└── __pycache__/           # 自动生成的编译缓存

```

## 🎮 使用指令

| 指令/关键词 | 权限 | 说明 |
| --- | --- | --- |
| `亚托莉帮助` | 用户 | 渲染并发送插件详细功能指南 |
| `我的亚托莉` | 用户 | 查看羁绊值及个人统计卡片 |
| `🦀` | 用户 | 投喂螃蟹 |
| `🍓/🍉/🍎/🍜/🍧/🍔/🍕/🍱/🍄/🍭/🍙` | 用户 | 投喂加好感 |
| `✨/🚬/💩/💉` | 用户 | 触发各种言语/反馈 |
| `萝卜子` | 用户 | 猜猜看会发生什么（笑） |
| `亚托莉我错了对不起` | 用户 | 被拉黑后道歉尝试恢复好感 |
| `/clear_feed_log` | 管理员 | 清空今日投喂记录 |


## 💡 关键词模式

若在配置中开启 `keyword_trigger_enabled`，则上述 emoji 和部分关键词可**直接发送**（不带类似于 `/` 的前缀）触发。

* 示例：直接在群里发一个 `🦀` 即可完成投喂。

## 🖼️ 功能演示
![好感度卡片演示](pic/demo/好感度卡片演示.png)
![投喂演示](pic/demo/投喂演示.png)
![帮助演示](pic/demo/帮助演示.png)

## ⚙️ 配置项说明

在 AstrBot 管理面板中可配置以下内容：

| 配置键 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `keyword_trigger_enabled` | bool | false | 是否启用关键词直接触发（无需前缀） |
| `keyword_trigger_mode` | string | exact | 匹配模式：`exact`(精确) / `starts_with`(开头) / `contains`(包含) |
| `global_ban_use_qq` | bool | true | 彻底激怒亚托莉后，是否通过框架全局封禁该 QQ（目前没用） |
| `whitelist_groups` | list | [] | 白名单群号列表 |
| `blacklist_groups` | list | [] | 黑名单群号列表 |

## 🛠️ 环境要求

本插件依赖 AstrBot 的浏览器渲染引擎：

1. **Playwright**：用于渲染 `template/` 下的 HTML 模板，请确保环境已安装。（一般自带，不用管）
2. **资源路径**：请勿随意移动 `pic/` 文件夹，否则会导致表情包发送失败。

觉得亚托莉可爱的话，就给个 star 吧 ❤️~
