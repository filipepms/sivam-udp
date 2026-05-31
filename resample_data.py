"""Resample de quaternions gravados em .sto usando timestamps reais.

Objetivo:
- Ler um arquivo .sto de quaternions (gravado com passo assumido constante).
- Ler um arquivo timestamp_*.npy (coluna 0 = timestamp real).
- Reinterpolar os quaternions para uma nova malha temporal constante (SLERP).
- Salvar um novo .sto corrigido.
"""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp


def find_latest_file(base_dir: Path, pattern: str) -> Path:
    candidates = sorted(base_dir.rglob(pattern), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"Nenhum arquivo encontrado para o padrão '{pattern}' em {base_dir}")
    return candidates[-1]


def load_timestamps(timestamp_file: Path) -> np.ndarray:
    data = np.load(timestamp_file)
    if data.ndim != 2 or data.shape[1] < 1:
        raise ValueError(f"Arquivo de timestamp inválido: {timestamp_file}. Esperado array (N, >=1).")
    timestamps = data[:, 0].astype(float)
    return timestamps


def read_quat_sto(sto_file: Path):
    with open(sto_file, "r") as f:
        raw_lines = [line.rstrip("\n") for line in f]

    endheader_idx = None
    for idx, line in enumerate(raw_lines):
        if line.strip().lower() == "endheader":
            endheader_idx = idx
            break
    if endheader_idx is None:
        raise ValueError(f"Arquivo .sto sem 'endheader': {sto_file}")

    if endheader_idx + 1 >= len(raw_lines):
        raise ValueError(f"Arquivo .sto sem linha de colunas: {sto_file}")

    header_lines = raw_lines[: endheader_idx + 1]
    column_line = raw_lines[endheader_idx + 1].strip()
    data_lines = [ln.strip() for ln in raw_lines[endheader_idx + 2 :] if ln.strip()]

    columns = [c for c in column_line.split("\t") if c != ""]
    if len(columns) < 2 or columns[0].lower() != "time":
        raise ValueError(f"Linha de colunas inválida em {sto_file}: '{column_line}'")

    sensor_labels = columns[1:]
    n_sensors = len(sensor_labels)

    times = []
    quats = []
    for line in data_lines:
        parts = [p for p in line.split("\t") if p != ""]
        if len(parts) < 1 + n_sensors:
            continue
        t = float(parts[0])
        row_quats = np.zeros((n_sensors, 4), dtype=float)
        for i in range(n_sensors):
            vals = parts[i + 1].split(",")
            if len(vals) != 4:
                raise ValueError(f"Quaternion inválido na linha: '{line}'")
            row_quats[i, :] = [float(v) for v in vals]
        times.append(t)
        quats.append(row_quats)

    if not quats:
        raise ValueError(f"Nenhum dado de quaternion encontrado em {sto_file}")

    return header_lines, sensor_labels, np.asarray(times), np.asarray(quats)


def enforce_strictly_increasing(timestamps: np.ndarray, quats: np.ndarray):
    keep = np.ones(len(timestamps), dtype=bool)
    keep[1:] = np.diff(timestamps) > 0.0
    t_new = timestamps[keep]
    q_new = quats[keep]
    if len(t_new) < 2:
        raise ValueError("Após remover timestamps duplicados/não crescentes, restaram menos de 2 amostras.")
    return t_new, q_new


def estimate_rate(timestamps: np.ndarray) -> float:
    dt = np.diff(timestamps)
    dt = dt[dt > 0]
    if len(dt) == 0:
        raise ValueError("Não foi possível estimar taxa: delta t inválido.")
    return 1.0 / float(np.median(dt))


def build_uniform_timebase(timestamps: np.ndarray, target_rate: float) -> np.ndarray:
    t0 = timestamps[0]
    t1 = timestamps[-1]
    if t1 <= t0:
        raise ValueError("Range de tempo inválido para resample.")
    n_samples = int(np.floor((t1 - t0) * target_rate)) + 1
    n_samples = max(n_samples, 2)
    return t0 + np.arange(n_samples, dtype=float) / target_rate


def slerp_resample_quaternions(source_t: np.ndarray, source_q_wxyz: np.ndarray, target_t: np.ndarray) -> np.ndarray:
    n_sensors = source_q_wxyz.shape[1]
    out = np.zeros((len(target_t), n_sensors, 4), dtype=float)

    t_rel = source_t - source_t[0]
    tq_rel = target_t - source_t[0]

    for s in range(n_sensors):
        q_wxyz = source_q_wxyz[:, s, :]
        q_xyzw = np.column_stack([q_wxyz[:, 1], q_wxyz[:, 2], q_wxyz[:, 3], q_wxyz[:, 0]])
        rot = Rotation.from_quat(q_xyzw)
        slerp = Slerp(t_rel, rot)
        interp = slerp(tq_rel).as_quat()  # x,y,z,w
        out[:, s, 0] = interp[:, 3]  # w
        out[:, s, 1] = interp[:, 0]  # x
        out[:, s, 2] = interp[:, 1]  # y
        out[:, s, 3] = interp[:, 2]  # z

    return out


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
    parser = argparse.ArgumentParser(description="Resample de arquivo .sto de quaternions usando timestamps reais")
    parser.add_argument("--quat-file", type=str, default=None, help="Caminho do arquivo .sto de quaternions")
    parser.add_argument("--timestamp-file", type=str, default=None, help="Caminho do arquivo timestamp_*.npy")
    parser.add_argument("--output", type=str, default=None, help="Caminho do .sto de saída")
    parser.add_argument(
        "--target-rate",
        type=float,
        default=None,
        help="Taxa de saída (Hz). Se omitido, usa taxa estimada pelos timestamps (mediana do delta t)",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default="/home/pebimu3/sivam/temp/",
        help="Diretório base para busca automática quando arquivos não são informados",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    base_dir = Path(args.base_dir).expanduser().resolve()

    quat_file = Path(args.quat_file).expanduser().resolve() if args.quat_file else find_latest_file(base_dir, "Moviemtnos Isoladosimu_quat_93.sto")
    timestamp_file = (
        Path(args.timestamp_file).expanduser().resolve() if args.timestamp_file else find_latest_file(base_dir, "timestamp_93.npy")
    )
    
    
    print(f"Lendo quaternions: {quat_file}")
    print(f"Lendo timestamps: {timestamp_file}")

    _, sensor_labels, _, quats = read_quat_sto(quat_file)
    timestamps = load_timestamps(timestamp_file)

    n = min(len(timestamps), len(quats))
    if len(timestamps) != len(quats):
        print(
            f"Aviso: tamanhos diferentes (timestamps={len(timestamps)}, quats={len(quats)}). "
            f"Usando {n} amostras (mínimo)."
        )
    timestamps = timestamps[:n]
    quats = quats[:n]

    timestamps, quats = enforce_strictly_increasing(timestamps, quats)

    estimated_rate = estimate_rate(timestamps)
    target_rate = args.target_rate if args.target_rate and args.target_rate > 0 else estimated_rate
    uniform_times = build_uniform_timebase(timestamps, target_rate)
    quats_resampled = slerp_resample_quaternions(timestamps, quats, uniform_times)
    output_times = uniform_times - uniform_times[0]

    if args.output:
        output_file = Path(args.output).expanduser().resolve()
    else:
        output_file = quat_file.with_name(quat_file.stem + f"_resampled_{target_rate:.2f}Hz.sto")

    write_quat_sto(output_file, sensor_labels, output_times, quats_resampled, target_rate)

    print("\nResample concluído")
    print(f"Taxa estimada pelos timestamps: {estimated_rate:.6f} Hz")
    print(f"Taxa usada na saída: {target_rate:.6f} Hz")
    print(f"Amostras entrada: {len(timestamps)}")
    print(f"Amostras saída: {len(output_times)}")
    print(f"Arquivo salvo em: {output_file}")


if __name__ == "__main__":
    main()