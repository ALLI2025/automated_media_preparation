#!/usr/bin/env python3
"""
简化版可视化测试脚本 - 确保退出功能正常
"""
# ✅ 运行这个进行测试
# 选择 1 - 完整可视化检测
# 选择 2 - 极简摄像头测试 不可调参数
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bottle_fill_detector import BottleFillDetector, DetectionConfig
import cv2


def simple_visualization_test():
    """简化的可视化测试 - 确保能正常退出"""
    print("=== 瓶子检测可视化测试 ===")
    print("正在启动摄像头...")
    print("按 'q' 键退出程序")
    print("按 'ESC' 键强制退出")
    
    # 创建配置
    config = DetectionConfig(
        debug_mode=True,
        save_debug_images=False,
        min_bottle_area=500,
        max_bottle_area=30000,
        fill_threshold_ratio=0.85
    )
    
    detector = BottleFillDetector(config)
    
    if not detector.initialize_camera():
        print("❌ 无法初始化摄像头，请检查设备连接")
        return
    
    print("✅ 摄像头初始化成功")
    print("开始检测，按 'q' 或 'ESC' 退出...")
    
    try:
        while True:
            # 读取帧
            ret, frame = detector.camera.read()
            if not ret:
                print("❌ 无法读取摄像头图像")
                break
            
            # 检测
            is_filled, debug_info = detector.detect_single_frame(frame)
            
            # 绘制可视化
            display_frame = detector._draw_detection_visualization(frame, is_filled, debug_info)
            
            # 显示
            cv2.imshow('Bottle Detection Test', display_frame)
            
            # 检查退出键 - 使用更简单的逻辑
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q') or key == 27:  # 'q' 或 ESC
                print(f"检测到退出键: {key} (q={ord('q')}, ESC=27)")
                break
                
    except KeyboardInterrupt:
        print("\n检测到 Ctrl+C，正在退出...")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        print("正在清理资源...")
        cv2.destroyAllWindows()
        detector.release_camera()
        print("程序已安全退出")


def ultra_simple_test():
    """极简测试 - 只检测是否能正常退出"""
    print("=== 极简摄像头测试 ===")
    print("测试摄像头和退出功能...")
    
    # 直接测试摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return
    
    print("✅ 摄像头已打开")
    print("按任意键退出测试...")
    
    try:
        while True:
            ret, frame = cap.read()
            if ret:
                cv2.putText(frame, "Press any key to exit", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow('Simple Camera Test', frame)
                
                # 任意键退出
                if cv2.waitKey(30) != -1:
                    break
            else:
                print("❌ 无法读取帧")
                break
                
    finally:
        cv2.destroyAllWindows()
        cap.release()
        print("测试完成")


if __name__ == "__main__":
    print("选择测试模式:")
    print("1. 完整可视化检测测试")
    print("2. 极简摄像头测试（测试退出功能）")
    
    choice = input("请输入选择 (1-2): ").strip() or "1"
    
    if choice == "1":
        simple_visualization_test()
    elif choice == "2":
        ultra_simple_test()
    else:
        print("默认选择完整测试")
        simple_visualization_test()