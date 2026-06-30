#!/usr/bin/env python3
"""
批量视频语音转文字工具

模型: 火山引擎录音文件识别大模型2.0 (默认)
     端点: openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash
     默认资源ID: volc.seedasr.auc (0.8元/小时)

API 文档: https://www.volcengine.com/docs/6561/1631584

用法:
    python batch_asr.py /path/to/videos/
    python batch_asr.py /path/to/videos/ -m flash     # 切换模型
    python batch_asr.py /path/to/videos/ -c 2          # 并发数

认证方式 (两种均已验证):
    新版 (推荐): export VOLCENGINE_SPEECH_API_KEY='...'
    旧版:        export VOLCENGINE_SPEECH_APP_ID='...' VOLCENGINE_SPEECH_ACCESS_TOKEN='...'

依赖: pip install requests pandas openpyxl; ffmpeg
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

# ── 常量 ──────────────────────────────────────────────

# 录音文件极速识别 API (同步接口)
ASR_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"

# 模型预设 (已验证可用)
MODEL_PRESETS = {
    "2.0":      {"resource_id": "volc.seedasr.auc",      "model_name": "volc.seedasr.auc",  "desc": "录音文件识别2.0",  "price": "0.8 元/小时"},
    "v2":       {"resource_id": "volc.seedasr.auc",      "model_name": "volc.seedasr.auc",  "desc": "录音文件识别2.0 (别名)", "price": "0.8 元/小时"},
    "flash":    {"resource_id": "volc.bigasr.auc_turbo", "model_name": "bigmodel",          "desc": "极速版",           "price": "4.5 元/小时"},
    "standard": {"resource_id": "volc.bigasr.auc",       "model_name": "bigmodel",          "desc": "标准版",           "price": "2.3 元/小时"},
    "bigmodel": {"resource_id": "volc.bigasr.auc_turbo", "model_name": "bigmodel",          "desc": "极速版 (别名)",   "price": "4.5 元/小时"},
}
DEFAULT_MODEL = "2.0"

# 支持的视频扩展名
SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"}


def _parse_price(price_str: str) -> float:
    """从价格字符串提取数值，如 '0.8 元/小时' → 0.8"""
    try:
        return float(price_str.split()[0])
    except (ValueError, IndexError):
        return 0.0


# ── 凭证加载 ──────────────────────────────────────────

def _load_dotenv(path: Path):
    """加载 .env 文件到 os.environ（不覆盖已有环境变量）"""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if k not in os.environ:
            os.environ[k] = v


def load_credentials() -> dict:
    """
    加载认证凭证（环境变量优先，绝不回退到 ARK Key）。

    优先级: 环境变量 > 本地 .env (仅兜底) > ~/.arkcli/.env

    返回:
        {"api_key": "..."}          新版控制台: 单一 X-Api-Key
        {"app_id": "...", "access_token": "..."}  旧版控制台: APP ID + Access Token
    """
    # .env 仅作兜底，不覆盖已设置的环境变量
    _load_dotenv(Path(__file__).resolve().parent / ".env")
    _load_dotenv(Path.home() / ".arkcli" / ".env")

    env = os.environ

    # 新版控制台: X-Api-Key
    api_key = env.get("VOLCENGINE_SPEECH_API_KEY")

    # 旧版控制台: APP ID + Access Token
    app_id = env.get("VOLCENGINE_SPEECH_APP_ID")
    access_token = env.get("VOLCENGINE_SPEECH_ACCESS_TOKEN")

    if api_key:
        return {"api_key": api_key}
    if app_id and access_token:
        return {"app_id": app_id, "access_token": access_token}

    raise RuntimeError(
        "未找到语音识别凭证。请设置环境变量:\n"
        "  export VOLCENGINE_SPEECH_API_KEY='your-api-key'\n"
        "获取地址: https://console.volcengine.com/speech/new/setting/apikeys"
    )


# ── 文件扫描 ────────────────────────────────────────────

def find_video_files(folder: Path) -> list[Path]:
    """递归扫描文件夹中的所有视频文件，按路径排序"""
    return sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_VIDEO_EXTS
    )


# ── 音频提取 ────────────────────────────────────────────

def extract_audio(video_path: Path, work_dir: Path) -> Path:
    """
    用 ffmpeg 从视频提取音频为 MP3 (API 支持 WAV/MP3/OGG OPUS)。

    使用 MP3 以减少文件体积，确保 ≤100MB 限制。
    """
    audio_path = work_dir / f"{video_path.stem}.mp3"
    if audio_path.exists():
        return audio_path

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",                    # 丢弃视频流
        "-acodec", "libmp3lame",  # MP3 编码
        "-ar", "16000",           # 16kHz 采样率
        "-ac", "1",               # 单声道
        "-b:a", "64k",            # 64kbps 比特率 (语音足够)
        "-loglevel", "error",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 音频提取失败: {result.stderr.strip()}")
    return audio_path


# ── ASR API (同步) ─────────────────────────────────────

def recognize_audio(audio_path: Path, creds: dict,
                   resource_id: str = "volc.seedasr.auc",
                   model_name: str = "volc.seedasr.auc") -> dict:
    """
    调用录音文件识别 API，一次请求返回完整结果。

    Args:
        audio_path: 音频文件路径
        creds: 认证凭证
        resource_id: 资源ID (决定用哪个模型)
        model_name: 模型名

    返回:
        {
            "audio_info": {"duration": 2499},
            "result": {
                "text": "...",
                "utterances": [
                    {"start_time": 450, "end_time": 1530, "text": "...",
                     "words": [{"text": "关", "start_time": 450, "end_time": 770, "confidence": 0}, ...]}
                ]
            }
        }
    """
    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()

    headers = {
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "X-Api-Sequence": "-1",
    }

    if "api_key" in creds:
        headers["X-Api-Key"] = creds["api_key"]
    else:
        headers["X-Api-App-Key"] = creds["app_id"]
        headers["X-Api-Access-Key"] = creds["access_token"]

    uid = creds.get("app_id") or creds.get("api_key", "")

    body = {
        "user": {"uid": uid},
        "audio": {"data": audio_b64},
        "request": {
            "model_name": model_name,
            "enable_itn": True,      # 数字归一化
            "enable_punc": True,     # 标点符号
            "enable_ddc": True,      # 顺滑 (去除语气词)
        },
    }

    resp = requests.post(ASR_URL, json=body, headers=headers, timeout=300)
    status_code = resp.headers.get("X-Api-Status-Code", "")

    if status_code == "20000000":
        return resp.json()
    elif status_code == "20000003":
        raise RuntimeError("静音音频，未检测到有效语音内容")
    elif status_code.startswith("45"):
        raise RuntimeError(f"请求参数错误 [{status_code}]: {resp.text[:300]}")
    elif status_code.startswith("55"):
        raise RuntimeError(f"服务端错误 [{status_code}]: {resp.text[:300]}")
    else:
        raise RuntimeError(
            f"ASR 请求失败 HTTP {resp.status_code}, "
            f"Status-Code: {status_code}, "
            f"Message: {resp.headers.get('X-Api-Message', 'N/A')}"
        )


# ── 结果处理 ────────────────────────────────────────────

def ms_to_hms(ms: int) -> str:
    """毫秒 → HH:MM:SS"""
    total_s = max(0, ms) // 1000
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_timestamped(utterances: list[dict]) -> str:
    """将 utterances 格式化为带时间码的文本。

    格式: [HH:MM:SS - HH:MM:SS] 句子文本
    """
    lines = []
    for u in utterances:
        start = ms_to_hms(u.get("start_time", 0))
        end = ms_to_hms(u.get("end_time", 0))
        text = u.get("text", "").strip()
        if text:
            lines.append(f"[{start} - {end}] {text}")
    return "\n\n".join(lines)


# ── 单文件处理 ──────────────────────────────────────────

def process_one(video_path: Path, creds: dict, work_dir: Path,
                resource_id: str = "volc.seedasr.auc",
                model_name: str = "volc.seedasr.auc") -> dict:
    """处理单个视频文件，返回结果行字典"""
    result = {
        "文件名": video_path.name,
        "文件路径": str(video_path),
        "时长 (秒)": None,
        "文件大小 (MB)": round(video_path.stat().st_size / 1024 / 1024, 2),
        "完整文本": "",
        "带时间码文本": "",
        "处理状态": "处理中",
        "处理耗时": 0,
        "错误信息": "",
    }
    t0 = time.time()

    try:
        # 1. 提取音频
        audio_path = extract_audio(video_path, work_dir)

        # 2. 校验音频大小 (API 限制 100MB)
        audio_size_mb = audio_path.stat().st_size / 1024 / 1024
        if audio_size_mb > 100:
            raise RuntimeError(f"音频文件 {audio_size_mb:.1f}MB 超过 100MB 限制")

        # 3. 调用 ASR (同步，一次返回)
        asr_data = recognize_audio(audio_path, creds, resource_id, model_name)

        # 4. 解析结果
        audio_info = asr_data.get("audio_info", {})
        duration_ms = audio_info.get("duration", 0)
        result["时长 (秒)"] = round(duration_ms / 1000, 2) if duration_ms else None

        asr_result = asr_data.get("result", {})
        result["完整文本"] = asr_result.get("text", "").strip()

        utterances = asr_result.get("utterances", [])
        result["带时间码文本"] = format_timestamped(utterances)

        result["处理状态"] = "成功"

    except Exception as e:
        result["处理状态"] = "失败"
        result["错误信息"] = f"{type(e).__name__}: {e}"
        err_str = str(e)
        if "静音" in err_str:
            result["处理状态"] = "跳过"
            result["错误信息"] = "静音音频，无有效语音内容"

    finally:
        result["处理耗时"] = round(time.time() - t0, 1)

    return result


# ── 进度管理 ────────────────────────────────────────────

def _progress_key(video_path: Path) -> str:
    """用文件名+文件大小作为去重 key，避免同名文件冲突"""
    return f"{video_path.name}|{video_path.stat().st_size}"


def load_progress(progress_file: Path) -> dict[str, dict]:
    """加载已完成的进度"""
    if progress_file.exists():
        return {_progress_key(Path(r["文件路径"])): r for r in json.loads(progress_file.read_text()) if "文件路径" in r}
    return {}


def save_progress(progress_file: Path, results: dict[str, dict]):
    """保存进度"""
    progress_file.write_text(
        json.dumps(list(results.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Excel 输出 ──────────────────────────────────────────

OUTPUT_COLUMNS = [
    "文件名", "文件路径", "时长 (秒)", "文件大小 (MB)",
    "完整文本", "带时间码文本", "处理状态", "处理耗时", "错误信息",
]


def write_excel(results: list[dict], output_path: Path):
    """将结果写入 Excel"""
    df = pd.DataFrame(results, columns=OUTPUT_COLUMNS)
    df.to_excel(str(output_path), index=False, engine="openpyxl")


# ── 主入口 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="批量视频语音转文字工具 — 火山引擎录音文件识别"
    )
    parser.add_argument("folder", type=str, help="包含视频文件的文件夹路径")
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="输出 Excel 路径 (默认: <folder>/batch_asr_result.xlsx)",
    )
    parser.add_argument(
        "--concurrency", "-c", type=int, default=1,
        help="并发处理数 (默认: 1，语音 API 建议串行)",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="禁用断点续传，重新处理全部文件",
    )
    parser.add_argument(
        "--model", "-m", type=str, default=DEFAULT_MODEL,
        choices=list(MODEL_PRESETS.keys()),
        help=f"选择模型预设: {', '.join(MODEL_PRESETS.keys())} (默认: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--resource-id", type=str, default=None,
        help="自定义 resource_id (覆盖 --model 预设)",
    )
    parser.add_argument(
        "--model-name", type=str, default=None,
        help="自定义 model_name (覆盖 --model 预设)",
    )
    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    if not folder.is_dir():
        print(f"错误: 文件夹不存在: {folder}")
        sys.exit(1)

    # 加载凭证
    creds = load_credentials()
    auth_type = "新版 X-Api-Key" if "api_key" in creds else "旧版 APP ID + Access Token"
    print(f"认证方式: {auth_type}")

    # 模型配置
    preset = MODEL_PRESETS[args.model]
    resource_id = args.resource_id or preset["resource_id"]
    model_name = args.model_name or preset["model_name"]
    price = preset.get("price", "? 元/小时")
    print(f"模型: {preset['desc']} ({price}, resource={resource_id}, model={model_name})")

    # 非默认模型时，显示价格差异提醒
    if args.model != DEFAULT_MODEL and not args.resource_id:
        default_price = MODEL_PRESETS[DEFAULT_MODEL].get("price", "")
        ratio = _parse_price(price) / _parse_price(default_price) if _parse_price(default_price) > 0 else 1
        print(f"  ⚠️  当前 {price}，默认 2.0 版仅 {default_price}（贵 {ratio:.1f}x）")
    if args.resource_id:
        print(f"  ⚠️  使用自定义 resource_id，请确认计费方式")

    # 工作目录
    work_dir = folder / "_asr_audio_cache"
    work_dir.mkdir(exist_ok=True)

    output_path = Path(args.output) if args.output else folder / "batch_asr_result.xlsx"
    progress_file = folder / "_asr_progress.json"

    # 扫描文件
    video_files = find_video_files(folder)
    if not video_files:
        print(f"未在 {folder} 中找到视频文件 ({', '.join(SUPPORTED_VIDEO_EXTS)})")
        sys.exit(1)

    print(f"找到 {len(video_files)} 个视频文件:")
    for vf in video_files:
        size_mb = vf.stat().st_size / 1024 / 1024
        print(f"  - {vf.name} ({size_mb:.1f} MB)")

    # 加载进度
    all_results: dict[str, dict] = {}
    if not args.no_resume:
        all_results = load_progress(progress_file)
        if all_results:
            done = sum(1 for r in all_results.values() if r["处理状态"] in ("成功", "跳过"))
            print(f"\n断点续传: 已完成 {done}/{len(all_results)}")

    # 过滤待处理
    pending = [vf for vf in video_files if _progress_key(vf) not in all_results]
    if not pending:
        print("所有文件已处理完毕，直接生成 Excel")
    else:
        print(f"\n待处理: {len(pending)} 个, 并发数: {args.concurrency}")

        total = len(pending)
        completed_count = 0
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {
                executor.submit(process_one, vf, creds, work_dir, resource_id, model_name): vf
                for vf in pending
            }
            for future in as_completed(futures):
                vf = futures[future]
                completed_count += 1
                try:
                    row = future.result()
                except Exception as e:
                    row = {
                        "文件名": vf.name, "文件路径": str(vf),
                        "时长 (秒)": None,
                        "文件大小 (MB)": round(vf.stat().st_size / 1024 / 1024, 2),
                        "完整文本": "", "带时间码文本": "",
                        "处理状态": "失败", "处理耗时": 0,
                        "错误信息": f"{type(e).__name__}: {e}",
                    }
                all_results[_progress_key(vf)] = row
                save_progress(progress_file, all_results)

                # 增量写入 Excel —— 即使中断，已完成的结果不会丢失
                results_so_far = []
                for vf2 in video_files:
                    r = all_results.get(_progress_key(vf2))
                    if r:
                        results_so_far.append(r)
                write_excel(results_so_far, output_path)

                icon = {"成功": "✓", "失败": "✗", "跳过": "⊘"}.get(row["处理状态"], "?")
                pct = f"{completed_count}/{total}" if total > 1 else ""
                print(f"  [{icon} {row['处理状态']}] {pct} {row['文件名']} ({row['处理耗时']}s)")
                if row["错误信息"]:
                    print(f"          {row['错误信息'][:120]}")

    # 最终统计 (Excel 已在上面的循环中增量写入)
    results_list = []
    for vf in video_files:
        row = all_results.get(_progress_key(vf))
        if row:
            results_list.append(row)

    success = sum(1 for r in results_list if r["处理状态"] == "成功")
    skipped = sum(1 for r in results_list if r["处理状态"] == "跳过")
    failed = sum(1 for r in results_list if r["处理状态"] == "失败")
    print(f"\n完成! 成功: {success}, 跳过: {skipped}, 失败: {failed}, 总计: {len(results_list)}")
    print(f"结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
