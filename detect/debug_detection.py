#!/usr/bin/env python3
"""
调试检测算法的详细步骤
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from bottle_fill_detector import BottleFillDetector, DetectionConfig

def debug_detection_steps(image_path):
    """详细调试检测步骤"""
    print(f"=== 详细调试检测步骤 ===")
    print(f"图像: {image_path}")
    
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ 无法读取图像: {image_path}")
        return
    
    print(f"图像尺寸: {image.shape}")
    
    # 创建检测器（开启调试模式）
    config = DetectionConfig(
        debug_mode=True,
        save_debug_images=True,  # 保存调试图像
        min_bottle_area=1000,    # 降低最小面积
        max_bottle_area=50000,
        fill_threshold_ratio=0.7
    )
    
    detector = BottleFillDetector(config)
    
    # 手动执行检测步骤
    print("\n1. 颜色分割...")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 多种颜色分割策略
    lower_transparent = np.array([0, 0, 100])
    upper_transparent = np.array([180, 60, 255])
    transparent_mask = cv2.inRange(hsv, lower_transparent, upper_transparent)
    
    lower_blue = np.array([90, 30, 100])
    upper_blue = np.array([130, 150, 255])
    blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    lower_gray = np.array([0, 0, 50])
    upper_gray = np.array([180, 50, 200])
    gray_mask = cv2.inRange(hsv, lower_gray, upper_gray)
    
    # 合并掩码
    bottle_mask = cv2.bitwise_or(transparent_mask, blue_mask)
    bottle_mask = cv2.bitwise_or(bottle_mask, gray_mask)
    
    # 形态学处理
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    bottle_mask = cv2.morphologyEx(bottle_mask, cv2.MORPH_CLOSE, kernel)
    bottle_mask = cv2.morphologyEx(bottle_mask, cv2.MORPH_OPEN, kernel)
    
    cv2.imwrite("debug_step1_mask.jpg", bottle_mask)
    print("   保存了掩码图像: debug_step1_mask.jpg")
    
    print("\n2. 寻找轮廓...")
    contours, _ = cv2.findContours(bottle_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"   找到 {len(contours)} 个轮廓")
    
    print("\n3. 瓶子特征筛选...")
    potential_bottles = []
    
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        print(f"   轮廓 {i}: 面积 = {area:.1f}")
        
        if area < 500 or area > 50000:  # 降低面积要求
            print(f"      -> 面积不符合要求，跳过")
            continue
        
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = h / w if w > 0 else 0
        print(f"      -> 边界框: ({x}, {y}, {w}, {h}), 长宽比: {aspect_ratio:.2f}")
        
        if aspect_ratio < 1.2:  # 降低长宽比要求
            print(f"      -> 长宽比太小，跳过")
            continue
        
        rect_area = w * h
        rectness = area / rect_area if rect_area > 0 else 0
        print(f"      -> 矩形度: {rectness:.3f}")
        
        if rectness < 0.4:  # 降低矩形度要求
            print(f"      -> 矩形度太低，跳过")
            continue
        
        # 位置评分
        image_center_x = image.shape[1] / 2
        image_center_y = image.shape[0] / 2
        box_center_x = x + w/2
        box_center_y = y + h/2
        distance_from_center = np.sqrt((box_center_x - image_center_x)**2 + (box_center_y - image_center_y)**2)
        max_distance = np.sqrt(image.shape[0]**2 + image.shape[1]**2) / 2
        position_score = 1.0 - (distance_from_center / max_distance)
        
        score = area / 500.0 + rectness * 3 + aspect_ratio * 2 + position_score * 3  # 降低评分标准
        
        potential_bottles.append({
            'contour': contour,
            'bbox': (x, y, w, h),
            'area': area,
            'aspect_ratio': aspect_ratio,
            'rectness': rectness,
            'score': score
        })
        
        print(f"      -> 符合要求，评分: {score:.2f}")
    
    print(f"\n4. 结果分析...")
    print(f"   候选瓶子数量: {len(potential_bottles)}")
    
    # 创建可视化图像
    debug_image = image.copy()
    
    if potential_bottles:
        # 选择最佳瓶子
        best_bottle = max(potential_bottles, key=lambda x: x['score'])
        
        # 绘制所有候选瓶子
        for i, bottle in enumerate(potential_bottles):
            x, y, w, h = bottle['bbox']
            color = (0, 255, 0) if bottle == best_bottle else (0, 255, 255)
            thickness = 3 if bottle == best_bottle else 1
            
            cv2.rectangle(debug_image, (x, y), (x + w, y + h), color, thickness)
            
            info_text = f"#{i}: S={bottle['score']:.1f}"
            cv2.putText(debug_image, info_text, (x, y - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        print(f"   最佳瓶子评分: {best_bottle['score']:.2f}")
        print(f"   最佳瓶子面积: {best_bottle['area']:.1f}")
        print(f"   最佳瓶子长宽比: {best_bottle['aspect_ratio']:.2f}")
        
    else:
        print("   未找到符合要求的瓶子")
    
    # 保存调试图像
    cv2.imwrite("debug_final_result.jpg", debug_image)
    print("\n5. 保存了最终调试图像: debug_final_result.jpg")
    
    # 显示结果
    print("\n显示调试结果（按任意键关闭）...")
    cv2.imshow("Debug Result", debug_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    print("调试完成")

if __name__ == "__main__":
    debug_detection_steps("1.jpg")