# 瓶子液体装满检测系统

## 系统概述
这是一个基于计算机视觉的瓶子液体装满检测系统，可以实时检测瓶子是否装满液体，并提供LabVIEW集成接口。

## 文件结构
```
培养基自动配置/
├── bottle_fill_detector.py    # 核心检测算法
├── labview_interface.py       # LabVIEW集成接口
├── requirements.txt           # Python依赖包
├── config.json               # 配置文件（可选）
└── debug_images/             # 调试图像保存目录
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 独立测试
```python
# 运行完整测试（需要摄像头）
python bottle_fill_detector.py
```

### 2. LabVIEW集成
在LabVIEW中使用Python Node调用以下函数：

#### 简单接口
```python
# 函数名: labview_simple_detection
# 参数: 无
# 返回: Boolean (True=已装满, False=未装满)
```

#### 参数化接口
```python
# 函数名: labview_bottle_detection
# 参数: 
#   - camera_index: Integer (摄像头ID, 默认0)
#   - threshold_ratio: Float (装满阈值, 默认0.85)
# 返回: Boolean
```

## 配置参数说明

### 检测参数
- `fill_threshold_ratio`: 装满判定阈值 (0.0-1.0)
  - 0.85 表示液面高度达到瓶高的85%认为已装满
- `min_bottle_area`: 最小瓶子轮廓面积
- `max_bottle_area`: 最大瓶子轮廓面积

### 图像处理参数
- `canny_threshold1`: Canny边缘检测阈值1
- `canny_threshold2`: Canny边缘检测阈值2
- `blur_kernel_size`: 高斯模糊核大小

### 调试参数
- `debug_mode`: 是否启用调试模式
- `save_debug_images`: 是否保存调试图像

## LabVIEW集成步骤

1. **安装Python支持**
   - LabVIEW 2018或更高版本
   - 安装Python 3.6-3.9
   - 安装所需Python包

2. **配置Python环境**
   - 在LabVIEW中配置Python路径
   - 设置工作目录为脚本所在目录

3. **创建Python Node**
   - 在LabVIEW框图中放置Python Node
   - 选择对应的Python函数
   - 连接输入输出参数

4. **实时调用**
   - 在LabVIEW循环中调用检测函数
   - 将返回的布尔值连接到布尔控件

## 算法原理

1. **图像预处理**
   - 灰度化转换
   - 高斯模糊去噪
   - 自适应直方图均衡化

2. **瓶子检测**
   - Canny边缘检测
   - 轮廓查找
   - 最大轮廓识别（瓶子）

3. **液面检测**
   - 瓶子区域ROI提取
   - 水平投影分析
   - 液面位置识别

4. **装满判定**
   - 计算液面高度比例
   - 与阈值比较
   - 返回布尔结果

## 性能优化建议

1. **光照控制**
   - 使用稳定的光源
   - 避免强光直射和阴影
   - 考虑背光照明

2. **摄像头设置**
   - 固定摄像头位置和角度
   - 使用合适的分辨率（建议640x480）
   - 调整焦距和曝光参数

3. **算法调优**
   - 根据实际瓶子调整轮廓面积参数
   - 优化装满阈值比例
   - 调整检测阈值

## 故障排除

### 常见问题
1. **检测失败**
   - 检查摄像头是否正常工作
   - 调整轮廓面积参数
   - 检查光照条件

2. **误检率高**
   - 调整装满阈值比例
   - 使用批量检测
   - 优化图像预处理参数

3. **LabVIEW集成失败**
   - 检查Python路径配置
   - 确认Python版本兼容性
   - 检查依赖包是否安装

## 扩展功能

- 支持多种瓶子类型
- 检测液位高度输出
- 图像记录和追溯
- 网络摄像头支持
- 多线程并行检测