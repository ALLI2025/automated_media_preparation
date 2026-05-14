# tcp_server.py
import socket

HOST = '127.0.0.1'
PORT = 65432

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print("等待 LabVIEW 连接...")
    conn, addr = s.accept()
    with conn:
        print(f"已连接 {addr}")
        while True:
            # 控制逻辑：这里可以替换成你的实际判断逻辑
            user_input = input("输入 1（开）或 0（关）: ").strip()
            if user_input in ('0', '1'):
                conn.sendall(user_input.encode())
            else:
                break