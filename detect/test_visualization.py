#!/usr/bin/env python3
"""
瓶子检测可视化测试脚本
用于实时查看检测效果和调整参数
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bottle_fill_detector import BottleFillDetector, DetectionConfig
import cv2


def test_with_visualization():
    """带可视化界面的测试函数"""
    print("=== 瓶子液体检测可视化测试 ===")
    print("按 'q' 键退出测试")
    print("按 's' 键保存当前参数配置")
    print("按 '+'/'-' 键调整检测阈值")
    
    # 创建配置 - 开启可视化
    config = DetectionConfig(
        debug_mode=True,
        save_debug_images=False,  # 只在检测到True时保存
        min_bottle_area=500,      # 降低最小面积要求
        max_bottle_area=30000,    # 调整最大面积
        fill_threshold_ratio=0.7
    )
    
    detector = BottleFillDetector(config)
    
    if not detector.initialize_camera():
        print("无法初始化摄像头")
        return
    
    try:
        detector.run_continuous_detection()
    finally:
        detector.release_camera()


def test_parameter_tuning():
    """参数调整测试"""
    print("=== 参数调整测试 ===")
    
    # 可调整的参数
    min_area = 500
    max_area = 30000
    threshold = 0.7
    
    config = DetectionConfig(
        debug_mode=True,
        min_bottle_area=min_area,
        max_bottle_area=max_area,
        fill_threshold_ratio=threshold
    )
    
    detector = BottleFillDetector(config)
    
    if not detector.initialize_camera():
        print("无法初始化摄像头")
        return
    
    try:
        print(f"当前参数: min_area={min_area}, max_area={max_area}, threshold={threshold}")
        print("观察检测效果，按Enter键继续...")
        input()
        
        detector.run_continuous_detection()
        
    finally:
        detector.release_camera()


def test_single_image():
    """单张图像测试"""
    print("=== 单张图像测试 ===")
    
    config = DetectionConfig(
        debug_mode=True,
        min_bottle_area=500,
        max_bottle_area=30000,
        fill_threshold_ratio=0.7
    )
    
    detector = BottleFillDetector(config)
    
    if not detector.initialize_camera():
        print("无法初始化摄像头")
        return
    
    try:
        ret, frame = detector.camera.read()
        if ret:
            is_filled, debug_info = detector.detect_single_frame(frame)
            
            print(f"检测结果: {is_filled}")
            print(f"调试信息: {debug_info}")
            
            # 保存调试图像
            if debug_info and debug_info.get("bbox"):
                x, y, w, h = debug_info["bbox"]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                result_text = f"FILLED: {is_filled}"
                cv2.putText(frame, result_text, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                cv2.imwrite("test_result.jpg", frame)
                print("结果已保存到 test_result.jpg")
            
        else:
            print("无法获取图像")
            
    finally:
        detector.release_camera()


def test_custom_image(image_path="1.jpg"):
    """自定义图像测试"""
    print(f"=== 自定义图像测试 ===")
    print(f"测试图像: {image_path}")
    
    if not os.path.exists(image_path):
        print(f"❌ 图像文件不存在: {image_path}")
        return
    
    config = DetectionConfig(
        debug_mode=True,
        min_bottle_area=500,
        max_bottle_area=30000,
        fill_threshold_ratio=0.7
    )
    
    detector = BottleFillDetector(config)
    
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ 无法读取图像: {image_path}")
        return
    
    print("执行检测...")
    is_filled, debug_info = detector.detect_single_frame(image)
    
    print(f"检测结果: {is_filled}")
    print(f"调试信息: {debug_info}")
    
    # 绘制结果
    result_image = image.copy()
    
    # 绘制检测框（如果有）
    if debug_info and debug_info.get("bbox"):
        x, y, w, h = debug_info["bbox"]
        
        # 检测框颜色：绿色表示已装满，黄色表示未装满
        bbox_color = (0, 255, 0) if is_filled else (0, 255, 255)
        cv2.rectangle(result_image, (x, y), (x + w, y + h), bbox_color, 2)
        
        # 状态文字
        status_text = "DETECTED: FILLED" if is_filled else "DETECTED: NOT FILLED"
        cv2.putText(result_image, status_text, (x, y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, bbox_color, 1)
        
        # 面积信息
        if debug_info.get("bottle_area"):
            area_text = f"Area: {debug_info['bottle_area']:.0f}"
            cv2.putText(result_image, area_text, (x, y + h + 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, bbox_color, 1)
        
        # 填充比例
        if debug_info.get("fill_ratio") is not None:
            ratio_text = f"Fill: {debug_info['fill_ratio']:.1%}"
            cv2.putText(result_image, ratio_text, (x + w + 10, y + h // 2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    else:
        # 没有检测到目标
        cv2.putText(result_image, "NO TARGET DETECTED", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    
    # 主要结果
    result_color = (0, 255, 0) if is_filled else (0, 0, 255)
    result_text = f"FILLED: {is_filled}"
    cv2.putText(result_image, result_text, (10, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, result_color, 2)
    
    # 调试信息
    if debug_info and debug_info.get("error"):
        error_text = f"Error: {debug_info['error']}"
        cv2.putText(result_image, error_text, (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    # 保存结果
    output_path = "custom_test_result.jpg"
    cv2.imwrite(output_path, result_image)
    print(f"结果已保存到: {output_path}")
    
    # 显示结果
    print("显示结果（按任意键关闭窗口）...")
    cv2.imshow("Custom Image Test Result", result_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    print("自定义图像测试完成")


if __name__ == "__main__":
    print("选择测试模式:")
    print("1. 可视化连续检测")
    print("2. 参数调整测试")
    print("3. 单张图像测试")
    print("4. 自定义图像测试")
    
    choice = input("请输入选择 (1-4): ").strip()
    
    if choice == "1":
        test_with_visualization()
    elif choice == "2":
        test_parameter_tuning()
    elif choice == "3":
        test_single_image()
    elif choice == "4":
        # 询问是否使用默认路径或自定义路径
        use_default = input("使用默认图像 (1.jpg)? (y/n): ").strip().lower()
        if use_default == 'y' or use_default == '':
            test_custom_image()
        else:
            custom_path = input("请输入图像文件路径: ").strip()
            test_custom_image(custom_path)
    else:
        print("无效选择，默认使用自定义图像测试")
        test_custom_image()