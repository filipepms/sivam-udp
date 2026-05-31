import time
import board
import busio
import adafruit_tca9548a
from adafruit_lsm6ds.ism330dhcx import ISM330DHCX

# Create I2C bus and TCA object
i2c = busio.I2C(board.SCL, board.SDA)
tca = adafruit_tca9548a.TCA9548A(i2c)

print("🔍 Scanning all TCA9548A channels...\n")

for channel in range(8):
    print(f"Channel {channel}:", end=" ")

    # Try to lock, scan, and unlock
    if not tca[channel].try_lock():
        print("⚠️ could not acquire lock")
        continue

    time.sleep(0.005)  # small delay for mux settle
    devices = tca[channel].scan()
    tca[channel].unlock()

    if not devices:
        print("No devices found")
        continue

    print([hex(d) for d in devices])

    # Try initializing IMU if we see 0x6A or 0x6B
    for addr in devices:
        if addr in (0x6A, 0x6B):
            success = False
            for attempt in range(2):  # try twice if first fails
                try:
                    # Important: ensure bus is unlocked before init
                    time.sleep(0.005)
                    sensor = ISM330DHCX(tca[channel], address=addr)
                    print(f"  ✅ IMU at 0x{addr:02X} chip ID: 0x{sensor._chip_id:02X}")
                    success = True
                    break
                except Exception as e:
                    print(f"  ❌ Attempt {attempt+1}: Failed to init IMU at 0x{addr:02X}: {e}")
                    time.sleep(0.05)
            if not success:
                print(f"  🚫 Giving up on IMU at channel {channel}, addr 0x{addr:02X}")
