"""
Script para exportar el contenido de una tabla SQLite a un archivo CSV.
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

    output = f"{table}_dump.csv"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    columns = [row[1] for row in cur.fetchall()]
    columns_str = ", ".join(columns)
    cur.execute(f"SELECT {columns_str} FROM {table};")
    rows = cur.fetchall()
    with open(output, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    conn.close()
    print(f"\nDump de la tabla '{table}' exportado a {output}")

if __name__ == "__main__":
    main()
