"""
Script para cargar datos desde un archivo CSV a una tabla SQLite.
"""


import sqlite3
import csv
import os

def list_sqlite_files(directory):
    return [f for f in os.listdir(directory) if f.endswith('.db')]

def list_tables(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return tables

def main():
    db_dir = "instance"
    db_files = list_sqlite_files(db_dir)
    if not db_files:
        print("No se encontraron bases de datos .db en la carpeta 'instance'.")
        return
    print("Bases de datos disponibles:")
    for idx, db in enumerate(db_files):
        print(f"  {idx+1}. {db}")
    db_idx = int(input("Selecciona la base de datos (número): ")) - 1
    db_path = os.path.join(db_dir, db_files[db_idx])

    tables = list_tables(db_path)
    print("\nTablas disponibles:")
    for idx, tbl in enumerate(tables):
        print(f"  {idx+1}. {tbl}")
    tbl_idx = int(input("Selecciona la tabla (número): ")) - 1
    table = tables[tbl_idx]

    csv_file = input(f"Nombre del archivo CSV a importar (ej: {table}_dump.csv): ").strip()
    if not os.path.exists(csv_file):
        print(f"No se encontró el archivo {csv_file}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    with open(csv_file, newline='', encoding="utf-8") as f:
        reader = csv.reader(f)
        columns = next(reader)
        placeholders = ", ".join(["?"] * len(columns))
        insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        rows = list(reader)
        cur.executemany(insert_sql, rows)
        conn.commit()
    conn.close()
    print(f"\nDatos importados de {csv_file} a la tabla '{table}' en la base {db_files[db_idx]}")

if __name__ == "__main__":
    main()