#!/usr/bin/env python3
"""
Exemplo de uso do script resample_data_raw.py

Este script demonstra como usar a funcionalidade de recuperação
de quaternions a partir de dados brutos de IMU.
"""

import numpy as np
from pathlib import Path
import sys

# Adicione o diretório ao path se necessário
sys.path.insert(0, '/home/pebimu3/sivam')

# Exemplo 1: Auto-detectar arquivos no diretório padrão
print("=" * 70)
print("Exemplo 1: Auto-detectar arquivos")
print("=" * 70)
print("\nCommand:")
print("  python resample_data_raw.py")
print("\nDescção: O script procura automaticamente pelos arquivos mais")
print("recentes no diretório /home/pebimu3/sivam/temp/")
print()

# Exemplo 2: Especificar arquivos manualmente
print("=" * 70)
print("Exemplo 2: Especificar arquivos manualmente")
print("=" * 70)
print("\nCommand:")
print("  python resample_data_raw.py \\")
print("    --raw-imu-file /home/pebimu3/sivam/temp/paciente_raw_imu_0.npy \\")
print("    --timestamp-file /home/pebimu3/sivam/temp/timestamp_0.npy")
print()

# Exemplo 3: Especificar taxa de amostragem alvo
print("=" * 70)
print("Exemplo 3: Especificar taxa de amostragem alvo")
print("=" * 70)
print("\nCommand:")
print("  python resample_data_raw.py \\")
print("    --raw-imu-file dados_raw.npy \\")
print("    --timestamp-file timestamps.npy \\")
print("    --target-rate 100.0")
print("\nDescção: Reamostre os dados para 100 Hz em vez de usar a taxa")
print("estimada a partir dos timestamps")
print()

# Exemplo 4: Usar tempo de calibração customizado
print("=" * 70)
print("Exemplo 4: Usar tempo de calibração customizado")
print("=" * 70)
print("\nCommand:")
print("  python resample_data_raw.py \\")
print("    --raw-imu-file dados_raw.npy \\")
print("    --timestamp-file timestamps.npy \\")
print("    --calibration-time 5.0")
print("\nDescção: Use 5 segundos iniciais para calibração do filtro Mahony")
print()

# Exemplo 5: Especificar arquivo de saída
print("=" * 70)
print("Exemplo 5: Especificar arquivo de saída")
print("=" * 70)
print("\nCommand:")
print("  python resample_data_raw.py \\")
print("    --raw-imu-file dados_raw.npy \\")
print("    --timestamp-file timestamps.npy \\")
print("    --output ./resultados/quaternions.sto")
print()

# Informações sobre como criar dados de teste
print("=" * 70)
print("Como criar dados de TESTE")
print("=" * 70)
print("\nSe você quiser testar o script com dados simulados:\n")

# Criar exemplo de dados de teste
test_script = '''
import numpy as np
from pathlib import Path

# Parâmetros
num_samples = 600
num_sensors = 8
rate = 48.0  # Hz

# Criar dados brutos simulados
# Estrutura: [accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z] * num_sensors
raw_imu_data = np.random.randn(num_samples, 6 * num_sensors).astype(np.float32)

# Criar timestamps realistas
start_time = 0.0
timestamps = np.arange(num_samples, dtype=np.float64) / rate + start_time
# Reshape para (N, 1) como esperado
timestamps = timestamps.reshape(-1, 1)

# Salvar dados
output_dir = Path('/home/pebimu3/sivam/temp')
np.save(output_dir / 'test_raw_imu_0.npy', raw_imu_data)
np.save(output_dir / 'timestamp_test.npy', timestamps)

print(f"Dados de teste criados!")
print(f"  raw_imu_data: shape {raw_imu_data.shape}")
print(f"  timestamps: shape {timestamps.shape}")
print(f"  Taxa: {rate} Hz")
'''

print(test_script)

print("\nDepois, execute:")
print("  python resample_data_raw.py \\")
print("    --raw-imu-file /home/pebimu3/sivam/temp/test_raw_imu_0.npy \\")
print("    --timestamp-file /home/pebimu3/sivam/temp/timestamp_test.npy")
print()

# Informações sobre estrutura de dados
print("=" * 70)
print("Estrutura dos Dados de Entrada")
print("=" * 70)
print("""
ARQUIVO: *_raw_imu_*.npy
- Shape: (N_amostras, 6*N_sensores)
- Exemplo com 8 sensores: (1000, 48)
- Estrutura por sensor (6 valores):
  [accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z]

ARQUIVO: timestamp_*.npy  
- Shape: (N_amostras, 1) - IMPORTANTE: deve ser 2D!
- Coluna 0: Tempo em segundos
- Deve ter os mesmos N_amostras que o arquivo raw_imu

SAÍDA: *_quat_*_resampled_*.sto
- Formato: OpenSim .sto (Tab-separado)
- Contém quaternions em formato w,x,y,z para cada sensor
- Pronto para importar no OpenSim
""")

# Informações sobre integração
print("=" * 70)
print("Próximos Passos no OpenSim")
print("=" * 70)
print("""
1. Abra seu modelo no OpenSim
2. Carregue o arquivo .sto em:
   - File > Import IK Results/Motion Files
3. Configure os rótulos dos sensores para corresponder ao seu modelo
4. Use os quaternions para análise de movimento
""")
