"""Resample de raw data timestamps reais.

Objetivo:
- Ler um arquivo .npy de dados brutos (gravado com passo assumido constante).
- Ler um arquivo timestamp_*.npy (coluna 0 = timestamp real).
- Reinterpolar os dados para uma nova malha temporal constante.
- Aplicar matrizes de rotação aos dados de aceleração e velocidade angular.
- Utilizar o filtro de Mahony para reconstruir os quaternions a partir dos dados brutos reamostrados.
- Salvar um novo .sto corrigido.
"""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from scipy.interpolate import interp1d
import ahrs


def find_latest_file(base_dir: Path, pattern: str) -> Path:
    candidates = sorted(base_dir.rglob(pattern), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"Nenhum arquivo encontrado para o padrão '{pattern}' em {base_dir}")
    return candidates[-1]


def load_raw_imu_data(raw_imu_file: Path) -> np.ndarray:
    """Carrega dados brutos de IMU (aceleração + giroscópio).
    
    Esperado shape: (N, 6*num_sensores) onde:
    - Primeiros 3 valores por sensor: aceleração (x, y, z)
    - Próximos 3 valores por sensor: giroscópio (x, y, z)
    """
    data = np.load(raw_imu_file)
    if data.ndim != 2:
        raise ValueError(f"Arquivo de IMU bruto inválido: {raw_imu_file}. Esperado array 2D.")
    return data


def load_timestamps(timestamp_file: Path) -> np.ndarray:
    data = np.load(timestamp_file)
    if data.ndim != 2 or data.shape[1] < 1:
        raise ValueError(f"Arquivo de timestamp inválido: {timestamp_file}. Esperado array (N, >=1).")
    timestamps = data[:, 0].astype(float)
    return timestamps


def estimate_rate(timestamps: np.ndarray) -> float:
    dt = np.diff(timestamps)
    dt = dt[dt > 0]
    if len(dt) == 0:
        raise ValueError("Não foi possível estimar taxa: delta t inválido.")
    return 1.0 / float(np.median(dt))


def build_rotation_matrices(num_sensors: int) -> np.ndarray:
    """Constrói as matrizes de rotação para cada sensor.
    
    Baseado em helper.py compute_quat. Define rotações específicas para diferentes
    tipos de sensores (pelvis, perna esquerda, perna direita, pé).
    
    Parameters
    ----------
    num_sensors : int
        Número de sensores
        
    Returns
    -------
    np.ndarray
        Array de shape (num_sensors, 3, 3) com as matrizes de rotação
    """
    d2g = np.pi / 180.0  # Constant to convert degrees to radians
    
    z_neg_90 = np.array([[0, 1.0, 0], [-1., 0, 0], [0, 0, 1.0]])
    y_180 = np.array([[-1.0, 0, 0], [0, 1.0, 0], [0, 0, -1.0]])
    z_180 = np.array([[-1.0, 0, 0], [0, -1.0, 0], [0, 0, 1.0]])
    y_neg_90 = np.array([[0, 0, -1.0], [0, 1.0, 0], [1.0, 0, 0]])
    
    ankle_offset = -100. * d2g
    x_pos_ankle = np.array([
        [1.0, 0, 0],
        [0, np.cos(ankle_offset), -np.sin(ankle_offset)],
        [0, np.sin(ankle_offset), np.cos(ankle_offset)]
    ])
    
    hip_rot = np.matmul(y_neg_90, z_180)
    foot_rot = np.matmul(x_pos_ankle, hip_rot)
    r_leg_rot = z_neg_90
    l_leg_rot = np.matmul(z_neg_90, y_180)
    
    # Mapeamento de rotação baseado na posição do sensor
    # 0: hip/torso/head, 1: left side, 2: right side, 3: foot
    rot_type = [0, 0, 1, 1, 3, 2, 2, 3, 1, 1, 1, 2, 2, 2]  # Padrão padrão
    
    rot_mats = np.zeros((num_sensors, 3, 3))
    for i in range(num_sensors):
        rot_idx = rot_type[i] if i < len(rot_type) else 0
        if rot_idx == 0:  # hip, torso, head
            rot_mats[i, :, :] = hip_rot
        elif rot_idx == 1:  # left side
            rot_mats[i, :, :] = l_leg_rot
        elif rot_idx == 2:  # right side
            rot_mats[i, :, :] = r_leg_rot
        elif rot_idx == 3:  # foot
            rot_mats[i, :, :] = foot_rot
        else:
            rot_mats[i, :, :] = np.eye(3)
    
    return rot_mats


def resample_raw_imu_data(
    timestamps: np.ndarray,
    raw_imu_data: np.ndarray,
    target_rate: float,
    signals_per_sensor: int = 6
) -> tuple:
    """Reamostre dados brutos de IMU para taxa constante.
    
    Usa interpolação linear para reinterpolar aceleração e giroscópio.
    
    Parameters
    ----------
    timestamps : np.ndarray
        Timestamps dos dados originais (shape: (N,))
    raw_imu_data : np.ndarray
        Dados brutos de IMU (shape: (N, 6*num_sensores))
    target_rate : float
        Taxa de amostragem alvo em Hz
    signals_per_sensor : int
        Número de sinais por sensor (padrão 6: acelerometro 3D + giroscópio 3D)
        
    Returns
    -------
    tuple
        (timestamps_resampled, imu_data_resampled)
    """
    # Remover timestamps duplicados/não crescentes
    keep = np.ones(len(timestamps), dtype=bool)
    keep[1:] = np.diff(timestamps) > 0.0
    timestamps_clean = timestamps[keep]
    imu_data_clean = raw_imu_data[keep, :]
    
    if len(timestamps_clean) < 2:
        raise ValueError("Após remover timestamps duplicados, restaram menos de 2 amostras.")
    
    # Construir nova base temporal uniforme
    t0 = timestamps_clean[0]
    t1 = timestamps_clean[-1]
    if t1 <= t0:
        raise ValueError("Range de tempo inválido para resample.")
    
    n_samples = int(np.floor((t1 - t0) * target_rate)) + 1
    n_samples = max(n_samples, 2)
    timestamps_resampled = t0 + np.arange(n_samples, dtype=float) / target_rate
    
    # Interpolar cada coluna de dados
    num_signal_types = imu_data_clean.shape[1]
    imu_data_resampled = np.zeros((len(timestamps_resampled), num_signal_types))
    
    for col in range(num_signal_types):
        f = interp1d(
            timestamps_clean,
            imu_data_clean[:, col],
            kind='linear',
            bounds_error=False,
            fill_value='extrapolate'
        )
        imu_data_resampled[:, col] = f(timestamps_resampled)
    
    return timestamps_resampled, imu_data_resampled


def generate_quaternions_from_imu(
    imu_data: np.ndarray,
    rate: float,
    rot_mats: np.ndarray,
    sensors_labels: list = None,
    signals_per_sensor: int = 6,
    calibration_samples: int = None
) -> tuple:
    """Gera quaternions a partir de dados de IMU usando filtro Mahony.
    
    Parameters
    ----------
    imu_data : np.ndarray
        Dados de IMU reamostrados (shape: (N, 6*num_sensores))
    rate : float
        Taxa de amostragem em Hz
    rot_mats : np.ndarray
        Matrizes de rotação para cada sensor
    sensors_labels : list, optional
        Rótulos dos sensores
    signals_per_sensor : int
        Número de sinais por sensor
    calibration_samples : int, optional
        Número de amostras iniciais para calibração. Se None, não usa calibração.
        
    Returns
    -------
    tuple
        (quaternions, timestamps, sensor_labels)
        - quaternions: shape (N, num_sensores, 4) em formato w,x,y,z
        - timestamps: timestamps para os quaternions
        - sensor_labels: rótulos dos sensores
    """
    num_sensors = imu_data.shape[1] // signals_per_sensor
    num_samples = imu_data.shape[0]
    
    if sensors_labels is None:
        sensors_labels = [f"sensor_{i}" for i in range(num_sensors)]
    
    # Inicializar quaternions
    quaternions = np.zeros((num_samples, num_sensors, 4))
    quaternions[:, :, 0] = 1.0  # w = 1, x,y,z = 0 (quaternion neutro)
    
    # Inicializar filtros Mahony para cada sensor
    madgwick_filters = [ahrs.filters.Mahony(frequency=rate) for _ in range(num_sensors)]
    
    # Fase de calibração (opcional)
    if calibration_samples is not None and calibration_samples > 0:
        print(f"Calibrando com {calibration_samples} amostras...")
        for t in range(1, min(calibration_samples, num_samples)):
            for i in range(num_sensors):
                s_off = i * signals_per_sensor
                accel_raw = imu_data[t, s_off:s_off+3]
                gyro_raw = imu_data[t, s_off+3:s_off+6]
                
                # Aplicar matrizes de rotação
                accel = np.matmul(accel_raw, rot_mats[i, :, :])
                gyro = np.matmul(gyro_raw, rot_mats[i, :, :])
                
                # Atualizar quaternion
                quaternions[t, i, :] = madgwick_filters[i].updateIMU(
                    quaternions[t-1, i, :],
                    gyro,
                    accel
                )
        start_idx = calibration_samples
    else:
        start_idx = 1
    
    # Processar dados normais
    print(f"Gerando quaternions para {num_samples} amostras...")
    for t in range(start_idx, num_samples):
        for i in range(num_sensors):
            s_off = i * signals_per_sensor
            accel_raw = imu_data[t, s_off:s_off+3]
            gyro_raw = imu_data[t, s_off+3:s_off+6]
            
            # Aplicar matrizes de rotação
            accel = np.matmul(accel_raw, rot_mats[i, :, :])
            gyro = np.matmul(gyro_raw, rot_mats[i, :, :])
            
            # Atualizar quaternion
            quaternions[t, i, :] = madgwick_filters[i].updateIMU(
                quaternions[t-1, i, :],
                gyro,
                accel
            )
        
        if (t + 1) % max(1, num_samples // 10) == 0:
            print(f"  Progresso: {(t+1)/num_samples*100:.1f}%")
    
    timestamps = np.arange(num_samples) / rate
    
    return quaternions, timestamps, sensors_labels


def write_quat_sto(output_file: Path, sensor_labels, times: np.ndarray, quats_wxyz: np.ndarray, rate: float):
    with open(output_file, "w") as f:
        f.write(f"DataRate={rate}\n")
        f.write("DataType=Quaternion\n")
        f.write("version=3\n")
        f.write("OpenSimVersion=4.2\n")
        f.write("endheader\n")
        f.write("time\t" + "\t".join(sensor_labels) + "\n")

        for i, t in enumerate(times):
            line = [f"{t:.9f}"]
            for s in range(len(sensor_labels)):
                w, x, y, z = quats_wxyz[i, s, :]
                line.append(f"{w:.12g},{x:.12g},{y:.12g},{z:.12g}")
            f.write("\t".join(line) + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Reconstruir quaternions de arquivo .npy de dados brutos de IMU")
    parser.add_argument(
        "--raw-imu-file",
        type=str,
        default=None,
        help="Caminho do arquivo .npy com dados brutos de IMU"
    )
    parser.add_argument(
        "--timestamp-file",
        type=str,
        default=None,
        help="Caminho do arquivo timestamp_*.npy"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Caminho do .sto de saída"
    )
    parser.add_argument(
        "--target-rate",
        type=float,
        default=None,
        help="Taxa de saída (Hz). Se omitido, usa taxa estimada pelos timestamps"
    )
    parser.add_argument(
        "--calibration-time",
        type=float,
        default=2.0,
        help="Tempo de calibração inicial em segundos (padrão: 2.0)"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default="/home/pebimu3/sivam/temp/",
        help="Diretório base para busca automática quando arquivos não são informados"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    base_dir = Path(args.base_dir).expanduser().resolve()

    # Encontrar arquivos de entrada
    raw_imu_file = None
    timestamp_file = None
    
    if args.raw_imu_file:
        raw_imu_file = Path(args.raw_imu_file).expanduser().resolve()
    else:
        try:
            raw_imu_file = find_latest_file(base_dir, "*_raw_imu_*.npy")
        except FileNotFoundError:
            print("Aviso: Nenhum arquivo raw_imu encontrado")
    
    if args.timestamp_file:
        timestamp_file = Path(args.timestamp_file).expanduser().resolve()
    else:
        try:
            timestamp_file = find_latest_file(base_dir, "timestamp_*.npy")
        except FileNotFoundError:
            print("Aviso: Nenhum arquivo timestamp encontrado")
    
    if not raw_imu_file or not timestamp_file:
        print("\nErro: Não foi possível encontrar os arquivos de entrada.")
        print("Forneça os caminhos manualmente:")
        print("  python resample_data_raw.py --raw-imu-file <path> --timestamp-file <path>")
        return
    
    print(f"Lendo dados brutos de IMU: {raw_imu_file}")
    print(f"Lendo timestamps: {timestamp_file}")
    
    # Carregar dados
    raw_imu_data = load_raw_imu_data(raw_imu_file)
    timestamps = load_timestamps(timestamp_file)
    
    num_sensors = raw_imu_data.shape[1] // 6
    print(f"Dados carregados: {raw_imu_data.shape[0]} amostras x {raw_imu_data.shape[1]} sinais ({num_sensors} sensores)")
    print(f"Timestamps: {len(timestamps)} amostras")
    
    # Sincronizar tamanhos
    n = min(len(timestamps), len(raw_imu_data))
    if len(timestamps) != len(raw_imu_data):
        print(f"Aviso: tamanhos diferentes. Usando {n} amostras (mínimo).")
    timestamps = timestamps[:n]
    raw_imu_data = raw_imu_data[:n]
    
    # Estimar taxa
    estimated_rate = estimate_rate(timestamps)
    target_rate = args.target_rate if args.target_rate and args.target_rate > 0 else estimated_rate
    
    print(f"\nTaxa estimada pelos timestamps: {estimated_rate:.6f} Hz")
    print(f"Taxa alvo: {target_rate:.6f} Hz")
    
    # Reamostrar dados
    print("\nResampling dos dados de IMU...")
    timestamps_resampled, imu_data_resampled = resample_raw_imu_data(
        timestamps,
        raw_imu_data,
        target_rate,
        signals_per_sensor=6
    )
    print(f"Resampling concluído: {len(timestamps_resampled)} amostras")
    
    # Construir matrizes de rotação
    print("\nConstruindo matrizes de rotação...")
    rot_mats = build_rotation_matrices(num_sensors)
    
    # Gerar rótulos de sensores
    sensor_labels_full = [
        'pelvis_imu', 'torso_imu',
        'femur_l_imu', 'tibia_l_imu', 'calcn_l_imu',
        'femur_r_imu', 'tibia_r_imu', 'calcn_r_imu',
        'humerus_l_imu', 'ulna_l_imu', 'hand_l_imu',
        'humerus_r_imu', 'ulna_r_imu', 'hand_r_imu'
    ]
    sensor_labels = sensor_labels_full[:num_sensors]
    
    # Gerar quaternions
    print("\nGerando quaternions com Mahony filter...")
    calibration_samples = int(args.calibration_time * target_rate) if args.calibration_time else None
    
    quaternions, times_quat, _ = generate_quaternions_from_imu(
        imu_data_resampled,
        target_rate,
        rot_mats,
        sensors_labels=sensor_labels,
        signals_per_sensor=6,
        calibration_samples=calibration_samples
    )
    
    print(f"Quaternions gerados: shape {quaternions.shape}")
    
    # Salvar arquivo .sto
    if args.output:
        output_file = Path(args.output).expanduser().resolve()
    else:
        output_file = raw_imu_file.with_name(
            raw_imu_file.stem.replace('_raw_imu_', '_quat_') + f"_resampled_{target_rate:.2f}Hz.sto"
        )
    
    print(f"\nSalvando arquivo .sto: {output_file}")
    write_quat_sto(output_file, sensor_labels, times_quat, quaternions, target_rate)
    
    print("\n" + "="*60)
    print("Processamento concluído com sucesso!")
    print("="*60)
    print(f"Taxa estimada pelos timestamps: {estimated_rate:.6f} Hz")
    print(f"Taxa usada na saída: {target_rate:.6f} Hz")
    print(f"Amostras entrada (raw): {len(timestamps)}")
    print(f"Amostras saída (quat): {len(times_quat)}")
    print(f"Número de sensores: {num_sensors}")
    print(f"Arquivo salvo em: {output_file}")


if __name__ == "__main__":
    main()