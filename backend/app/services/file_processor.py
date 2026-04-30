"""
File processor service — uses Polars for fast reading of large xlsx/csv files.

Curva calculation replicates the Excel formula:
  =SI.ERROR(BUSCARV(C2, !$B$2:$G$12921, 6, 0), 0)

The file has a SINGLE sheet. The formula looks up the value in column C
(Producto) within the range B2:G12921 (a reference sub-table embedded in the
same sheet), and returns column 6 of that range (column G = index 5).

In Python terms:
  - Load the full sheet into a Polars DataFrame.
  - Slice rows 0..12920 (1-indexed rows 2..12921), columns B..G (indices 1..6).
  - Build a dict { col_B_value → col_G_value }.
  - For each inventory row, look up df["producto"] in the dict → curva.
  - Default "0" when not found.
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import polars as pl

from app.core.config import get_settings
from app.core.exceptions import FileProcessingException

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Column name aliases ───────────────────────────────────────────────────
LPN_ALIASES         = ["Nro LPN", "NRO LPN", "nro_lpn", "LPN", "lpn", "Número LPN"]
ESTADO_ALIASES      = ["Estado", "ESTADO", "estado"]
PRODUCTO_ALIASES    = ["Producto", "PRODUCTO", "producto", "Cod. Producto", "Código Producto"]
DESCRIPCION_ALIASES = ["Descripcion", "Descripción", "DESCRIPCION", "descripcion"]


def _find_column(df_columns: list[str], aliases: list[str]) -> Optional[str]:
    col_lower = {c.lower().strip(): c for c in df_columns}
    for alias in aliases:
        if alias.lower().strip() in col_lower:
            return col_lower[alias.lower().strip()]
    return None


def _build_curva_lookup_same_sheet(df: pl.DataFrame) -> dict[str, str]:
    """
    Build the curva lookup dict from the same single-sheet DataFrame.

    Replicates: BUSCARV(C2, $B$2:$G$12921, 6, 0)
      - Range: rows 0..12919 (Excel rows 2..12921), columns at index 1..6 (B..G)
      - Key:    column index 1 (B)  → typically a product/reference code
      - Value:  column index 5 (G)  → curva letter (A/B/C)
    """
    key_idx = settings.CURVA_LOOKUP_KEY_COL    # default 1  (col B, 0-indexed)
    val_idx = settings.CURVA_RESULT_COL        # default 5  (col G, 0-indexed)
    ref_end  = settings.CURVA_REFERENCE_ROW_END  # default 12920 (exclusive)

    cols = df.columns
    if len(cols) <= max(key_idx, val_idx):
        logger.warning(
            f"File has only {len(cols)} columns; expected ≥{max(key_idx, val_idx)+1} "
            "for curva lookup. All curvas will default to '0'."
        )
        return {}

    key_col = cols[key_idx]
    val_col = cols[val_idx]

    # Slice the reference sub-table (rows up to ref_end)
    ref_slice = df.slice(0, min(ref_end, len(df))).select([key_col, val_col])
    ref_slice = ref_slice.drop_nulls()

    lookup: dict[str, str] = {
        str(k).strip(): str(v).strip()
        for k, v in zip(ref_slice[key_col].to_list(), ref_slice[val_col].to_list())
        if k is not None and v is not None
    }

    logger.info(f"Curva lookup built from same sheet: {len(lookup)} entries.")
    return lookup


def _normalize_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Rename to standard column names and select the 4 required fields."""
    cols = df.columns
    rename_map: dict[str, str] = {}

    lpn_col         = _find_column(cols, LPN_ALIASES)
    estado_col      = _find_column(cols, ESTADO_ALIASES)
    producto_col    = _find_column(cols, PRODUCTO_ALIASES)
    descripcion_col = _find_column(cols, DESCRIPCION_ALIASES)

    missing = []
    if not lpn_col:         missing.append("Nro LPN")
    if not estado_col:      missing.append("Estado")
    if not producto_col:    missing.append("Producto")
    if not descripcion_col: missing.append("Descripcion")

    if missing:
        raise FileProcessingException(
            f"Columnas requeridas no encontradas: {', '.join(missing)}. "
            f"Columnas disponibles: {', '.join(cols)}"
        )

    rename_map[lpn_col]         = "nro_lpn"
    rename_map[estado_col]      = "estado"
    rename_map[producto_col]    = "producto"
    rename_map[descripcion_col] = "descripcion"

    df = (
        df.rename(rename_map)
          .select(["nro_lpn", "estado", "producto", "descripcion"])
          .with_columns([
              pl.col("nro_lpn").cast(pl.Utf8).str.strip_chars().str.to_uppercase(),
              pl.col("estado").cast(pl.Utf8).str.strip_chars(),
              pl.col("producto").cast(pl.Utf8).str.strip_chars(),
              pl.col("descripcion").cast(pl.Utf8).str.strip_chars(),
          ])
          .drop_nulls(subset=["nro_lpn"])
    )
    return df


async def process_inventory_file(
    file_path: str,
    batch_id: str,
    on_progress: Optional[callable] = None,
) -> tuple[int, list[dict]]:
    """
    Read the inventory file (single sheet xlsx or csv), compute curva,
    and return (total_rows, list_of_row_dicts) ready for DB bulk insert.
    """
    ext = Path(file_path).suffix.lower()

    # ── Step 1: Load raw DataFrame ───────────────────────────────────────────
    if ext == ".csv":
        raw_df = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: pl.scan_csv(
                file_path, infer_schema_length=2000, ignore_errors=True
            ).collect(),
        )
    elif ext in (".xlsx", ".xls"):
        raw_df = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: pl.read_excel(file_path, engine="openpyxl"),
        )
    else:
        raise FileProcessingException(
            f"Formato no soportado: '{ext}'. Use .xlsx o .csv"
        )

    logger.info(f"Raw file loaded: {len(raw_df)} rows × {len(raw_df.columns)} cols.")

    # ── Step 2: Build curva lookup from the same single sheet ────────────────
    curva_lookup = await asyncio.get_event_loop().run_in_executor(
        None, _build_curva_lookup_same_sheet, raw_df
    )

    # ── Step 3: Normalize to our 4 required columns ──────────────────────────
    df = _normalize_dataframe(raw_df)
    total_rows = len(df)
    logger.info(f"After normalization: {total_rows} rows.")

    # ── Step 4: Apply curva lookup ────────────────────────────────────────────
    if curva_lookup:
        curva_series = df["producto"].map_elements(
            lambda p: curva_lookup.get(str(p).strip(), "0"),
            return_dtype=pl.Utf8,
        )
    else:
        curva_series = pl.Series("curva", ["0"] * total_rows)

    df = df.with_columns(curva_series.alias("curva"))

    # ── Step 5: Add metadata ─────────────────────────────────────────────────
    now = datetime.utcnow()
    df = df.with_columns([
        pl.lit(batch_id).alias("batch_id"),
        pl.lit(now).alias("uploaded_at"),
    ])

    # ── Step 6: Build list[dict] in batches (yields to event loop) ──────────
    batch_size = settings.BATCH_SIZE
    all_rows: list[dict] = []

    for i in range(0, total_rows, batch_size):
        chunk = df.slice(i, batch_size)
        all_rows.extend(chunk.to_dicts())
        if on_progress:
            await on_progress(len(all_rows))
        await asyncio.sleep(0)

    return total_rows, all_rows
