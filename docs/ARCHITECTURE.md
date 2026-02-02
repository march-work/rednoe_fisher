# 架构概览

本项目目标是在 Windows 桌面端以“视觉自动化 + OCR”的方式采集小红书内容：通过截图识别文本并在后台模拟点击/滚动，不依赖 Web API 或抓包。

## 模块划分

### 入口与编排

- `src/main.py`
  - 负责加载配置、选择目标窗口、驱动主循环（截图 → OCR → 匹配 → 交互 → 落盘）

### 窗口管理（Window）

- `src/modules/window_manager.py`
  - 枚举可见窗口并选择目标窗口（交互式 / 按标题正则）
  - 获取窗口 client 区域在屏幕上的坐标
  - 查找可投递输入消息的子窗口句柄（用于后台点击/滚动）

### 视觉引擎（Vision / OCR）

- `src/modules/vision_engine.py`
  - 屏幕/窗口截图（`ImageGrab` / `PrintWindow`）
  - 图像预处理（灰度、缩放、中值滤波、阈值化）
  - OCR 提取整段文本（`image_to_string`）
  - OCR 文本定位（`image_to_data`）用于“精准点击”关键词所在区域

### 交互模拟（Interaction）

- `src/modules/interaction_simulator.py`
  - 使用 Win32 `PostMessage` 发送鼠标/滚轮/键盘消息
  - 默认拖拽模拟滑动，失败时可切换滚轮滚动
  - 调试 overlay：`src/utils/overlay.py` 会在屏幕上绘制触点位置，便于对齐/排错

### 数据处理与落盘（Data）

- `src/modules/data_processor.py`
  - 解析发布时间（相对时间、日期等）
  - 按配置生成文件名并写入 JSON

## 主循环数据流

1. 选择目标窗口并聚焦
2. 获取 client 区域屏幕坐标
3. 截图（`screen` 或 `printwindow`）
4. OCR 提取文本
5. 关键词匹配
6. 命中后尝试 OCR 定位点击点进入详情页
7. 详情页分页滚动并 OCR 抓取正文与图片文字
8. 写入 JSON（可选 debug 产物）
9. 返回列表页继续下一轮

## 配置与可观测性

- `config/config.json`
  - 关键词列表、OCR 参数、滚动节奏、输出目录、调试开关
- `logs/`
  - 运行日志（含窗口选择、点击/滚动动作、OCR 摘要等）
- `result/`
  - 结构化输出 JSON
- `result/debug/`
  - 截图、OCR 文本、细节 debug 日志（定位误差/误点排查最有用）
