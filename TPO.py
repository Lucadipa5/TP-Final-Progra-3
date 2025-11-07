#!/usr/bin/env python3
import sys
import time

# ------------------------------------------------------------
# FUNCIONES DE LECTURA Y PREPARACIÓN DE DATOS
# ------------------------------------------------------------

def eliminar_comentario(linea: str) -> str:
    """
    Elimina los comentarios de una línea y los espacios sobrantes.

    Paso a paso:
    1. Divide la línea en dos partes usando "//" como separador.
    2. Toma la primera parte (antes del comentario).
    3. Elimina los espacios en blanco al inicio y al final.
    4. Devuelve la línea limpia.
    """
    return linea.split("//")[0].strip()


def leer_seccion(lineas, inicio, cantidad, parser):
    """Lee una sección del archivo con una cantidad conocida de líneas."""
    datos = []
    leidos = 0
    for i in range(inicio, len(lineas)):
        if leidos >= cantidad:
            break
        linea = eliminar_comentario(lineas[i])
        if not linea:
            continue
        try:
            datos.append(parser(linea))
            leidos += 1
        except Exception:
            print(f"Advertencia: no se pudo leer la línea -> {linea}")
    return datos


def leer_datos(nombre_archivo: str) -> dict:
    """Lee el archivo del caso y devuelve todos los datos en un diccionario estructurado."""
    try:
        with open(nombre_archivo, 'r') as f:
            lineas = f.readlines()
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{nombre_archivo}'")
        return None

    datos = {
        'configuracion': {},
        'nodos': {},
        'hubs': {},
        'paquetes': {},
        'aristas': {}
    }

    # --- LEER CONFIGURACIÓN GENERAL ---
    for linea in lineas:
        linea = eliminar_comentario(linea)
        if not linea:
            continue
        partes = linea.split()
        if len(partes) < 2:
            continue
        if partes[0] == "NODOS":
            datos['configuracion']['num_nodos'] = int(partes[1])
        elif partes[0] == "HUBS":
            datos['configuracion']['num_hubs'] = int(partes[1])
        elif partes[0] == "PAQUETES":
            datos['configuracion']['num_paquetes'] = int(partes[1])
        elif partes[0] == "CAPACIDAD_CAMION":
            datos['configuracion']['capacidad_camion'] = int(partes[1])
        elif partes[0] == "DEPOSITO_ID":
            datos['configuracion']['deposito_id'] = int(partes[1])
            break  # termina la lectura de configuración

    # --- DETECTAR SECCIONES (--- NODOS, HUBS, ETC.) ---
    secciones = {}
    for i, linea in enumerate(lineas):
        if "---" in linea:
            partes = linea.split("---")
            if len(partes) > 1:
                nombre = partes[1].strip().split()[0].upper()
                secciones[nombre] = i + 1

    # --- PARSERS SIMPLES PARA CADA SECCIÓN ---

    def parsear_nodo(linea):
        partes = linea.split()
        id_nodo = int(partes[0])
        x = int(partes[1])
        y = int(partes[2])
        return id_nodo, {'x': x, 'y': y}

    def parsear_hub(linea):
        partes = linea.split()
        id_hub = int(partes[0])
        costo = float(partes[1])
        return id_hub, costo

    def parsear_paquete(linea):
        partes = linea.split()
        id_paquete = int(partes[0])
        origen = int(partes[1])
        destino = int(partes[2])
        return id_paquete, {'origen': origen, 'destino': destino}

    def parsear_arista(linea):
        partes = linea.split()
        nodo1 = int(partes[0])
        nodo2 = int(partes[1])
        peso = float(partes[2])
        return (nodo1, nodo2), peso

    # --- LEER NODOS ---
    if "NODOS" in secciones:
        nodos_list = leer_seccion(lineas, secciones["NODOS"], datos['configuracion']['num_nodos'], parsear_nodo)
        for id_nodo, props in nodos_list:
            datos['nodos'][id_nodo] = props

    # --- LEER HUBS ---
    if "HUBS" in secciones:
        hubs_list = leer_seccion(lineas, secciones["HUBS"], datos['configuracion']['num_hubs'], parsear_hub)
        for id_hub, costo in hubs_list:
            datos['hubs'][id_hub] = costo

    # --- LEER PAQUETES ---
    if "PAQUETES" in secciones:
        paquetes_list = leer_seccion(lineas, secciones["PAQUETES"], datos['configuracion']['num_paquetes'], parsear_paquete)
        for id_paq, props in paquetes_list:
            datos['paquetes'][id_paq] = props

    # --- LEER ARISTAS ---
    if "ARISTAS" in secciones:
        aristas_list = leer_seccion(lineas, secciones["ARISTAS"], float('inf'), parsear_arista)
        for edge, peso in aristas_list:
            datos['aristas'][edge] = peso
            # grafo no dirigido
            if (edge[1], edge[0]) not in datos['aristas']:
                datos['aristas'][(edge[1], edge[0])] = peso

    return datos


# ------------------------------------------------------------
# ALGORITMO DE FLOYD-WARSHALL
# ------------------------------------------------------------

def floyd_warshall(aristas, num_nodos):
    """
    Calcula las distancias mínimas entre todos los nodos del grafo usando el algoritmo de Floyd-Warshall.

    Paso a paso:
    1. Inicializa la matriz de distancias con infinito para todas las parejas, excepto la diagonal con 0.
    2. Para cada arista directa, establece la distancia como el peso dado.
    3. Para cada nodo intermedio k, actualiza las distancias entre i y j si pasando por k es más corto.
    4. Devuelve la matriz de distancias mínimas.
    """
    dist = [[float('inf')] * num_nodos for _ in range(num_nodos)]
    for i in range(num_nodos):
        dist[i][i] = 0
    for (u, v), peso in aristas.items():
        dist[u][v] = peso
        dist[v][u] = peso

    # Aplicar el algoritmo de Floyd-Warshall para calcular distancias mínimas
    for k in range(num_nodos):
        for i in range(num_nodos):
            for j in range(num_nodos):
                if dist[i][j] > dist[i][k] + dist[k][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]

    return dist



# ------------------------------------------------------------
# BACKTRACKING: SELECCIÓN DE HUBS Y RUTA ÓPTIMA
# ------------------------------------------------------------

def calcular_mejor_camino(datos, matriz):
    """Explora combinaciones de hubs activados mediante backtracking 
    y calcula la ruta de menor costo total (distancia + activación)."""

    deposito = datos['configuracion']['deposito_id']
    capacidad = datos['configuracion']['capacidad_camion']
    hubs = list(datos['hubs'].keys())
    costo_hubs = datos['hubs']

    # Agrupa los paquetes por destino
    paquetes_por_destino = {}
    for _, paquete in datos['paquetes'].items():    #//TODO
        destino = paquete['destino']
        paquetes_por_destino[destino] = paquetes_por_destino.get(destino, 0) + 1

    # Variables globales del mejor resultado encontrado
    mejor_costo = float('inf')
    mejor_hubs = []
    mejor_ruta = []
    mejor_distancia = 0



    # ---------------------------------------------------------
    # Función recursiva de backtracking
    # ---------------------------------------------------------
    def probar_combinaciones(indice, hubs_activos, costo_activacion):
        nonlocal mejor_costo, mejor_hubs, mejor_ruta, mejor_distancia

        # Caso base: se decidió sobre todos los hubs
        if indice == len(hubs):
            destinos = list(paquetes_por_destino.keys())
            viajes = []
            viaje_actual = []
            carga_actual = 0

            # Agrupar destinos respetando la capacidad del camión
            for d in destinos:
                cant = paquetes_por_destino[d]
                if carga_actual + cant > capacidad:
                    viajes.append(viaje_actual)
                    viaje_actual = []
                    carga_actual = 0
                viaje_actual.append(d)
                carga_actual += cant
            if viaje_actual:
                viajes.append(viaje_actual)

            # Calcular distancia total
            distancia_total = 0
            ruta_total = [deposito]

            for viaje in viajes:
                # Usar el orden de destinos sin heurística
                viaje_ordenado = viaje

                mejor_inicio = deposito
                menor_distancia_viaje = float('inf')

                # Probar salir desde el depósito o un hub activo
                for punto_inicio in [deposito] + hubs_activos:
                    distancia_viaje = matriz[punto_inicio][viaje_ordenado[0]]
                    for k in range(len(viaje_ordenado) - 1):
                        distancia_viaje += matriz[viaje_ordenado[k]][viaje_ordenado[k + 1]]
                    distancia_viaje += matriz[viaje_ordenado[-1]][deposito]

                    if distancia_viaje < menor_distancia_viaje:
                        menor_distancia_viaje = distancia_viaje
                        mejor_inicio = punto_inicio

                distancia_total += menor_distancia_viaje
                ruta_total.append(mejor_inicio)
                for d in viaje_ordenado:
                    ruta_total.append(d)
                ruta_total.append(deposito)

            costo_total = distancia_total + costo_activacion

            # Actualizar mejor combinación encontrada
            if costo_total < mejor_costo:
                mejor_costo = costo_total
                mejor_hubs = hubs_activos[:]
                mejor_ruta = ruta_total[:]
                mejor_distancia = distancia_total

            return  # Fin de la rama

        # ---------------------------------------------------------
        # Paso recursivo: decidir activar o no el hub actual
        # ---------------------------------------------------------
        # No activar el hub
        probar_combinaciones(indice + 1, hubs_activos, costo_activacion)

        # Activar el hub actual
        hub_actual = hubs[indice]
        hubs_activos.append(hub_actual)
        probar_combinaciones(indice + 1, hubs_activos, costo_activacion + costo_hubs[hub_actual])
        hubs_activos.pop()  # volver atrás (backtracking)

    # Llamada inicial
    probar_combinaciones(0, [], 0)

    costo_solo_hubs = mejor_costo - mejor_distancia
    return mejor_ruta, mejor_hubs, mejor_costo, mejor_distancia, costo_solo_hubs


# ------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ------------------------------------------------------------

def main():
    if len(sys.argv) != 2: #//TODO que significa sys
        print(f"Uso: {sys.argv[0]} <archivo_caso.txt>")
        sys.exit(1)

    archivo = sys.argv[1]
    inicio = time.time()

    datos = leer_datos(archivo)
    if datos is None:
        print("No se pudo leer el archivo correctamente.")
        sys.exit(1)

    num_nodos = datos['configuracion']['num_nodos']
    matriz = floyd_warshall(datos['aristas'], num_nodos)

    ruta, hubs, costo_total, distancia, costo_hubs = calcular_mejor_camino(datos, matriz)

    fin = time.time()
    duracion = fin - inicio

    # --- GUARDAR RESULTADO ---
    with open("solucion.txt", "w") as f:
        f.write("// --- HUBS ACTIVADOS ---\n")
        for h in hubs:
            f.write(f"ID_HUB_{h}\n")
        f.write("\n// --- RUTA OPTIMA ---\n")
        f.write(" -> ".join(map(str, ruta)) + "\n")
        f.write("\n// --- METRICAS ---\n")
        f.write(f"COSTO_TOTAL: {costo_total:.2f}\n")
        f.write(f"DISTANCIA_RECORRIDA: {distancia:.2f}\n")
        f.write(f"COSTO_HUBS: {costo_hubs:.2f}\n")
        f.write(f"TIEMPO_EJECUCION: {duracion:.6f} segundos\n")

    print("\nArchivo solucion.txt generado con éxito.")


if __name__ == "__main__":
    main()
