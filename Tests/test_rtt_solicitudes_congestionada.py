import time
import csv
import matplotlib.pyplot as plt
from facultad import Facultad

FACULTAD = "Facultad de Ingeniería"
AULAS = 5
LABS = 3
LOTES = [10, 50, 100, 200, 300]
REPETICIONES = 3

def medir_rtt_lote(facultad_nombre, num_salones, num_labs, n_solicitudes):
    facultad = Facultad(facultad_nombre)
    rtts = []
    for _ in range(n_solicitudes):
        inicio = time.time()
        facultad.enviar_solicitud(num_salones, num_labs)
        fin = time.time()
        rtts.append((fin - inicio) * 1000)
    return rtts

def main():
    resultados = []
    for n in LOTES:
        all_rtts = []
        print(f"\nLote de {n} solicitudes (congestión activa)...")
        for i in range(REPETICIONES):
            rtts = medir_rtt_lote(FACULTAD, AULAS, LABS, n)
            all_rtts.extend(rtts)
        rtt_prom = sum(all_rtts) / len(all_rtts)
        print(f"==> {n} solicitudes - RTT promedio: {rtt_prom:.2f} ms")
        resultados.append({"lote": n, "rtt_prom": rtt_prom})

    with open("rtt_congestionada.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["lote", "rtt_promedio"])
        for r in resultados:
            writer.writerow([r["lote"], r["rtt_prom"]])

    # Gráfica
    x = [r["lote"] for r in resultados]
    y = [r["rtt_prom"] for r in resultados]
    plt.plot(x, y, marker="o", color='red', label="Red congestionada")
    plt.xlabel("Número de Solicitudes")
    plt.ylabel("RTT Promedio (ms)")
    plt.title("RTT vs Solicitudes (Red congestionada)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig("grafico_rtt_congestionada.png")
    plt.show()

if __name__ == "__main__":
    main()
