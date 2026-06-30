# ark-echo

[中文](#中文) | [English](#english)

---

<a name="中文"></a>
## 中文

批量视频语音转文字工具。使用火山引擎录音文件识别大模型 2.0，将本地视频文件夹转为带**句子级时间码**的结构化 Excel 表格。

### 快速开始

```bash
brew install ffmpeg                               # macOS
pip install requests pandas openpyxl

export VOLCENGINE_SPEECH_API_KEY="your-api-key"    # 语音控制台获取

python3 batch_asr.py /path/to/videos/             # 运行
```

### 前置依赖

| 依赖 | 安装方式 |
|------|----------|
| Python 3.8+ | https://python.org |
| ffmpeg | macOS: `brew install ffmpeg` / Windows: `winget install ffmpeg` / Linux: `sudo apt install ffmpeg` |
| requests, pandas, openpyxl | `pip install requests pandas openpyxl` |

### 认证配置

1. 打开 https://console.volcengine.com/speech/new/setting/activate → 开通「录音文件识别 2.0」
2. 打开 https://console.volcengine.com/speech/new/setting/apikeys → 生成 API Key
3. 设置环境变量: `export VOLCENGINE_SPEECH_API_KEY="your-key"`
4. 或创建 `.env` 文件（脚本自动加载）: `VOLCENGINE_SPEECH_API_KEY=your-key`

> 也支持旧版 APP ID + Access Token: `VOLCENGINE_SPEECH_APP_ID` + `VOLCENGINE_SPEECH_ACCESS_TOKEN`

### 命令行参数

```
python3 batch_asr.py <文件夹> [选项]
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `folder` | 必填 | 视频文件夹路径（递归扫描子目录） |
| `-o, --output` | `batch_asr_result.xlsx` | 输出 Excel 路径 |
| `-c, --concurrency` | 1 | 并发数（建议 1-2） |
| `-m, --model` | `2.0` | 模型: `2.0`(0.8元/h) / `standard`(2.3元/h) / `flash`(4.5元/h) |
| `--no-resume` | 否 | 禁用断点续传 |

### 输出格式

| 列名 | 说明 |
|------|------|
| 文件名 | 原始视频文件名 |
| 文件路径 | 完整绝对路径 |
| 时长 (秒) | ASR 返回的音频时长 |
| 文件大小 (MB) | 原始视频文件大小 |
| 完整文本 | 纯文本转写 |
| 带时间码文本 | `[HH:MM:SS - HH:MM:SS] 句子文本` |
| 处理状态 | 成功 / 失败 / 跳过 |
| 处理耗时 | API 调用耗时 |
| 错误信息 | 失败异常详情 |

时间码格式示例:

```
[00:00:00 - 00:00:06] 就在刚刚，信仁智能发布了全球第一款产品。
[00:00:06 - 00:00:13] 我非常荣幸和现场200位企业家共同见证了这个时刻。
```

### 可选模型

| `-m` 值 | 单价 | 说明 |
|---------|------|------|
| `2.0` (默认) | **0.8 元/小时** | 最便宜 |
| `standard` | 2.3 元/小时 | 标准版 |
| `flash` | 4.5 元/小时 | 极速版 |

切换到非默认模型时显示价格差异警告。

### 特性

- **断点续传**: 中断后重跑自动跳过已完成文件
- **增量写入**: 每完成一个文件立即写入 Excel，中途中断不丢失结果
- **递归扫描**: 自动处理子目录中的视频
- **多平台**: macOS / Windows / Linux

### 限制

- 单文件音频 ≤ 100MB，时长 ≤ 2 小时
- 并发建议 ≤ 2
- 格式: mp4 / mov / avi / mkv / wmv / flv / webm / m4v / mpg / mpeg

### 费用

| 模型 | 单价 | 100 小时成本 |
|------|------|-------------|
| 2.0（默认） | 0.8 元/h | ≈ 80 元 |
| 标准版 | 2.3 元/h | ≈ 230 元 |
| 极速版 | 4.5 元/h | ≈ 450 元 |

> 定价页: https://www.volcengine.com/docs/6561/1359370 | 首次开通有免费额度

### 故障排查

| 现象 | 解决 |
|------|------|
| `ffmpeg: command not found` | `brew install ffmpeg` |
| `未找到语音识别凭证` | 设置 `VOLCENGINE_SPEECH_API_KEY` |
| `Invalid X-Api-Key` | 确认是语音控制台 Key，非 ARK `ark-xxx` 格式 |
| `55000031` | 降低并发，等待重试 |
| `20000003` | 静音音频，正常跳过 |

### 注意

- 火山引擎语音识别与 ARK 平台独立，API Key 不互通
- 不需要安装 arkcli

---

<a name="english"></a>
## English

Batch video-to-text transcription tool. Uses Volcengine BigModel ASR 2.0 to convert local video folders into structured Excel sheets with **sentence-level timestamps**.

### Quick Start

```bash
brew install ffmpeg                               # macOS
pip install requests pandas openpyxl

export VOLCENGINE_SPEECH_API_KEY="your-api-key"    # from speech console

python3 batch_asr.py /path/to/videos/             # run
```

### Prerequisites

| Dependency | Installation |
|------------|-------------|
| Python 3.8+ | https://python.org |
| ffmpeg | macOS: `brew install ffmpeg` / Windows: `winget install ffmpeg` / Linux: `sudo apt install ffmpeg` |
| requests, pandas, openpyxl | `pip install requests pandas openpyxl` |

### Authentication

1. Go to https://console.volcengine.com/speech/new/setting/activate → Activate "Audio File Recognition 2.0"
2. Go to https://console.volcengine.com/speech/new/setting/apikeys → Generate API Key
3. Set environment variable: `export VOLCENGINE_SPEECH_API_KEY="your-key"`
4. Or create `.env` file: `VOLCENGINE_SPEECH_API_KEY=your-key`

> Legacy APP ID + Access Token also supported via `VOLCENGINE_SPEECH_APP_ID` + `VOLCENGINE_SPEECH_ACCESS_TOKEN`

### CLI Options

```
python3 batch_asr.py <folder> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `folder` | required | Video folder path (scans recursively) |
| `-o, --output` | `batch_asr_result.xlsx` | Output Excel path |
| `-c, --concurrency` | 1 | Concurrent workers (1-2 recommended) |
| `-m, --model` | `2.0` | Model: `2.0`(¥0.8/h) / `standard`(¥2.3/h) / `flash`(¥4.5/h) |
| `--no-resume` | no | Disable checkpoint resume |

### Output

| Column | Description |
|--------|-------------|
| 文件名 | Original filename |
| 文件路径 | Full absolute path |
| 时长 (秒) | Audio duration from ASR |
| 文件大小 (MB) | Original file size |
| 完整文本 | Full transcription text |
| 带时间码文本 | `[HH:MM:SS - HH:MM:SS] sentence text` |
| 处理状态 | Success / Failed / Skipped |
| 处理耗时 | API call duration |
| 错误信息 | Error details on failure |

Timestamp format:

```
[00:00:00 - 00:00:06] Just now, Xinren Intelligence released the world's first product.
[00:00:06 - 00:00:13] I am honored to witness this moment with 200 entrepreneurs.
```

### Models

| `-m` value | Price | Note |
|------------|-------|------|
| `2.0` (default) | **¥0.8/hour** | Cheapest |
| `standard` | ¥2.3/hour | Standard |
| `flash` | ¥4.5/hour | Fastest, most expensive |

Price warning displayed when switching from default model.

### Features

- **Checkpoint resume**: Auto-skip completed files on restart
- **Incremental write**: Excel updated after each file — no data loss on interruption
- **Recursive scan**: Auto-processes videos in subdirectories
- **Cross-platform**: macOS / Windows / Linux

### Limits

- Per-file audio ≤ 100MB, duration ≤ 2 hours
- Concurrency ≤ 2 recommended
- Formats: mp4 / mov / avi / mkv / wmv / flv / webm / m4v / mpg / mpeg

### Pricing

| Model | Unit Price | 100 hours cost |
|------|------------|----------------|
| 2.0 (default) | ¥0.8/h | ≈ ¥80 |
| Standard | ¥2.3/h | ≈ ¥230 |
| Flash | ¥4.5/h | ≈ ¥450 |

> Pricing: https://www.volcengine.com/docs/6561/1359370 | Free trial available

### Troubleshooting

| Symptom | Solution |
|---------|----------|
| `ffmpeg: command not found` | Install ffmpeg |
| `未找到语音识别凭证` | Set `VOLCENGINE_SPEECH_API_KEY` |
| `Invalid X-Api-Key` | Use speech console key, not ARK `ark-xxx` format |
| `55000031` | Reduce concurrency, retry |
| `20000003` | Silent audio, auto-skipped |

### Notes

- Volcengine Speech is independent from the ARK platform — API keys are not interchangeable
- arkcli is not required
