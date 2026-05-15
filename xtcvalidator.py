#!/usr/bin/env python3
"""
XTC/XTCH File Validator & Inspector
Validuje a zobrazuje technické informace ze souborů formátů XTC a XTCH.
Specifikace: XTC/XTG/XTH/XTCH Format Technical Specification v1.0
"""

import struct
import sys
import os
import datetime
from pathlib import Path


# ── Konstanty ──────────────────────────────────────────────────────────────────

MAGIC = {
    0x00475458: "XTG",
    0x00485458: "XTH",
    0x00435458: "XTC",
    0x48435458: "XTCH",
}

READ_DIRECTION = {0: "L→R (zleva doprava)", 1: "R→L (zprava doleva, japonská manga)", 2: "Shora dolů"}

XTG_MAGIC = 0x00475458
XTH_MAGIC = 0x00485458
XTC_MAGIC  = 0x00435458
XTCH_MAGIC = 0x48435458

HEADER_SIZE_CONTAINER = 56
HEADER_SIZE_IMAGE     = 22
METADATA_SIZE         = 256
CHAPTER_ENTRY_SIZE    = 96
INDEX_ENTRY_SIZE      = 16


# ── Pomocné funkce ──────────────────────────────────────────────────────────────

def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n} {unit}"
        n //= 1024
    return f"{n} TB"


def hex32(v: int) -> str:
    return f"0x{v:08X}"


def read_cstr(data: bytes, offset: int, max_len: int) -> str:
    chunk = data[offset:offset + max_len]
    end = chunk.find(b"\x00")
    raw = chunk[:end] if end != -1 else chunk
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace") + " [CHYBNÉ UTF-8!]"


def section(title: str, width: int = 70) -> str:
    return f"\n{'═' * width}\n  {title}\n{'═' * width}"


def row(label: str, value, indent: int = 4) -> str:
    pad = " " * indent
    return f"{pad}{label:<35} {value}"


def warn(msg: str) -> str:
    return f"  ⚠️  {msg}"


def ok(msg: str) -> str:
    return f"  ✅ {msg}"


def error(msg: str) -> str:
    return f"  ❌ {msg}"


# ── Validace XTG/XTH hlavičky (obrázek) ────────────────────────────────────────

def inspect_image_header(data: bytes, base_offset: int, file_size: int, index: int = None) -> dict:
    """Parsuje a validuje 22-bajtovou hlavičku XTG/XTH obrázku.
    Vrací dict s informacemi a seznamem chyb/varování."""
    result = {"errors": [], "warnings": [], "info": {}}
    label = f"stránka {index}" if index is not None else "obrázek"

    if len(data) < base_offset + HEADER_SIZE_IMAGE:
        result["errors"].append(f"[{label}] Soubor je příliš krátký pro hlavičku obrázku (offset {hex(base_offset)})")
        return result

    chunk = data[base_offset:]
    mark, width, height, color_mode, compression, data_size = struct.unpack_from("<IHHBBIQ"[:7], chunk, 0)
    # Přesný rozklad:
    mark       = struct.unpack_from("<I", chunk, 0)[0]
    width      = struct.unpack_from("<H", chunk, 4)[0]
    height     = struct.unpack_from("<H", chunk, 6)[0]
    color_mode = chunk[8]
    compression = chunk[9]
    data_size  = struct.unpack_from("<I", chunk, 10)[0]
    md5_bytes  = chunk[14:22]

    fmt_name = MAGIC.get(mark, f"NEZNÁMÝ ({hex32(mark)})")

    result["info"] = {
        "mark": mark,
        "format": fmt_name,
        "width": width,
        "height": height,
        "color_mode": color_mode,
        "compression": compression,
        "data_size": data_size,
        "md5": md5_bytes,
    }

    # Validace magic
    if mark not in (XTG_MAGIC, XTH_MAGIC):
        result["errors"].append(f"[{label}] Neplatný magic: {hex32(mark)} (očekáváno XTG nebo XTH)")

    # Validace rozměrů
    if width == 0:
        result["errors"].append(f"[{label}] Šířka je 0")
    if height == 0:
        result["errors"].append(f"[{label}] Výška je 0")

    # Validace color_mode a compression
    if color_mode != 0:
        result["warnings"].append(f"[{label}] colorMode={color_mode} (specifikace definuje pouze 0=monochrome)")
    if compression != 0:
        result["warnings"].append(f"[{label}] compression={compression} (specifikace definuje pouze 0=nekomprimováno)")

    # Validace dataSize
    if mark == XTG_MAGIC:
        expected = ((width + 7) // 8) * height
    else:  # XTH
        expected = ((width * height + 7) // 8) * 2

    if data_size != expected:
        result["errors"].append(
            f"[{label}] dataSize={data_size}, očekáváno {expected} "
            f"({'XTG' if mark == XTG_MAGIC else 'XTH'} výpočet pro {width}×{height})"
        )

    # Kontrola, zda data přesahují soubor
    data_end = base_offset + HEADER_SIZE_IMAGE + data_size
    if data_end > file_size:
        result["errors"].append(
            f"[{label}] Obrazová data by přesahovala soubor "
            f"(konec dat: {data_end}, velikost souboru: {file_size})"
        )

    return result


# ── Hlavní parser XTC/XTCH ───────────────────────────────────────────────────────

def inspect_xtc(path: str) -> None:
    path = Path(path)
    lines = []
    all_errors = []
    all_warnings = []

    def add(line: str):
        lines.append(line)

    def e(msg: str):
        all_errors.append(msg)
        add(error(msg))

    def w(msg: str):
        all_warnings.append(msg)
        add(warn(msg))

    def g(msg: str):
        add(ok(msg))

    # ── Načtení souboru ──
    if not path.exists():
        print(error(f"Soubor neexistuje: {path}"))
        return

    file_size = path.stat().st_size
    with open(path, "rb") as f:
        data = f.read()

    add(section(f"XTC/XTCH Validátor & Inspektor — {path.name}"))
    add(row("Cesta k souboru:", str(path.resolve())))
    add(row("Velikost souboru:", f"{file_size} B ({format_bytes(file_size)})"))

    # ── Kontrola minimální velikosti ──
    if file_size < HEADER_SIZE_CONTAINER:
        e(f"Soubor je příliš krátký pro hlavičku kontejneru ({file_size} < {HEADER_SIZE_CONTAINER} B)")
        print("\n".join(lines))
        return

    # ── Parsování hlavičky (56 bajtů) ──
    add(section("HLAVIČKA KONTEJNERU (56 bajtů)"))

    mark           = struct.unpack_from("<I", data, 0x00)[0]
    version        = struct.unpack_from("<H", data, 0x04)[0]
    page_count     = struct.unpack_from("<H", data, 0x06)[0]
    read_dir       = data[0x08]
    has_metadata   = data[0x09]
    has_thumbnails = data[0x0A]
    has_chapters   = data[0x0B]
    current_page   = struct.unpack_from("<I", data, 0x0C)[0]
    meta_offset    = struct.unpack_from("<Q", data, 0x10)[0]
    index_offset   = struct.unpack_from("<Q", data, 0x18)[0]
    data_offset    = struct.unpack_from("<Q", data, 0x20)[0]
    thumb_offset   = struct.unpack_from("<Q", data, 0x28)[0]
    chapter_offset = struct.unpack_from("<Q", data, 0x30)[0]

    fmt_name = MAGIC.get(mark, None)

    add(row("Magic (mark):", f"{hex32(mark)}  →  \"{fmt_name or 'NEZNÁMÝ'}\""))
    add(row("Verze:", f"0x{version:04X}  ({version >> 8}.{version & 0xFF})"))
    add(row("Počet stránek:", page_count))
    add(row("Směr čtení:", f"{read_dir}  →  {READ_DIRECTION.get(read_dir, 'NEZNÁMÝ')}"))
    add(row("Má metadata:", f"{has_metadata}  ({'ano' if has_metadata else 'ne'})"))
    add(row("Má miniatury:", f"{has_thumbnails}  ({'ano' if has_thumbnails else 'ne'})"))
    add(row("Má kapitoly:", f"{has_chapters}  ({'ano' if has_chapters else 'ne'})"))
    add(row("Aktuální stránka:", f"{current_page}  (1-based zobrazení)"))
    add(row("Offset metadat:", f"{meta_offset}  ({hex(meta_offset)})"))
    add(row("Offset indexu stránek:", f"{index_offset}  ({hex(index_offset)})"))
    add(row("Offset datové oblasti:", f"{data_offset}  ({hex(data_offset)})"))
    add(row("Offset miniatur:", f"{thumb_offset}  ({hex(thumb_offset)})"))
    add(row("Offset kapitol:", f"{chapter_offset}  ({hex(chapter_offset)})"))

    # ── Validace hlavičky ──
    add(section("VALIDACE HLAVIČKY"))

    if mark not in (XTC_MAGIC, XTCH_MAGIC):
        e(f"Neplatný magic: {hex32(mark)} (očekáváno 0x00435458 XTC nebo 0x48435458 XTCH)")
    else:
        g(f"Magic je platný: {fmt_name} ({hex32(mark)})")

    if version != 0x0100:
        w(f"Neočekávaná verze: 0x{version:04X} (specifikace definuje 0x0100 = v1.0)")
    else:
        g("Verze: 0x0100 (v1.0) — OK")

    if page_count == 0:
        e("Počet stránek je 0")
    else:
        g(f"Počet stránek: {page_count}")

    if read_dir not in (0, 1, 2):
        e(f"Neplatný směr čtení: {read_dir} (povoleno: 0, 1, 2)")
    else:
        g(f"Směr čtení: platný ({read_dir})")

    if has_metadata not in (0, 1):
        w(f"hasMetadata={has_metadata} (očekáváno 0 nebo 1)")
    if has_thumbnails not in (0, 1):
        w(f"hasThumbnails={has_thumbnails} (očekáváno 0 nebo 1)")
    if has_chapters not in (0, 1):
        w(f"hasChapters={has_chapters} (očekáváno 0 nebo 1)")

    # Kontrola offsetů — nesmí přesahovat soubor
    offset_fields = {
        "indexOffset": index_offset,
        "dataOffset":  data_offset,
    }
    if has_metadata:
        offset_fields["metadataOffset"] = meta_offset
    if has_thumbnails:
        offset_fields["thumbOffset"] = thumb_offset
    if has_chapters:
        offset_fields["chapterOffset"] = chapter_offset

    for field, offset in offset_fields.items():
        if offset >= file_size:
            e(f"{field}={offset} přesahuje velikost souboru ({file_size})")
        elif offset == 0 and field not in ("dataOffset",):
            w(f"{field}=0 — může být neplatné, pokud sekce existuje")

    # Kontrola indexOffset + velikosti tabulky
    index_table_size = page_count * INDEX_ENTRY_SIZE
    if index_offset + index_table_size > file_size:
        e(f"Index tabulka ({index_offset} + {index_table_size} B) přesahuje soubor")
    else:
        g(f"Index tabulka: {index_table_size} B na offsetu {index_offset} — OK")

    # ── Metadata ──
    if has_metadata and meta_offset + METADATA_SIZE <= file_size:
        add(section("METADATA (256 bajtů)"))
        m = data[meta_offset:]
        title     = read_cstr(m, 0x00, 128)
        author    = read_cstr(m, 0x80, 64)
        publisher = read_cstr(m, 0xC0, 32)
        language  = read_cstr(m, 0xE0, 16)
        create_time  = struct.unpack_from("<I", m, 0xF0)[0]
        cover_page   = struct.unpack_from("<H", m, 0xF4)[0]
        chapter_count = struct.unpack_from("<H", m, 0xF6)[0]
        reserved     = m[0xF8:0x100]

        add(row("Název (title):", repr(title) if title else "(prázdný)"))
        add(row("Autor:", repr(author) if author else "(prázdný)"))
        add(row("Vydavatel:", repr(publisher) if publisher else "(prázdný)"))
        add(row("Jazyk:", repr(language) if language else "(prázdný)"))

        if create_time:
            dt = datetime.datetime.fromtimestamp(create_time, tz=datetime.timezone.utc)
            add(row("Čas vytvoření:", f"{create_time}  →  {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC"))
        else:
            add(row("Čas vytvoření:", "0 (nenastaveno)"))

        cover_str = "(žádná)" if cover_page == 0xFFFF else str(cover_page)
        add(row("Titulní stránka (0-based):", cover_str))
        add(row("Počet kapitol (v metadatech):", chapter_count))

        if any(reserved):
            w("Rezervované pole metadat není nulové (offset 0xF8)")

    elif has_metadata:
        e(f"metadataOffset={meta_offset} + {METADATA_SIZE} přesahuje soubor")

    # ── Kapitoly ──
    if has_chapters:
        chapter_count_hdr = 0
        if has_metadata and meta_offset + METADATA_SIZE <= file_size:
            chapter_count_hdr = struct.unpack_from("<H", data, meta_offset + 0xF6)[0]

        if chapter_count_hdr > 0 and chapter_offset + chapter_count_hdr * CHAPTER_ENTRY_SIZE <= file_size:
            add(section(f"KAPITOLY ({chapter_count_hdr} záznamy × 96 bajtů)"))
            for i in range(chapter_count_hdr):
                off = chapter_offset + i * CHAPTER_ENTRY_SIZE
                c = data[off:]
                ch_name  = read_cstr(c, 0x00, 80)
                start_pg = struct.unpack_from("<H", c, 0x50)[0]
                end_pg   = struct.unpack_from("<H", c, 0x52)[0]
                r1 = struct.unpack_from("<I", c, 0x54)[0]
                r2 = struct.unpack_from("<I", c, 0x58)[0]
                r3 = struct.unpack_from("<I", c, 0x5C)[0]

                add(f"\n    Kapitola {i}:")
                add(row("  Název:", repr(ch_name)))
                add(row("  Začátek (0-based):", start_pg))
                add(row("  Konec (0-based, včetně):", end_pg))
                if r1 or r2 or r3:
                    w(f"  Kapitola {i}: rezervovaná pole nejsou nulová ({r1}, {r2}, {r3})")

                # Logická validace
                if start_pg > end_pg:
                    e(f"Kapitola {i}: startPage ({start_pg}) > endPage ({end_pg})")
                if page_count > 0 and end_pg >= page_count:
                    e(f"Kapitola {i}: endPage ({end_pg}) >= pageCount ({page_count})")
        elif has_chapters:
            w("Kapitoly jsou označeny jako přítomné, ale nelze je načíst (offset nebo počet neplatný)")

    # ── Index stránek ──
    if index_offset + index_table_size <= file_size:
        add(section(f"INDEX STRÁNEK ({page_count} záznamů × 16 bajtů)"))

        page_issues = 0
        for i in range(page_count):
            off = index_offset + i * INDEX_ENTRY_SIZE
            pg_offset = struct.unpack_from("<Q", data, off)[0]
            pg_size   = struct.unpack_from("<I", data, off + 8)[0]
            pg_width  = struct.unpack_from("<H", data, off + 12)[0]
            pg_height = struct.unpack_from("<H", data, off + 14)[0]

            add(f"\n    Stránka {i + 1} (0-based index: {i}):")
            add(row("  Offset v souboru:", f"{pg_offset}  ({hex(pg_offset)})"))
            add(row("  Velikost (včetně hlavičky):", f"{pg_size} B ({format_bytes(pg_size)})"))
            add(row("  Rozměry:", f"{pg_width} × {pg_height} px"))

            # Validace rozsahu
            if pg_offset + pg_size > file_size:
                e(f"Stránka {i + 1}: data přesahují soubor (offset {pg_offset} + {pg_size} = {pg_offset + pg_size} > {file_size})")
                page_issues += 1
            elif pg_offset < data_offset:
                w(f"Stránka {i + 1}: offset ({pg_offset}) je před dataOffset ({data_offset})")
            elif pg_size < HEADER_SIZE_IMAGE:
                e(f"Stránka {i + 1}: velikost {pg_size} B je menší než minimální hlavička obrazu ({HEADER_SIZE_IMAGE} B)")
                page_issues += 1
            else:
                # Inspekce XTG/XTH hlavičky stránky
                img_result = inspect_image_header(data, pg_offset, file_size, index=i + 1)
                for err in img_result["errors"]:
                    e(err)
                    page_issues += 1
                for wrn in img_result["warnings"]:
                    w(wrn)
                if not img_result["errors"]:
                    info = img_result["info"]
                    add(row("  Formát stránky:", info["format"]))
                    md5_val = info["md5"]
                    if any(md5_val):
                        add(row("  MD5 (prvních 8 B):", md5_val.hex()))
                    else:
                        add(row("  MD5:", "(nenastaveno, samé nuly)"))

        if page_issues == 0:
            g(f"Všechny stránky ({page_count}) prošly validací")

    # ── Miniatury ──
    if has_thumbnails:
        add(section("MINIATURY"))
        if thumb_offset == 0:
            w("hasThumbnails=1, ale thumbOffset=0")
        elif thumb_offset >= file_size:
            e(f"thumbOffset={thumb_offset} přesahuje soubor")
        else:
            add(row("Offset miniatur:", f"{thumb_offset}  ({hex(thumb_offset)})"))
            remaining = file_size - thumb_offset
            add(row("Dostupný prostor pro miniatury:", f"{remaining} B ({format_bytes(remaining)})"))
            add("    (Detailní parsování miniatur vyžaduje znalost jejich indexu)")

    # ── Shrnutí ──
    add(section("SHRNUTÍ VALIDACE"))
    total_errors   = len(all_errors)
    total_warnings = len(all_warnings)

    if total_errors == 0 and total_warnings == 0:
        add(ok("Soubor je PLATNÝ — žádné chyby ani varování"))
    elif total_errors == 0:
        add(warn(f"Soubor je PLATNÝ s {total_warnings} varování(-mi):"))
        for w_ in all_warnings:
            add(f"    • {w_.strip()}")
    else:
        add(error(f"Soubor SELHAL validací: {total_errors} chyb, {total_warnings} varování"))
        add("\n  Chyby:")
        for err in all_errors:
            add(f"    • {err.strip()}")
        if all_warnings:
            add("\n  Varování:")
            for w_ in all_warnings:
                add(f"    • {w_.strip()}")

    add("")
    print("\n".join(lines))


# ── Vstupní bod ──────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Použití: python xtc_validator.py <soubor.xtc> [<soubor2.xtch> ...]")
        print()
        print("Validuje a zobrazuje technické informace ze souborů formátů XTC a XTCH.")
        sys.exit(1)

    for filepath in sys.argv[1:]:
        ext = Path(filepath).suffix.lower()
        if ext not in (".xtc", ".xtch"):
            print(warn(f"'{filepath}' nemá příponu .xtc nebo .xtch — pokusím se přesto zpracovat"))
        inspect_xtc(filepath)
        if len(sys.argv) > 2:
            print("\n" + "─" * 70 + "\n")


if __name__ == "__main__":
    main()
