#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钧舵 ERG32-150 极简 Modbus RTU 控制脚本（Simple & Stupid）

用法：
  python dianzhua.py enable       # 夹爪+旋转 使能
  python dianzhua.py close        # 夹爪闭合（位置=GRIP_CLOSE_POS、速度=FF、力=FF）
  python dianzhua.py open         # 夹爪打开（位置=00、速度=FF、力=FF）
  python dianzhua.py rotate360    # 旋转到绝对位置 360°
  python dianzhua.py disable      # 关闭使能
  python dianzhua.py demo         # 依次执行：使能→闭合→旋转→打开→关闭

仅保留最小必要逻辑，不做端口扫描与状态等待。
如无响应，请手动改动 SERIAL_PORT / SLAVE_ID / PARITY。
"""

import sys
import time
from pymodbus.client import ModbusSerialClient

# ========= 配置（按需修改） =========
SERIAL_PORT = 'COM9'   # Windows 示例；Linux 可用 '/dev/ttyUSB0'
SLAVE_ID    = 9        # 设备站号（默认 1 或 9，视设备而定）
BAUDRATE    = 115200   # 波特率
PARITY      = 'N'      # 8E1：多数 Modbus RTU 设备默认；不通可改 'N'
TIMEOUT_S   = 2        # 串口超时秒
# ==================================
        
# ===== 运行行为配置（按需修改） =====
AUTO_ENABLE = True          # 执行动作前自动使能，避免单独命令无响应
AUTO_DISABLE_AT_END = False # 脚本结束是否自动关闭使能（默认不关闭）
# ==================================

# ===== 夹爪位置配置（按需修改） =====
GRIP_CLOSE_POS = 0x00FF  # 闭合位置（0x00-0xFF，越大越闭合；默认略小于满闭合）
# ==================================

# ===== 动作间延时（可按实际速度调整） =====
DELAY_ENABLE     = 5.0
DELAY_CLOSE      = 2.0
DELAY_ROTATE360  = 3.0
DELAY_OPEN       = 2.0
DELAY_DISABLE    = 0.5
# ==================================


def wr(client, addr, values):
    """智能写寄存器：单寄存器优先用 FC06，多寄存器用 FC16。"""
    try:
        if isinstance(values, (list, tuple)) and len(values) == 1:
            r = client.write_register(address=addr, value=values[0], slave=SLAVE_ID)
        else:
            r = client.write_registers(address=addr, values=values, slave=SLAVE_ID)
    except Exception as e:
        print(f"❌ 写寄存器异常 addr=0x{addr:04X} values={values}: {e}")
        return None
    if r is None or (hasattr(r, 'isError') and r.isError()):
        print(f"⚠️ 写寄存器失败 addr=0x{addr:04X} values={values}: {r}")
    return r

def rd(client, addr, count):
    """读保持寄存器（FC03），返回列表或 None。"""
    try:
        r = client.read_holding_registers(address=addr, count=count, slave=SLAVE_ID)
    except Exception as e:
        print(f"❌ 读寄存器异常 addr=0x{addr:04X} count={count}: {e}")
        return None
    if r is None or (hasattr(r, 'isError') and r.isError()):
        print(f"⚠️ 读寄存器失败 addr=0x{addr:04X} count={count}: {r}")
        return None
    return getattr(r, 'registers', None)

def rd_input(client, addr, count):
    """读输入寄存器（FC04），返回列表或 None。"""
    try:
        r = client.read_input_registers(address=addr, count=count, slave=SLAVE_ID)
    except Exception as e:
        print(f"❌ 读输入寄存器异常 addr=0x{addr:04X} count={count}: {e}")
        return None
    if r is None or (hasattr(r, 'isError') and r.isError()):
        print(f"⚠️ 读输入寄存器失败 addr=0x{addr:04X} count={count}: {r}")
        return None
    return getattr(r, 'registers', None)

def rd_coils(client, addr, count):
    """读线圈（FC01），返回列表或 None。"""
    try:
        r = client.read_coils(address=addr, count=count, slave=SLAVE_ID)
    except Exception as e:
        print(f"❌ 读线圈异常 addr=0x{addr:04X} count={count}: {e}")
        return None
    if r is None or (hasattr(r, 'isError') and r.isError()):
        print(f"⚠️ 读线圈失败 addr=0x{addr:04X} count={count}: {r}")
        return None
    return getattr(r, 'bits', None)

def pause(tag, seconds):
    print(f'⏳ 等待 {seconds:.1f}s ({tag})...')
    time.sleep(seconds)


def enable(client):
    print('🔧 使能...')
    wr(client, 0x03E8, [0x0101])  # 夹爪：rACT=1, rMODE=1（按说明书可为 0/1）
    wr(client, 0x03E9, [0x0101])  # 旋转：同样使能


def disable(client):
    print('🔌 关闭使能...')
    wr(client, 0x03E8, [0x0000])
    wr(client, 0x03E9, [0x0000])


def close_grip(client):
    print('夹爪闭合...')
    # 设置目标位置与速度
    wr(client, 0x03EA, [GRIP_CLOSE_POS, 0x00FF])
    # 触发位采用脉冲：先清零，再置1，确保设备识别新动作
    wr(client, 0x03EB, [0x0000 | 0x00FF])
    time.sleep(0.05)
    wr(client, 0x03EB, [0x0100 | 0x00FF])


def open_grip(client):
    print('夹爪打开...')
    # 设置目标位置与速度
    wr(client, 0x03EA, [0x0000, 0x00FF])
    # 触发位采用脉冲：先清零，再置1
    wr(client, 0x03EB, [0x0000 | 0x00FF])
    time.sleep(0.05)
    wr(client, 0x03EB, [0x0100 | 0x00FF])


def rotate_360(client):
    print('🔄 旋转到 360°...')
    wr(client, 0x03EC, [0x0168])             # 绝对位置 360°
    wr(client, 0x03ED, [0xFFFF])             # 速度=FF, 扭矩=FF（同一个寄存器按高低字节）
    # 触发采用脉冲：先清零，再置1
    wr(client, 0x03EF, [0x0001])             # 圈数=1, 触发位=0
    time.sleep(0.05)
    wr(client, 0x03EF, [0x0101])             # 触发=1, 圈数=1

def status_diag(client):
    """读取关键寄存器区段，便于诊断（尝试 Holding/Input/Coils）。"""
    ranges = [0x03E8, 0x03EA, 0x03EC, 0x0400, 0x0000]
    cnt = 6
    for base in ranges:
        print(f"🔎 扫描地址段 0x{base:04X}（{cnt} 个）...")
        h = rd(client, base, cnt)
        if h is not None:
            print("  Holding:", " ".join(f"[{base+i:04X}]=0x{v:04X}" for i, v in enumerate(h)))
        else:
            print("  Holding: 读取失败")
        inp = rd_input(client, base, cnt)
        if inp is not None:
            print("  Input:  ", " ".join(f"[{base+i:04X}]=0x{v:04X}" for i, v in enumerate(inp)))
        else:
            print("  Input:   读取失败")
        coils = rd_coils(client, base, min(cnt*8, 16))
        if coils is not None:
            print("  Coils:  ", " ".join(f"[{base+i:04X}]={int(v)}" for i, v in enumerate(coils)))
        else:
            print("  Coils:   读取失败")

def quick_scan(client):
    """快速扫描常见基址，找出能读的功能码与地址范围。"""
    bases = [0x0000, 0x0100, 0x0200, 0x0300, 0x03E8, 0x0400, 0x0500]
    for base in bases:
        print(f"🔍 试读 Holding 0x{base:04X}~0x{base+7:04X}")
        h = rd(client, base, 8)
        ok_h = h is not None
        if ok_h:
            print(f"    结果: OK")
            print("    值:   ", " ".join(f"[{base+i:04X}]=0x{v:04X}" for i, v in enumerate(h)))
        else:
            print(f"    结果: FAIL")
        print(f"🔍 试读 Input   0x{base:04X}~0x{base+7:04X}")
        i = rd_input(client, base, 8)
        ok_i = i is not None
        if ok_i:
            print(f"    结果: OK")
            print("    值:   ", " ".join(f"[{base+i:04X}]=0x{v:04X}" for i, v in enumerate(i)))
        else:
            print(f"    结果: FAIL")
        print(f"🔍 试读 Coils   0x{base:04X}~0x{base+15:04X}")
        c = rd_coils(client, base, 16)
        ok_c = c is not None
        if ok_c:
            print(f"    结果: OK")
            print("    值:   ", " ".join(f"[{base+i:04X}]={int(v)}" for i, v in enumerate(c)))
        else:
            print(f"    结果: FAIL")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    client = ModbusSerialClient(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        bytesize=8,
        parity=PARITY,
        stopbits=1,
        timeout=TIMEOUT_S,
    )

    if not client.connect():
        print(f"❌ 无法打开串口 {SERIAL_PORT}，请检查线缆/端口占用/权限")
        return

    try:
        # 执行动作前自动使能（除 disable 以外）
        if AUTO_ENABLE and cmd in ('close', 'open', 'rotate360', 'demo'):
            enable(client);       pause('enable', DELAY_ENABLE)
        if cmd == 'close':
            close_grip(client);   pause('close', DELAY_CLOSE)
        elif cmd == 'open':
            open_grip(client);    pause('open', DELAY_OPEN)
        elif cmd == 'rotate360':
            rotate_360(client);   pause('rotate360', DELAY_ROTATE360)
        elif cmd == 'disable':
            disable(client);      pause('disable', DELAY_DISABLE)
        elif cmd == 'status':
            status_diag(client)
        elif cmd == 'scan':
            quick_scan(client)
        elif cmd == 'demo':
            close_grip(client);   pause('close', DELAY_CLOSE)
            rotate_360(client);   pause('rotate360', DELAY_ROTATE360)
            open_grip(client);    pause('open', DELAY_OPEN)
            if AUTO_DISABLE_AT_END:
                disable(client);  pause('disable', DELAY_DISABLE)
        else:
            print('❓ 未知命令：', cmd)
            print('用法: python dianzhua.py [enable|close|open|rotate360|disable|status|scan|demo]')
            return
        print('命令执行完毕')
    except Exception as e:
        print('❌ 错误:', e)
    finally:
        client.close()


if __name__ == '__main__':
    main()