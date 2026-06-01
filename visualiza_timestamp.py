import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def find_latest_timestamp_file(base_dir: Path) -> Path:
    candidates = sorted(base_dir.rglob("*timestamp_file_*.npy"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"Nenhum arquivo timestamp_*.npy encontrado em {base_dir}")
    return candidates[-1]


def load_timestamp_data(file_path: Path) -> np.ndarray:
    data = np.load(file_path)
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(
            f"Formato inesperado em {file_path}. Esperado array (N,2) com [timestamp, delay]."
        )
    return data


def visualize_timestamp(file_path: Path) -> None:
    data = load_timestamp_data(file_path)
    timestamps = data[:, 0]
    delays = data[:, 1]
    sample_index = np.arange(len(data))

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    axes[0].plot(sample_index, delays * 1000.0, color="tab:blue", marker='+', markersize=1)
    axes[0].set_ylabel("Delay (ms)")
    axes[0].set_title(f"Delay por amostra\n{file_path}")
    axes[0].grid(True, alpha=0.3)

    axes[0].plot(sample_index, delays * 1000.0, color="tab:blue", marker='+', markersize=1, linestyle='-') 

    if len(timestamps) > 1:
        dt = np.diff(timestamps)
        axes[1].plot(sample_index[1:], dt * 1000.0, color="tab:orange", marker='+', markersize=1, linestyle='-')
        axes[1].set_ylabel("delta t entre amostras (ms)")
    else:
        axes[1].text(0.5, 0.5, "Poucas amostras para calcular delta t", ha="center", va="center")
        axes[1].set_ylabel("delta t")

    axes[1].set_xlabel("Indice da amostra")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualiza arquivo timestamp_<n>.npy")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Caminho do arquivo .npy de timestamp. Se omitido, usa o mais recente em ./recordings.",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default="recordings/debug",
        help="Diretorio base para buscar timestamp_*.npy quando --file nao e informado.",
    )
    return parser.parse_args()

def mostrar_valores(file_dir):
    data = np.load(file_dir)
    print("Timestamps (s):", data[:,0])
    print("Delays (s):", data[:,1])
    #criar um arquivo texto com os valores
    try:
        file_dir = Path(file_dir)
        output_file = file_dir.with_suffix('.txt')
    except Exception as e:
        print(f"Erro ao criar caminho do arquivo de saída: {e}")
        return
    with open(output_file, 'w') as f:
        f.write("Timestamps (s):\n")
        for t in data[:,0]:
            f.write(f"{t}\n")
        f.write("\nDelays (s):\n")
        for d in data[:,1]:
            f.write(f"{d}\n")

if __name__ == "__main__":
    args = parse_args()
    if args.file:
        target = Path(args.file).expanduser().resolve()
    else:
        target = find_latest_timestamp_file(Path(args.base_dir).expanduser().resolve())

    target = "recordings/debug/teste-45hz_timestamp_33.npy"
    print(f"Abrindo: {target}")
    visualize_timestamp(target)
    #mostrar_valores(target)