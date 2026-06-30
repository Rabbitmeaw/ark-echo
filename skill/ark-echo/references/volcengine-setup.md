# 火山引擎语音识别 — 开通与 API 参考

## 服务开通

### 推荐方式: X-Api-Key（两步）

1. **开通模型**: https://console.volcengine.com/speech/new/setting/activate → 开通「录音文件识别2.0」
2. **生成 Key**: https://console.volcengine.com/speech/new/setting/apikeys → 生成 API Key → 写入 `.env`:
   ```
   VOLCENGINE_SPEECH_API_KEY=你的Key
   ```

### 备用方式: APP ID + Access Token（三步）

1. **创建应用**: https://console.volcengine.com/speech/app → 获取 APP ID + Access Token
2. **开通模型**: 同上
3. **配置凭证**: 写入 `.env`:
   ```
   VOLCENGINE_SPEECH_APP_ID=你的APP ID
   VOLCENGINE_SPEECH_ACCESS_TOKEN=你的Access Token
   ```

> ⚠️ 两种方式二选一，推荐 X-Api-Key（更简洁）。ARK 平台的 `ark-xxx` Key 不适用。

## 费用

录音文件识别按音频时长计费（元/小时）：

| 版本 | resource_id | 单价 | 端点 |
|------|-------------|------|------|
| **2.0版** | `volc.seedasr.auc` | **0.8 元/小时** | Flash ✅ |
| 闲时版 | — | 1.2 元/小时 | 标准(异步) ❓ |
| 标准版 | `volc.bigasr.auc` | 2.3 元/小时 | Flash ✅ |
| 极速版 | `volc.bigasr.auc_turbo` | 4.5 元/小时 | Flash ✅ |

> 定价页: https://www.volcengine.com/docs/6561/1359370
> 2.0版开通: https://console.volcengine.com/speech/new/setting/activate
> 首次开通通常有免费体验额度，文件上传 (base64) 不收费

## API 规格

| 项目 | 值 |
|------|-----|
| 端点 | `POST https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash` |
| 协议 | 同步（一次请求即返回，无需 submit/poll） |
| 默认资源 ID | `volc.seedasr.auc` (2.0版, 0.8元/h) |
| 默认模型名 | `volc.seedasr.auc` |
| 支持资源 ID | `volc.seedasr.auc` / `volc.bigasr.auc` / `volc.bigasr.auc_turbo` |
| 音频传入 | `audio.data` (base64) 或 `audio.url` (HTTP URL) |
| 时长限制 | ≤ 2 小时 |
| 大小限制 | ≤ 100MB |
| 格式支持 | WAV / MP3 / OGG OPUS |

### 请求示例（推荐: X-Api-Key）

```python
headers = {
    "X-Api-Key": API_KEY,
    "X-Api-Resource-Id": "volc.seedasr.auc",   # 2.0版
    "X-Api-Request-Id": str(uuid.uuid4()),
    "X-Api-Sequence": "-1",
}
body = {
    "user": {"uid": "ark_echo_user"},
    "audio": {"data": base64_audio},
    "request": {
        "model_name": "volc.seedasr.auc",
        "enable_itn": True,     # 数字归一化
        "enable_punc": True,    # 标点
        "enable_ddc": True,     # 顺滑
    },
}
resp = requests.post(ASR_URL, json=body, headers=headers)
```

旧版认证方式见脚本 `recognize_audio()` 函数。

### 响应格式

```json
{
  "audio_info": {"duration": 52501},
  "result": {
    "text": "完整转写文本...",
    "utterances": [
      {
        "start_time": 80,
        "end_time": 6920,
        "text": "句子文本。",
        "words": [
          {"text": "就", "start_time": 80, "end_time": 290, "confidence": 0.99}
        ]
      }
    ]
  }
}
```

- `utterances` = 句子级分段（start_time/end_time 单位毫秒）
- `words` = 词级细节（含置信度）

### 错误码

| 状态码 | 含义 | 处理 |
|--------|------|------|
| `20000000` | 成功 | — |
| `20000003` | 静音音频 | 跳过该文件 |
| `45000001` | 参数无效 | 检查请求体 |
| `45000151` | 音频格式不正确 | 检查 ffmpeg 输出格式 |
| `55000031` | 服务器繁忙/限流 | 降低并发、等待重试 |

### 并发限制

火山语音 API 按 AppID 限流：

- 安全并发: **1（串行）**
- 最大建议: 2-3（更高风险触发 `55000031`）
- 需要提升配额：提交工单

> 与 ARK 平台按 Endpoint 维度的并发限制不同，语音服务是 AppID 级别限流。

## 认证方式对比

| 方式 | 状态 | 凭证来源 |
|------|------|----------|
| 新版 X-Api-Key | ✅ **已跑通 (推荐)** | https://console.volcengine.com/speech/new/setting/apikeys |
| 旧版 APP ID + Access Token | ✅ **已跑通** | https://console.volcengine.com/speech/app |
| ARK 平台 Key (`ark-xxx`) | ❌ **不适用** | ARK 平台 — 与语音服务不互通 |

## 常见问题

**Q: 和 ARK 平台的关系？**
A: 独立产品。ARK 是模型推理平台（LLM/图片/视频），语音识别是单独的语音服务。API Key 不互通，控制台独立。

**Q: 标准版 vs 极速版的区别？**
A: 极速版是同步接口（一次返回）、适合 ≤2h 音频；标准版是异步接口（submit+轮询）、适合长音频。

**Q: 需要安装 arkcli 吗？**
A: 不需要。脚本只用 `requests` 直接调 HTTP API，不依赖 arkcli。
