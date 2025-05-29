
# Proyecto Distribuidos – Sistema de Gestión de Aulas y Laboratorios

Este proyecto implementa un sistema distribuido tolerante a fallos que permite gestionar la asignación de aulas y laboratorios entre múltiples facultades universitarias y un Servidor Central, con una Réplica activa-pasiva y pruebas de rendimiento automatizadas.

Repositorio oficial: [github.com/carlosrojasmart/ProyectoDistribuidos](https://github.com/carlosrojasmart/ProyectoDistribuidos)

---

## 🧩 Arquitectura

El sistema se distribuye en 3 máquinas virtuales:

| VM  | Rol              | Descripción |
|-----|------------------|-------------|
| VM1 | Servidor Central | Procesa las solicitudes y guarda en SQLite |
| VM2 | Réplica          | Replica pasiva sincronizada |
| VM3 | Cliente          | Simula Facultades y ejecuta pruebas de rendimiento |

---

## 📁 Estructura del proyecto

- servidor.py: Servidor Central (interfaz interactiva incluida)
- replica.py: Réplica pasiva sincronizada
- facultad.py: Cliente simulador de facultades (envía solicitudes al servidor)
- database.py: Utilidades para SQLite (si aplica)
- README.md: Documentación
- LICENSE.txt

### 📂 Tests

Scripts automatizados para pruebas de rendimiento:

- test_async_pattern.py
- test_broker_pattern.py
- test_comparacion_sinc_async.py
- test_rtt_solicitudes_no_congestionada.py
- test_rtt_solicitudes_congestionada.py

### 📂 Datos

Archivos generados por las pruebas:

- *.csv → resultados detallados por escenario
- *.png → gráficas de rendimiento y comparación

---

## ⚙️ Dependencias

Requiere Python 3.8 o superior y las siguientes librerías:

```bash
pip install pyzmq matplotlib pandas tabulate
```

---

## 🚀 Ejecución

1. Clona el repositorio en las tres máquinas:
```bash
git clone https://github.com/carlosrojasmart/ProyectoDistribuidos.git
cd ProyectoDistribuidos
```

2. En VM1 (Servidor Central):
```bash
python3 servidor.py
```

3. En VM2 (Réplica):
```bash
python3 replica.py
```

4. En VM3 (Facultades/Cliente):
Edita IPs en facultad.py si es necesario. Luego:

- Para pruebas asíncronas:
```bash
python3 test_async_pattern.py
```

- Para pruebas con balanceo:
```bash
python3 test_broker_pattern.py
```

- Para RTT no congestionado:
```bash
python3 test_rtt_solicitudes_no_congestionada.py
```

- Para RTT con congestión de red (usar iperf o tráfico paralelo):
```bash
python3 test_rtt_solicitudes_congestionada.py
```

---

## 📊 Resultados y Reporte

Cada prueba genera automáticamente:

- Archivos .csv con tiempos de respuesta y éxito/fallo
- Gráficas .png para incluir en reportes
- Tabla resumen de rendimiento para llenar manualmente con los valores impresos por consola

---

## 📌 Observaciones

- Servidor y réplica usan sockets ZeroMQ (REQ-REP) y SQLite como almacenamiento persistente.
- La réplica recibe notificaciones del servidor en segundo plano.
- El cliente (facultad) implementa reintento automático ante falla del servidor central.
- El sistema soporta múltiples programas académicos por facultad.
- Incluye interfaz de consola para borrar registros, reiniciar base o consultar estado.

---

## 🧑‍💻 Autor

Carlos Rojas — Proyecto académico para Sistemas Distribuidos
Mariana Pérez — Proyecto académico para Sistemas Distribuidos
Juan Vargas — Proyecto académico para Sistemas Distribuidos

Licencia: MIT
