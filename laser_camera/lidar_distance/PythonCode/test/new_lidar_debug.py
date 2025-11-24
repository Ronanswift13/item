import time
import serial

PORT = "/dev/tty.usbserial-1120"  # 你现在用到的端口
BAUD = 9600                       # 协议说明书指定的波特率

# 单次测距指令：ADDR=0x80, LEN=0x06, CMD=0x02, CS=0x78
SINGLE_MEASURE_CMD = bytes([0x80, 0x06, 0x02, 0x78])

def main():
    print(f"Opening {PORT} at {BAUD} bps ...")
    ser = serial.Serial(PORT, BAUD, timeout=0.5)

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    print("Port opened. Send SINGLE measure command & read response... (Ctrl+C to stop)")

    try:
        while True:
            # 1. 发送单次测距命令
            print("[TX]", SINGLE_MEASURE_CMD.hex(" ").upper())
            ser.write(SINGLE_MEASURE_CMD)
            ser.flush()

            # 2. 读取一帧返回（最多 32 字节）
            data = ser.read(32)
            if not data:
                print("[TIMEOUT] no data from device")
            else:
                print(f"[RX RAW] {len(data)} bytes:", data)

                try:
                    ascii_part = data[3:-1].decode(errors="ignore")
                    print("[RX ASCII]", repr(ascii_part))

                    if ascii_part.startswith("ERR--"):
                        print(">> MODULE ERROR:", ascii_part)
                    else:
                        # 正常情况下应该是类似 '012.345' 这样的 ASCII 距离
                        dist_m = float(ascii_part)
                        print(f">> DISTANCE = {dist_m} m  (~{dist_m*100:.1f} cm)")
                except Exception as e:
                    print(">> parse failed:", e)

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        ser.close()
        print("Serial port closed.")

if __name__ == "__main__":
    main()