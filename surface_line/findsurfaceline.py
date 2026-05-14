import cv2
import numpy as np
import argparse
import os
import json
# import gxipy as gx

import socket
import threading
import time

# ===== 配置参数 ====
# --- 检测算法相关 ---
FULL_LINE_Y = 400
TOLERANCE = 5
GRADIENT_THRESHOLD = 20

# --- 相机相关 ---
EXPOSURE_TIME = 10000
GAIN = 10.0

# --- 网络相关 ---
HOST = '127.0.0.1'
PORT = 65432

# --- 共享资源 ---
latest_frame = None
frame_lock = threading.Lock()

def detect_fill_level(roi_frame):
    """核心检测算法，保持不变"""
    if roi_frame is None or roi_frame.size == 0:
        return False, None
    gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=5)
    surface_points = []
    h, w = sobel_y.shape
    step = 2
    for col in range(0, w, step):
        column_grad = sobel_y[:, col]
        max_grad_idx = np.argmin(column_grad)
        max_grad_val = column_grad[max_grad_idx]
        if abs(max_grad_val) > GRADIENT_THRESHOLD:
            surface_points.append(max_grad_idx)
    if not surface_points:
        return False, None
    hist = np.bincount(surface_points)
    most_frequent_y = np.argmax(hist)
    liquid_y = int(most_frequent_y)
    is_full = abs(liquid_y - FULL_LINE_Y) <= TOLERANCE
    return is_full, liquid_y

def camera_thread_func(cam_index=1):
    """独立线程，负责相机图像采集和预览图生成"""
    global latest_frame

    # 1. 初始化并打开相机
    print(f"[相机线程] 尝试打开摄像头，索引: {cam_index}")
    # 优先尝试 DirectShow 后端 (Windows)，适配 ni-IMAQdx 等驱动
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    
    if not cap.isOpened():
        print(f"[相机线程] ❌ 无法打开摄像头索引 {cam_index} (CAP_DSHOW)。尝试默认后端...")
        cap = cv2.VideoCapture(cam_index)
        if not cap.isOpened():
            print(f"[相机线程] ❌ 致命错误: 无法打开摄像头索引 {cam_index}")
            return

    # 尝试设置参数 (OpenCV参数与SDK不同，需根据实际情况调整，此处暂注释)
    # cap.set(cv2.CAP_PROP_EXPOSURE, -5) 
    # cap.set(cv2.CAP_PROP_GAIN, GAIN)
    
    print(f"[相机线程] ✅ 相机已启动")

    # 2. 循环采集
    while True:
        try:
            ret, frame = cap.read()
            if not ret:
                print("[相机线程] ❌ 无法读取帧")
                time.sleep(1)
                continue

            # --- 更新全局高清帧 ---
            with frame_lock:
                global latest_frame
                latest_frame = frame.copy()

            # --- 生成并保存预览图 (供LabVIEW读取) ---
            preview_frame = cv2.resize(frame, (640, 512)) # 缩小尺寸
            temp_path = "latest_preview.tmp.jpg"
            final_path = "latest_preview.jpg"
            cv2.imwrite(temp_path, preview_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            try:
                os.replace(temp_path, final_path) # 原子操作
            except OSError:
                pass # 忽略文件占用错误

            time.sleep(0.03) # 控制预览图更新频率，约30fps

        except Exception as e:
            print(f"[相机线程] 采集循环出错: {e}")
            time.sleep(1)

    # 3. 清理资源
    if cap.isOpened():
        cap.release()
    print("[相机线程] 已停止。")

def handle_client(conn, addr):
    """为每个客户端连接创建一个处理函数"""
    print(f"[TCP服务] ✅ 接受来自 {addr} 的连接")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                print(f"[TCP服务] 客户端 {addr} 已断开")
                break

            try:
                # 1. 解析ROI坐标
                message = data.decode('utf-8')
                roi_data = json.loads(message)
                x, y, w, h = roi_data['roi']
                print(f"[TCP服务] 收到 ROI: {(x, y, w, h)}")

                # 2. 获取最新帧并检测
                is_full_result = False
                local_frame = None
                with frame_lock:
                    if latest_frame is not None:
                        local_frame = latest_frame.copy()
                
                if local_frame is not None and w > 0 and h > 0:
                    roi_frame = local_frame[y:y+h, x:x+w]
                    is_full_result, _ = detect_fill_level(roi_frame)
                
                # 3. 发送结果
                response = json.dumps({'is_full': bool(is_full_result)})
                conn.sendall(response.encode('utf-8'))
                print(f"[TCP服务] 发送结果: {response}")

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"[TCP服务] ❌ 无效数据格式: {data.decode('utf-8', errors='ignore')} | 错误: {e}")
            except Exception as e:
                print(f"[TCP服务] ❌ 处理请求时出错: {e}")

    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="通用相机液面检测TCP服务器")
    parser.add_argument("--cam-index", type=int, default=0, help="摄像头索引 (通常为0)")
    args = parser.parse_args()

    # 启动相机线程
    cam_thread = threading.Thread(target=camera_thread_func, args=(args.cam_index,), daemon=True)
    cam_thread.start()

    # 启动TCP服务器
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 允许端口复用，防止重启脚本时报错 "Address already in use"
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"[TCP服务] 🚀 服务器已启动，正在监听 {HOST}:{PORT}...")

    try:
        while True:
            conn, addr = server_socket.accept()
            # 为每个连接创建一个新线程来处理，避免阻塞
            client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            client_thread.start()
    except KeyboardInterrupt:
        print("\n[TCP服务] 收到退出信号，正在关闭服务器...")
    finally:
        server_socket.close()
        print("[TCP服务] 服务器已关闭。")

if __name__ == "__main__":
    main()
