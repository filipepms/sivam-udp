#import os
#from adafruit_blinka.agnostic import detector

#print(f"Board ID: {detector.board.id}")
#print(f"Chip ID: {detector.chip.id}")
#print(f"Is Raspberry Pi: {detector.board.any_raspberry_pi}")
#print(f"Is Raspberry Pi 5: {'raspberrypi_5' == detector.board.id}")

import adafruit_bus_device.i2c_device
print(adafruit_bus_device.i2c_device.__file__)

from adafruit_bus_device.i2c_device import I2CDevice
help(I2CDevice.write)