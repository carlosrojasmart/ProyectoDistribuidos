import time
import csv
import matplotlib.pyplot as plt
from facultad import Facultad
from concurrent.futures import ThreadPoolExecutor

# Configuración
FACULTAD = "Facultad de Ingeniería"
AULAS = 5
LABS = 3
LOTES = [100, 200, 300]  # Tamaños de lote a comparar
REPETICIONES = 3
MAX_HILOS_ASYNC = 50     # Controla cuántos hilos simultáneos usa el modo asíncrono

# Envío SÍNCRONO: uno por uno
def medir_sync(facultad_nombre, n, aulas, labs):
    facultad = Facultad(facultad_nombre)
    rtts = []
    for _ in range(n):
        inicio = time.time()
        facultad.enviar_solicitud(aulas, labs)
        fin = time.time()
        rtts.append((fin - inicio) * 1000)
    return rtts

# Envío ASÍNCRONO: en paralelo con hilos limitados
def medir_async(facultad_nombre, n, aulas, labs, max_workers=MAX_HILOS_ASYNC):
    resultados = [0] * n

    def enviar(i):
        facultad = Facultad(facultad_nombre)
        inicio = time.time()
        facultad.enviar_solicitud(aulas, labs)
        fin = time.time()
        resultados[i] = (fin - inicio) * 1000

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i in range(n):
            executor.submit(enviar, i)

    return resultados

# Programa principal
def main():
    datos_sync = []
    datos_async = []

    for n in LOTES:
        total_sync = []
        total_async = []

        print(f"\nLote de {n} solicitudes...")

        for _ in range(REPETICIONES):
            total_sync.extend(medir_sync(FACULTAD, n, AULAS, LABS))
            total_async.extend(medir_async(FACULTAD, n, AULAS, LABS))

        prom_sync = sum(total_sync) / len(total_sync)
        prom_async = sum(total_async) / len(total_async)
        datos_sync.append((n, prom_sync))
        datos_async.append((n, prom_async))

        print(f"⏱️  {n} solicitudes: Síncrono = {prom_sync:.2f} ms, Asíncrono = {prom_async:.2f} ms")

    # Guardar resultados en CSV
    with open("comparacion_sinc_async.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["lote", "rtt_sync", "rtt_async"])
        for s, a in zip(datos_sync, datos_async):
            writer.writerow([s[0], s[1], a[1]])

    # Graficar
    x = [s[0] for s in datos_sync]
    y_sync = [s[1] for s in datos_sync]
    y_async = [a[1] for a in datos_async]

    plt.plot(x, y_sync, marker="o", label="Síncrono")
    plt.plot(x, y_async, marker="o", color="green", label="Asíncrono (ThreadPool)")
    plt.xlabel("Número de Solicitudes")
    plt.ylabel("RTT Promedio (ms)")
    plt.title("Comparación de Desempeño: Síncrono vs Asíncrono")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig("comparacion_sinc_async.png")
    plt.show()

if __name__ == "__main__":
    main()
