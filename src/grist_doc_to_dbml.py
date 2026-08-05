import logging
import sqlite3
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# ===================================
# Logging configuration
# ===================================
custom_logger = logging.Logger(name=__name__, level=logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)  # Handler pour afficher les logs dans la console
formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(fmt=formatter)
custom_logger.addHandler(hdlr=handler)


@dataclass
class Config:
    # User-defined parameters
    grist_doc_path: str
    csv_output_path: str
    dbml_output_path: str
    export: bool = False
    # Grist additional tables and internal columns to drop
    grist_internal_tables: list[str] = field(default_factory=lambda: ["summary"])
    grist_internal_columns: list[str] = field(
        default_factory=lambda: ["manual", "grist", "summary", "count", "group", "GristDocTour"]
    )

    # Grist info to look for Metadata
    grist_table_with_table_information: str = "_grist_Tables"
    grist_column_with_tablename: str = "tableId"
    grist_table_with_column_information: str = "_grist_Tables_column"
    grist_column_with_columnname: str = "colId"
    grist_column_with_column_type: str = "type"
    grist_column_with_parentid: str = "parentId"


TYPE_CONVERT = {
    "Any": "grist_any",
    "Blob": "binary",
    "Text": "text",
    "Numeric": "numeric",
    "Int": "int",
    "Bool": "boolean",
    "Date": "date",
    "DateTime": "datetime",
    "Choice": "text",
    "ChoiceList": "text[]",
    "Ref": "int",
    "RefList": "int[]",
    "Attachments": "file",
}


# ===================================
# Grist Metadata
# ===================================
def get_grist_table_definitions(tbl_name: str, conn: sqlite3.Connection) -> pd.DataFrame:
    custom_logger.info(msg="Fetching table information from Grist document metadata.")
    df_tbl = pd.read_sql(f"SELECT * FROM {tbl_name}", con=conn)
    return df_tbl


def get_grist_column_definitions(tbl_name: str, conn: sqlite3.Connection) -> pd.DataFrame:
    custom_logger.info(msg="Fetching columns information from Grist document metadata.")
    df_col = pd.read_sql(f"SELECT * FROM {tbl_name}", con=conn)
    return df_col


# ===================================
# Processing - Table definitions
# ===================================
def drop_grist_internal_table(df: pd.DataFrame, column: str, grist_internal_tables: Iterable[str]) -> pd.DataFrame:
    """
    Drop rows where the specified table name contains any of the grist internal tables.
    The aim is to keep only business tables.

    Args:
        df (pd.DataFrame): DataFrame of the table information.
        column (str): The column which contains table names.
        grist_internal_tables (Iterable[str]): Internal tables to drop.

    Returns:
        pd.DataFrame: The filtered DataFrame.
    """
    df_filtered = df.loc[df[column].str.contains(pat="|".join(grist_internal_tables), na=False)]
    df = df.drop(index=df_filtered.index)
    return df


def process_tbl_info(
    df: pd.DataFrame, grist_internal_tables: Iterable[str], tablename_column: str, lower_tbl_name: bool = False
) -> pd.DataFrame:
    cols_to_keep = ["id", tablename_column]
    df = df.loc[:, cols_to_keep].copy()
    df = drop_grist_internal_table(df=df, column=tablename_column, grist_internal_tables=grist_internal_tables)
    if lower_tbl_name:
        df[tablename_column] = df.loc[:, tablename_column].str.lower()
    return df


# ===================================
# Processing - Column definitions
# ===================================
def drop_grist_internal_columns(df: pd.DataFrame, column: str, grist_internal_columns: Iterable[str]) -> pd.DataFrame:
    """
    Drop rows where the specified column contains any of the grist internal columns.
    The aim is to keep only business tables.

    Args:
        df (pd.DataFrame): DataFrame of the column information.
        column (str): The column which contains column names.
        grist_internal_columns (Iterable[str]): Internal columns to drop.

    Returns:
        pd.DataFrame: The filtered DataFrame.
    """
    df_filtered = df.loc[df[column].str.contains(pat="|".join(grist_internal_columns), na=False)]
    df = df.drop(index=df_filtered.index)
    return df


def convert_grist_data_type_to_dbml(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df["type_dbml"] = df.loc[:, column].map(TYPE_CONVERT)
    return df


def process_col_info(
    df: pd.DataFrame,
    grist_internal_columns: Iterable[str],
    parent_id_column: str,
    columnname_column: str,
    columntype_column: str,
    lower_col_name: bool = False,
) -> pd.DataFrame:
    cols_to_keep = ["id", parent_id_column, columnname_column, "type", "description"]
    df = df.loc[:, cols_to_keep].copy()
    df = drop_grist_internal_columns(df=df, column=columnname_column, grist_internal_columns=grist_internal_columns)
    df = convert_grist_data_type_to_dbml(df=df, column=columntype_column)
    if lower_col_name:
        df[columnname_column] = df.loc[:, columnname_column].str.lower()
    return df


# ===================================
# DBML & Export
# ===================================
def process_dbml(df_tbl: pd.DataFrame, df_col: pd.DataFrame, parent_id_column: str) -> pd.DataFrame:
    df = pd.merge(left=df_tbl, right=df_col, left_on="id", right_on=parent_id_column)
    df = df.drop(columns=["id_x", "id_y"])
    df = df.sort_values(by=parent_id_column)
    return df


def generate_dbml_file(df: pd.DataFrame, output_path: Path, parentid_column: str) -> None:
    tbl_names = df.loc[:, parentid_column].unique()
    dbml = {}
    for tbl in tbl_names:
        dbml[tbl] = []
        dbml[tbl].append(f"Table {tbl}")
        dbml[tbl].append("\n{\n\tid integer [primary key]")

    for row in df.itertuples():
        if row.type in ["Ref:Check", "RefList:Check"]:  # type: ignore
            dbml[row.tableId].append(f"\n\tid_{row.colId} {row.type_dbml} [ref: > {row.type_grist_tbl_name}.id]")  # type: ignore
        else:
            dbml[row.tableId].append(f"\n\t{row.colId} {row.type_dbml}")  # type: ignore

    with open(file=output_path, mode="w") as dbml_file:
        for _key, values in dbml.items():
            dbml_file.write("".join(values))
            dbml_file.write("\n}\n\n")


def export_to_csv(df: pd.DataFrame, path: Path, sep: str = ";") -> None:
    df.to_csv(path_or_buf=path, sep=sep)


# ===================================
# All in one function
# ===================================
def convert_grist_schema_to_dbml(config: Config) -> None:
    custom_logger.info(msg="Starting conversion of Grist schema to DBML format script.")

    # Start
    custom_logger.info(msg="Step 1/5 - Initialization of the sqlite3 connection.")
    db_conn = sqlite3.connect(config.grist_doc_path)
    custom_logger.info(msg="Step 1/5 - Connection established.")

    # Process table information
    custom_logger.info(msg="Step 2/5 - Starting processing of table information.")
    df_tbl = get_grist_table_definitions(tbl_name=config.grist_table_with_table_information, conn=db_conn)
    custom_logger.info(msg=f"Nb lignes avant processing: {len(df_tbl)}")
    df_tbl = process_tbl_info(
        df=df_tbl,
        tablename_column=config.grist_column_with_tablename,
        grist_internal_tables=config.grist_internal_tables,
        lower_tbl_name=True,
    )
    custom_logger.info(msg=f"Nb lignes après processing: {len(df_tbl)}")
    custom_logger.info(msg="Step 2/5 - Finished.")

    # Process columns information
    custom_logger.info(msg="Step 3/5 - Starting processing of columns information")
    df_cols = get_grist_column_definitions(tbl_name=config.grist_table_with_column_information, conn=db_conn)
    custom_logger.info(msg=f"Nb lignes avant processing: {len(df_cols)}")
    df_cols = process_col_info(
        df=df_cols,
        grist_internal_columns=config.grist_internal_columns,
        parent_id_column=config.grist_column_with_parentid,
        columnname_column=config.grist_column_with_columnname,
        columntype_column=config.grist_column_with_column_type,
        lower_col_name=True,
    )
    custom_logger.info(msg=f"\n{df_cols.head()}")
    custom_logger.info(msg=f"Nb lignes après processing: {len(df_cols)}")
    custom_logger.info(msg="Step 3/5 - Finished.")

    # Prepare last df before formating
    custom_logger.info(msg="Step 4/5 - Generating DBML formated string from the processed dataframes.")
    df_dbml = process_dbml(df_tbl=df_tbl, df_col=df_cols, parent_id_column=config.grist_column_with_parentid)
    custom_logger.info(msg=f"\n{df_dbml.head()}")
    custom_logger.info(msg="Step 4/5 - Finished.")

    # (Optional) Export dataframe to csv format
    custom_logger.info(msg="Step 5/5 - Exporting data.")
    if config.export:
        export_to_csv(df=df_dbml, path=Path(config.csv_output_path))

    # Export to dbml format
    generate_dbml_file(df=df_dbml, output_path=Path(config.dbml_output_path), parentid_column=config.grist_column_with_tablename)
    custom_logger.info(msg="Step 5/5 - Finished.")
