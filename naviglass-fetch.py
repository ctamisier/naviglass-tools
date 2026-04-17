import argparse
import asyncio
import json
import os
import sys

try:
    import aiohttp
except ImportError:
    print("Dépendance manquante : pip install aiohttp aiofiles", file=sys.stderr)
    sys.exit(1)

try:
    import aiofiles
except ImportError:
    print("Dépendance manquante : pip install aiohttp aiofiles", file=sys.stderr)
    sys.exit(1)

API_URL = "https://naviglass.saint-gobain-glass.com/api/internet-fiche"

DEFAULT_CONCURRENT = 50
DEFAULT_RETRIES = 3
RETRY_DELAY = 0.5  # secondes entre deux tentatives

# Alphabet Naviglass : chiffres 0-9 puis A,C,E,F,H,K (base 16 custom)
ALPHABET = "0123456789ACEFHK"
ALPHA_INDEX = {c: i for i, c in enumerate(ALPHABET)}


def code_to_int(code: str) -> int:
    """Convertit un code Naviglass en entier (base 16 custom)."""
    result = 0
    for char in code.upper():
        if char not in ALPHA_INDEX:
            raise ValueError(f"Caractere invalide dans le code : '{char}'. Alphabet autorise : {ALPHABET}")
        result = result * 16 + ALPHA_INDEX[char]
    return result


def int_to_code(n: int, length: int) -> str:
    """Convertit un entier en code Naviglass de longueur fixe."""
    digits = []
    for _ in range(length):
        digits.append(ALPHABET[n % 16])
        n //= 16
    if n != 0:
        raise OverflowError("L'entier est trop grand pour la longueur de code demandee.")
    return "".join(reversed(digits))


def generate_range(start: str, end: str) -> list[str]:
    """Genere tous les codes Naviglass entre start et end inclus."""
    start = start.upper()
    end = end.upper()

    if len(start) != len(end):
        raise ValueError(
            f"Les deux codes doivent avoir la meme longueur ({len(start)} vs {len(end)})."
        )

    n_start = code_to_int(start)
    n_end = code_to_int(end)

    if n_start > n_end:
        raise ValueError(f"Le code de debut ({start}) est superieur au code de fin ({end}).")

    length = len(start)
    return [int_to_code(n, length) for n in range(n_start, n_end + 1)]


async def fetch_and_save(
        session: aiohttp.ClientSession,
        code: str,
        index: int,
        total: int,
        existing_files: set[str],
        retries: int,
) -> bool:
    prefix = f"[{index}/{total}] {code}"

    # Check fichier déjà présent (set pré-calculé, O(1))
    if f"{code}.json" in existing_files or any(f.startswith(code) for f in existing_files):
        print(f"{prefix} → [SKIP]")
        return True

    url = f"{API_URL}?code={code}"

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url) as response:
                if response.status == 500:
                    print(f"{prefix} → [INEXISTANT] code inconnu (HTTP 500)")
                    return False
                if response.status != 200:
                    print(f"{prefix} → [ERREUR] HTTP {response.status}", file=sys.stderr)
                    return False
                raw = await response.read()
                data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"{prefix} → [ERREUR] JSON invalide : {e}", file=sys.stderr)
            return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == retries:
                print(f"{prefix} → [ERREUR] {type(e).__name__}: {e} (abandon apres {retries} tentatives)",
                      file=sys.stderr)
                return False
            wait = RETRY_DELAY * attempt
            print(f"{prefix} → [RETRY {attempt}/{retries}] dans {wait}s")
            await asyncio.sleep(wait)
        else:
            break  # Pas d'exception : succès, on sort de la boucle
    else:
        return False  # Toutes les tentatives ont échoué

    naviglass_id = (
            data.get("identifiantNaviglass")
            or data.get("id")
            or data.get("code")
            or code
    )

    filename = os.path.join("data", f"{naviglass_id}.json")
    async with aiofiles.open(filename, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))

    print(f"{prefix} → [OK] {filename}")
    return True


async def worker(
        queue: asyncio.Queue,
        session: aiohttp.ClientSession,
        total: int,
        existing_files: set[str],
        retries: int,
        results: list,
) -> None:
    while True:
        try:
            index, code = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        ok = await fetch_and_save(session, code, index, total, existing_files, retries)
        results.append(ok)
        queue.task_done()


async def run(codes: list[str], concurrent: int, retries: int) -> int:
    total = len(codes)

    os.makedirs("data", exist_ok=True)
    existing_files = {f for f in os.listdir("data") if f.endswith(".json")}

    # File avec tous les codes à traiter
    queue: asyncio.Queue = asyncio.Queue()
    for i, code in enumerate(codes, 1):
        queue.put_nowait((i, code))

    # Timeouts explicites sur chaque phase de la connexion
    timeout = aiohttp.ClientTimeout(
        total=60,  # durée max totale par requête
        connect=10,  # connexion TCP + SSL handshake
        sock_connect=10,  # connexion socket
        sock_read=30,  # lecture de la réponse
    )
    connector = aiohttp.TCPConnector(
        limit=concurrent,
        limit_per_host=concurrent,
        ttl_dns_cache=600,
        enable_cleanup_closed=True,
    )

    results: list[bool] = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        workers = [
            asyncio.create_task(
                worker(queue, session, total, existing_files, retries, results)
            )
            for i in range(concurrent)
        ]
        await queue.join()
        for w in workers:
            w.cancel()

    return sum(results)


def load_codes(filepath: str) -> list[str]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            codes = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Fichier introuvable : {filepath}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Impossible de lire le fichier : {e}", file=sys.stderr)
        sys.exit(1)

    if not codes:
        print("Le fichier ne contient aucun code.", file=sys.stderr)
        sys.exit(1)

    return codes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recupere des fiches Naviglass en parallele et les enregistre en JSON."
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "fichier",
        nargs="?",
        help="Fichier texte avec un code Naviglass par ligne",
    )
    source.add_argument(
        "--range",
        nargs=2,
        metavar=("DEBUT", "FIN"),
        help="Genere et fetche tous les codes entre DEBUT et FIN inclus (ex: --range 10023HC49900 10023HC499FF)",
    )

    parser.add_argument(
        "--concurrent", type=int, default=DEFAULT_CONCURRENT, metavar="N",
        help=f"Requetes simultanees (defaut : {DEFAULT_CONCURRENT})",
    )
    parser.add_argument(
        "--retries", type=int, default=DEFAULT_RETRIES, metavar="N",
        help=f"Tentatives par code en cas d'erreur reseau (defaut : {DEFAULT_RETRIES})",
    )
    args = parser.parse_args()

    if args.range:
        start, end = args.range
        try:
            codes = generate_range(start, end)
        except (ValueError, KeyError) as e:
            print(f"Erreur de plage : {e}", file=sys.stderr)
            sys.exit(1)
        print(f"{len(codes)} code(s) dans la plage [{start.upper()} … {end.upper()}]")
    else:
        codes = load_codes(args.fichier)

    total = len(codes)
    print(f"{total} code(s) — {args.concurrent} requetes simultanees — {args.retries} tentatives max\n")

    succes = asyncio.run(run(codes, args.concurrent, args.retries))

    print(f"\nTermine : {succes}/{total} fichier(s) enregistre(s).")
    if succes < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
