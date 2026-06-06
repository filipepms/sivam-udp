import os

#arquivo para chamar o resample_data_raw.py para automatizar o processo de resampling dos dados
from pathlib import Path
import subprocess

from resample_data_raw import find_latest_file

def main():
    base_dir = Path("/home/pebimu3/sivam/temp/todos")
    for i in range(1):
        try:
            timestamp_file = base_dir / f"timestamp_{103+i}.npy"
            raw_imu_file = base_dir / f"raw_imu_{103+i}.npy"
            
            print(f"Usando timestamp: {timestamp_file}")
            print(f"Usando raw IMU: {raw_imu_file}")

            # Chamar o script de resampling
            subprocess.run([
                "/home/pebimu3/miniforge3/envs/opensim-env311/bin/python",
                "resample_data_raw.py",
                "--timestamp-file", str(timestamp_file),
                "--raw-imu-file", str(raw_imu_file),
                "--target-rate", "48.0",
                "--calibration-time", "4.0",
            ], check=True)
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    main()


   