#!/usr/bin/env python3
"""Write a Temple Main antibiogram transcript from parked PDFs.

This is a typed copy of printed cells. It is not an AT-12 event.
2017 is printed as 'TEMPLE UNIVERSITY HOSPITAL', not Main Campus.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "parked_antibiograms"
OUT = ROOT / "data" / "derived" / "antibiograms"

SOURCES = {
    2017: {
        "pdf": RAW / "TUH_Antibiogram_2017.pdf",
        "campus_id": "TUH",
        "campus_as_printed": "TEMPLE UNIVERSITY HOSPITAL",
        "period_start": "2017-01-01",
        "period_end": "2017-12-31",
        "title": "ANTIBIOTIC SUSCEPTIBILITY PROFILE 2017",
    },
    2024: {
        "pdf": RAW / "TUH_Main_Antibiogram_2024.pdf",
        "campus_id": "TUH-Main",
        "campus_as_printed": "TEMPLE UNIVERSITY HOSPITAL – MAIN CAMPUS",
        "period_start": "2024-01-01",
        "period_end": "2024-12-31",
        "title": "ANTIBIOTIC SUSCEPTIBILITY PROFILE 2024",
    },
    2025: {
        "pdf": RAW / "TUH_Main_Antibiogram_2025.pdf",
        "campus_id": "TUH-Main",
        "campus_as_printed": "TEMPLE UNIVERSITY HOSPITAL – MAIN CAMPUS",
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
        "title": "ANTIBIOTIC SUSCEPTIBILITY PROFILE 2025",
    },
}

GN_2017 = [
    "ampicillin",
    "amox_clav",
    "amp_sulbact",
    "cefazolin",
    "ceftazidime",
    "cefepime",
    "ceftriaxone",
    "pip_tazo",
    "aztreonam",
    "meropenem",
    "ciprofloxacin",
    "levofloxacin",
    "gentamicin",
    "tobramycin",
    "amikacin",
    "trimeth_sulfa",
    "ertapenem",
    "nitrofurantoin",
]
GN_2024 = [
    "ampicillin",
    "amox_clav",
    "amp_sulbact",
    "cefazolin",
    "ceftazidime",
    "cefepime",
    "ceftriaxone",
    "pip_tazo",
    "aztreonam",
    "ertapenem",
    "meropenem",
    "minocycline",
    "ciprofloxacin",
    "levofloxacin",
    "gentamicin",
    "tobramycin",
    "amikacin",
    "trimeth_sulfa",
    "nitrofurantoin",
]
GP_2017 = [
    "penicillin",
    "ceftriaxone",
    "cefotaxime",
    "ampicillin",
    "oxacillin",
    "levofloxacin",
    "clindamycin",
    "erythromycin",
    "tetracycline",
    "vancomycin",
    "trimeth_sulfa",
    "linezolid",
    "nitrofurantoin",
]
GP_2024 = GP_2017  # same 13 columns; 2025 adds daptomycin
GP_2025 = GP_2017 + ["daptomycin"]
PNEUMO = ["penicillin", "ceftriaxone", "cefotaxime"]

# Cells are percent susceptible, or IR / ID / INS / "-" / "*".
# 2017 printed 0 for many intrinsically resistant pairs; 0 is stored as 0, not IR.

GN_ROWS = {
    2017: [
        ("Escherichia coli", 1255, [44, 79, 49, 66, 89, 90, 89, 96, 92, 100, 70, 71, 90, 89, 100, 69, 100, 98]),
        ("Citrobacter koseri", 51, [0, 98, 90, 80, 96, 98, 96, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 60]),
        ("Citrobacter freundii", 64, [0, 0, 0, 0, 79, 98, 76, 78, 79, 100, 92, 94, 97, 98, 100, 91, 100, 93]),
        ("Klebsiella pneumoniae", 585, [0, 85, 71, 72, 87, 88, 87, 87, 86, 98, 86, 86, 100, 86, 86, 92, 99, 50]),
        ("Enterobacter aerogenes", 81, [0, 0, 0, 0, 80, 98, 80, 78, 83, 100, 100, 100, 100, 100, 100, 100, 100, 21]),
        ("Enterobacter cloacae complex", 209, [0, 0, 0, 0, 77, 88, 74, 78, 79, 100, 92, 97, 98, 95, 100, 86, 97, 35]),
        ("Morganella morganii", 60, [0, 0, 22, 0, 91, 98, 86, 100, 98, 100, 72, 86, 83, 93, 100, 76, 100, 0]),
        ("Proteus mirabilis", 286, [79, 95, 84, 2, 99, 96, 94, 99, 99, "ID", 81, 83, 93, 90, 99, 88, 100, 0]),
        ("Serratia marcescens", 91, [0, 0, 0, 0, 99, 98, 89, 91, 94, 99, 92, 99, 99, 81, 99, 67, 100, 0]),
        ("Acinetobacter baumannii complex", 77, [0, 0, "ID", 0, "ID", 56, 32, "ID", 0, 28, 53, 57, 68, 82, 87, 61, 0, 0]),
        ("Haemophilus influenzae", 107, [65, "ID", "ID", 0, "ID", "ID", 100, "ID", 0, "ID", 0, "ID", 0, 0, 0, 0, 0, 0]),
        ("Pseudomonas aeruginosa", 457, [0, 0, 0, 0, 90, 89, 0, 85, 78, 84, 79, 78, 96, 97, 99, 0, 0, 0]),
        ("Stenotrophomonas maltophilia", 81, [0, 0, 0, 0, 48, 0, 0, 0, 0, 0, 0, 77, 0, 0, 0, 97, 0, 0]),
    ],
    2024: [
        ("Escherichia coli", 1603, [41, 82, 50, 62, 85, 82, 80, 94, 82, 99, 99, "-", 60, 71, 88, 88, 100, 64, 97]),
        ("Citrobacter koseri", 64, ["IR", 97, 90, 90, 97, 99, 97, 97, 99, 100, 100, 100, 99, 99, 99, 100, 100, 100, "-"]),
        ("Citrobacter freundii complex", 51, ["IR", "IR", "IR", "IR", 80, 92, 84, 99, 80, 98, 98, "INS", 84, 88, 94, 96, 98, 92, "INS"]),
        ("Klebsiella pneumoniae ssp", 744, ["IR", 81, 60, 61, 72, 74, 72, 82, 73, 96, 97, "-", 68, 73, 89, 84, 100, 72, 45]),
        ("Klebsiella oxytoca", 101, ["IR", 87, 53, 46, 98, 99, 92, 93, 94, 100, 100, 97, 93, 97, 99, 98, 100, 95, 89]),
        ("Klebsiella aerogenes", 87, ["IR", "IR", "IR", "IR", 66, 94, 65, 69, 67, 98, 100, 92, 98, 99, 100, 100, 100, 98, 57]),
        ("Enterobacter cloacae complex", 213, ["IR", "IR", "IR", "IR", 74, 86, 71, 77, 77, 97, 100, 85, 92, 95, 99, 98, 100, 88, 33]),
        ("Morganella morganii", 78, ["IR", "IR", "INS", "IR", 86, 96, 94, 98, 96, 99, 100, "IR", 70, 70, 94, 91, 99, 70, "IR"]),
        ("Proteus mirabilis", 530, [69, 97, 83, 4, 93, 88, 85, 99, 95, 100, "INS", "IR", 73, 74, 86, 83, 97, 76, "IR"]),
        ("Providencia stuartii", 64, ["IR", "IR", "INS", "IR", 71, 76, 71, 83, 81, 100, 100, "IR", 24, 24, "IR", "IR", 100, 73, "IR"]),
        ("Serratia marcescens", 131, ["IR", "IR", "IR", "IR", 88, 84, 70, 86, 83, 95, 97, 0, 68, 72, 97, 68, 97, 100, "IR"]),
        ("Acinetobacter calcoaceticus-baumannii complex", 119, ["IR", "IR", 37, "IR", 33, 24, 19, "INS", "IR", "IR", 27, 32, 23, 25, 38, 49, 55, 40, "IR"]),
        ("Haemophilus influenzae", 83, [76, 76, 76, "-", "-", "-", 100, "-", "-", "-", "-", 100, 100, "-", "-", "-", "-", 55, "-"]),
        ("Pseudomonas aeruginosa", 751, ["IR", "IR", "IR", "IR", 74, 79, "IR", 68, 64, "IR", 74, "IR", 66, 66, 93, 98, 99, "IR", "IR"]),
        ("Stenotrophomonas maltophilia", 117, ["IR", "IR", "IR", "IR", "IR", "IR", "IR", "IR", "IR", "IR", "IR", 93, "-", 69, "IR", "IR", "IR", 95, "IR"]),
    ],
    2025: [
        ("Escherichia coli", 1630, [41, 81, 50, 62, 85, 82, 78, 94, 82, 98, 98, "-", 56, 68, 87, 87, 100, 60, 97]),
        ("Citrobacter koseri", 68, ["IR", 99, 94, 90, 99, 100, 99, 97, 97, 97, 100, "-", 99, 99, 100, 100, 100, 100, 64]),
        ("Citrobacter freundii complex", 62, ["IR", "IR", "IR", "IR", 77, 95, 72, 78, 77, 94, 98, "-", 84, 88, 94, 94, 100, 88, 91]),
        ("Klebsiella pneumoniae ssp", 816, ["IR", 79, 58, 59, 70, 72, 71, 81, 78, 93, 95, "INS", 69, 75, 89, 83, 100, 69, 48]),
        ("Klebsiella oxytoca", 89, ["IR", 90, 57, 38, 91, 94, 88, 91, 87, 96, 97, "-", 93, 97, 95, 94, 100, 89, "INS"]),
        ("Klebsiella aerogenes", 85, ["IR", "IR", "IR", "IR", 66, 88, 64, 69, 65, 94, 98, "-", 93, 95, 100, 100, 100, 98, "INS"]),
        ("Enterobacter cloacae complex", 252, ["IR", "IR", "IR", "IR", 70, 83, 69, 76, 71, 76, 97, "-", 86, 92, 96, 95, 100, 86, 37]),
        ("Morganella morganii", 71, ["IR", "IR", 26, "IR", 85, 100, 93, 93, 97, 100, 100, "IR", 66, 66, 88, 92, 100, 73, "IR"]),
        ("Proteus mirabilis", 505, [75, 97, 89, 2, 92, 88, 86, 99, 92, 98, "INS", "IR", 75, 77, 84, 82, 95, 76, "IR"]),
        ("Providencia stuartii", 63, ["IR", "IR", 16, "IR", 69, 78, 67, 91, 80, 95, 98, "IR", 25, 28, "IR", "IR", 97, 69, "IR"]),
        ("Serratia marcescens", 138, ["IR", "IR", "IR", "IR", 75, 69, 63, 81, 71, 85, 94, "INS", 66, 71, 94, 66, 98, "INS", "IR"]),
        ("Acinetobacter calcoaceticus-baumannii complex", 101, ["IR", "IR", 47, "IR", 48, 37, 26, "INS", "IR", "IR", 41, 66, 40, 42, 54, 66, 74, 53, "IR"]),
        ("Haemophilus influenzae", 74, [80, 80, 80, "-", "-", "-", 100, "-", "-", "-", "-", "-", 100, "-", "-", "-", "-", "-", "-"]),
        ("Pseudomonas aeruginosa", 751, ["IR", "IR", "IR", "IR", 68, 73, "IR", 63, 60, "IR", 72, "IR", 68, 68, "INS", 96, 99, "IR", "IR"]),
        ("Stenotrophomonas maltophilia", 144, ["IR", "IR", "IR", "IR", "IR", "IR", "IR", "IR", "IR", "IR", "IR", 95, "-", 70, "IR", "IR", "IR", 96, "IR"]),
    ],
}

GP_ROWS = {
    2017: [
        ("Staphylococcus aureus", 1046, ["ID", 57, 57, 57, 57, "ID", 68, 35, 92, 100, 95, 100, 100]),
        ("Staphylococcus epidermidis", 233, [9, 37, 37, "ID", 37, "ID", 47, 25, 80, 100, 45, "ID", 100]),
        ("Enterococcus faecalis", 492, ["ID", 0, 0, 100, 0, "ID", 0, "ID", "ID", 95, 0, "ID", 99]),
        ("Enterococcus faecium", 182, ["ID", 0, 0, 11, 0, "ID", 0, "ID", "ID", 19, 0, 97, "ID"]),
        ("Streptococcus agalactiae", 353, [100, 100, 100, 100, 100, 99, 57, 37, "ID", 100, 0, 100, 0]),
        ("Streptococcus pneumoniae", 86, ["*", "*", "*", "ID", "ID", "ID", 85, 58, 78, 100, "ID", 100, 0]),
    ],
    2024: [
        ("Staphylococcus aureus", 1434, ["-", 41, 41, "-", 41, 74, 76, 27, 65, 100, 98, 100, 100]),
        ("Staphylococcus epidermidis", 452, ["-", 44, 44, "-", 44, 72, 52, 29, 75, 100, 33, "INS", 99]),
        ("Enterococcus faecalis", 379, ["-", "IR", "IR", 99, "-", "-", "IR", "-", "-", 96, "IR", "-", 100]),
        ("Enterococcus faecium", 166, ["-", "IR", "IR", 8, "-", "-", "IR", "-", "-", 25, "IR", 88, "INS"]),
        ("Streptococcus agalactiae", 395, [100, 100, 100, 100, "-", 100, 33, 20, "-", 100, "-", 100, "-"]),
        ("Streptococcus pyogenes", 222, [100, 100, 100, 100, "-", 91, 49, 46, "-", 100, "-", 100, "-"]),
        ("Streptococcus pneumoniae", 97, [100, 100, 100, "-", "-", 92, 87, 81, 79, 100, 80, 100, "-"]),
    ],
    2025: [
        ("Staphylococcus aureus", 1342, ["-", 47, 47, "-", 47, 76, 78, 32, 69, 100, 87, 100, 100, "-"]),
        ("Staphylococcus epidermidis", 489, ["-", 46, 46, "-", 46, 71, 52, 32, 76, 100, 50, 99, 100, "-"]),
        ("Enterococcus faecalis", 348, ["-", "IR", "IR", 98, "-", "-", "IR", "-", "-", 95, "IR", 99, 98, 75]),
        ("Enterococcus faecium", 173, ["-", "IR", "IR", 8, "-", "-", "IR", "-", "-", 29, "IR", 92, 46, 90]),
        ("Streptococcus agalactiae", 369, [100, 100, 100, 100, "-", 98, 41, 23, "-", 100, "-", 100, "-", "-"]),
        ("Streptococcus pyogenes", 157, [100, 100, 100, 100, "-", 77, 71, 70, "-", 100, "-", 100, "-", "-"]),
        ("Streptococcus pneumoniae", 93, ["*", "*", "*", "-", "-", 96, 92, 82, 80, 100, 84, 100, "-", "-"]),
    ],
}

PNEUMO_SUB = {
    2017: [
        ("Streptococcus pneumoniae meningitis", None, [90, 100, 100]),
        ("Streptococcus pneumoniae non-meningitis", None, [99, 100, 100]),
        ("Streptococcus pneumoniae oral penicillin V", None, [90, "-", "-"]),
    ],
    2024: [
        ("Streptococcus pneumoniae meningitis", 57, [98, 100, 100]),
        ("Streptococcus pneumoniae non-meningitis", 57, [100, 100, 100]),
        ("Streptococcus pneumoniae oral penicillin V", 57, [98, 100, 100]),
    ],
    2025: [
        ("Streptococcus pneumoniae meningitis", 38, [92, 97, 100]),
        ("Streptococcus pneumoniae non-meningitis", 38, [100, 97, 100]),
        ("Streptococcus pneumoniae oral penicillin V", 38, [92, "-", "-"]),
    ],
}

HL_NOTES = {
    2017: {
        "Enterococcus faecalis": {"high_level_gentamicin": 78, "high_level_streptomycin": 82},
        "Enterococcus faecium": {"high_level_gentamicin": 96, "high_level_streptomycin": 84},
    },
    2024: {
        "Enterococcus faecalis": {"high_level_gentamicin": 77, "high_level_streptomycin": 87},
        "Enterococcus faecium": {"high_level_gentamicin": 96, "high_level_streptomycin": 63},
    },
    2025: {
        "Enterococcus faecalis": {"high_level_gentamicin": 79, "high_level_streptomycin": 89},
        "Enterococcus faecium": {"high_level_gentamicin": 95, "high_level_streptomycin": 75},
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def cell(value):
    if isinstance(value, int):
        return value, None
    flag = str(value)
    return None, flag


def note_for(drug: str, organism: str) -> str:
    notes = []
    if drug == "nitrofurantoin":
        notes.append("urinary_isolates_only")
    if organism.startswith("Streptococcus pneumoniae") and drug in {
        "penicillin",
        "cefotaxime",
        "ceftriaxone",
    }:
        notes.append("s_pneumoniae_breakpoint_depends_on_diagnosis")
    return "|".join(notes)


def expand(year: int, group: str, drugs: list[str], rows: list) -> list[dict]:
    meta = SOURCES[year]
    out = []
    for organism, n, values in rows:
        if len(values) != len(drugs):
            raise ValueError(f"{year} {organism}: {len(values)} cells vs {len(drugs)} drugs")
        for drug, raw in zip(drugs, values, strict=True):
            pct, flag = cell(raw)
            rec = {
                "year": year,
                "campus_id": meta["campus_id"],
                "campus_as_printed": meta["campus_as_printed"],
                "period_start": meta["period_start"],
                "period_end": meta["period_end"],
                "source_pdf": str(meta["pdf"].relative_to(ROOT)),
                "organism": organism,
                "group": group,
                "n_isolates": n,
                "drug": drug,
                "percent_susceptible": pct,
                "flag": flag,
                "note": note_for(drug, organism),
                "not_at12": True,
            }
            out.append(rec)
    return out


def high_level_rows() -> list[dict]:
    out = []
    for year, orgs in HL_NOTES.items():
        meta = SOURCES[year]
        n_by_org = {name: n for name, n, _ in GP_ROWS[year]}
        for organism, drugs in orgs.items():
            for drug, pct in drugs.items():
                out.append(
                    {
                        "year": year,
                        "campus_id": meta["campus_id"],
                        "campus_as_printed": meta["campus_as_printed"],
                        "period_start": meta["period_start"],
                        "period_end": meta["period_end"],
                        "source_pdf": str(meta["pdf"].relative_to(ROOT)),
                        "organism": organism,
                        "group": "gram_positive_footnote",
                        "n_isolates": n_by_org[organism],
                        "drug": drug,
                        "percent_susceptible": pct,
                        "flag": None,
                        "note": "footnote_on_printed_sheet",
                        "not_at12": True,
                    }
                )
    return out


def build_records() -> list[dict]:
    recs: list[dict] = []
    recs += expand(2017, "gram_negative", GN_2017, GN_ROWS[2017])
    recs += expand(2024, "gram_negative", GN_2024, GN_ROWS[2024])
    recs += expand(2025, "gram_negative", GN_2024, GN_ROWS[2025])
    recs += expand(2017, "gram_positive", GP_2017, GP_ROWS[2017])
    recs += expand(2024, "gram_positive", GP_2024, GP_ROWS[2024])
    recs += expand(2025, "gram_positive", GP_2025, GP_ROWS[2025])
    recs += expand(2017, "gram_positive_pneumococcal_subset", PNEUMO, PNEUMO_SUB[2017])
    recs += expand(2024, "gram_positive_pneumococcal_subset", PNEUMO, PNEUMO_SUB[2024])
    recs += expand(2025, "gram_positive_pneumococcal_subset", PNEUMO, PNEUMO_SUB[2025])
    recs += high_level_rows()
    return recs


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in SOURCES.values():
        if not spec["pdf"].is_file():
            raise FileNotFoundError(spec["pdf"])
    records = build_records()
    sources = {
        year: {
            "path": str(spec["pdf"].relative_to(ROOT)),
            "sha256": sha256(spec["pdf"]),
            "campus_id": spec["campus_id"],
            "campus_as_printed": spec["campus_as_printed"],
            "period_start": spec["period_start"],
            "period_end": spec["period_end"],
            "title": spec["title"],
        }
        for year, spec in SOURCES.items()
    }
    payload = {
        "kind": "antibiogram_transcript",
        "not_at12": True,
        "scope": "Temple printed sheets transcribed by hand from parked PDFs. 2017 is not labeled Main Campus.",
        "sources": sources,
        "n_records": len(records),
        "records": records,
    }
    json_path = OUT / "tuh_main_transcript.json"
    csv_path = OUT / "tuh_main_transcript.csv"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    fields = [
        "year",
        "campus_id",
        "campus_as_printed",
        "period_start",
        "period_end",
        "source_pdf",
        "organism",
        "group",
        "n_isolates",
        "drug",
        "percent_susceptible",
        "flag",
        "note",
        "not_at12",
    ]
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(records)
    manifest = {
        "kind": "antibiogram_transcript_manifest",
        "not_at12": True,
        "sources": sources,
        "outputs": {
            "json": {
                "path": str(json_path.relative_to(ROOT)),
                "sha256": sha256(json_path),
                "n_records": len(records),
            },
            "csv": {
                "path": str(csv_path.relative_to(ROOT)),
                "sha256": sha256(csv_path),
                "n_records": len(records),
            },
        },
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {len(records)} records")


if __name__ == "__main__":
    main()
