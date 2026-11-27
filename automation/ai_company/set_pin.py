from getpass import getpass
from pathlib import Path
import os
import re
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def main():
    print("Pengaturan PIN CEO InfoLoker")
    print("Minimal 12 karakter. PIN tidak akan ditampilkan.")

    first = getpass("Masukkan PIN baru: ")
    second = getpass("Ulangi PIN baru: ")

    if len(first) < 12:
        raise SystemExit("PIN minimal harus 12 karakter.")

    if first != second:
        raise SystemExit("Kedua PIN tidak sama.")

    if "\n" in first or "\r" in first:
        raise SystemExit("PIN tidak boleh mengandung baris baru.")

    old_text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = old_text.splitlines()

    replacement = "CEO_SECRET_PIN=" + first
    found = False
    output = []

    for line in lines:
        if re.match(r"^\s*CEO_SECRET_PIN\s*=", line):
            if not found:
                output.append(replacement)
                found = True
        else:
            output.append(line)

    if not found:
        output.append(replacement)

    new_text = "\n".join(output).rstrip() + "\n"

    fd, temp_path = tempfile.mkstemp(
        prefix=".env.",
        dir=str(PROJECT_ROOT)
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(new_text)
            file.flush()
            os.fsync(file.fileno())

        os.chmod(temp_path, 0o600)
        os.replace(temp_path, ENV_FILE)
        os.chmod(ENV_FILE, 0o600)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise

    print("PIN CEO berhasil disimpan ke .env.")
    print("PIN tidak ditampilkan dan tidak dicetak ke terminal.")


if __name__ == "__main__":
    main()
