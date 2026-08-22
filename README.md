# layerkit

一个基于 Pillow + numpy 的轻量级 Python 图层图像处理库。可以像 Photoshop 一样把多张图片作为独立图层叠加、调整混合模式与不透明度、对单个图层做裁剪/滤镜/画笔编辑，最终导出合成结果。

## 功能

- **基础图层管理**：增删图层、按索引/名称重排顺序、显示/隐藏、重命名、复制
- **混合模式与不透明度**：`normal`、`multiply`、`screen`、`darken`、`lighten`、`difference`、`add`、`subtract`、`overlay`、`hard_light`、`soft_light`，每个图层独立的 0–1 不透明度
- **图层内编辑**：裁剪、缩放、旋转、翻转、亮度/对比度/饱和度调整、灰度、反色、高斯模糊、锐化、自由画笔涂抹
- **导出合成结果**：合成为单张 RGBA 图像，支持导出 PNG（保留透明）或展平到不透明背景后导出 JPEG 等格式

## 安装

```bash
cd layerkit
pip install -r requirements.txt
```

或作为可编辑包安装：

```bash
pip install -e .
```

## 快速上手

```python
from layerkit import Document

doc = Document(800, 600, background=(255, 255, 255, 255))

# 添加图层（从文件，或空白图层手动绘制/赋值）
bg = doc.add_image_layer("background.png", name="Background")
logo = doc.add_image_layer("logo.png", name="Logo", opacity=0.8, blend_mode="multiply")

# 图层内编辑
logo.crop((0, 0, 200, 200)).adjust_brightness(1.1).move_to(50, 50)

# 图层管理
doc.rename_layer("Logo", "Logo (edited)")
doc.set_visible("Background", True)
doc.move_layer_up("Logo (edited)")

# 导出
doc.export("out.png")                                    # 保留透明
doc.export("out.jpg", flatten_background=(255, 255, 255))  # 展平为不透明背景
```

跑一个不依赖外部图片、自己生成素材的完整示例：

```bash
python examples/demo.py
```

会在 `examples/` 下生成 `demo_output.png`（渐变背景 + 半透明圆形 + 画笔笔触）和 `demo_output_no_circle.png`（隐藏圆形图层后的版本）。

## 核心概念

### `Layer`

一个图层持有自己的 RGBA 图像、在画布上的 `(x, y)` 偏移、不透明度（0–1）、混合模式和可见性。图层尺寸可以与画布不同（比如只裁剪出一部分），超出画布的部分会在合成时被裁掉。

常用方法：`crop`、`resize`、`rotate`、`flip_horizontal`/`flip_vertical`、`move`/`move_to`、
`adjust_brightness`/`adjust_contrast`/`adjust_saturation`、`grayscale`、`invert`、`blur`、`sharpen`、
`draw_brush_stroke`、`duplicate`、`clear`。

### `Document`

图层的有序容器（`layers[0]` 是最底层，`layers[-1]` 是最顶层），负责合成与导出。

常用方法：`add_layer`/`new_layer`/`add_image_layer`、`remove_layer`、`get_layer`（按索引或名称）、
`rename_layer`、`set_visible`/`toggle_visible`、`move_layer`/`move_layer_up`/`move_layer_down`、
`composite`、`export`。

### 混合与合成

`layerkit.blend.composite_over` 实现了标准的 Porter-Duff "source-over" 合成公式，混合函数（`multiply`/`screen`/`overlay`…）替换其中的源颜色项，因此半透明图层、图层间不透明度叠加、混合模式三者可以正确组合，而不是简单的线性插值近似。

## 照片卡片生成（`layerkit.card`）

在 `Document`/`Layer` 之上封装的一个具体场景：393×852 的竖版卡片，三个图层——纯色背景、图片、中英文文字。背景色会自动从图片的主色调取色并压暗，图片顶部铺满、底部圆角 35px（顶部为直角），下方留白区域放中英文标题。

命令行：

```bash
python generate_card.py --image photo.jpg --cn "日落时分" --en "Sunset over the bay" --out card.png
```

- `--scale`：导出倍数，默认 `3`（对应 iPhone @3x，输出 1179×2556 高清图），改成 `1` 即输出 393×852 的逻辑尺寸。
- 每次只需换 `--image`/`--cn`/`--en`/`--out` 四个参数即可生成新卡片。

作为库调用：

```python
from layerkit.card import generate_card

out_path, bg_color = generate_card(
    "photo.jpg",
    cn_text="日落时分",
    en_text="Sunset over the bay",
    out_path="card.png",
    scale=3,              # 默认 3x 高清导出
)
print(out_path, bg_color)  # 自动匹配到的深色背景 (R, G, B)
```

也可以传 `bg_color=(R, G, B)` 跳过自动取色，强制指定背景色。

### 批量模式：`origin_cards/` + `mapping.txt`

把一批图片放进 `origin_cards/`，同目录下放一个 `mapping.txt` 做文件名到中英文的映射，每行一条：

```
# 图片文件名 | 中文文字 | 英文文字
height.png | 身高 | Height
musicians.jpg | 音乐家 | Musicians
no_english.jpg | 只有中文
```

- 图片文件名要和 `origin_cards/` 里的实际文件名完全一致（含扩展名、含空格）
- 英文可以留空（该行只写两段）
- `#` 开头的行和空行会被忽略
- 某一行的图片文件找不到时，会打印 `[skip] ...` 跳过，不会中断整批

一键跑：

```bash
./run.sh cards
```

会读取 `origin_cards/mapping.txt`，逐张生成卡片到 `cards/` 目录，文件名与原图同名（`.png`）。也可以自定义参数：

```bash
./run.sh cards --dir origin_cards --mapping origin_cards/mapping.txt --out cards --scale 3
python batch_cards.py --dir origin_cards --out cards --scale 2   # 或者不经 run.sh 直接调
```

图层结构（对应 [layerkit/card.py](layerkit/card.py)）：

| 图层 | 内容 |
|---|---|
| `Background` | 393×852 纯色，取自 `extract_dark_bg_color()`：从图片取主色调 hue/saturation，压低亮度得到深色 |
| `Image` | 393×612，`ImageOps.fit` 做 cover 裁剪填满，`rounded_rectangle(corners=(False, False, True, True))` 只圆角处理左下/右下 |
| `Text` | 英文标题（Noteworthy Bold，大号手写体，在上）+ 中文副标题（PingFang SC Medium，小号，在下），整体水平垂直居中于图片下方的纯色区域；字号按文字长度动态适配，保证两侧各 ≥100px 留白（`TEXT_MARGIN_X`），不设固定上限 |

## 运行测试

```bash
pytest
```

## 目录结构

```
layerkit/
  layerkit/
    __init__.py     导出 Document / Layer / 混合模式常量
    layer.py         Layer 类：几何变换、像素调整、画笔
    document.py       Document 类：图层管理与合成
    blend.py           混合模式数学与 Porter-Duff 合成
  examples/
    demo.py             端到端示例（自动生成素材，无需外部图片）
  tests/
    test_blend.py
    test_layer.py
    test_document.py
  pyproject.toml
  requirements.txt
```

## 后续可扩展方向

- 图层组（嵌套 group）与图层蒙版（layer mask）
- 项目文件保存/加载（把图层栈序列化为自定义工程格式，而不仅是导出扁平图）
- 更多滤镜（色阶、曲线、HSL 调整）与更多画笔样式（软笔刷、橡皮擦、图层内选区）
- 一个简单的 GUI（例如基于 PyQt/Tkinter）在这个库之上做可视化编辑
