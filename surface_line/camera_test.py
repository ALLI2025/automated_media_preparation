import cv2
import time

print("1. 脚本开始执行")

# 尝试用不同的后端 API 打开摄像头
camera_index = 1
print(f"2. 尝试打开摄像头，索引: {camera_index}")

cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW) # 使用 DirectShow 后端，在 Windows 上更稳定

if not cap.isOpened():
    print(f"!! 错误: 使用 CAP_DSHOW 无法打开摄像头索引 {camera_index}")
    print("   正在尝试默认后端...")
    cap = cv2.VideoCapture(camera_index) # 尝试默认后端
    if not cap.isOpened():
        print(f"!! 致命错误: 使用默认后端也无法打开摄像头索引 {camera_index}")  
        print("   请确认：")
        print("   - 摄像头已正确连接并已安装驱动。")
        print("   - 摄像头没有被其他程序（如 Zoom, Skype, Windows相机）占用。")
        print("   - 如果有多个摄像头，尝试更改 camer-index 的值 (例如 1, 2)。")
        exit()

print("3. 摄像头成功打开")

# 设置一个较低的分辨率，以提高兼容性
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
print("4. 已设置分辨率为 640x480")

window_name = "Camera Test - Press 'q' to quit"
cv2.namedWindow(window_name)
print(f"5. 创建窗口: '{window_name}'")

frame_count = 0
while True:
    print(f"--- 循环开始: 第 {frame_count + 1} 帧 ---")
    
    ret, frame = cap.read()
    print(f"  - cap.read() 返回值: ret={ret}")

    if not ret:
        print("  !! 错误: 无法从摄像头读取帧。")
        time.sleep(1) # 等待一秒再试
        continue

    print("  - 成功读取帧")
    cv2.imshow(window_name, frame)
    print("  - cv2.imshow() 已调用")

    key = cv2.waitKey(1) & 0xFF
    if key != 255: # 255 表示没有按键
        print(f"  - 检测到按键: ASCII码={key}, 字符='{chr(key)}'")

    if key == ord('q'):
        print("  - 按下 'q'，准备退出循环")
        break
    
    frame_count += 1
    print(f"--- 循环结束: 第 {frame_count} 帧 ---")
    time.sleep(0.1) # 稍微减慢循环速度，方便观察日志

print("6. 循环已退出")

cap.release()
print("7. 摄像头已释放 (cap.release())")

cv2.destroyAllWindows()
print("8. 所有窗口已销毁 (cv2.destroyAllWindows())")

print("9. 脚本正常结束")