import cv2
import numpy as np
import argparse
import os
import json
# import gxipy as gx
import socket
import struct
import threading

# ===== 配置参数 ====
FULL_LINE_Y = 400          # 预设“满水线”的 y 坐标（从 ROI 顶部起算）
TOLERANCE = 5              # 像素容差
GRADIENT_THRESHOLD = 20    # 梯度阈值

# ===== 相机参数 (可调整) ====
EXPOSURE_TIME = 10000      # 曝光时间 (us)
GAIN = 10.0                # 增益

# ===== 网络参数 ====
HOST = '127.0.0.1'
PORT = 65432

# ===== 全局变量 =====
latest_frame = None
frame_lock = threading.Lock()
roi_rect = None
roi_lock = threading.Lock()
should_exit = False


def detect_fill_level(roi_frame):
    """
    在 ROI 区域内进行液面检测
    返回: (is_full, liquid_y_relative)
    """
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

# --- 全局变量用于鼠标交互 ---
select_start = None
select_end = None
is_selecting = False
# roi_rect is now defined globally above

def mouse_callback(event, x, y, flags, param):
    global select_start, select_end, is_selecting, roi_rect
    if event == cv2.EVENT_LBUTTONDOWN:
        is_selecting = True
        select_start = (x, y)
        select_end = (x, y)
        with roi_lock:
            roi_rect = None
    elif event == cv2.EVENT_MOUSEMOVE:
        if is_selecting:
            select_end = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        is_selecting = False
        select_end = (x, y)
        x1, y1 = select_start
        x2, y2 = select_end
        x_min, x_max = min(x1, x2), max(x1, x2)
        y_min, y_max = min(y1, y2), max(y1, y2)
        w, h = x_max - x_min, y_max - y_min
        if w > 10 and h > 10:
            with roi_lock:
                roi_rect = (x_min, y_min, w, h)
            print(f"✅ 新 ROI 已设定: {roi_rect}")
            save_roi_config(roi_rect, param['config_path'])
        else:
            print("⚠️ 区域太小，已忽略")

def tcp_server_thread():
    """
    TCP 服务器线程：接收 LabVIEW 发送的 ROI 坐标 (4个I32, Big Endian)
    并返回检测结果 (JSON 字符串)
    """
    global roi_rect, should_exit
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"[TCP] 🚀 服务器正在监听 {HOST}:{PORT}...")
        server_socket.settimeout(1.0) # 设置超时以便能够响应退出信号
    except Exception as e:
        print(f"[TCP] ❌ 绑定失败: {e}")
        return

    while not should_exit:
        try:
            conn, addr = server_socket.accept()
            print(f"[TCP] ✅ 连接来自: {addr}")
            conn.settimeout(None) 
            
            with conn:
                while not should_exit:
                    # 1. 接收 16 字节 (4 * 4 bytes)
                    # LabVIEW Flatten To String (Network order) -> I32, I32, I32, I32 (x, y, w, h)
                    try:
                        data = conn.recv(16)
                        if not data:
                            print(f"[TCP] 客户端 {addr} 断开连接")
                            break
                        
                        if len(data) != 16:
                            print(f"[TCP] ⚠️ 接收到的数据长度不足 16 字节: {len(data)}")
                            continue

                        # 2. 解包数据 (!iiii 表示 Network order, 4个 signed int)
                        # 如果 LabVIEW 发送的是 U32，可以使用 '!IIII'
                        x, y, w, h = struct.unpack('!iiii', data)
                        
                        # 更新全局 ROI
                        with roi_lock:
                            roi_rect = (x, y, w, h)
                        print(f"[TCP] 收到 ROI: {roi_rect}")

                        # 3. 执行检测 (使用最新的帧)
                        result_data = {'is_full': False, 'liquid_y': -1, 'status': 'error'}
                        
                        local_frame = None
                        with frame_lock:
                            if latest_frame is not None:
                                local_frame = latest_frame.copy()
                        
                        if local_frame is not None and w > 0 and h > 0:
                            # 确保坐标在图像范围内
                            h_img, w_img = local_frame.shape[:2]
                            x = max(0, min(x, w_img - 1))
                            y = max(0, min(y, h_img - 1))
                            w = min(w, w_img - x)
                            h = min(h, h_img - y)
                            
                            roi_frame = local_frame[y:y+h, x:x+w]
                            is_full, liquid_y = detect_fill_level(roi_frame)
                            
                            result_data['is_full'] = bool(is_full)
                            if liquid_y is not None:
                                result_data['liquid_y'] = int(liquid_y)
                                result_data['status'] = 'ok'
                            else:
                                result_data['status'] = 'no_liquid'
                        
                        # 4. 发送结果 (JSON 格式)
                        response = json.dumps(result_data)
                        conn.sendall(response.encode('utf-8'))
                        
                    except ConnectionResetError:
                        print("[TCP] 连接被重置")
                        break
                    except Exception as e:
                        print(f"[TCP] 处理出错: {e}")
                        break
                        
        except socket.timeout:
            continue # 检查 should_exit
        except Exception as e:
            print(f"[TCP] 接受连接出错: {e}")
            time.sleep(1)

    server_socket.close()
    print("[TCP] 服务器已停止")



def load_roi_config(path):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return tuple(data['roi'])
        except Exception as e:
            print(f"⚠️ 无法加载 ROI 配置: {e}")
    return None

def save_roi_config(roi, path):
    try:
        with open(path, 'w') as f:
            json.dump({'roi': roi}, f)
        print(f"💾 ROI 配置已保存至 {path}")
    except Exception as e:
        print(f"❌ 保存配置失败: {e}")

import time

def main():
    global roi_rect, latest_frame, should_exit
    
    parser = argparse.ArgumentParser(description="通用相机液面实时检测 (支持TCP)")
    parser.add_argument("--roi-config", default="roi_config.json", help="ROI 配置文件路径")
    parser.add_argument("--cam-index", type=int, default=0, help="摄像头索引 (通常为0)")
    args = parser.parse_args()

    # 1. 启动 TCP 服务器线程
    tcp_thread = threading.Thread(target=tcp_server_thread, daemon=True)
    tcp_thread.start()

    # 2. 初始化并打开相机 (OpenCV)
    print(f"正在打开索引为 {args.cam_index} 的相机...")
    # 优先尝试 DirectShow (Windows)
    cap = cv2.VideoCapture(args.cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"⚠️ 无法使用 CAP_DSHOW 打开索引 {args.cam_index}，尝试默认后端...")
        cap = cv2.VideoCapture(args.cam_index)
        if not cap.isOpened():
            print(f"❌ 无法打开相机索引 {args.cam_index}")
            should_exit = True
            return

    # 3. 配置相机参数 (如果支持)
    # cap.set(cv2.CAP_PROP_EXPOSURE, -5) # 示例值
    # cap.set(cv2.CAP_PROP_GAIN, GAIN)
    
    print(f"✅ 相机已启动 | 分辨率: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

    # 4. 加载 ROI
    with roi_lock:
        roi_rect = load_roi_config(args.roi_config)
    if roi_rect:
        print(f"ℹ️  已加载上次的 ROI: {roi_rect}")
    else:
        print("ℹ️  未找到 ROI 配置，请在画面中拖拽鼠标绘制。")

    # 5. 设置窗口和回调
    window_name = "Real-time Level Detection (TCP)"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, mouse_callback, {'config_path': args.roi_config})

    print("\n=== 操作指南 ===")
    print("🖱️  鼠标左键拖拽: 绘制/重新绘制检测区域 (ROI)")
    print("⌨️  'r': 清除当前 ROI")
    print("⌨️  'q' / ESC: 退出程序")
    print("================\n")

    try:
        while not should_exit:
            # 从 OpenCV 获取图像
            ret, frame = cap.read()
            if not ret:
                print("❌ 获取图像失败，重试中...")
                time.sleep(0.1)
                continue
            
            # 更新全局帧 (供 TCP 线程使用)
            with frame_lock:
                latest_frame = frame.copy()

            # --- 后续处理与显示 ---
            display_frame = frame.copy()
            
            # 获取当前 ROI (线程安全)
            current_roi = None
            with roi_lock:
                if roi_rect:
                    current_roi = roi_rect

            if is_selecting and select_start and select_end:
                cv2.rectangle(display_frame, select_start, select_end, (255, 0, 0), 1)

            if current_roi:
                x, y, w, h = current_roi
                h_img, w_img = frame.shape[:2]
                # 边界检查
                x, y = max(0, min(x, w_img - 1)), max(0, min(y, h_img - 1))
                w, h = min(w, w_img - x), min(h, h_img - y)
                
                if w > 0 and h > 0:
                    cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
                    roi_frame = frame[y:y+h, x:x+w]
                    is_full, liquid_y_rel = detect_fill_level(roi_frame)
                    
                    cv2.line(display_frame, (x, y + FULL_LINE_Y), (x+w, y + FULL_LINE_Y), (0, 0, 255), 2)
                    
                    status_text, status_color = "Searching...", (0, 165, 255)
                    if liquid_y_rel is not None:
                        liquid_y_abs = y + liquid_y_rel
                        cv2.line(display_frame, (x, liquid_y_abs), (x+w, liquid_y_abs), (0, 255, 0), 2)
                        if is_full:
                            status_text, status_color = "FULL", (0, 255, 0)
                        else:
                            status_text, status_color = "FILLING", (0, 255, 255)
                        cv2.putText(display_frame, f"Y: {liquid_y_rel}", (x, y - 5), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    cv2.putText(display_frame, status_text, (x, y + h + 25), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 2)

            cv2.imshow(window_name, display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                should_exit = True
                break
            elif key == ord('r'):
                with roi_lock:
                    roi_rect = None
                print("🔄 ROI 已重置")

    finally:
        should_exit = True
        # 7. 清理资源
        print("正在关闭相机...")
        if cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
        print("程序已退出。")


if __name__ == "__main__":
    main()
