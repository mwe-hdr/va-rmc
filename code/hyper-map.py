from tableauhyperapi import HyperProcess, Connection, Telemetry
from pathlib import Path
import shutil
import tempfile
import re

# --------------------------------------------------
# FILES
# --------------------------------------------------

hyper_files = [
    r"C:\Users\medwards\OneDrive - HDR, Inc\Arch. Advisory Services - Clients\Virginia\Riverside\mwe.01\data\input\ed_censusCY2025 (thdn.ed_censusCY2025) (CLIENT).hyper",
    r"C:\Users\medwards\OneDrive - HDR, Inc\Arch. Advisory Services - Clients\Virginia\Riverside\mwe.01\data\input\ed_uc (thdn.ed_uc) (CLIENT).hyper"
]

twb_path = Path(
    r"C:\Users\medwards\OneDrive - HDR, Inc\Arch. Advisory Services - Clients\Virginia\Riverside\mwe.01\data\input\ED_THRDenton.twb"
)

output_file = Path("hyper_schema_summary.txt")

# --------------------------------------------------
# SAFE COPY (avoids lock issues)
# --------------------------------------------------

def get_temp_copy(path):
    temp_dir = Path(tempfile.mkdtemp())
    temp_file = temp_dir / Path(path).name
    shutil.copy2(path, temp_file)
    return temp_file

# --------------------------------------------------
# DESCRIBE (Hyper-native)
# --------------------------------------------------

def describe_hyper(hyper_path):
    results = []

    results.append("=" * 80)
    results.append(f"FILE: {hyper_path}")
    results.append("=" * 80)

    safe_path = get_temp_copy(hyper_path)

    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(endpoint=hyper.endpoint,
                        database=str(safe_path)) as conn:

            catalog = conn.catalog

            for schema in catalog.get_schema_names():
                for table in catalog.get_table_names(schema):

                    results.append(f"\nTable: {table.schema_name}.{table.name}")

                    # Row count
                    try:
                        count = conn.execute_scalar_query(
                            f"SELECT COUNT(*) FROM {table.schema_name}.{table.name}"
                        )
                        results.append(f"Row Count: {count:,}")
                    except Exception as e:
                        results.append(f"Row Count: (error: {e})")

                    # Columns
                    table_def = catalog.get_table_definition(table)

                    results.append("\nColumns:")
                    results.append("-" * 50)

                    for col in table_def.columns:
                        col_name = col.name.unescaped
                        col_type = str(col.type)

                        # ✅ Avoid nullability bug entirely
                        results.append(
                            f"{col_name:35} | {col_type}"
                        )

                    field_names = []

                    for col in table_def.columns:
                        col_name = col.name.unescaped
                        col_type = str(col.type)

                        field_names.append(col_name)

                        results.append(f"{col_name:35} | {col_type}")                   

    return results, field_names

def analyze_twb_usage(twb_file, fields):
    results = []

    results.append("\n" + "=" * 80)
    results.append("FIELD USAGE REPORT")
    results.append("=" * 80)

    # Load workbook XML
    content = twb_file.read_text(encoding="utf-8", errors="ignore")

    for field in sorted(set(fields)):
        pattern = re.escape(field)

        matches = re.findall(rf".{{0,80}}{pattern}.{{0,80}}", content, re.IGNORECASE)

        if matches:
            results.append(f"\nFIELD: {field}")
            results.append(f"✅ USED ({len(matches)} occurrences)")

            # Show sample contexts (cap at 5 for readability)
            for m in matches[:5]:
                cleaned = m.replace("\n", " ").strip()
                results.append(f"  - {cleaned}")

        else:
            results.append(f"\nFIELD: {field}")
            results.append("⚠️ NOT FOUND IN WORKBOOK")

    return results

# --------------------------------------------------
# MAIN
# --------------------------------------------------

all_output = []
all_fields = []

for file in hyper_files:
    print(f"\n🔍 Inspecting: {file}")
    try:
        result, fields = describe_hyper(file)
        all_output.extend(result)
        all_fields.extend(fields)
    except Exception as e:
        msg = f"❌ Error reading {file}: {e}"
        print(msg)
        all_output.append(msg)

if twb_path.exists():
    log_msg = f"\n🔍 Analyzing TWB: {twb_path}"
    print(log_msg)
    all_output.append(log_msg)

    usage_report = analyze_twb_usage(twb_path, all_fields)
    all_output.extend(usage_report)
else:
    msg = f"\n⚠️ TWB file not found: {twb_path}"
    print(msg)
    all_output.append(msg)

# --------------------------------------------------
# OUTPUT
# --------------------------------------------------

output_text = "\n".join(all_output)

print("\n" + output_text)

with open(output_file, "w", encoding="utf-8") as f:
    f.write(output_text)

print(f"\n✅ Schema summary saved to: {output_file}")