import cv2
# 设置 OpenCV 日志级别为静默，避免读取冲突时的控制台报错
cv2.setLogLevel(0) # 0 = LOG_LEVEL_SILENT

import numpy as np
import argparse
import os
import json
import socket
import struct
import threading
import time
import sys
import traceback
import signal

def signal_handler(sig, frame):
    """信号处理函数，实现优雅退出"""
    global should_exit
    sig_name = "SIGTERM" if sig == signal.SIGTERM else "SIGINT"
    log_message(f"Received {sig_name}, exiting...")
    should_exit = True

# 绑定信号
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
if hasattr(signal, 'SIGBREAK'):
    signal.signal(signal.SIGBREAK, signal_handler) # Windows Ctrl+Break / taskkill /IM

# --- 全局日志记录 ---
LOG_FILE = "server_debug.log"

def log_message(msg):
    with open(LOG_FILE, "a", encoding='utf-8') as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {msg}\n")

def safe_print(msg):
    """安全的打印函数，防止因 stdout 管道断裂导致程序崩溃"""
    try:
        print(msg)
        sys.stdout.flush()
    except (BrokenPipeError, OSError) as e:
        # 如果 stdout 挂了，尝试记录到文件，但不抛出异常
        log_message(f"STDOUT Error (logging instead): {msg} | Error: {e}")
    except Exception as e:
        log_message(f"Print Error: {e}")

# 捕获所有未处理异常
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log_message(f"CRITICAL ERROR:\n{error_msg}")
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

# 启动即记录
# 强制 stdout 使用行缓冲 (Python 3.7+)
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass # 旧版本 Python 可能不支持

log_message("=== 服务脚本启动 ===")
log_message(f"Python Executable: {sys.executable}")
log_message(f"Working Directory: {os.getcwd()}")

# ===== 配置参数 ====
TOLERANCE = 5              # 像素容差
GRADIENT_THRESHOLD = 20    # 梯度阈值
CONFIRM_FRAMES = 3         # 连续确认帧数：只有连续 N 帧检测为满，才真正判定为满

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


def detect_fill_level(roi_frame, target_y_relative):
    """
    在 ROI 区域内进行液面检测 (工业精简优化版)
    :param roi_frame: ROI 图像区域
    :param target_y_relative: 目标满水线 Y 坐标 (相对于 ROI 顶部的像素距离)
    返回: (is_full, liquid_y_relative)
    """
    if roi_frame is None or roi_frame.size == 0:
        return False, None

    # 1. 轻量预处理：减小模糊半径 (3,3)，避免过度平滑掉真实的液面边缘
    gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    
    # 2. 边缘提取：减小 Sobel 核 (ksize=3)，让边缘更锐利
    sobel_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)

    surface_points = []
    h, w = sobel_y.shape
    step = 1 # 提高采样密度，从 2 改为 1
    
    for col in range(0, w, step):
        column_grad = sobel_y[:, col]
        
        # 寻找最强负梯度 (弯月面边缘)
        max_grad_idx = np.argmin(column_grad)
        max_grad_val = column_grad[max_grad_idx]
        
        # 阈值校验
        if max_grad_val < -GRADIENT_THRESHOLD: # 注意：由于是负梯度，用小于号
            surface_points.append(max_grad_idx)

    if not surface_points or len(surface_points) < (w * 0.2): # 至少 20% 覆盖
        return False, None

    # 3. 统计策略回归：使用众数 (Mode) 锁定水平直线
    # 使用 np.bincount 寻找出现次数最多的 Y 坐标，这对水平液面最有效
    counts = np.bincount(surface_points)
    liquid_y = np.argmax(counts)
    
    # 辅助校验：计算有多少点落在众数附近 (容差 2 像素)
    # 如果只有孤立的几个点，说明是噪声而不是直线
    support_count = np.sum((np.abs(np.array(surface_points) - liquid_y) <= 2))
    if support_count < (w * 0.15): # 支持点太少，判定为噪声
        return False, None

    # 4. 判定
    is_full = liquid_y <= (target_y_relative + TOLERANCE)
    return is_full, int(liquid_y)

import re

def robust_read_image(path, retries=3, delay=0.02):
    """
    尝试多次读取图像，解决 LabVIEW 正在写入时的冲突问题
    """
    for i in range(retries):
        if not os.path.exists(path):
            return None
            
        # 简单的文件大小检查，如果文件为空则跳过
        try:
            if os.path.getsize(path) == 0:
                time.sleep(delay)
                continue
        except OSError:
            time.sleep(delay)
            continue

        try:
            frame = cv2.imread(path)
            if frame is not None:
                return frame
        except Exception:
            pass
            
        time.sleep(delay)
    return None

def tcp_server_thread():
    """
    TCP 服务器线程：
    1. 接收 LabVIEW 发送的 ROI 坐标 (字符串格式, 如 "x1,y1,x2,y2\n")
    2. 读取本地图片 'temp/temp.bmp'
    3. 裁剪并检测液面
    4. 返回结果: b'\x01' (满) 或 b'\x00' (不满/错误)
    """
    global should_exit
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        log_message(f"Socket bound to {HOST}:{PORT}")
        safe_print(f"[TCP服务器] 正在监听 {HOST}:{PORT}...")
        safe_print(f"[TCP服务器] 等待 LabVIEW 连接并发送 ROI+满水线 (格式: x1,y1,x2,y2,target_y)")
        
        safe_print("SERVER_READY") # LabVIEW 可以扫描 stdout
        
        server_socket.settimeout(1.0)
    except Exception as e:
        log_message(f"Bind failed: {e}")
        safe_print(f"[TCP] ❌ 绑定失败: {e}")
        server_socket.close()
        return

    while not should_exit:
        try:
            conn, addr = server_socket.accept()
            log_message(f"New connection from {addr}")
            
            # 设置非阻塞模式，以便我们可以持续发送数据
            conn.setblocking(False)
            
            with conn:
                buffer = ""
                last_valid_params = None
                loop_count = 0
                full_counter = 0 # 用于连续帧确认的计数器
                
                while not should_exit:
                    loop_count += 1
                    # A. 尝试接收新参数 (非阻塞)
                    try:
                        data = conn.recv(1024)
                        if not data:
                            log_message(f"Connection closed by {addr}")
                            break
                        
                        log_message(f"Received bytes: {data}")
                        try:
                            text_chunk = data.decode('utf-8', errors='ignore')
                            buffer += text_chunk
                        except Exception as e:
                            log_message(f"Decode error: {e}")
                            
                        # 处理缓冲区
                        while '\n' in buffer or '\r' in buffer:
                            if '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                            elif '\r' in buffer:
                                line, buffer = buffer.split('\r', 1)
                            else:
                                break
                            
                            line = line.strip()
                            if not line: continue
                            
                            # --- 增加 RESET 指令处理 ---
                            if line.upper() == "RESET":
                                last_valid_params = None
                                full_counter = 0 # 重置计数器
                                safe_print("🔄 Reset received: Clearing parameters")
                                continue

                            safe_print(f"📥 Raw input: {line}")
                            numbers = re.findall(r'-?\d+', line)
                            if len(numbers) >= 5:
                                try:
                                    x1, y1, x2, y2, target_y_abs = map(int, numbers[:5])
                                    last_valid_params = (x1, y1, x2, y2, target_y_abs)
                                    full_counter = 0 # 参数更新，重置计数器
                                    safe_print(f"✅ Updated params: {last_valid_params}") # Changed to safe_print
                                except ValueError:
                                    pass
                            else:
                                safe_print(f"⚠️ Invalid format (need 5 nums): {line}") # Changed to safe_print
                                
                    except BlockingIOError:
                        pass # 无新数据
                    except socket.error as e:
                        # 真正的错误
                        if e.errno != 10035: # WSAEWOULDBLOCK
                             log_message(f"Socket error: {e}")
                             break

                    # B. 如果有有效参数，执行检测并发送结果
                    if last_valid_params:
                        x1, y1, x2, y2, target_y_abs = last_valid_params
                        
                        # 转换坐标
                        x = min(x1, x2)
                        y = min(y1, y2)
                        w = abs(x2 - x1)
                        h = abs(y2 - y1)
                        target_y_rel = target_y_abs - y

                        # 读取图片
                        img_path = os.path.join("temp", "temp.bmp")
                        is_full_result = False
                        read_success = False
                        
                        try:
                            frame = robust_read_image(img_path)
                            if frame is not None:
                                read_success = True
                                h_img, w_img = frame.shape[:2]
                                if w > 0 and h > 0:
                                    x = max(0, min(x, w_img - 1))
                                    y = max(0, min(y, h_img - 1))
                                    w = min(w, w_img - x)
                                    h = min(h, h_img - y)
                                    roi_frame = frame[y:y+h, x:x+w]
                                    is_full_now, _ = detect_fill_level(roi_frame, target_y_rel)

                                    # --- 核心改进：连续帧确认机制 ---
                                    if is_full_now:
                                        full_counter += 1
                                    else:
                                        full_counter = 0 # 只要有一帧不满足，立即重置计数器 (极其保守，防止误报)
                                    
                                    # 只有计数器达到阈值，才判定为真正满
                                    is_full_result = (full_counter >= CONFIRM_FRAMES)
                                    
                                    # 防止计数器无限增长
                                    if full_counter > CONFIRM_FRAMES:
                                        full_counter = CONFIRM_FRAMES
                                
                                # --- 发送结果 ---
                                try:
                                    resp_byte = b'\x01' if is_full_result else b'\x00'
                                    try:
                                        conn.sendall(resp_byte)
                                    except BlockingIOError:
                                        time.sleep(0.01)
                                        conn.sendall(resp_byte)
                                    
                                    # 打印状态
                                    if loop_count % 20 == 0 or is_full_result: # 满的时候立即打印
                                        status_icon = "🟢" if is_full_result else "⚪"
                                        # 如果正在确认中，显示黄色/中间状态图标
                                        if not is_full_result and full_counter > 0:
                                            status_icon = "🟡" 

                                        img_status = "📷OK" if read_success else "📷FAIL"
                                        safe_print(f"[{loop_count}] {img_status} | Detect: {status_icon} ({full_counter}/{CONFIRM_FRAMES}) | Sent: {resp_byte}")

                                except Exception as e:
                                    # 只有真正的错误才打印，避免刷屏
                                    if not isinstance(e, BlockingIOError):
                                        safe_print(f"❌ Send error: {e}")
                                    break
                            else:
                                # 读取失败（文件被占用等），不发送任何数据，等待下一轮重试
                                if loop_count % 20 == 0:
                                    safe_print(f"[{loop_count}] 📷FAIL | Waiting for file access...")
                        except Exception as e:
                            log_message(f"Process error: {e}")
                            pass # 读取或处理失败默认为跳过本轮
                    
                    # C. 稍微延时，避免 CPU 占用过高和网络拥塞
                    time.sleep(0.05) # 20Hz 更新率
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[TCP] 接受连接出错: {e}")
            time.sleep(1)

    server_socket.close()

def main():
    global should_exit
    
    # 1. 启动 TCP 服务器 (主线程直接运行)
    print("=== 液面检测服务 ===")
    tcp_server_thread()

if __name__ == "__main__":
    main()
