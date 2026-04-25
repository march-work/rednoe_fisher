# 方案四：Airtest + Poco 开发手册

> 小红书帖子截图提取工具 — 基于网易 Airtest 框架

---

## 目录

1. [方案概述](#1-方案概述)
2. [环境搭建](#2-环境搭建)
3. [设备连接](#3-设备连接)
4. [Airtest 图像识别 API](#4-airtest-图像识别-api)
5. [Poco UI 控件树 API](#5-poco-ui-控件树-api)
6. [弹窗与等待处理](#6-弹窗与等待处理)
7. [OCR 文字识别](#7-ocr-文字识别)
8. [长截图与滚动拼接](#8-长截图与滚动拼接)
9. [Airtest IDE 使用指南](#9-airtest-ide-使用指南)
10. [小红书提取实战](#10-小红书提取实战)
11. [反检测策略](#11-反检测策略)
12. [常见问题排查](#12-常见问题排查)
13. [与方案一的对比](#13-与方案一的对比)

---

## 1. 方案概述

### 架构

```
┌──────────────────────────────────────────────┐
│              Python 控制脚本                   │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Airtest  │  │  Poco    │  │PaddleOCR │   │
│  │图像识别操作│  │UI控件树操作│  │ 文字识别  │   │
│  └────┬─────┘  └────┬─────┘  └──────────┘   │
│       │             │                        │
│  ┌────┴─────────────┴─────┐                  │
│  │   Airtest Android Driver│                 │
│  │  (minicap + minitouch)  │                 │
│  └───────────┬────────────┘                  │
│              │ ADB 协议                       │
└──────────────┼───────────────────────────────┘
               │
          ┌────┴────┐
          │ Android │
          │  小米手机 │
          │(小红书App)│
          └─────────┘
```

### 工作流程

1. Airtest 通过 minicap 投屏 + minitouch 控制连接手机
2. Poco 通过 Android UIAutomation 获取 UI 控件树
3. 图像识别 (Template) 处理控件树无法覆盖的场景
4. PaddleOCR 补充识别截图中的文字
5. 按帖子标题建立文件夹，分类保存截图

### 双引擎优势

Airtest 框架最大的特点是**图像识别 + UI 控件树**双引擎：

| 引擎 | 用途 | 特点 |
|------|------|------|
| **Airtest (图像)** | 点击按钮、滑动、判断页面状态 | 不依赖 App 内部结构，抗 UI 更新 |
| **Poco (控件树)** | 读取文字、定位元素、判断状态 | 精确、快速，可直接获取文本内容 |

---

## 2. 环境搭建

### 2.1 手机端配置

```
设置 → 我的设备 → MIUI版本 → 连续点击7次 → 开启开发者模式
设置 → 更多设置 → 开发者选项 → 开启以下选项：
  ✓ USB 调试
  ✓ USB 安装
  ✓ USB 调试（安全设置）
  ✓ 禁止权限监控
```

### 2.2 PC 端安装

```bash
# 核心 Airtest 库
pip install airtest

# Poco UI 控件树库（包名是 pocoui，不是 poco）
pip install pocoui

# OCR
pip install paddleocr paddlepaddle

# 图像处理
pip install opencv-python Pillow numpy

# 验证安装
python -c "from airtest.core.api import *; print('Airtest OK')"
python -c "from poco.drivers.android.uiautomation import AndroidUiautomationPoco; print('Poco OK')"
```

### 2.3 Airtest IDE 安装（可选但推荐）

Airtest IDE 是一个可视化编辑器，提供：
- 实时手机投屏
- 一键截图生成 Template
- Poco UI 树检查器
- 脚本录制与回放

```
下载地址: https://airtest.netease.com/
选择 Windows 版本下载，解压即可使用，无需安装
```

### 2.4 ADB 工具

```bash
# 方式 A: Airtest IDE 自带 ADB，启动 IDE 即可使用
# 方式 B: 单独安装 Android Platform Tools
#   下载: https://developer.android.com/studio/releases/platform-tools

# 验证
adb devices
```

---

## 3. 设备连接

### 3.1 基本连接

```python
from airtest.core.api import connect_device, device

# USB 连接 — 自动检测第一个设备
dev = connect_device("Android:///")

# USB 连接 — 指定设备序列号
dev = connect_device("Android:///SJE5T17B17")

# USB 连接 — 指定 ADB 服务器地址和设备
dev = connect_device("Android://127.0.0.1:5037/SJE5T17B17")

# 验证连接
info = dev.get_display_info()
print(f"分辨率: {info['width']}x{info['height']}")
```

### 3.2 WiFi 无线连接

```bash
# 先用 USB 连接，开启 TCP 模式
adb tcpip 5555

# 获取手机 IP
adb shell ip addr show wlan0
# 例如: 192.168.1.100

# 无线连接
adb connect 192.168.1.100:5555

# 拔掉 USB
```

```python
# WiFi 连接
dev = connect_device("Android://192.168.1.100:5555")
```

### 3.3 auto_setup 便捷连接

```python
from airtest.core.api import auto_setup

# 自动初始化，适合脚本模式
auto_setup(
    __file__,
    devices=["Android:///127.0.0.1:5037/SJE5T17B17"],
    logdir=True,           # 保存日志到 ./log 目录
    project_root=r"D:\xhs",  # 项目根目录
    compress=90             # 截图压缩质量 1-99
)
```

### 3.4 多设备切换

```python
from airtest.core.api import connect_device, set_current, device

dev1 = connect_device("Android:///device_1")
dev2 = connect_device("Android:///device_2")

# 切换到设备1
set_current(0)
set_current("device_1")  # 也可用序列号

# 获取当前设备
current = device()
current.touch((100, 100))
```

### 3.5 连接参数

URI 格式: `Platform://adbhost:adbport/serialno?param=value`

| 参数 | 可选值 | 说明 |
|------|--------|------|
| `cap_method` | `MINICAP`(默认), `JAVACAP`, `ADBCAP` | 截图方式 |
| `touch_method` | `MINITOUCH`(默认), `ADBTOUCH` | 触摸方式 |
| `ori_method` | `MINICAPORI`(默认), `ADBORI` | 方向检测 |

```python
# 使用 JAVACAP（兼容性更好但更慢）
dev = connect_device("Android:///SJE5T17B17?cap_method=JAVACAP")
```

---

## 4. Airtest 图像识别 API

所有 API 通过 `from airtest.core.api import *` 导入。

### 4.1 Template — 图像模板

```python
from airtest.core.api import Template

tpl = Template(
    r"button.png",          # 必须: 模板图片路径
    threshold=0.7,          # 匹配置信度阈值 (0~1)，默认 0.7
    target_pos=5,           # 点击位置 (九宫格 1-9)，默认 5 (中心)
    record_pos=(0.3, -0.2), # 录制时的归一化坐标提示（加速查找）
    resolution=(1080, 2400) # 录制时的设备分辨率
)

# target_pos 九宫格:
# 7  8  9   ← 顶部
# 4  5  6   ← 中间
# 1  2  3   ← 底部
```

### 4.2 touch — 点击

```python
from airtest.core.api import *

# 坐标点击 (绝对坐标)
touch((100, 200))

# 坐标点击 (归一化坐标 0~1)
touch((0.5, 0.5))  # 屏幕中心

# 图像识别点击 — 找到模板图片的位置并点击
touch(Template(r"search_btn.png"))

# 双击
touch((100, 200), times=2)

# 长按 (2秒)
touch((100, 200), duration=2)
```

### 4.3 swipe — 滑动

```python
# 两点滑动
swipe((100, 500), (100, 200))

# 归一化坐标
swipe((0.5, 0.8), (0.5, 0.2))

# 用向量滑动 (相对位移)
swipe((100, 500), vector=(0, -0.3))  # 向上滑屏幕30%

# 模板到坐标
swipe(Template(r"icon.png"), (500, 300))

# 带速度控制
swipe((100, 100), (200, 200), duration=1, steps=6)
```

### 4.4 snapshot — 截图

```python
# 简单截图 (保存到日志目录)
snapshot()

# 指定文件名和描述
result = snapshot(filename="screen.png", msg="首页截图")
# 返回: {"screen": "screen.png", "resolution": (1080, 2400)}

# 高质量截图
snapshot(filename="hd.png", quality=90, max_size=1280)
```

### 4.5 exists — 判断存在

```python
# 返回坐标或 False（不会抛异常，安全）
pos = exists(Template(r"like_btn.png"))
if pos:
    print(f"找到了，位置: {pos}")
    touch(pos)  # 复用坐标，不再搜索第二次
```

### 4.6 wait — 等待出现

```python
from airtest.core.api import wait, Template

# 等待图片出现（默认超时 20 秒）
pos = wait(Template(r"home_icon.png"))

# 自定义超时和检查间隔
pos = wait(Template(r"loading_done.png"), timeout=60, interval=2)

# 超时回调 — 每次未找到时执行
def on_not_found():
    print("还在等...")

wait(Template(r"element.png"), timeout=30, intervalfunc=on_not_found)

# 超时抛出 TargetNotFoundError 异常
```

### 4.7 keyevent — 按键

```python
keyevent("HOME")
keyevent("BACK")
keyevent("ENTER")
keyevent("SEARCH")
keyevent("3")               # HOME 键的 keycode
keyevent("KEYCODE_DEL")     # 删除键
```

### 4.8 App 控制

```python
from airtest.core.api import start_app, stop_app, clear_app

# 启动小红书
start_app("com.xingin.xhs")

# 启动指定 Activity
start_app("com.xingin.xhs/.index.v2.IndexActivityV2")

# 停止
stop_app("com.xingin.xhs")

# 清除数据
clear_app("com.xingin.xhs")
```

### 4.9 其他实用 API

```python
# 文字输入（需先聚焦到输入框）
text("搜索关键词")
text("美食", enter=True)      # 输入后按回车
text("美食", search=True)      # 输入后按搜索键

# 等待
sleep(2.0)

# 查找所有匹配
results = find_all(Template(r"star.png"))
# 返回: [{'result': (x,y), 'rectangle': ..., 'confidence': 0.99}, ...]

# 唤醒屏幕
wake()

# 回到桌面
home()

# 剪贴板
set_clipboard("内容")
text = get_clipboard()

# 执行 shell 命令
output = shell("ls /data/local/tmp")
```

### 4.10 全局设置

```python
from airtest.core.settings import Settings as ST

ST.THRESHOLD = 0.7                     # 默认匹配阈值
ST.CVSTRATEGY = ['mstpl', 'tpl', 'sift', 'brisk']  # CV 算法
ST.FIND_TIMEOUT = 20                   # wait() 默认超时(秒)
ST.FIND_TIMEOUT_TMP = 3                # 内部操作超时
ST.OPDELAY = 0.1                       # 操作后延迟(秒)
ST.SNAPSHOT_QUALITY = 10               # 截图质量(1-99)，默认10太低，建议改为90
ST.IMAGE_MAXSIZE = None                # 截图最大尺寸

# 重要: 截图质量默认只有 10，做 OCR 的话务必调高
ST.SNAPSHOT_QUALITY = 90
```

---

## 5. Poco UI 控件树 API

Poco 通过 Android UIAutomation 访问无障碍控件树，可以直接读取文字、定位元素。

### 5.1 初始化

```python
from airtest.core.api import connect_device
from poco.drivers.android.uiautomation import AndroidUiautomationPoco

# 必须先连接设备
connect_device("Android:///")

# 创建 Poco 实例
poco = AndroidUiautomationPoco()
```

### 5.2 选择器

```python
# 按节点名称
elem = poco('bg_mission')

# 按 type (类名)
elem = poco(type='android.widget.TextView')

# 按 text (文字精确匹配)
elem = poco(text='搜索')

# 按文字正则
elem = poco(textMatches='^关注.*$')

# 按 resourceId
elem = poco(resourceId='com.xingin.xhs:id/title')

# 按 description
elem = poco(description='关闭')

# 组合条件
elem = poco(text='关注', type='android.widget.Button')

# 按可见性
elem = poco(type='android.widget.TextView', visible=True)
```

### 5.3 元素操作

```python
elem = poco(text='搜索')

# 点击
elem.click()

# 点击指定位置 (归一化坐标)
elem.click([0.5, 0.5])  # 元素中心
elem.click([0.9, 0.1])  # 元素右上角

# 长按
elem.long_click(duration=2.0)

# 双击
elem.double_click()

# 获取文字
title = elem.get_text()

# 获取属性
text = elem.attr('text')
etype = elem.attr('type')
pos = elem.attr('pos')      # [x, y] 归一化坐标
size = elem.attr('size')     # [w, h] 归一化尺寸
visible = elem.attr('visible')

# 是否存在
if elem.exists():
    elem.click()

# 等待出现
elem.wait(timeout=5).click()

# 严格等待 (超时抛异常 PocoTargetTimeout)
elem.wait_for_appearance(timeout=120)

# 等待消失
elem.wait_for_disappearance(timeout=60)

# 获取边界
bounds = elem.get_bounds()   # [top, right, bottom, left]
sz = elem.get_size()         # [width, height] 归一化

# 设置文字
poco('search_box').set_text("美食")
```

### 5.4 层级遍历

```python
# 子元素
child = poco('main_node').child('list_item')

# 后代 (任意深度)
desc = poco('main_node').offspring('item_title')

# 兄弟
sibling = poco('btn_close').sibling('btn_ok')

# 父元素
parent = poco('btn_close').parent()

# 链式调用
poco('main').child('list').offspring('title_text')

# 索引访问 (按从左到右、从上到下排序)
items = poco('list').child('item')
print(items[0].child('name').get_text())
print(items[1].child('name').get_text())

# 遍历
count = len(items)
for item in items:
    print(item.child('name').get_text())
```

### 5.5 滑动操作

```python
# Poco 元素的 swipe
elem = poco(type='android.widget.ScrollView')
elem.swipe('up')         # 向上滑
elem.swipe('down')       # 向下滑
elem.swipe('left')       # 向左滑
elem.swipe('right')      # 向右滑

# 用向量
elem.swipe([0.2, -0.2])  # [水平, 垂直]，负值=上/左

# scroll 方法
elem.scroll(direction='vertical', percent=0.6, duration=2.0)
elem.scroll(direction='horizontal', percent=0.3)
```

### 5.6 全局操作

```python
# 全局坐标点击 (归一化)
poco.click([0.5, 0.5])            # 屏幕中心
poco.long_click([0.5, 0.5], duration=3)

# 全局滑动
poco.swipe([0.1, 0.1], direction=[0.4, 0.4])  # 从某点沿方向
poco.swipe([0.1, 0.1], [0.5, 0.5])             # 从A点到B点
```

### 5.7 UI 树遍历

```python
# 获取所有 TextView 中的文字
all_texts = poco(type='android.widget.TextView')
for tv in all_texts:
    text = tv.get_text()
    if text:
        print(text)

# 遍历子节点
root = poco('android.widget.FrameLayout')
for child in root.children():
    print(child.attr('type'), child.get_text())
```

---

## 6. 弹窗与等待处理

### 6.1 exists + touch 模式（推荐，安全无异常）

```python
from airtest.core.api import exists, touch, Template

# 安全检查: 找到就点击，找不到就跳过，不会抛异常
pos = exists(Template(r"btn_agree.png"))
if pos:
    touch(pos)

# 用 Poco 处理弹窗
if poco(text='同意').exists():
    poco(text='同意').click()

if poco(text='知道了').exists():
    poco(text='知道了').click()
```

### 6.2 循环等待

```python
import time

def wait_and_click(target, timeout=30, interval=1):
    """循环等待目标出现并点击，不抛异常。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        pos = exists(target)
        if pos:
            touch(pos)
            return True
        time.sleep(interval)
    print(f"等待超时: {timeout}s")
    return False

# 使用
wait_and_click(Template(r"home_tab.png"), timeout=20)
```

### 6.3 Poco 等待

```python
# 等待元素出现 (不抛异常)
elem = poco(text='加载完成')
if elem.wait(timeout=10):
    elem.click()

# 严格等待 (超时抛 PocoTargetTimeout)
elem.wait_for_appearance(timeout=30)
elem.click()

# 等待消失
poco(text='加载中').wait_for_disappearance(timeout=60)
```

### 6.4 综合弹窗处理器

```python
import time
from airtest.core.api import exists, touch, Template

def dismiss_popups():
    """一次性检查并关闭所有已知弹窗。"""
    popup_buttons = [
        Template(r"tpl/btn_agree.png"),
        Template(r"tpl/btn_know.png"),
        Template(r"tpl/btn_close.png"),
        Template(r"tpl/btn_update_later.png"),
    ]
    for btn in popup_buttons:
        pos = exists(btn)
        if pos:
            touch(pos)
            time.sleep(0.5)
            return True

    # Poco 方式检查
    poco_texts = ['同意', '知道了', '以后再说', '暂不更新', '取消']
    for t in poco_texts:
        elem = poco(text=t)
        if elem.exists():
            elem.click()
            time.sleep(0.5)
            return True

    return False

def wait_until_stable(max_wait=10):
    """循环处理弹窗直到稳定（一段时间内没有新弹窗）。"""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if dismiss_popups():
            continue  # 又发现弹窗，继续检查
        time.sleep(1)
    print("页面已稳定")
```

---

## 7. OCR 文字识别

### 7.1 PaddleOCR 集成（推荐）

Airtest **没有内置 OCR**，需要使用 PaddleOCR。

```bash
pip install paddleocr paddlepaddle
```

```python
from paddleocr import PaddleOCR
import numpy as np

ocr = PaddleOCR(use_angle_cls=True, lang='ch')

# 从截图文件识别
result = ocr.ocr("screenshot.png", cls=True)
for line in result:
    for box, (text, conf) in line:
        print(f"{text} ({conf:.2f})")

# 从 Airtest 截图识别
from airtest.core.api import snapshot
path = snapshot(filename="temp.png", quality=90)
result = ocr.ocr(path, cls=True)
```

### 7.2 截图 + OCR 一体化

```python
from airtest.core.api import snapshot, touch
from paddleocr import PaddleOCR
import numpy as np

ocr = PaddleOCR(use_angle_cls=True, lang='ch')

def find_text_on_screen(target_text):
    """截图 → OCR → 找到目标文字的位置。"""
    path = snapshot(filename="ocr_temp.png", quality=90)
    result = ocr.ocr(path, cls=True)

    for line in result:
        for box, (text, conf) in line:
            if target_text in text and conf > 0.8:
                # 计算文字中心坐标
                box_arr = np.array(box)
                cx = int((box_arr[0][0] + box_arr[2][0]) / 2)
                cy = int((box_arr[0][1] + box_arr[2][1]) / 2)
                return (cx, cy)
    return None

# 使用
pos = find_text_on_screen("关注")
if pos:
    touch(pos)
```

### 7.3 区域 OCR

```python
from PIL import Image

def ocr_region(region_box, screen_path="temp.png"):
    """只识别屏幕的指定区域。"""
    img = Image.open(screen_path)
    # region_box: (left, top, right, bottom)
    cropped = img.crop(region_box)

    result = ocr.ocr(np.array(cropped), cls=True)
    texts = []
    for line in result:
        for box, (text, conf) in line:
            texts.append({'text': text, 'confidence': conf, 'box': box})
    return texts

# 使用: 只识别屏幕上半部分
snapshot(filename="temp.png", quality=90)
texts = ocr_region((0, 0, 1080, 1200))
```

---

## 8. 长截图与滚动拼接

### 8.1 滚动截取

```python
import time
import hashlib
from airtest.core.api import swipe, snapshot, sleep
from pathlib import Path

def scroll_and_capture(save_dir, max_scrolls=20, scroll_start=0.7, scroll_end=0.3):
    """
    滚动并逐张截图。

    Args:
        save_dir: 截图保存目录
        max_scrolls: 最大滚动次数
        scroll_start: 滑动起始Y (归一化)
        scroll_end: 滑动结束Y (归一化)

    Returns:
        截图文件路径列表
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    screenshots = []
    prev_hash = None

    for i in range(max_scrolls):
        # 截图
        filepath = str(save_dir / f"scroll_{i:03d}.png")
        snapshot(filename=filepath, quality=90)

        # 检测是否到底（比较截图哈希）
        with open(filepath, 'rb') as f:
            curr_hash = hashlib.md5(f.read()).hexdigest()

        if prev_hash and curr_hash == prev_hash:
            # 删除重复的最后一张
            Path(filepath).unlink()
            print(f"  已到底部，共 {i} 张截图")
            break

        prev_hash = curr_hash
        screenshots.append(filepath)
        print(f"  截图 {i}: {filepath}")

        # 向上滚动
        swipe((0.5, scroll_start), (0.5, scroll_end), duration=0.4)
        sleep(0.8)

    return screenshots
```

### 8.2 图像拼接

```python
import cv2
import numpy as np

def stitch_screenshots(image_paths, output_path, overlap_ratio=0.15):
    """
    将多张截图拼接为长图。
    使用 SIFT 特征匹配找到精确重叠位置。
    """
    if len(image_paths) == 0:
        return
    if len(image_paths) == 1:
        import shutil
        shutil.copy(image_paths[0], output_path)
        return

    imgs = [cv2.imread(p) for p in image_paths]
    result = imgs[0]
    sift = cv2.SIFT_create()
    bf = cv2.BFMatcher()

    for i in range(1, len(imgs)):
        curr = imgs[i]
        overlap = int(min(result.shape[0], curr.shape[0]) * overlap_ratio)

        # 提取重叠区域特征
        gray_prev = cv2.cvtColor(result[-overlap:, :], cv2.COLOR_BGR2GRAY)
        gray_curr = cv2.cvtColor(curr[:overlap, :], cv2.COLOR_BGR2GRAY)

        kp1, des1 = sift.detectAndCompute(gray_prev, None)
        kp2, des2 = sift.detectAndCompute(gray_curr, None)

        actual_overlap = overlap  # 默认值

        if des1 is not None and des2 is not None and len(kp1) > 4 and len(kp2) > 4:
            matches = bf.knnMatch(des1, des2, k=2)
            good = [m for m, n in matches if m.distance < 0.75 * n.distance]

            if len(good) > 4:
                src_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                dy = np.mean(dst_pts[:, 0, 1] - src_pts[:, 0, 1])
                actual_overlap = int(overlap + dy)
                actual_overlap = max(0, min(actual_overlap, min(result.shape[0], curr.shape[0])))

        result = np.vstack([result, curr[actual_overlap:]])
        print(f"  拼接第 {i+1} 张，重叠区域: {actual_overlap}px")

    cv2.imwrite(str(output_path), result)
    print(f"  长图已保存: {output_path} (高度: {result.shape[0]}px)")
```

### 8.3 检测滚动终止

```python
def is_at_bottom(screenshot_dir, threshold=0.98):
    """对比最后两张截图的相似度，判断是否到底。"""
    files = sorted(Path(screenshot_dir).glob("scroll_*.png"))
    if len(files) < 2:
        return False

    img1 = cv2.imread(str(files[-2]), cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(str(files[-1]), cv2.IMREAD_GRAYSCALE)

    # 确保 same size
    h = min(img1.shape[0], img2.shape[0])
    img1 = img1[:h, :]
    img2 = img2[:h, :]

    similarity = np.sum(img1 == img2) / img1.size
    return similarity > threshold
```

---

## 9. Airtest IDE 使用指南

### 9.1 连接设备

1. 打开 Airtest IDE
2. 手机用 USB 连接 PC
3. 点击 IDE 右侧「设备窗口」中的「Connect」按钮
4. 选择设备序列号，连接成功后可看到手机实时画面

### 9.2 截取模板图片

1. 在设备画面上**右键框选**要识别的区域
2. 自动保存为 `.png` 文件到项目目录
3. 自动生成 `Template()` 代码

### 9.3 Poco UI 检查器

1. 点击 IDE 左侧「Poco Assistant」面板
2. 选择 `AndroidUiAutomation` 模式
3. 展开控件树，查看每个元素的:
   - `name` / `resourceId`
   - `text` (显示文字)
   - `type` (类名)
   - `pos` / `size` (位置和尺寸)
   - `visible` (是否可见)
4. 双击元素可自动生成 Poco 选择代码

### 9.4 脚本录制

1. 点击 IDE 顶部的「录制」按钮
2. 在设备画面上操作（点击、滑动）
3. IDE 自动生成对应 Python 代码
4. 生成的代码可以直接复制到你的脚本中使用

### 9.5 从 IDE 导出脚本

Airtest IDE 生成的脚本和纯 Python 脚本格式相同，可以直接在命令行运行:

```bash
python your_script.py
```

---

## 10. 小红书提取实战

### 10.1 项目结构

```
xhs/
├── main.py              # 主入口
├── config.py            # 配置
├── device.py            # 设备连接
├── xhs_app.py           # 小红书操作封装
├── ocr_engine.py        # OCR 封装
├── image_utils.py       # 图像拼接/裁剪
├── storage.py           # 文件存储
├── tpl/                 # Template 模板图片
│   ├── btn_close.png
│   ├── tab_home.png
│   ├── btn_like.png
│   └── ...
├── output/
│   └── {帖子标题}/
│       ├── images/      # 帖子图片截图
│       ├── content.png  # 正文长截图
│       └── comments/    # 评论截图
└── docs/
```

### 10.2 完整提取流程

```python
"""
小红书帖子提取 — Airtest + Poco 完整示例
"""
import time
from pathlib import Path
from airtest.core.api import (
    connect_device, start_app, stop_app,
    touch, swipe, snapshot, exists, wait, sleep,
    keyevent, Template
)
from airtest.core.error import TargetNotFoundError, DeviceConnectionError
from poco.drivers.android.uiautomation import AndroidUiautomationPoco
from poco.exceptions import PocoNoSuchNodeException, PocoTargetTimeout

XHS_PACKAGE = "com.xingin.xhs"


class XHSExtractorAirtest:
    def __init__(self, output_dir="output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 连接设备
        self.dev = connect_device("Android:///")

        # 初始化 Poco
        self.poco = AndroidUiautomationPoco()

    # ===== 基础操作 =====

    def launch_xhs(self):
        """启动小红书并处理弹窗。"""
        start_app(XHS_PACKAGE)
        sleep(5)
        self.dismiss_all_popups()

    def dismiss_all_popups(self):
        """处理所有弹窗，直到页面稳定。"""
        popup_texts = ['同意', '知道了', '以后再说', '暂不更新', '跳过']
        stable_count = 0
        while stable_count < 3:
            found = False
            for text in popup_texts:
                elem = self.poco(text=text)
                if elem.exists():
                    elem.click()
                    sleep(0.5)
                    found = True
                    stable_count = 0
                    break
            if not found:
                stable_count += 1
                sleep(1)

    # ===== 列表获取 =====

    def get_feed_titles(self, count=10):
        """从首页推荐流获取帖子标题。"""
        titles = []
        seen = set()

        for _ in range(30):  # 最多滚动30次
            if len(titles) >= count:
                break

            # 通过 Poco 获取所有可见文字
            elems = self.poco(type='android.widget.TextView')
            for elem in elems:
                try:
                    text = elem.get_text()
                    if (text
                        and len(text) > 5
                        and text not in seen
                        and text not in ['关注', '分享', '点赞', '评论', '收藏', '']):
                        seen.add(text)
                        titles.append(text)
                        print(f"  [{len(titles)}] {text[:40]}")
                except PocoNoSuchNodeException:
                    continue

            # 向上滚动
            swipe((0.5, 0.7), (0.5, 0.3), duration=0.4)
            sleep(1.5)

        return titles[:count]

    # ===== 帖子详情 =====

    def enter_post(self, title):
        """进入帖子详情页。"""
        # 方法1: Poco 文字匹配点击
        elem = self.poco(text=title)
        if elem.exists():
            elem.click()
            sleep(2)
            return True

        # 方法2: 包含匹配
        short = title[:15]
        elem = self.poco(textMatches=f'.*{short}.*')
        if elem.exists():
            elem.click()
            sleep(2)
            return True

        # 方法3: OCR 查找 + 点击（兜底）
        from paddleocr import PaddleOCR
        import numpy as np
        ocr = PaddleOCR(use_angle_cls=True, lang='ch')
        path = snapshot(filename="find_post.png", quality=90)
        result = ocr.ocr(path, cls=True)
        for line in result:
            for box, (text, conf) in line:
                if title[:10] in text and conf > 0.8:
                    box_arr = np.array(box)
                    cx = int((box_arr[0][0] + box_arr[2][0]) / 2)
                    cy = int((box_arr[0][1] + box_arr[2][1]) / 2)
                    touch((cx, cy))
                    sleep(2)
                    return True

        print(f"  未找到帖子: {title[:30]}")
        return False

    def capture_images(self, save_dir):
        """截取帖子中的所有图片（左右滑动）。"""
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        img_idx = 0
        # 截取第一张
        filepath = str(save_dir / f"img_{img_idx:02d}.png")
        snapshot(filename=filepath, quality=95)
        print(f"    图片 {img_idx}: 已保存")
        img_idx += 1

        # 检查是否有图片指示器 (如 "2/5")
        total_images = None

        for _ in range(20):
            # 尝试读取指示器
            indicator_elem = self.poco(textMatches=r'^\d+/\d+$')
            if indicator_elem.exists():
                indicator_text = indicator_elem.get_text()
                current, total = indicator_text.split('/')
                total_images = int(total)
                if int(current) >= total:
                    break

            # 向左滑动查看下一张
            prev_path = str(save_dir / f"img_{img_idx-1:02d}.png")
            swipe((0.8, 0.5), (0.2, 0.5), duration=0.3)
            sleep(0.8)

            # 截图
            filepath = str(save_dir / f"img_{img_idx:02d}.png")
            snapshot(filename=filepath, quality=95)

            # 检测是否和上一张相同（已到最后）
            import hashlib
            with open(prev_path, 'rb') as f:
                h1 = hashlib.md5(f.read()).hexdigest()
            with open(filepath, 'rb') as f:
                h2 = hashlib.md5(f.read()).hexdigest()
            if h1 == h2:
                Path(filepath).unlink()  # 删除重复截图
                break

            print(f"    图片 {img_idx}: 已保存")
            img_idx += 1

        return img_idx

    def capture_content(self, save_dir):
        """截取帖子正文区域（向下滚动拼接长截图）。"""
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        screenshots = []
        prev_hash = None

        for i in range(15):
            filepath = str(save_dir / f"content_{i:02d}.png")
            snapshot(filename=filepath, quality=90)

            import hashlib
            with open(filepath, 'rb') as f:
                curr_hash = hashlib.md5(f.read()).hexdigest()

            if prev_hash == curr_hash:
                Path(filepath).unlink()
                break
            prev_hash = curr_hash
            screenshots.append(filepath)
            print(f"    正文截图 {i}")

            swipe((0.5, 0.7), (0.5, 0.3), duration=0.4)
            sleep(0.8)

        return screenshots

    def extract_text_info(self):
        """通过 Poco 控件树读取帖子文字信息。"""
        info = {
            'author': '',
            'title': '',
            'content': '',
            'post_time': '',
            'likes': '',
        }

        # 收集所有文字
        all_texts = []
        elems = self.poco(type='android.widget.TextView')
        for elem in elems:
            try:
                text = elem.get_text()
                if text and text.strip():
                    all_texts.append(text.strip())
            except PocoNoSuchNodeException:
                continue

        # 智能分类（需根据实际 UI 调整）
        for text in all_texts:
            if '编辑于' in text or '发布于' in text or '天前' in text:
                info['post_time'] = text
            elif len(text) > 20 and not info['content']:
                info['content'] = text

        # 第一个非特殊文字通常是作者
        special = {'关注', '分享', '点赞', '评论', '收藏', '', '搜索'}
        for text in all_texts:
            if text not in special and len(text) < 20 and not info['author']:
                info['author'] = text
                break

        return info

    def capture_comments(self, save_dir, max_scrolls=15):
        """截取评论区。"""
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        # 点击评论区域
        comment_tab = self.poco(text='评论')
        if comment_tab.exists():
            comment_tab.click()
            sleep(1)

        screenshots = []
        prev_hash = None

        for i in range(max_scrolls):
            filepath = str(save_dir / f"comment_{i:02d}.png")
            snapshot(filename=filepath, quality=90)

            import hashlib
            with open(filepath, 'rb') as f:
                curr_hash = hashlib.md5(f.read()).hexdigest()

            if prev_hash == curr_hash:
                Path(filepath).unlink()
                break
            prev_hash = curr_hash
            screenshots.append(filepath)
            print(f"    评论截图 {i}")

            swipe((0.5, 0.7), (0.5, 0.3), duration=0.4)
            sleep(0.8)

        return screenshots

    # ===== 主流程 =====

    def extract_single_post(self, title):
        """提取单个帖子的完整内容。"""
        if not self.enter_post(title):
            return None

        sleep(2)

        # 创建帖子目录
        safe_title = "".join(
            c for c in title[:30]
            if c.isalnum() or c in ' _-\u4e00-\u9fff'
        )
        post_dir = self.output_dir / safe_title
        post_dir.mkdir(parents=True, exist_ok=True)

        # 1. 截取图片
        print("  截取图片...")
        img_count = self.capture_images(post_dir / "images")

        # 2. 读取文字
        print("  读取文字信息...")
        post_info = self.extract_text_info()

        # 3. 截取正文
        print("  截取正文...")
        content_shots = self.capture_content(post_dir)

        # 4. 截取评论
        print("  截取评论...")
        comment_shots = self.capture_comments(post_dir / "comments")

        # 保存信息
        import json
        with open(post_dir / "info.json", 'w', encoding='utf-8') as f:
            json.dump(post_info, f, ensure_ascii=False, indent=2)

        # 返回列表
        keyevent("BACK")
        sleep(1)

        return {
            'title': title,
            'dir': str(post_dir),
            'images': img_count,
            'content_screenshots': len(content_shots),
            'comment_screenshots': len(comment_shots),
            'info': post_info,
        }

    def run(self, target_titles=None, max_posts=5):
        """主运行入口。"""
        print("=== 小红书帖子提取工具 (Airtest 版) ===")

        # 启动小红书
        print("启动小红书...")
        self.launch_xhs()

        # 获取帖子列表
        if target_titles:
            titles = target_titles
        else:
            print(f"从首页获取 {max_posts} 个帖子...")
            titles = self.get_feed_titles(count=max_posts)

        print(f"\n共 {len(titles)} 个帖子待提取")

        # 逐个提取
        results = []
        for i, title in enumerate(titles):
            print(f"\n--- [{i+1}/{len(titles)}] {title[:30]} ---")
            result = self.extract_single_post(title)
            if result:
                results.append(result)
                print(f"  完成: {result['images']}张图片, "
                      f"{result['content_screenshots']}张正文, "
                      f"{result['comment_screenshots']}张评论")
            sleep(2)

        print(f"\n=== 提取完成: {len(results)} 个帖子 ===")
        print(f"输出: {self.output_dir.absolute()}")
        return results


# ===== 运行 =====
if __name__ == "__main__":
    extractor = XHSExtractorAirtest(output_dir="output")

    # 自动从首页提取
    extractor.run(max_posts=5)

    # 或指定帖子
    # extractor.run(target_titles=["某某的美食攻略", "另一个帖子"])
```

---

## 11. 反检测策略

```python
import random
import time
from airtest.core.api import swipe, sleep, touch

def human_delay(min_s=0.5, max_s=2.0):
    """随机延迟，模拟人类操作间隔。"""
    time.sleep(random.uniform(min_s, max_s))

def human_swipe(direction="up"):
    """模拟人类滑动，带随机偏移和速度。"""
    cx = 0.5 + random.uniform(-0.03, 0.03)  # 水平微偏移

    if direction == "up":
        start_y = random.uniform(0.65, 0.75)
        end_y = random.uniform(0.25, 0.35)
    else:
        start_y = random.uniform(0.25, 0.35)
        end_y = random.uniform(0.65, 0.75)

    duration = random.uniform(0.3, 0.7)
    swipe((cx, start_y), (cx + random.uniform(-0.02, 0.02), end_y), duration=duration)

def random_reading_pause():
    """随机停顿，模拟阅读行为。"""
    if random.random() < 0.2:  # 20% 概率
        time.sleep(random.uniform(3, 8))

# 建议限制
MAX_POSTS_PER_SESSION = 20    # 单次最多处理帖子数
SCROLL_INTERVAL = (1.0, 3.0)  # 滑动间隔
POST_INTERVAL = (3.0, 6.0)    # 帖子间间隔
REHOME_INTERVAL = 5           # 每隔几个帖子回首页重新进入
```

---

## 12. 常见问题排查

### 12.1 连接问题

| 问题 | 解决方案 |
|------|---------|
| `DeviceConnectionError` | 确认 `adb devices` 能看到设备；重启 IDE |
| minicap 安装失败 | 改用 `cap_method=JAVACAP`：`connect_device("Android:///?cap_method=JAVACAP")` |
| 连接后黑屏 | 尝试 `cap_method=JAVACAP`；或重启 adb 服务 |
| WiFi 连接不稳定 | 确保同一网络；信号强度足够 |

### 12.2 图像识别问题

| 问题 | 解决方案 |
|------|---------|
| Template 找不到 | 降低 `threshold` (如 0.5)；截图质量调高 `ST.SNAPSHOT_QUALITY = 90` |
| 匹配位置偏移 | 检查 `resolution` 是否和当前设备一致 |
| 匹配太慢 | 减少 `CVSTRATEGY`：`ST.CVSTRATEGY = ['tpl']` |
| 误匹配 | 提高 `threshold` (如 0.85)；使用更独特的模板区域 |

### 12.3 Poco 问题

| 问题 | 解决方案 |
|------|---------|
| `PocoNoSuchNodeException` | 元素已消失，用 `try/except` 包裹 |
| UI 树获取为空 | 检查手机无障碍服务是否正常；重启 App |
| 元素 visible=False | 元素在屏幕外，需要先滚动到可见位置 |
| Poco 操作很慢 | 减少遍历范围；用更精确的选择器 |

### 12.4 调试技巧

```python
# 1. 保存截图分析
snapshot(filename="debug.png", quality=90)

# 2. 打印所有 Poco 可见文字
poco = AndroidUiautomationPoco()
elems = poco(type='android.widget.TextView')
for elem in elems:
    try:
        text = elem.get_text()
        if text:
            pos = elem.attr('pos')
            print(f"  {text:40s} pos={pos}")
    except:
        pass

# 3. 用 Airtest IDE 的 Poco Inspector 可视化查看 UI 树

# 4. 检查 Template 匹配结果
pos = exists(Template(r"debug_target.png"))
print(f"匹配结果: {pos}")

# 5. 调整全局设置
from airtest.core.settings import Settings as ST
ST.SNAPSHOT_QUALITY = 90   # 提高截图质量
ST.THRESHOLD = 0.6         # 降低匹配阈值
ST.OPDELAY = 0.5           # 增加操作间隔
```

---

## 13. 与方案一的对比

| 维度 | 方案一 (uiautomator2) | 方案四 (Airtest + Poco) |
|------|:---:|:---:|
| **安装复杂度** | `pip install uiautomator2` | `pip install airtest pocoui` |
| **设备连接** | `u2.connect()` 一行搞定 | 需 `connect_device()` + `AndroidUiautomationPoco()` |
| **截图** | `d.screenshot()` 返回 PIL.Image | `snapshot(filename=)` 保存到文件 |
| **UI 树** | `d.dump_hierarchy()` 返回 XML 字符串 | Poco 选择器直接操作，无需手动解析 XML |
| **文字获取** | 需解析 XML 或 OCR | `poco(text=).get_text()` 直接获取 |
| **图像识别** | `d.image.match()` (需额外依赖) | 内置 `Template` + `touch/exists/wait` |
| **弹窗处理** | `watch_context()` 后台自动处理 | 需手动写循环或用 `exists()` 检查 |
| **IDE 支持** | uiautodev (轻量 Web UI) | Airtest IDE (功能丰富的桌面 IDE) |
| **滚动** | `d(scrollable=True).scroll` | `poco(elem).scroll()` 或 Airtest `swipe()` |
| **学习曲线** | 较低，API 直观 | 中等，需理解 Airtest + Poco 两套 API |
| **社区活跃度** | 高 (GitHub 5k+ stars) | 高 (网易维护，大量中文文档) |
| **坐标系统** | 绝对像素 + 百分比 | Airtest 用绝对/归一化；Poco 用归一化 |

### 选哪个？

- **选方案一**：如果你偏好简洁 API、不需要可视化 IDE、希望用 XML 解析灵活处理 UI 树
- **选方案四**：如果你需要图像识别能力、喜欢用 IDE 可视化调试、希望 Poco 选择器直接操作元素
- **两者都能完成任务**，核心区别在于开发体验和工作流偏好

---

## 快速参考卡

```python
from airtest.core.api import *
from poco.drivers.android.uiautomation import AndroidUiautomationPoco

connect_device("Android:///")                    # 连接设备
poco = AndroidUiautomationPoco()                 # 初始化 Poco

start_app("com.xingin.xhs")                      # 启动小红书
snapshot(filename="screen.png", quality=90)       # 截图
touch((540, 1200))                                # 坐标点击
swipe((0.5, 0.7), (0.5, 0.3))                    # 滑动
keyevent("BACK")                                  # 返回
poco(text="搜索").click()                         # Poco 文字点击
title = poco(text="标题").get_text()               # 获取文字
pos = exists(Template(r"btn.png"))                # 图像识别
wait(Template(r"icon.png"), timeout=10)           # 等待出现
```
