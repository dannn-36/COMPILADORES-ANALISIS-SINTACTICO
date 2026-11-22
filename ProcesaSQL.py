import mysql.connector

# Conexión a la base de datos
conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="12345678",
    database="ubosquebd"
)

consultas = []

cursor = conexion.cursor()
# Leer archivo con consultas SQL
with open("ejemplo.csv", "r", encoding="utf-8") as archivo:
    for num_linea, linea in enumerate(archivo, start=1):
        consulta = linea.strip()

        if consulta.endswith(";"):
            consulta = consulta[:-1]

        if consulta:
            consultas.append(consulta)

        try:
            print(f"Ejecutando línea {num_linea}: {consulta}")
            cursor.execute(consulta)

            # Si es SELECT, mostrar resultados
            if consulta.upper().startswith("SELECT"):
                resultados = cursor.fetchall()
                for fila in resultados:
                    print(fila)

            else:
                conexion.commit()
                print(f"Filas afectadas: {cursor.rowcount}")

        except Exception as e:
            print(f"Error en línea {num_linea}: {e}")

cursor.close()
conexion.close()

#for consulta in consultas:
#    print(consulta)