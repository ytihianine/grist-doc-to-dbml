from src.grist_doc_to_dbml import (
    Config,
    convert_grist_schema_to_dbml,
)

if __name__ == "__main__":
    # Set those values
    config = Config(
        grist_doc_path="path/to/your/grist_doc.db",
        dbml_output_path="path/to/your/output.dbml",
        csv_output_path="path/to/your/output.csv",
        export=True,
    )

    convert_grist_schema_to_dbml(config=config)
