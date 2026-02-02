# Rednoe Fisher（小红书 OCR 采集器 / MVP）

这是一个 Windows 上运行的 Python 采集器：对指定窗口截图 → Tesseract OCR 识别文本 → 通过 Win32 `PostMessage` 在后台模拟点击/滚动进入详情页 → 将结果以 JSON 落盘。

## 特性

- 支持窗口交互式选择或按标题正则自动选择
- 支持 `screen` 截图与 `PrintWindow` 截图（可配置）
- 关键词命中后可尝试 OCR 精准定位点击点，定位失败可回退为滚动
- 输出结构化 JSON（包含标题/作者/发布时间/正文/图片文字 OCR 等）
- `result/debug/` 支持抓图、OCR 文本与调试日志落盘（便于排查误点/误识别）

## 环境要求

- Windows 10/11
- Python 3.10+（项目当前在 Python 3.12 环境验证过）
- 安装 Tesseract-OCR（建议包含 `chi_sim` 语言包）
  - 可通过环境变量 `TESSERACT_CMD` 指定 tesseract.exe 路径

## 安装

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## 配置

编辑 `config/config.json`：

- `keywords`: 关键词列表（命中后会尝试打开详情页）
- `ocr_config`: OCR 参数（语言 `language`、`psm`、`scale`、阈值模式等）
- `scroll_config`: 滚动速度与停顿范围
- `output_config`: 输出目录与文件命名规则
- `debug_dump/debug_folder`: 调试产物开关与目录

## 运行

推荐用模块方式启动（更规范、导入更稳定）：

```bash
python -m src.main
```

按窗口标题正则自动选窗（示例）：

```bash
python -m src.main -w "Chrome|雷电|MuMu|模拟器"
```

## 输出

- 结果：`result/*.json`
- 调试：`result/debug/`（截图、OCR 文本、debug 日志、详情页截图等）
- 日志：`logs/fisher_*.log`

## 测试

```bash
python -m pytest
```

## 文档

- 产品需求：`xiaohongshu-scraper-prd.md`
- 技术架构：`xiaohongshu-scraper-tech-arch.md`
- 本仓库补充的架构说明：`docs/ARCHITECTURE.md`
