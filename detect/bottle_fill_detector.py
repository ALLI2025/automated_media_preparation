#!/usr/bin/env python3
"""
瓶子液体装满检测脚本
用于实时检测瓶子是否装满液体，可集成到LabVIEW中作为布尔控件
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class DetectionStatus(Enum):
    """检测状态枚举"""
    NOT_DETECTED = 0
    FILLED = 1
    NOT_FILLED = 2
    ERROR = 3


@dataclass
class DetectionConfig:
    """检测配置参数"""
    # 图像处理参数
    canny_threshold1: int = 50
    canny_threshold2: int = 150
    blur_kernel_size: int = 5
    
    # 检测参数
    min_bottle_area: int = 1000
    max_bottle_area: int = 50000
    fill_threshold_ratio: float = 0.7  # 液面高度占瓶高的比例阈值
    
    # ROI参数
    roi_top_ratio: float = 0.1  # ROI顶部占图像比例
    roi_bottom_ratio: float = 0.9  # ROI底部占图像比例
    
    # 调试参数
    debug_mode: bool = False
    save_debug_images: bool = False


class BottleFillDetector:
    """瓶子液体装满检测器"""
    
    def __init__(self, config: Optional[DetectionConfig] = None):
        self.config = config or DetectionConfig()
        self.logger = self._setup_logger()
        self.camera = None
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('BottleFillDetector')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def initialize_camera(self, camera_id: int = 0, width: int = 640, height: int = 480) -> bool:
        """初始化摄像头"""
        try:
            self.camera = cv2.VideoCapture(camera_id)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            if not self.camera.isOpened():
                self.logger.error("无法打开摄像头")
                return False
                
            self.logger.info(f"摄像头初始化成功: {width}x{height}")
            return True
            
        except Exception as e:
            self.logger.error(f"摄像头初始化失败: {e}")
            return False
    
    def release_camera(self):
        """释放摄像头资源"""
        if self.camera:
            self.camera.release()
            self.camera = None
            self.logger.info("摄像头已释放")
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """预处理图像"""
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 高斯模糊去噪
        blurred = cv2.GaussianBlur(
            gray, 
            (self.config.blur_kernel_size, self.config.blur_kernel_size), 
            0
        )
        
        # 自适应直方图均衡化
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)
        
        return enhanced
    
    def detect_bottle_and_liquid_level(self, image: np.ndarray) -> Tuple[DetectionStatus, float, Dict[str, Any]]:
        """
        改进的瓶子液面检测算法 - 针对透明瓶子优化
        
        Returns:
            status: 检测状态
            fill_ratio: 液面高度占瓶高的比例 (-1 表示检测失败)
            debug_info: 调试信息，包含检测框坐标
        """
        try:
            # 1. 多种颜色分割策略 - 适应不同瓶子颜色
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 策略1: 透明/白色瓶子
            lower_transparent = np.array([0, 0, 100])
            upper_transparent = np.array([180, 60, 255])
            transparent_mask = cv2.inRange(hsv, lower_transparent, upper_transparent)
            
            # 策略2: 淡蓝色瓶子（常见液体瓶）
            lower_blue = np.array([90, 30, 100])
            upper_blue = np.array([130, 150, 255])
            blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
            
            # 策略3: 灰色/银色瓶子
            lower_gray = np.array([0, 0, 50])
            upper_gray = np.array([180, 50, 200])
            gray_mask = cv2.inRange(hsv, lower_gray, upper_gray)
            
            # 合并所有策略的掩码
            bottle_mask = cv2.bitwise_or(transparent_mask, blue_mask)
            bottle_mask = cv2.bitwise_or(bottle_mask, gray_mask)
            
            # 2. 形态学处理 - 清理噪声
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
            bottle_mask = cv2.morphologyEx(bottle_mask, cv2.MORPH_CLOSE, kernel)
            bottle_mask = cv2.morphologyEx(bottle_mask, cv2.MORPH_OPEN, kernel)
            
            # 保存调试图像（如果开启调试模式）
            if self.config.debug_mode and self.config.save_debug_images:
                cv2.imwrite("debug_mask.jpg", bottle_mask)
            
            # 3. 寻找潜在瓶子区域
            contours, _ = cv2.findContours(bottle_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return DetectionStatus.NOT_DETECTED, -1.0, {"error": "未找到瓶子轮廓", "bbox": None}
            
            # 4. 瓶子识别 - 基于形状和尺寸特征
            potential_bottles = []
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # 面积过滤
                if area < self.config.min_bottle_area or area > self.config.max_bottle_area:
                    continue
                
                # 获取边界框
                x, y, w, h = cv2.boundingRect(contour)
                
                # 形状分析 - 瓶子应该是高大于宽的矩形
                aspect_ratio = h / w if w > 0 else 0
                if aspect_ratio < 1.0:  # 进一步降低要求：高度至少等于宽度
                    continue
                
                # 计算轮廓的矩形度
                rect_area = w * h
                if rect_area == 0:
                    continue
                
                rectness = area / rect_area
                
                # 降低矩形度要求，适应透明瓶子
                if rectness < 0.4:  # 瓶子应该有基本的矩形度
                    continue
                
                # 计算综合评分（考虑多个因素）
                score = 0
                score += area / 500.0   # 面积权重（降低要求）
                score += rectness * 3   # 矩形度权重（降低权重）
                score += aspect_ratio * 2  # 长宽比权重
                
                # 位置权重（图像中心区域的瓶子更可能是目标）
                image_center_x = image.shape[1] / 2
                image_center_y = image.shape[0] / 2
                box_center_x = x + w/2
                box_center_y = y + h/2
                distance_from_center = np.sqrt((box_center_x - image_center_x)**2 + (box_center_y - image_center_y)**2)
                max_distance = np.sqrt(image.shape[0]**2 + image.shape[1]**2) / 2
                position_score = 1.0 - (distance_from_center / max_distance)
                score += position_score * 3
                
                potential_bottles.append({
                    'contour': contour,
                    'bbox': (x, y, w, h),
                    'area': area,
                    'rectness': rectness,
                    'aspect_ratio': aspect_ratio,
                    'score': score
                })
            
            if not potential_bottles:
                return DetectionStatus.NOT_DETECTED, -1.0, {
                    "error": "未找到符合瓶子特征的轮廓", 
                    "suggestion": "请检查瓶子是否完整可见，或调整检测参数",
                    "bbox": None
                }
            
            # 选择最佳瓶子
            best_bottle_info = max(potential_bottles, key=lambda x: x['score'])
            x, y, w, h = best_bottle_info['bbox']
            
            # 5. 液面检测 - 在瓶子区域内寻找液体界面
            bottle_roi = image[y:y+h, x:x+w]
            
            # 转换为灰度并增强对比度
            gray_roi = cv2.cvtColor(bottle_roi, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_roi = clahe.apply(gray_roi)
            
            # 寻找水平边缘（液面线）
            sobel_y = cv2.Sobel(enhanced_roi, cv2.CV_64F, 0, 1, ksize=3)
            edge_strength = np.abs(sobel_y)
            
            # 垂直投影寻找最强边缘
            vertical_projection = np.mean(edge_strength, axis=1)
            
            # 寻找液面位置（从下到上寻找最强边缘）
            min_liquid_level = int(h * 0.1)  # 液面最低可能在10%位置
            max_liquid_level = int(h * 0.95)  # 液面最高可能在95%位置
            
            liquid_level_idx = int(h * 0.5)  # 默认位置
            if max_liquid_level > min_liquid_level:
                liquid_region = vertical_projection[min_liquid_level:max_liquid_level]
                if len(liquid_region) > 0:
                    # 找到最强边缘位置
                    liquid_offset = np.argmax(liquid_region)
                    liquid_level_idx = min_liquid_level + liquid_offset
            
            # 计算填充比例（从底部到液面的比例）
            fill_ratio = (h - liquid_level_idx) / h
            
            # 确保填充比例在合理范围内
            fill_ratio = max(0.0, min(1.0, fill_ratio))
            
            # 保存调试信息
            self._debug_intermediate_steps(image, bottle_mask, potential_bottles, best_bottle_info)
            
            # 判断瓶子是否装满
            status = DetectionStatus.FILLED if fill_ratio >= self.config.fill_threshold_ratio else DetectionStatus.NOT_FILLED
            
            debug_info = {
                "bottle_area": best_bottle_info['area'],
                "bbox": (x, y, w, h),
                "rectness": best_bottle_info['rectness'],
                "aspect_ratio": best_bottle_info['aspect_ratio'],
                "score": best_bottle_info['score'],
                "liquid_level_idx": liquid_level_idx,
                "fill_ratio": fill_ratio,
                "threshold_ratio": self.config.fill_threshold_ratio,
                "potential_bottles": len(potential_bottles),
                "detection_success": True
            }
            
            self.logger.info(f"检测到瓶子: 面积={best_bottle_info['area']:.1f}, 长宽比={best_bottle_info['aspect_ratio']:.2f}, 填充比例={fill_ratio:.2f}, 状态={status.name}")
            
            return status, fill_ratio, debug_info
            
        except Exception as e:
            self.logger.error(f"检测过程出错: {e}")
            return DetectionStatus.ERROR, -1.0, {"error": str(e), "detection_success": False, "bbox": None}
    
    def detect_single_frame(self, image: Optional[np.ndarray] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        检测单帧图像，返回布尔值和调试信息（用于LabVIEW集成）
        
        Args:
            image: 输入图像，如果为None则从摄像头获取
            
        Returns:
            Tuple[bool, Optional[Dict]]: (是否装满, 调试信息包含检测框)
        """
        try:
            # 获取图像
            if image is None:
                if self.camera is None:
                    self.logger.error("摄像头未初始化")
                    return False, None
                
                ret, frame = self.camera.read()
                if not ret or frame is None:
                    self.logger.error("无法从摄像头获取图像")
                    return False, None
            else:
                frame = image.copy()
            
            # 检测液面
            status, fill_ratio, debug_info = self.detect_bottle_and_liquid_level(frame)
            
            # 记录调试信息
            if self.config.debug_mode:
                self.logger.info(f"检测状态: {status.name}, 填充比例: {fill_ratio:.2f}")
                self.logger.info(f"调试信息: {debug_info}")
            
            # 只在检测到True时保存调试图像
            if self.config.save_debug_images and status == DetectionStatus.FILLED:
                self._save_debug_image(frame, status, fill_ratio)
            
            # 返回布尔结果和调试信息
            is_filled = status == DetectionStatus.FILLED
            return is_filled, debug_info
            
        except Exception as e:
            self.logger.error(f"单帧检测失败: {e}")
            return False, None
    
    def _debug_intermediate_steps(self, image: np.ndarray, bottle_mask: np.ndarray, potential_bottles: list, best_bottle_info: dict) -> None:
        """保存中间步骤的调试图像"""
        if not self.config.debug_mode or not self.config.save_debug_images:
            return
            
        try:
            # 保存掩码图像
            cv2.imwrite("debug_bottle_mask.jpg", bottle_mask)
            
            # 创建调试图像显示所有候选瓶子
            debug_image = image.copy()
            
            # 绘制所有候选瓶子
            for i, bottle in enumerate(potential_bottles):
                x, y, w, h = bottle['bbox']
                color = (0, 255, 0) if bottle == best_bottle_info else (0, 255, 255)
                thickness = 3 if bottle == best_bottle_info else 1
                
                cv2.rectangle(debug_image, (x, y), (x + w, y + h), color, thickness)
                
                # 添加评分信息
                info_text = f"#{i}: S={bottle['score']:.1f}, A={bottle['area']:.0f}, R={bottle['aspect_ratio']:.1f}"
                cv2.putText(debug_image, info_text, (x, y - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            cv2.imwrite("debug_candidates.jpg", debug_image)
            self.logger.info(f"保存了调试图像，找到 {len(potential_bottles)} 个候选瓶子")
            
        except Exception as e:
            self.logger.error(f"保存调试图像失败: {e}")

    def _draw_detection_visualization(self, frame: np.ndarray, is_filled: bool, debug_info: Optional[Dict[str, Any]]) -> np.ndarray:
        """绘制检测可视化信息"""
        display_frame = frame.copy()
        
        # 绘制检测框和信息
        if debug_info and debug_info.get("bbox"):
            bbox = debug_info["bbox"]
            x, y, w, h = bbox
            
            # 根据检测结果显示不同颜色的框
            if is_filled:
                bbox_color = (0, 255, 0)  # 绿色 - 检测到装满
                status_text = "DETECTED: FILLED"
            else:
                bbox_color = (0, 255, 255)  # 黄色 - 检测到但未装满
                status_text = "DETECTED: NOT FILLED"
            
            # 绘制检测框
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), bbox_color, 2)
            
            # 绘制检测框标签
            label_bg_color = bbox_color
            cv2.rectangle(display_frame, (x, y - 25), (x + 150, y), label_bg_color, -1)
            cv2.putText(display_frame, status_text, (x + 5, y - 8), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            
            # 显示液面位置（如果检测成功）
            if debug_info.get("liquid_level_idx") is not None:
                liquid_y = y + debug_info["liquid_level_idx"]
                cv2.line(display_frame, (x, liquid_y), (x + w, liquid_y), (255, 0, 0), 2)
                cv2.putText(display_frame, "Liquid Level", (x + w + 10, liquid_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            
            # 显示面积信息
            if debug_info.get("bottle_area"):
                area_text = f"Area: {debug_info['bottle_area']:.0f}"
                cv2.putText(display_frame, area_text, (x, y + h + 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, bbox_color, 1)
                
        else:
            # 没有检测到目标
            cv2.putText(display_frame, "NO TARGET DETECTED", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # 显示主要结果
        result_color = (0, 255, 0) if is_filled else (0, 0, 255)
        result_text = f"FILLED: {is_filled}"
        cv2.putText(display_frame, result_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, result_color, 2)
        
        # 显示填充比例（如果有）
        if debug_info and debug_info.get("fill_ratio") is not None:
            fill_ratio = debug_info["fill_ratio"]
            ratio_text = f"Fill Ratio: {fill_ratio:.1%}"
            cv2.putText(display_frame, ratio_text, (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # 显示阈值信息
        threshold_text = f"Threshold: {self.config.fill_threshold_ratio:.1%}"
        cv2.putText(display_frame, threshold_text, (10, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return display_frame
    
    def run_continuous_detection(self, callback=None):
        """连续检测模式（用于测试）- 带可视化bbox显示"""
        if self.camera is None:
            self.logger.error("摄像头未初始化")
            return
        
        self.logger.info("开始连续检测，按'q'键退出，按ESC键强制退出")
        
        try:
            while True:
                ret, frame = self.camera.read()
                if not ret:
                    self.logger.error("无法获取图像")
                    break
                
                # 检测 - 获取详细结果
                is_filled, debug_info = self.detect_single_frame(frame)
                
                # 绘制检测可视化
                display_frame = self._draw_detection_visualization(frame, is_filled, debug_info)
                
                cv2.imshow('Bottle Fill Detection', display_frame)
                
                # 回调函数
                if callback:
                    callback(is_filled)
                
                # 退出条件 - 增强退出响应
                key = cv2.waitKey(50) & 0xFF  # 增加等待时间到50ms
                if key == ord('q') or key == 27:  # 'q'键或ESC键
                    self.logger.info(f"用户按下退出键: {key}")
                    break
                    
        except KeyboardInterrupt:
            self.logger.info("用户中断检测")
        finally:
            cv2.destroyAllWindows()
            self.logger.info("检测窗口已关闭")


# LabVIEW集成接口函数
def detect_bottle_fill_status(camera_id: int = 0, config_dict: Optional[Dict] = None) -> bool:
    """
    LabVIEW调用的主函数
    
    Args:
        camera_id: 摄像头ID（通常为0）
        config_dict: 配置参数字典（可选）
        
    Returns:
        bool: True表示瓶子已装满，False表示未装满或检测失败
    """
    try:
        # 创建配置
        config = DetectionConfig()
        if config_dict:
            for key, value in config_dict.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        # 创建检测器
        detector = BottleFillDetector(config)
        
        # 初始化摄像头
        if not detector.initialize_camera(camera_id):
            return False
        
        try:
            # 执行单次检测 - 获取布尔结果
            is_filled, debug_info = detector.detect_single_frame()
            return is_filled
            
        finally:
            # 释放资源
            detector.release_camera()
            
    except Exception as e:
        logging.error(f"LabVIEW接口函数出错: {e}")
        return False


# 测试函数
def test_detection():
    """测试检测功能"""
    config = DetectionConfig(debug_mode=True, save_debug_images=True)
    detector = BottleFillDetector(config)
    
    if detector.initialize_camera():
        try:
            detector.run_continuous_detection()
        finally:
            detector.release_camera()
    else:
        print("无法初始化摄像头，请检查设备")


if __name__ == "__main__":
    # 运行测试
    test_detection()