"""Verify or repair the checksum in a TKG keymap.eep.

tkg.io generated these images and is permanently offline, so hand-editing is now
the only way to change a keymap. A hand-edit that leaves the checksum stale is
worse than a no-op: check_keymap_in_eeprom() fails, and the firmware responds by
overwriting EEPROM with its compiled-in default keymap -- roughly 2.5 seconds of
EEPROM writes on every plug-in, and the custom layout silently gone.

Algorithm, from kairyu/tmk_core_custom common/keymap_in_eeprom.c: a 16-bit
little-endian word sum seeded with EECONFIG_MAGIC_NUMBER, taken over the
fn_actions and keymap region and stored little-endian just below it.

Because the sum is over words rather than bytes, byte position matters: a byte at
an even offset carries weight 256 and its neighbour weight 1. Transposing two
adjacent keycodes therefore changes the checksum, which is exactly the trap this
module exists to close.
"""

import sys

MAGIC = 0xFEED
CKSUM_LO, CKSUM_HI = 0x11, 0x12
START, LENGTH = 0x13, 736  # u16 fn_actions[32] + keymaps[8][6][14]
SIZE = 1024


def decode(text):
    mem = bytearray(SIZE)
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if not line.startswith(":"):
            raise ValueError(f"line {n}: not an Intel HEX record")
        rec = bytes.fromhex(line[1:])
        if (-sum(rec[:-1])) & 0xFF != rec[-1]:
            raise ValueError(f"line {n}: bad record checksum")
        count, addr, kind = rec[0], int.from_bytes(rec[1:3], "big"), rec[3]
        if kind == 0:
            mem[addr:addr + count] = rec[4:4 + count]
    return mem


def encode(mem):
    out = []
    for addr in range(0, SIZE, 16):
        rec = bytes([16, addr >> 8, addr & 0xFF, 0]) + bytes(mem[addr:addr + 16])
        out.append(":" + (rec + bytes([(-sum(rec)) & 0xFF])).hex().upper())
    out.append(":00000001FF")
    return "\r\n".join(out) + "\r\n"


def checksum(mem):
    total = MAGIC
    for i in range(START, START + LENGTH, 2):
        total = (total + mem[i] + (mem[i + 1] << 8)) & 0xFFFF
    return total


def stored(mem):
    return mem[CKSUM_LO] | (mem[CKSUM_HI] << 8)


def apply(mem):
    value = checksum(mem)
    mem[CKSUM_LO], mem[CKSUM_HI] = value & 0xFF, value >> 8
    return value


def main(argv):
    if len(argv) < 2:
        sys.exit("usage: eep.py <keymap.eep> [--fix]")
    path = argv[1]
    mem = decode(open(path, newline="").read())
    want, have = checksum(mem), stored(mem)
    if want == have:
        print(f"{path}: checksum 0x{have:04X} OK")
        return 0
    if "--fix" in argv:
        apply(mem)
        open(path, "w", newline="").write(encode(mem))
        print(f"{path}: checksum 0x{have:04X} -> 0x{want:04X}, repaired")
        return 0
    print(f"{path}: checksum 0x{have:04X}, expected 0x{want:04X}", file=sys.stderr)
    print("the firmware will discard this keymap; rerun with --fix", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
