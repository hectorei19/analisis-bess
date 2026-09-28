"""
Exporta los precios de la base de datos a snapshot/prices.csv.gz, el archivo
del que se alimenta la web publicada.

Uso (desde la carpeta del proyecto):
    .\\.venv\\Scripts\\python.exe -m scripts.export_snapshot
"""

import sys

from src.db.connection import get_connection
from src.db.snapshot import SNAPSHOT_PATH, export_snapshot


def main() -> int:
    n = export_snapshot(get_connection())
    size_kb = SNAPSHOT_PATH.stat().st_size / 1024
    print(f"{n} filas exportadas a {SNAPSHOT_PATH} ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
