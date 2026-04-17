import argparse
import csv
import json
import os
import sys

# Colonnes du CSV dans l'ordre souhaité, avec leur chemin dans le JSON
COLUMNS = [
    ("naviglassId",                    lambda d: d.get("naviglassId")),
    ("libArticle",                     lambda d: d.get("libArticle")),
    ("verre1_description",             lambda d: (d.get("verre1") or {}).get("description")),
    ("verre1_epaisseur",               lambda d: (d.get("verre1") or {}).get("epaisseur")),
    ("verre1_codeVisuel",              lambda d: (d.get("verre1") or {}).get("codeVisuel")),
    ("verre1_position",                lambda d: (d.get("verre1") or {}).get("position")),
    ("espaceur1_typeIntercalaire",     lambda d: (d.get("espaceur1") or {}).get("typeIntercalaire")),
    ("espaceur1_couleurIntercalaire",  lambda d: (d.get("espaceur1") or {}).get("couleurIntercalaire")),
    ("espaceur1_espaceGaz",            lambda d: (d.get("espaceur1") or {}).get("espaceGaz")),
    ("espaceur1_typeGaz",              lambda d: (d.get("espaceur1") or {}).get("typeGaz")),
    ("verre2_description",             lambda d: (d.get("verre2") or {}).get("description")),
    ("verre2_epaisseur",               lambda d: (d.get("verre2") or {}).get("epaisseur")),
    ("verre2_codeVisuel",              lambda d: (d.get("verre2") or {}).get("codeVisuel")),
    ("verre2_position",                lambda d: (d.get("verre2") or {}).get("position")),
    ("espaceur2_typeIntercalaire",     lambda d: (d.get("espaceur2") or {}).get("typeIntercalaire")),
    ("espaceur2_couleurIntercalaire",  lambda d: (d.get("espaceur2") or {}).get("couleurIntercalaire")),
    ("espaceur2_espaceGaz",            lambda d: (d.get("espaceur2") or {}).get("espaceGaz")),
    ("espaceur2_typeGaz",              lambda d: (d.get("espaceur2") or {}).get("typeGaz")),
    ("verre3_description",             lambda d: (d.get("verre3") or {}).get("description")),
    ("verre3_epaisseur",               lambda d: (d.get("verre3") or {}).get("epaisseur")),
    ("verre3_codeVisuel",              lambda d: (d.get("verre3") or {}).get("codeVisuel")),
    ("verre3_position",                lambda d: (d.get("verre3") or {}).get("position")),
    ("dateCommande",                   lambda d: d.get("dateCommande")),
    ("cekal",                          lambda d: d.get("cekal")),
    ("centreProduction",               lambda d: d.get("centreProduction")),
    ("performanceThermique",           lambda d: d.get("performanceThermique")),
    ("classeAcoustique",               lambda d: d.get("classeAcoustique")),
    ("extension",                      lambda d: d.get("extension")),
    ("origineFranceGarantie",          lambda d: d.get("origineFranceGarantie")),
    ("coefficientThermique",           lambda d: d.get("coefficientThermique")),
    ("stadip",                         lambda d: d.get("stadip")),
]

HEADERS = [col for col, _ in COLUMNS]


def read_json_dir(directory: str) -> list[dict]:
    rows = []
    files = sorted(f for f in os.listdir(directory) if f.endswith(".json"))

    if not files:
        print(f"Aucun fichier .json trouvé dans : {directory}", file=sys.stderr)
        sys.exit(1)

    errors = 0
    for filename in files:
        path = os.path.join(directory, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rows.append({col: extractor(data) for col, extractor in COLUMNS})
        except (json.JSONDecodeError, OSError) as e:
            print(f"[ERREUR] {filename} : {e}", file=sys.stderr)
            errors += 1

    print(f"{len(rows)} fichier(s) lus, {errors} erreur(s).")
    return rows


def write_csv(rows: list[dict], output: str) -> None:
    with open(output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV enregistré : {output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convertit un répertoire de fichiers JSON Naviglass en CSV."
    )
    parser.add_argument(
        "repertoire",
        help="Répertoire contenant les fichiers JSON (ex: ./data)",
    )
    parser.add_argument(
        "-o", "--output",
        default="naviglass.csv",
        help="Nom du fichier CSV de sortie (défaut : naviglass.csv)",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.repertoire):
        print(f"Répertoire introuvable : {args.repertoire}", file=sys.stderr)
        sys.exit(1)

    rows = read_json_dir(args.repertoire)
    write_csv(rows, args.output)


if __name__ == "__main__":
    main()