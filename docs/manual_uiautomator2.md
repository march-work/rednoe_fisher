# 方案一：uiautomator2 + ADB 开发手册

> 小红书帖子截图提取工具 — 基于 uiautomator2 直连控制 Android 设备

---

## 目录

1. [方案概述](#1-方案概述)
2. [环境搭建](#2-环境搭建)
3. [设备连接](#3-设备连接)
4. [核心 API 速查](#4-核心-api-速查)
5. [UI 元素定位](#5-ui-元素定位)
6. [弹窗与等待处理](#6-弹窗与等待处理)
7. [图像识别与模板匹配](#7-图像识别与模板匹配)
8. [OCR 文字识别](#8-ocr-文字识别)
9. [长截图与滚动拼接](#9-长截图与滚动拼接)
10. [小红书提取实战](#10-小红书提取实战)
11. [反检测策略](#11-反检测策略)
12. [常见问题排查](#12-常见问题排查)

---

## 1. 方案概述

### 架构

```
┌─────────────────────────────────────────┐
│           Python 控制脚本                │
│                                         │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │uiautomator2│ │PaddleOCR │ │ OpenCV  │ │
│  │  设备控制  │ │  文字识别  │ │图像处理  │ │
│  └─────┬─────┘ └──────────┘ └─────────┘ │
│        │                                │
│   ADB 协议 (USB / WiFi)                 │
└────────┼────────────────────────────────┘
         │
    ┌────┴────┐
    │ Android │
    │  小米手机 │
    │(小红书App)│
    └─────────┘
```

### 工作流程

1. 通过 ADB 连接手机（USB 或无线）
2. 用 `uiautomator2` 控制小红书 App（启动、点击、滑动）
3. 通过 `dump_hierarchy()` 获取 UI 控件树读取文字信息
4. 通过 `screenshot()` 截取帖子图片、正文、评论
5. 用 PaddleOCR 识别截图中的文字（补充控件树无法获取的内容）
6. 按帖子标题建立文件夹，分类保存截图

### 优势

- **不依赖投屏软件**：直接通过 ADB 协议控制手机，无需小米跨屏协作
- **像素级精确**：截图基于手机真实分辨率，不受 PC DPI 和窗口位置影响
- **双通道信息获取**：UI 控件树（结构化文字）+ 截图（视觉内容）
- **稳定可靠**：坐标基于手机分辨率，不受 PC 窗口变化干扰

---

## 2. 环境搭建

### 2.1 手机端配置（小米手机）

```
设置 → 我的设备 → MIUI版本 → 连续点击7次 → 开启开发者模式
设置 → 更多设置 → 开发者选项 → 开启以下选项：
  ✓ USB 调试
  ✓ USB 安装（允许通过 USB 安装应用）
  ✓ USB 调试（安全设置）— 允许模拟点击
  ✓ 禁止权限监控 — 避免弹窗干扰
```

### 2.2 PC 端安装

```bash
# 1. 安装 Python 依赖
pip install uiautomator2
pip install opencv-python Pillow
pip install paddleocr paddlepaddle
pip install lxml

# 2. 安装 ADB 工具
#    方式 A: 安装 Android SDK Platform Tools
#      下载: https://developer.android.com/studio/releases/platform-tools
#      解压后加入 PATH
#    方式 B: 通过 uiautomator2 自动获取 (首次连接时自动处理)

# 3. 安装 UI 检查工具 (替代已废弃的 weditor)
pip install uiautodev
# 启动: uiautodev  →  浏览器访问 http://localhost:8000

# 4. 验证 ADB 连接
adb devices
# 应显示类似:
# List of devices attached
# abc12345    device
```

### 2.3 首次连接初始化

```bash
# 用数据线连接手机后执行:
adb devices                    # 确认设备已连接

# uiautomator2 v3 不再需要 python -m uiautomator2 init
# 首次调用 connect() 时自动完成设备端组件安装
```

---

## 3. 设备连接

### 3.1 USB 连接

```python
import uiautomator2 as u2

# 自动检测第一个 USB 设备
d = u2.connect()

# 指定设备序列号
d = u2.connect('abc12345')

# 查看所有已连接设备
import adbutils
for dev in adbutils.adb.device_list():
    print(dev.serial)
```

### 3.2 WiFi 无线连接

```bash
# 步骤 1: 手机先用 USB 连接 PC
# 步骤 2: 开启 TCP 模式
adb tcpip 5555

# 步骤 3: 获取手机 IP
adb shell ip addr show wlan0
# 找到 inet 开头的行，如 192.168.1.100

# 步骤 4: 无线连接
adb connect 192.168.1.100:5555

# 步骤 5: 拔掉 USB 线
```

```python
# 无线连接
d = u2.connect('192.168.1.100:5555')
```

### 3.3 验证连接

```python
d = u2.connect()
info = d.info
print(info)
# {
#   'currentPackageName': 'com.xingin.xhs',
#   'displayWidth': 1080,
#   'displayHeight': 2400,
#   'productName': 'cepheus',
#   'screenOn': True,
#   'sdkInt': 33
# }

w, h = d.window_size()
print(f"分辨率: {w}x{h}")
```

---

## 4. 核心 API 速查

### 4.1 截图

```python
# 方式 1: 返回 PIL.Image 对象（推荐）
img = d.screenshot()

# 方式 2: 直接保存到文件
d.screenshot("screen.png")

# 方式 3: 获取原始字节
img_bytes = d.screenshot(format="raw")
```

### 4.2 点击

```python
# 绝对坐标点击
d.click(540, 1200)

# 百分比坐标点击 (0~1 范围，自动转换为绝对坐标)
d.click(0.5, 0.6)

# 长按
d.long_click(540, 1200)
d.long_click(540, 1200, duration=2.0)  # 长按2秒
```

### 4.3 滑动

```python
# 从 (540,1800) 滑到 (540,400) — 向上滚动
d.swipe(540, 1800, 540, 400)

# 带速度控制
d.swipe(540, 1800, 540, 400, duration=0.5)  # 0.5秒完成
d.swipe(540, 1800, 540, 400, steps=20)       # 分20步完成

# 百分比坐标
d.swipe(0.5, 0.8, 0.5, 0.2)

# 方向滑动 (简化版)
d.swipe_ext("up", scale=0.7)     # 向上滑，距离为屏幕70%
d.swipe_ext("down", scale=0.5)
d.swipe_ext("left", scale=0.9)   # 向左滑，距离90%
d.swipe_ext("right", scale=0.9)  # 向右滑（浏览帖子图片用）
```

### 4.4 按键

```python
d.press("home")
d.press("back")
d.press("enter")
d.press("search")
d.press("delete")
```

### 4.5 App 控制

```python
# 启动小红书
d.app_start("com.xingin.xhs")
d.app_start("com.xingin.xhs", wait=True)    # 等待启动完成
d.app_start("com.xingin.xhs", stop=True)    # 先强制停止再启动

# 停止
d.app_stop("com.xingin.xhs")

# 查看当前运行的 App
current = d.app_current()
print(current)
# {'package': 'com.xingin.xhs', 'activity': '.index.v2.IndexActivityV2'}
```

### 4.6 屏幕

```python
# 获取分辨率
w, h = d.window_size()  # (1080, 2400)

# 屏幕方向
d.orientation  # 0=竖屏, 1=横屏左, 2=反向竖屏, 3=横屏右

# 亮屏/息屏
d.screen_on()
d.screen_off()
```

---

## 5. UI 元素定位

### 5.1 选择器（Selector）

```python
# 按文字精确匹配
elem = d(text="关注")

# 按文字包含
elem = d(textContains="搜索")

# 按文字正则
elem = d(textMatches="^关注.*")

# 按 resourceId
elem = d(resourceId="com.xingin.xhs:id/title")
elem = d(resourceIdMatches=".*id/title")

# 按类名
elem = d(className="android.widget.TextView")
elem = d(classNameMatches=".*TextView$")

# 组合条件 (AND 逻辑)
elem = d(text="关注", className="android.widget.Button")

# 可滚动容器
scroller = d(scrollable=True)

# 多个匹配中的第几个 (从0开始)
d(text="关注", instance=0).click()  # 第1个
d(text="关注", instance=2).click()  # 第3个
```

### 5.2 元素操作

```python
elem = d(text="搜索")

# 点击
elem.click()
elem.click(timeout=10)  # 最多等待10秒出现再点击

# 获取文字
title = elem.get_text()

# 设置文字（输入框）
d(resourceId="com.xingin.xhs:id/search_input").set_text("美食")

# 是否存在
if elem.exists:
    print("找到了")

# 匹配数量
count = elem.count

# 等待出现 / 消失
appeared = elem.wait(timeout=10)
gone = elem.wait_gone(timeout=10)

# 获取元素信息
info = elem.info        # dict: text, bounds, className, ...
bounds = elem.bounds()  # (left, top, right, bottom)
center = elem.center()  # (x, y)

# 截取元素区域
elem_img = elem.screenshot()  # 返回 PIL.Image，只包含该元素区域
```

### 5.3 层级遍历

```python
# 子元素
parent = d(resourceId="com.xingin.xhs:id/recycler_view")
child = parent.child(text="笔记标题")

# 兄弟元素
sibling = child.sibling(text="作者名")

# 方向查找
d(text="价格").right(text="¥99")    # 右边
d(text="标签").left(text="类型")     # 左边
d(text="标题").up(text="作者")       # 上方
d(text="标题").down(text="内容")     # 下方
```

### 5.4 XPath 定位

```python
# 用 XPath 查找（更灵活）
elem = d.xpath('//android.widget.TextView[@text="搜索"]')
elem.click()
text = elem.get_text()

# 获取所有匹配
for e in d.xpath('//android.widget.TextView').all():
    print(e.text)
```

### 5.5 dump_hierarchy — 获取完整 UI 树

```python
# 获取 UI 树 XML
xml = d.dump_hierarchy()

# 解析提取信息
from lxml import etree
root = etree.fromstring(xml.encode('utf-8'))

# 查找所有包含文字的节点
for node in root.xpath('//node[@text]'):
    text = node.attrib.get('text', '')
    bounds = node.attrib.get('bounds', '')
    rid = node.attrib.get('resource-id', '')
    if text.strip():
        print(f"文字: {text}")
        print(f"  bounds: {bounds}")
        print(f"  resourceId: {rid}")
```

### 5.6 使用 uiautodev 检查元素

```bash
# 启动 UI 检查工具
uiautodev

# 浏览器访问 http://localhost:8000
# 可以看到实时手机屏幕 + UI 控件树
# 点击任意元素可查看其 resourceId、text、bounds 等属性
```

---

## 6. 弹窗与等待处理

### 6.1 全局等待设置

```python
# 设置所有元素操作的默认超时时间
d.implicitly_wait(10.0)  # 10秒

# 元素级等待
elem = d(text="加载完成")
if elem.wait(timeout=30):   # 最多等30秒
    elem.click()
```

### 6.2 WatchContext — 自动处理弹窗（推荐）

```python
# 在代码块执行期间，自动监控并处理弹窗
with d.watch_context() as ctx:
    # 注册弹窗规则
    ctx.when("同意并继续").click()
    ctx.when("我知道了").click()
    ctx.when("^(立即更新|立即下载)$").call(lambda d: d.press("back"))

    # 等待稳定（5秒内无新弹窗出现）
    ctx.wait_stable()

    # 在此执行你的操作，弹窗会被自动处理
    d(text="搜索").click()
    # ...

# 使用内置处理器（处理常见系统弹窗）
with d.watch_context(builtin=True) as ctx:
    ctx.when("自定义弹窗文本").click()
    ctx.wait_stable()
    # 你的操作...
```

### 6.3 Watcher — 后台守护

```python
# 注册后台弹窗处理器
d.watcher.when("同意").click()
d.watcher.when("取消").click()
d.watcher.start(interval=2.0)  # 每2秒检查一次

# ... 执行你的操作 ...

# 停止监控
d.watcher.stop()
```

---

## 7. 图像识别与模板匹配

```python
# 查找模板图像在屏幕上的位置
result = d.image.match("like_button.png")
# 返回: {"similarity": 0.95, "point": [540, 1200]} 或 None

# 等待图像出现
result = d.image.wait("like_button.png", timeout=30.0, threshold=0.9)

# 查找并点击（一步到位）
d.image.click("like_button.png", timeout=5.0, threshold=0.85)

# 使用 PIL.Image 作为模板
from PIL import Image
template = Image.open("assets/heart_icon.png")
result = d.image.match(template)
```

依赖安装:
```bash
pip install opencv-python Pillow findit
```

---

## 8. OCR 文字识别

### 8.1 安装 PaddleOCR

```bash
pip install paddleocr paddlepaddle
```

### 8.2 基础用法

```python
from paddleocr import PaddleOCR

# 初始化（首次运行会自动下载模型）
ocr = PaddleOCR(use_angle_cls=True, lang='ch')

# 识别图片中的文字
result = ocr.ocr("screenshot.png", cls=True)

# 解析结果
for line in result:
    for box, (text, confidence) in line:
        print(f"文字: {text}")
        print(f"置信度: {confidence:.2f}")
        print(f"位置: {box}")  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
```

### 8.3 从截图直接 OCR

```python
import uiautomator2 as u2
from paddleocr import PaddleOCR
import numpy as np

d = u2.connect()
ocr = PaddleOCR(use_angle_cls=True, lang='ch')

# 截图 → OCR
img = d.screenshot()                    # PIL.Image
img_array = np.array(img)               # 转为 numpy 数组
result = ocr.ocr(img_array, cls=True)   # 直接传入数组

for line in result:
    for box, (text, conf) in line:
        print(f"{text} ({conf:.2f})")
```

### 8.4 区域 OCR（只识别屏幕一部分）

```python
from PIL import Image

# 方法: 先截取区域，再 OCR
img = d.screenshot()

# crop 参数: (left, top, right, bottom)
region = img.crop((100, 500, 900, 1200))

result = ocr.ocr(np.array(region), cls=True)
for line in result:
    for box, (text, conf) in line:
        print(text)
```

---

## 9. 长截图与滚动拼接

### 9.1 滚动截图拼接原理

```
截图1          截图2          截图3
┌───────┐    ┌───────┐    ┌───────┐
│ 区域A │    │       │    │       │
│───────│    │ 区域B │    │       │
│ 重叠区│ ←→ │ 重叠区│    │ 区域C │
│       │    │───────│    │───────│
└───────┘    │       │    │       │
             └───────┘    └───────┘

通过特征点匹配找到重叠区域，裁剪后拼接
```

### 9.2 滚动截取实现

```python
import uiautomator2 as u2
import cv2
import numpy as np
from pathlib import Path

d = u2.connect()

def scroll_and_capture(d, save_dir, scroll_px=1500, max_scrolls=20):
    """
    滚动截取长内容，保存每张截图。

    Args:
        d: uiautomator2 设备对象
        save_dir: 保存目录
        scroll_px: 每次滚动像素数
        max_scrolls: 最大滚动次数

    Returns:
        截图文件路径列表
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    screenshots = []
    prev_hash = None

    for i in range(max_scrolls):
        # 截图
        img = d.screenshot()
        img_array = np.array(img)

        # 检测是否滚到底了（和上一张对比）
        curr_hash = hash(img_array.tobytes())
        if prev_hash is not None and curr_hash == prev_hash:
            print(f"已到底部，共截取 {i} 张")
            break
        prev_hash = curr_hash

        # 保存
        filepath = save_dir / f"scroll_{i:03d}.png"
        img.save(str(filepath))
        screenshots.append(str(filepath))
        print(f"截图 {i}: {filepath}")

        # 向上滚动
        w, h = d.window_size()
        d.swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.3), duration=0.3)
        import time; time.sleep(0.8)

    return screenshots


def stitch_images(image_paths, output_path, overlap_ratio=0.15):
    """
    将多张截图拼接为长图。

    Args:
        image_paths: 截图路径列表
        output_path: 输出路径
        overlap_ratio: 预估重叠比例
    """
    if not image_paths:
        return

    imgs = [cv2.imread(p) for p in image_paths]
    result = imgs[0]

    for i in range(1, len(imgs)):
        curr = imgs[i]
        h_prev = result.shape[0]
        h_curr = curr.shape[0]
        overlap = int(min(h_prev, h_curr) * overlap_ratio)

        # 取重叠区域进行特征匹配
        prev_region = result[-overlap:, :]
        curr_region = curr[:overlap, :]

        # 使用 SIFT 找最佳匹配位置
        sift = cv2.SIFT_create()
        kp1, des1 = sift.detectAndCompute(cv2.cvtColor(prev_region, cv2.COLOR_BGR2GRAY), None)
        kp2, des2 = sift.detectAndCompute(cv2.cvtColor(curr_region, cv2.COLOR_BGR2GRAY), None)

        if des1 is not None and des2 is not None and len(kp1) > 0 and len(kp2) > 0:
            bf = cv2.BFMatcher()
            matches = bf.knnMatch(des1, des2, k=2)

            good = []
            for m, n in matches:
                if m.distance < 0.75 * n.distance:
                    good.append(m)

            if len(good) > 4:
                src_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)

                # 计算垂直偏移
                dy = np.mean(dst_pts[:, 0, 1] - src_pts[:, 0, 1])
                actual_overlap = int(overlap + dy)
                actual_overlap = max(0, min(actual_overlap, min(h_prev, h_curr)))
            else:
                actual_overlap = overlap
        else:
            actual_overlap = overlap

        # 拼接
        result = np.vstack([result, curr[actual_overlap:]])

    cv2.imwrite(str(output_path), result)
    print(f"长图已保存: {output_path} (高度: {result.shape[0]}px)")
```

### 9.3 检测滚动终止

```python
def is_scroll_stuck(d, max_attempts=3):
    """连续截图对比，检测是否已到页面底部。"""
    import hashlib

    hashes = []
    for _ in range(max_attempts):
        img = d.screenshot()
        h = hashlib.md5(img.tobytes()).hexdigest()
        hashes.append(h)

        w, ht = d.window_size()
        d.swipe(w // 2, int(ht * 0.7), w // 2, int(ht * 0.3), duration=0.3)
        import time; time.sleep(0.5)

    # 如果连续几张截图的哈希都一样，说明没滚动
    return len(set(hashes)) == 1
```

---

## 10. 小红书提取实战

### 10.1 项目结构

```
xhs/
├── main.py              # 主入口
├── config.py            # 配置文件
├── device.py            # 设备连接与控制
├── xhs_app.py           # 小红书操作封装
├── ocr_engine.py        # OCR 封装
├── image_utils.py       # 图像处理（拼接、裁剪）
├── storage.py           # 文件存储管理
├── output/              # 输出目录
│   └── {帖子标题}/
│       ├── images/      # 帖子图片
│       ├── content.png  # 正文长截图
│       └── comments/    # 评论截图
└── docs/
```

### 10.2 完整提取流程

```python
"""
小红书帖子提取 — 完整示例
演示从首页列表到帖子详情再到评论的全流程截图提取
"""
import uiautomator2 as u2
import time
from pathlib import Path
from PIL import Image

XHS_PACKAGE = "com.xingin.xhs"


class XHSExtractor:
    def __init__(self, output_dir="output"):
        self.d = u2.connect()
        self.d.implicitly_wait(10)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 反检测: 操作间随机延迟
        self.d.settings['operation_delay'] = (0.3, 0.8)
        self.d.settings['operation_delay_methods'] = ['click', 'swipe']

    def launch_xhs(self):
        """启动小红书并处理弹窗。"""
        self.d.app_start(XHS_PACKAGE, stop=True, wait=True)
        time.sleep(3)

        # 自动处理弹窗
        with self.d.watch_context(builtin=True) as ctx:
            ctx.when("同意").click()
            ctx.when("知道了").click()
            ctx.when("升级").call(lambda d: d.press("back"))
            ctx.wait_stable()

    def get_feed_titles(self, count=10):
        """
        从首页推荐流中获取帖子标题。
        通过滚动页面收集可见帖子的标题文字。
        """
        titles = []
        seen = set()

        for scroll_idx in range(20):  # 最多滚20次
            if len(titles) >= count:
                break

            # 从 UI 控件树获取文字
            xml = self.d.dump_hierarchy()
            from lxml import etree
            root = etree.fromstring(xml.encode('utf-8'))

            # 小红书帖子卡片中的标题通常在 TextView 中
            for node in root.xpath('//node[@text]'):
                text = node.attrib.get('text', '').strip()
                bounds = node.attrib.get('bounds', '')

                # 过滤：标题通常有一定长度，且不是按钮文字
                if (text
                    and len(text) > 5
                    and text not in seen
                    and text not in ['关注', '分享', '点赞', '评论', '收藏']
                    and '广告' not in text):
                    seen.add(text)
                    titles.append({
                        'title': text,
                        'bounds': bounds
                    })
                    print(f"  [{len(titles)}] {text[:40]}")

            # 向上滚动查看更多
            w, h = self.d.window_size()
            self.d.swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.3), duration=0.4)
            time.sleep(1.5)

        return titles[:count]

    def click_post_by_title(self, title):
        """根据标题点击帖子进入详情。"""
        # 方法1: 通过文字选择器点击
        if self.d(text=title).exists:
            self.d(text=title).click()
            time.sleep(2)
            return True

        # 方法2: 通过文字包含匹配
        if self.d(textContains=title[:10]).exists:
            self.d(textContains=title[:10]).click()
            time.sleep(2)
            return True

        print(f"未找到帖子: {title}")
        return False

    def capture_post_images(self, save_dir):
        """
        在帖子详情页，截取所有图片。
        左右滑动浏览帖子中的多张图片。
        """
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        img_idx = 0

        # 截取第一张
        img = self.d.screenshot()
        img.save(str(save_dir / f"img_{img_idx:02d}.png"))
        print(f"  图片 {img_idx}: 已保存")
        img_idx += 1

        # 获取屏幕尺寸
        w, h = self.d.window_size()

        # 向左滑动查看更多图片
        for _ in range(20):  # 最多20张图
            # 检查是否有图片指示器（如 "2/5"）
            indicator = None
            xml = self.d.dump_hierarchy()
            from lxml import etree
            root = etree.fromstring(xml.encode('utf-8'))

            for node in root.xpath('//node'):
                text = node.attrib.get('text', '')
                if '/' in text and len(text) <= 5:
                    parts = text.split('/')
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        indicator = (int(parts[0]), int(parts[1]))

            # 如果有指示器，判断是否到了最后一张
            if indicator and indicator[0] >= indicator[1]:
                break

            # 向左滑动
            self.d.swipe(int(w * 0.8), h // 2, int(w * 0.2), h // 2, duration=0.3)
            time.sleep(0.8)

            # 检查页面是否变化（是否滑到了下一张）
            new_img = self.d.screenshot()
            if new_img.tobytes() == img.tobytes():
                break  # 没有变化，已到最后一张

            img = new_img
            img.save(str(save_dir / f"img_{img_idx:02d}.png"))
            print(f"  图片 {img_idx}: 已保存")
            img_idx += 1

        return img_idx

    def capture_post_content(self, save_dir):
        """
        截取帖子正文区域（文字 + 发帖时间 + 作者）。
        通过向下滚动拼接长截图。
        """
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        w, h = self.d.window_size()
        screenshots = []
        prev_hash = None

        for i in range(15):
            img = self.d.screenshot()

            # 检测重复（到底了）
            curr_hash = hash(img.tobytes())
            if prev_hash == curr_hash:
                break
            prev_hash = curr_hash

            filepath = str(save_dir / f"content_{i:02d}.png")
            img.save(filepath)
            screenshots.append(filepath)

            # 向上滚动
            self.d.swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.3), duration=0.3)
            time.sleep(0.8)

        return screenshots

    def extract_post_text_via_tree(self):
        """通过 UI 控件树直接读取帖子文字信息。"""
        xml = self.d.dump_hierarchy()
        from lxml import etree
        root = etree.fromstring(xml.encode('utf-8'))

        info = {
            'author': '',
            'title': '',
            'content': '',
            'post_time': '',
            'likes': '',
        }

        # 遍历所有节点收集文字
        all_texts = []
        for node in root.xpath('//node[@text]'):
            text = node.attrib.get('text', '').strip()
            rid = node.attrib.get('resource-id', '')
            if text:
                all_texts.append({
                    'text': text,
                    'resource_id': rid,
                    'bounds': node.attrib.get('bounds', ''),
                    'class': node.attrib.get('class', ''),
                })

        # 注意: 具体的 resourceId 和层级关系需要通过 uiautodev 实际查看确定
        # 以下为通用逻辑，需根据实际 UI 调整

        for item in all_texts:
            text = item['text']
            rid = item['resource_id']

            # 识别作者（通常在顶部）
            if 'author' in rid.lower() or 'user' in rid.lower() or 'name' in rid.lower():
                info['author'] = text

            # 识别时间
            if '编辑于' in text or '发布于' in text or '天前' in text or '小时前' in text:
                info['post_time'] = text

            # 识别点赞数
            if text.isdigit() and '赞' in text or text.endswith('万'):
                info['likes'] = text

        # 正文通常是最长的文字块
        content_parts = [t['text'] for t in all_texts if len(t['text']) > 10
                         and t['text'] not in ['关注', '分享', '评论', '收藏']]
        if content_parts:
            info['content'] = '\n'.join(content_parts[:3])  # 取前几段

        return info

    def capture_comments(self, save_dir, max_scrolls=15):
        """
        截取评论区域。
        点击评论区 → 滚动截取 → 保存。
        """
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        # 点击评论区域或评论按钮
        if self.d(text="评论").exists:
            self.d(text="评论").click()
            time.sleep(1)

        # 或者通过 resourceId 点击
        # self.d(resourceIdMatches=".*comment.*").click()

        w, h = self.d.window_size()
        screenshots = []
        prev_hash = None

        for i in range(max_scrolls):
            img = self.d.screenshot()

            curr_hash = hash(img.tobytes())
            if prev_hash == curr_hash:
                break
            prev_hash = curr_hash

            filepath = str(save_dir / f"comment_{i:02d}.png")
            img.save(filepath)
            screenshots.append(filepath)

            self.d.swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.3), duration=0.3)
            time.sleep(0.8)

        return screenshots

    def extract_single_post(self, title):
        """
        提取单个帖子的完整内容。

        流程: 点击帖子 → 截取图片 → 截取正文 → 截取评论 → 返回列表
        """
        # 点击进入帖子
        if not self.click_post_by_title(title):
            return None

        time.sleep(2)

        # 创建帖子目录（用标题作为文件夹名，去除非法字符）
        safe_title = "".join(c for c in title[:30] if c.isalnum() or c in ' _-\u4e00-\u9fff')
        post_dir = self.output_dir / safe_title
        post_dir.mkdir(parents=True, exist_ok=True)

        # 1. 截取帖子图片
        print("  截取图片...")
        img_count = self.capture_post_images(post_dir / "images")

        # 2. 读取帖子文字信息
        print("  读取文字信息...")
        post_info = self.extract_post_text_via_tree()

        # 3. 截取正文（长截图）
        print("  截取正文...")
        content_shots = self.capture_post_content(post_dir)

        # 4. 截取评论
        print("  截取评论...")
        comment_shots = self.capture_comments(post_dir / "comments")

        # 保存帖子信息
        import json
        with open(post_dir / "info.json", 'w', encoding='utf-8') as f:
            json.dump(post_info, f, ensure_ascii=False, indent=2)

        # 返回列表
        self.d.press("back")
        time.sleep(1)

        return {
            'title': title,
            'dir': str(post_dir),
            'images': img_count,
            'content_screenshots': len(content_shots),
            'comment_screenshots': len(comment_shots),
            'info': post_info,
        }

    def run(self, target_titles=None, max_posts=5):
        """
        主运行方法。

        Args:
            target_titles: 指定帖子标题列表，为 None 则自动从首页获取
            max_posts: 最大处理帖子数
        """
        print("=== 小红书帖子提取工具 ===")
        print(f"设备: {self.d.info['productName']}")
        print(f"分辨率: {self.d.window_size()}")

        # 启动小红书
        print("\n启动小红书...")
        self.launch_xhs()

        # 获取帖子列表
        if target_titles:
            titles = target_titles
        else:
            print(f"\n从首页获取 {max_posts} 个帖子...")
            post_list = self.get_feed_titles(count=max_posts)
            titles = [p['title'] for p in post_list]

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
            time.sleep(2)  # 帖子间间隔

        # 汇总
        print(f"\n=== 提取完成 ===")
        print(f"共提取 {len(results)} 个帖子")
        print(f"输出目录: {self.output_dir.absolute()}")

        return results


# ===== 运行 =====
if __name__ == "__main__":
    extractor = XHSExtractor(output_dir="output")

    # 方式1: 自动从首页提取
    extractor.run(max_posts=5)

    # 方式2: 指定帖子标题
    # extractor.run(target_titles=["某某分享的美食攻略", "另一个帖子标题"])
```

---

## 11. 反检测策略

```python
def setup_stealth_mode(d):
    """配置反检测参数。"""

    # 1. 随机操作延迟
    d.settings['operation_delay'] = (0.3, 1.2)
    d.settings['operation_delay_methods'] = ['click', 'swipe', 'long_click']

    # 2. 不要太快滚动
    # 每次操作后 sleep 1~3 秒
    import random
    def human_delay(min_s=1.0, max_s=3.0):
        time.sleep(random.uniform(min_s, max_s))

    # 3. 随机化滑动轨迹
    w, h = d.window_size()
    def human_swipe(d, direction="up"):
        """模拟人类滑动，带随机偏移和速度变化。"""
        cx = w // 2 + random.randint(-50, 50)
        if direction == "up":
            d.swipe(cx, int(h * random.uniform(0.65, 0.75)),
                    cx + random.randint(-30, 30), int(h * random.uniform(0.25, 0.35)),
                    duration=random.uniform(0.3, 0.7))
        elif direction == "down":
            d.swipe(cx, int(h * random.uniform(0.25, 0.35)),
                    cx + random.randint(-30, 30), int(h * random.uniform(0.65, 0.75)),
                    duration=random.uniform(0.3, 0.7))

    # 4. 偶尔随机停顿（模拟阅读）
    def random_pause():
        if random.random() < 0.2:  # 20%概率停顿
            time.sleep(random.uniform(3, 8))

    # 5. 控制单次运行数量
    # 不要一次提取太多帖子，建议每次不超过 20 个
    MAX_POSTS_PER_SESSION = 20

    # 6. 每隔几个帖子回到首页重新进入
    REHOME_INTERVAL = 5

    return human_delay, human_swipe, random_pause
```

---

## 12. 常见问题排查

### 12.1 连接问题

| 问题 | 解决方案 |
|------|---------|
| `DeviceNotFound` | 确认 `adb devices` 能看到设备；检查 USB 调试是否开启 |
| 连接后无响应 | 拔掉 USB 重连；重启 adb: `adb kill-server && adb start-server` |
| WiFi 连接断开 | 确保手机和 PC 在同一 WiFi；重新 `adb connect` |
| 小米手机授权弹窗 | 勾选"一律允许使用这台计算机进行调试" |

### 12.2 操作问题

| 问题 | 解决方案 |
|------|---------|
| 点击位置不对 | 检查 `d.window_size()` 是否和手机真实分辨率一致 |
| 截图黑屏 | 尝试 `d.app_start("com.xingin.xhs", stop=True)` 重启应用 |
| 滑动无效果 | 增大滑动距离；检查坐标是否在屏幕范围内 |
| 元素找不到 | 使用 `uiautodev` 检查实际 UI 树；可能是动态加载未完成 |

### 12.3 小红书 App 特有问题

| 问题 | 解决方案 |
|------|---------|
| 更新弹窗 | 使用 `watch_context` 自动处理 |
| 广告帖子 | 通过 UI 树中 "广告" 标签过滤 |
| 视频帖子 | 视频类帖子没有图片轮播，跳过或单独处理 |
| 帖子打不开 | 可能已被删除或设为私密，跳过并记录 |
| 滑动后内容重复 | 增加等待时间，或检测截图哈希避免重复 |

### 12.4 调试技巧

```python
# 1. 保存当前 UI 树到文件，用于离线分析
xml = d.dump_hierarchy()
with open("debug_ui_tree.xml", 'w', encoding='utf-8') as f:
    f.write(xml)

# 2. 保存截图用于模板匹配
d.screenshot("debug_screen.png")

# 3. 打印所有可见文字
from lxml import etree
root = etree.fromstring(xml.encode('utf-8'))
for node in root.xpath('//node[@text]'):
    text = node.attrib.get('text', '').strip()
    if text:
        rid = node.attrib.get('resource-id', '')
        bounds = node.attrib.get('bounds', '')
        print(f"{text:40s} | {rid:50s} | {bounds}")

# 4. 实时查看元素
# 在终端运行: uiautodev
# 浏览器访问: http://localhost:8000
```

---

## 快速参考卡

```python
import uiautomator2 as u2

d = u2.connect()                          # 连接设备
d.app_start("com.xingin.xhs")             # 启动小红书
img = d.screenshot()                       # 截图
d.click(540, 1200)                         # 点击
d.swipe(540, 1800, 540, 400)              # 滑动
d.press("back")                            # 返回
d(text="搜索").click()                     # 文字点击
title = d(text="标题").get_text()           # 获取文字
xml = d.dump_hierarchy()                   # 获取 UI 树
d(scrollable=True).scroll.forward()        # 滚动
d.image.click("template.png")              # 图像匹配点击
```
