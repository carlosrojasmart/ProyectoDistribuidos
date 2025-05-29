import threading
import time
import statistics
import csv
import matplotlib.pyplot as plt
from facultad import enviar_peticiones_a_facultad_balanceado

NUM_FACULTADES = 5
PROGRAMAS_POR_FACULTAD = 5
ESCENARIOS = [
    {'aulas': 7, 'labs': 2, 'nombre': 'mínimo'},
    {'aulas': 10, 'labs': 4, 'nombre': 'máximo'}
]

def programa_academico(facultad_id, programa_id, aulas, labs, resultados):
    start = time.time()
    response = enviar_peticiones_a_facultad_balanceado(facultad_id, aulas, labs)
    end = time.time()

    resultado = {
        'facultad': facultad_id,
        'programa': programa_id,
        'tiempo_respuesta': end - start,
        'exito': response.get("status", "") in ["success", "partial"]
    }

    resultados.append(resultado)

def ejecutar_prueba(escenario):
    resultados = []
    threads = []

    for fid in range(NUM_FACULTADES):
        for pid in range(PROGRAMAS_POR_FACULTAD):
            t = threading.Thread(
                target=programa_academico,
                args=(fid + 1, pid + 1, escenario['aulas'], escenario['labs'], resultados)
            )
            threads.append(t)
            t.start()

    for t in threads:
        t.join()

    tiempos = [r['tiempo_respuesta'] for r in resultados]
    exitos = [r for r in resultados if r['exito']]
    fallidos = [r for r in resultados if not r['exito']]

    nombre_csv = f"broker_resultados_{escenario['nombre']}.csv"
    with open(nombre_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["facultad", "programa", "tiempo_respuesta", "exito"])
        writer.writeheader()
        writer.writerows(resultados)

    print(f"📊 Resultados BROKER ({escenario['nombre']}):")
    print(f"Total programas: {len(resultados)}")
    print(f"Éxitos: {len(exitos)} | Fallidos: {len(fallidos)}")
    print(f"Tiempo Promedio: {statistics.mean(tiempos):.4f} s")
    print(f"Tiempo Mínimo: {min(tiempos):.4f} s")
    print(f"Tiempo Máximo: {max(tiempos):.4f} s")

    return {
        "nombre": escenario["nombre"],
        "total": len(resultados),
        "exitos": len(exitos),
        "fallidos": len(fallidos),
        "tiempo_promedio": statistics.mean(tiempos),
        "tiempo_min": min(tiempos),
        "tiempo_max": max(tiempos)
    }

def main():
    resumen = []

    for escenario in ESCENARIOS:
        print(f"Ejecutando escenario BROKER {escenario['nombre'].upper()}...")
        resumen.append(ejecutar_prueba(escenario))
        time.sleep(2)

    # Graficar resultados
    nombres = [r['nombre'] for r in resumen]
    tiempos_prom = [r['tiempo_promedio'] for r in resumen]
    exitos = [r['exitos'] for r in resumen]
    fallidos = [r['fallidos'] for r in resumen]

    fig, ax = plt.subplots(2, 1, figsize=(8, 6))
    ax[0].bar(nombres, tiempos_prom, color='orange')
    ax[0].set_ylabel("RTT promedio (s)")
    ax[0].set_title("Tiempo de respuesta promedio por escenario (BROKER)")

    ax[1].bar(nombres, exitos, label="Éxitos", color="green")
    ax[1].bar(nombres, fallidos, bottom=exitos, label="Fallidos", color="red")
    ax[1].set_ylabel("Cantidad de solicitudes")
    ax[1].set_title("Éxitos vs Fallos (BROKER)")
    ax[1].legend()

    plt.tight_layout()
    plt.savefig("grafica_broker_resultados.png")
    plt.show()

if __name__ == "__main__":
    main()