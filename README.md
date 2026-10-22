# Reverse Cinema

从案例视频逆向还原故事、剧本节拍、镜头轨道和视听规律，再输出可用于二次创作的 AI 视频提示词。

**成片 → 证据 → 剧情因果 → 剧本节拍 → 镜头轨道 → Style DNA → 二创 → AI 提示词**

这是一套可供支持 `SKILL.md` 的 AI 助手使用的创作 skill，默认中文，模型无关。它提供分析与提示词，不自带视频理解模型、视频生成服务或剪辑渲染器。

## 相比初版的改进

| 初版容易遇到的问题 | 本版处理 |
| --- | --- |
| 截图也被当成完整视频分析 | 按视频、截图、字幕、描述分别限定证据能力 |
| 焦段、光比、运镜被写得过于确定 | 观察 / 推测 / 未知 / 创作建议分层，结论带定位 |
| 所有短片套六段故事，强凑 8–12 条 DNA | 接受非叙事结构和缺失节拍；DNA 按证据给足，不凑数 |
| 分镜很多，前后却接不上 | 补角色、持物手、视线、方向、轴线、主光和首尾状态表 |
| “统一风格”锁成同焦段、同镜长 | 用镜头族与条件变化保留高潮/转折的导演决策 |
| 风格提示词混入原片人物剧情 | Global 去内容化，二创另绑定，逐片段给完整提示词 |
| 将跨镜剪辑和精确声音都交给一次生成 | 分开生成片段、剪辑/声音执行表，并核验模型能力 |

## 安装

将整个仓库文件夹放入你的技能目录，文件夹名使用 `reverse-cinema`。Codex 本地常用目录是 `~/.codex/skills/reverse-cinema/`；若配置了其他 skills 目录，使用其实际路径。不要覆盖已经存在且有自定义修改的版本。

```bash
git clone https://github.com/wudixiaoxiao666-web/reverse-cinema.git /path/to/skills/reverse-cinema
```

入口是 [SKILL.md](SKILL.md)。支持技能调用的助手可使用 `$reverse-cinema`；其他助手可读取入口及按需引用文件。技能发现/刷新行为取决于宿主。

## 使用示例

完整逆向：

```text
使用 $reverse-cinema 分析这条参考视频。
还原故事和逐镜分镜，提取有证据的 Style DNA。
把无法确认的内容标记为推测或未知，最后给去内容化的风格提示词。
```

新主题二创：

```text
使用 $reverse-cinema 先拆解参考视频，再迁移到“雨夜书店的神秘来客”。
目标 30 秒、9:16；保留构图、声音揭示和节奏规律，人物与情节重新设计。
给我二创剧本、分镜、每片段的完整中文提示词、Hard Lock 和后期声音表。
```

只有截图：

```text
使用 $reverse-cinema 分析这三张无时码截图。
先只判断静态视觉，再为新主题设计运镜；新增运动必须标明为二创设计。
```

## 输出

1. 素材范围与证据台账。
2. 一句话故事、剧本节拍及价值变化（或非叙事信息结构）。
3. 逐镜轨道、切点和连续性表。
4. Camera / Lens / Composition / Lighting / Color / Texture / Movement / Editing / Sound。
5. 有来源、适用条件和例外的 Style DNA。
6. Global Style Prompt、二创内容绑定及剧本、Temporal Prompts、Hard Lock。
7. 剪辑与声音执行表、未知项。

仅请求其中一项时缩减报告。没有新主题时给待填模板，有明确主题时给绑定后的可粘贴成稿。

## 可选本地素材整理

核心文字 skill 无第三方 Python 包依赖。辅助脚本需要 Python 3.9+ 及可运行的 FFmpeg/FFprobe，工具须自行准备。

```bash
python3 scripts/prepare_video.py reference.mp4 --out evidence --audio
python3 scripts/prepare_video.py reference.mp4 --out evidence-12-32 --start 12 --end 32 --interval 0.5
```

生成抽帧 JPG、本地 HTML 浏览页、CSV、元数据 JSON 和可选 WAV。脚本只读本地输入，拒绝覆盖非空输出目录；不自动下载、上传、识别对白或切镜。抽帧时间是请求时间约数，不能当精确 PTS 或镜头边界。音轨导出是单声道监听副本，精细声音判断应听原片。

详细读取方法见 [evidence-workflow.md](references/evidence-workflow.md)，提示词输出契约和行为用例见 [output-contract.md](references/output-contract.md)。

## 验证与边界

脚本已做端到端回归检查，见 [验证记录](VALIDATION.md)。未拿任何真实参考视频做过完整模型拉片验收；运行效果仍取决于助手的视觉/听觉能力、输入完整度及目标视频模型。Hard Lock 是约束提示，不保证精确复现。

原始创作框架来自使用者提供的 Reverse Cinema V2 提示词，本版补充了证据工作流、二创绑定和可执行素材工具。仓库不附原片、音乐、人物参考或私有素材。
