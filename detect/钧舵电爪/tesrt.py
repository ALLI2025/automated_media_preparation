#!/usr/bin/env python3
"""
极简伺服485通讯测试脚本
依赖: pymodbus
pip install pymodbus
"""

import sys
import time
from pymodbus.client import ModbusSerialClient

# -------------------- 配置 --------------------
PORT = 'COM9'      # 改成你的串口号
SLAVE = 1          # 驱动器站号
BAUD = 9600
# ---------------------------------------------

def ok(txt):
    print(f"[OK] {txt}")

def fail(txt):
    print(f"[FAIL] {txt}")
    sys.exit(1)

def main():
    cli = ModbusSerialClient(port=PORT, baudrate=BAUD, timeout=1)
    if not cli.connect():
        fail("串口打开失败")

    try:
        # 1. 启停模式→485
        rq = cli.write_register(address=0x0000, value=5, slave=SLAVE)
        if rq.isError():
            fail("设置启停模式")
        ok("启停模式→485")

        # 2. 转速来源→485
        rq = cli.write_register(address=0x0001, value=4, slave=SLAVE)
        if rq.isError():
            fail("设置转速来源")
        ok("转速来源→485")

        # 3. 设定转速3000
        rq = cli.write_register(address=0x2001, value=3000, slave=SLAVE)
        if rq.isError():
            fail("设置转速")
        ok("设定转速3000")

        # 4. 启动
        rq = cli.write_register(address=0x2000, value=7, slave=SLAVE)
        if rq.isError():
            fail("启动")
        ok("启动电机")

        time.sleep(2)

        # 5. 读状态
        rr = cli.read_holding_registers(address=0x2002, count=1, slave=SLAVE)
        if rr.isError():
            fail("读取状态")
        ok(f"状态字: {rr.registers[0]}")

        # 6. 停止
        rq = cli.write_register(address=0x2000, value=6, slave=SLAVE)
        if rq.isError():
            fail("停止")
        ok("停止电机")

    finally:
        cli.close()

if __name__ == '__main__':
    main()