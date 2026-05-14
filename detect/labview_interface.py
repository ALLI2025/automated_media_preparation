#!/usr/bin/env python3
"""
LabVIEW集成示例脚本
演示如何与LabVIEW Python Node集成
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bottle_fill_detector import detect_bottle_fill_status, DetectionConfig


def labview_bottle_detection(camera_index=0, threshold_ratio=0.85):
    """
    LabVIEW Python Node调用的简化接口函数
    
    参数:
        camera_index: 摄像头索引 (默认0)
        threshold_ratio: 装满阈值比例 (默认0.85)
        
    返回:
        boolean: True=已装满, False=未装满或检测失败
    """
    try:
        # 配置参数
        config_dict = {
            'fill_threshold_ratio': float(threshold_ratio),
            'debug_mode': False,
            'save_debug_images': False
        }
        
        # 执行检测
        result = detect_bottle_fill_status(
            camera_id=int(camera_index),
            config_dict=config_dict
        )
        
        return bool(result)
        
    except Exception as e:
        print(f"检测错误: {e}")
        return False





# LabVIEW直接调用的函数（无参数版本）- 推荐用于LabVIEW集成
def labview_simple_detection():
    """LabVIEW调用的最简单接口函数"""
    return labview_bottle_detection()


if __name__ == "__main__":
    # 测试LabVIEW接口
    print("测试LabVIEW接口...")
    
    # 测试简单检测
    result = labview_simple_detection()
    print(f"简单检测结果: {result}")
    
    # 测试带参数检测
    result = labview_bottle_detection(camera_index=0, threshold_ratio=0.8)
    print(f"参数化检测结果: {result}")