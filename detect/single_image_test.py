#!/usr/bin/env python3
"""
单张图像测试脚本 - 验证检测框功能
修复按键检测问题，提供多种测试模式
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import cv2
from bottle_fill_detector import BottleFillDetector, DetectionConfig


def test_with_image_file(image_path=None):
    """使用图像文件测试检测功能"""
    print("=== 单张图像测试 ===")
    
    if image_path is None:
        # 创建一张测试图像
        print("创建测试图像...")
        test_image = create_test_image()
    else:
        # 读取指定图像
        print(f"读取图像: {image_path}")
        test_image = cv2.imread(image_path)
        if test_image is None:
            print(f"❌ 无法读取图像: {image_path}")
            return
    
    # 创建检测器
    config = DetectionConfig(
        debug_mode=True,
        save_debug_images=False,
        min_bottle_area=1000,
        max_bottle_area=50000,
        fill_threshold_ratio=0.85
    )
    
    detector = BottleFillDetector(config)
    
    print("执行检测...")
    # 注意：这里不初始化摄像头，直接处理图像
    is_filled, debug_info = detector.detect_single_frame(test_image)
    
    print(f"检测结果: {is_filled}")
    print(f"调试信息: {debug_info}")
    
    # 绘制结果
    result_image = draw_test_results(test_image, is_filled, debug_info)
    
    # 保存结果
    output_path = "test_result.jpg"
    cv2.imwrite(output_path, result_image)
    print(f"结果已保存到: {output_path}")
    
    # 显示结果
    print("显示结果（按任意键关闭窗口）...")
    cv2.imshow("Detection Result", result_image)
    cv2.waitKey(0)  # 等待任意按键
    cv2.destroyAllWindows()
    
    print("测试完成")


def create_test_image():
    """创建模拟瓶子图像用于测试"""
    # 创建空白图像
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # 绘制背景
    image[:] = (50, 50, 50)  # 深灰色背景
    
    # 绘制瓶子轮廓（矩形模拟）
    bottle_x, bottle_y = 200, 100
    bottle_width, bottle_height = 100, 300
    
    # 瓶子外框
    cv2.rectangle(image, (bottle_x, bottle_y), 
                  (bottle_x + bottle_width, bottle_y + bottle_height), 
                  (200, 200, 200), 2)
    
    # 绘制液体（部分填充）
    liquid_height = int(bottle_height * 0.7)  # 70% 填充
    cv2.rectangle(image, 
                  (bottle_x, bottle_y + bottle_height - liquid_height),
                  (bottle_x + bottle_width, bottle_y + bottle_height),
                  (100, 150, 255), -1)  # 蓝色液体
    
    # 添加一些噪声和纹理
    noise = np.random.randint(0, 50, (480, 640, 3), dtype=np.uint8)
    image = cv2.add(image, noise)
    
    return image


def draw_test_results(image, is_filled, debug_info):
    """在图像上绘制检测结果"""
    result_image = image.copy()
    
    # 绘制主要结果
    result_color = (0, 255, 0) if is_filled else (0, 0, 255)
    result_text = f"FILLED: {is_filled}"
    cv2.putText(result_image, result_text, (10, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, result_color, 2)
    
    # 绘制检测框（如果有）
    if debug_info and debug_info.get("bbox"):
        bbox = debug_info["bbox"]
        x, y, w, h = bbox
        
        # 检测框颜色
        bbox_color = (0, 255, 0) if is_filled else (0, 255, 255)
        cv2.rectangle(result_image, (x, y), (x + w, y + h), bbox_color, 2)
        
        # 检测信息
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
    
    # 调试信息
    if debug_info and debug_info.get("error"):
        error_text = f"Error: {debug_info['error']}"
        cv2.putText(result_image, error_text, (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    return result_image


def test_camera_capture():
    """测试摄像头捕获单张图像"""
    print("=== 摄像头单张捕获测试 ===")
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return None
    
    print("摄像头已打开，捕获图像...")
    
    # 读取一帧
    ret, frame = cap.read()
    cap.release()
    
    if ret:
        print("✅ 成功捕获图像")
        return frame
    else:
        print("❌ 无法捕获图像")
        return None


def main():
    """主函数 - 提供多种测试选项"""
    print("=== 瓶子检测测试菜单 ===")
    print("1. 使用测试图像（模拟瓶子）")
    print("2. 使用摄像头捕获单张图像")
    print("3. 测试自定义图像文件")
    print("4. 仅测试OpenCV按键功能")
    
    choice = input("请选择测试模式 (1-4): ").strip() or "1"
    
    if choice == "1":
        test_with_image_file()
    elif choice == "2":
        frame = test_camera_capture()
        if frame is not None:
            # 保存捕获的图像
            cv2.imwrite("captured_image.jpg", frame)
            print("图像已保存为 captured.jpg，开始检测...")
            test_with_image_file("captured_image.jpg")
    elif choice == "3":
        image_path = input("请输入图像文件路径: ").strip()
        if os.path.exists(image_path):
            test_with_image_file(image_path)
        else:
            print(f"❌ 文件不存在: {image_path}")
    elif choice == "4":
        test_key_press()
    else:
        print("无效选择，使用默认测试")
        test_with_image_file()


def test_key_press():
    """测试按键检测功能"""
    print("=== 按键测试 ===")
    print("测试OpenCV按键检测...")
    print("按任意键退出测试")
    
    # 创建简单图像
    test_img = np.zeros((200, 400, 3), dtype=np.uint8)
    cv2.putText(test_img, "Press any key", (50, 100), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    cv2.imshow("Key Test", test_img)
    key = cv2.waitKey(0)  # 等待按键
    
    print(f"检测到按键: {key} (字符: {chr(key) if key < 256 else '特殊按键'})")
    cv2.destroyAllWindows()
    print("按键测试完成")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        cv2.destroyAllWindows()
        print("测试程序结束")