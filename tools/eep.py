"""Inspect, edit and repair a TKG keymap.eep.

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
module exists to close. --set recomputes it for you; prefer it over editing the
hex by hand.
"""

import argparse
import sys

MAGIC = 0xFEED
CKSUM_LO, CKSUM_HI = 0x11, 0x12
START, LENGTH = 0x13, 736  # u16 fn_actions[32] + keymaps[8][6][14]
KEYMAP = 0x53
ROWS, COLS, LAYERS = 6, 14, 8
PER_LAYER = ROWS * COLS
SIZE = 1024

_NAMES = {
    0x00: "---", 0x01: "trns",
    0x28: "ent", 0x29: "esc", 0x2A: "bspc", 0x2B: "tab", 0x2C: "spc",
    0x2D: "mins", 0x2E: "eql", 0x2F: "lbrc", 0x30: "rbrc", 0x31: "bsls",
    0x32: "nuhs", 0x33: "scln", 0x34: "quot", 0x35: "grv", 0x36: "comm",
    0x37: "dot", 0x38: "slsh", 0x39: "caps",
    0x46: "pscr", 0x47: "slck", 0x48: "paus", 0x49: "ins", 0x4A: "home",
    0x4B: "pgup", 0x4C: "del", 0x4D: "end", 0x4E: "pgdn", 0x4F: "rght",
    0x50: "left", 0x51: "down", 0x52: "up", 0x53: "nlck",
    0x54: "psls", 0x55: "past", 0x56: "pmns", 0x57: "ppls", 0x58: "pent",
    0x63: "pdot", 0x65: "app",
    0xE0: "lctl", 0xE1: "lsft", 0xE2: "lalt", 0xE3: "lgui",
    0xE4: "rctl", 0xE5: "rsft", 0xE6: "ralt", 0xE7: "rgui",
}
_NAMES.update({0x04 + i: c for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")})
_NAMES.update({0x1E + i: c for i, c in enumerate("1234567890")})
_NAMES.update({0x3A + i: f"f{i + 1}" for i in range(12)})
_NAMES.update({0x59 + i: f"kp{i + 1}" for i in range(9)})
_NAMES[0x62] = "kp0"
# TMK maps action keycodes 0xC0-0xDF onto fn_actions[0..31].
_NAMES.update({0xC0 + i: f"fn{i}" for i in range(32)})

_CODES = {v: k for k, v in _NAMES.items()}


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


def offset(layer, pos):
    if not 0 <= layer < LAYERS:
        raise ValueError(f"layer {layer} out of range 0-{LAYERS - 1}")
    if not 0 <= pos < PER_LAYER:
        raise ValueError(f"position {pos} out of range 0-{PER_LAYER - 1}")
    return KEYMAP + layer * PER_LAYER + pos


def name(code):
    return _NAMES.get(code, f"{code:02x}")


def parse_key(text):
    key = text.strip().lower()
    if key.startswith("0x"):
        return int(key, 16)
    if key.startswith("kc_"):
        key = key[3:]
    if key in _CODES:
        return _CODES[key]
    raise ValueError(f"unknown keycode {text!r}; use a name like KC_X or a byte like 0x1B")


def dump(mem, only=None):
    for layer in range(LAYERS):
        base = KEYMAP + layer * PER_LAYER
        block = mem[base:base + PER_LAYER]
        if only is None and not any(b not in (0x00, 0x01) for b in block):
            continue
        if only is not None and layer != only:
            continue
        print(f"layer {layer} @ 0x{base:04X}")
        # Seven cells a line splits each row at the ErgoDone's physical halves.
        for row in range(ROWS):
            for half in (0, 7):
                start = row * COLS + half
                cells = (f"{start + i:3d} {name(block[start + i]):<5}" for i in range(7))
                print("  " + " ".join(cells))
            print()


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="eep", description="inspect, edit and repair a TKG keymap.eep")
    ap.add_argument("file")
    ap.add_argument("--fix", action="store_true",
                    help="recompute the checksum and write it back")
    ap.add_argument("--dump", nargs="?", type=int, const=-1, metavar="LAYER",
                    help="print layers as position/keycode grids (default: those in use)")
    ap.add_argument("--set", action="append", default=[], metavar="LAYER,POS=KEY",
                    help="assign a keycode, e.g. --set 0,45=KC_X (repeatable)")
    args = ap.parse_args(argv)

    mem = decode(open(args.file, newline="").read())

    if args.dump is not None:
        dump(mem, None if args.dump < 0 else args.dump)
        return 0

    if args.set:
        for spec in args.set:
            try:
                where, key = spec.split("=", 1)
                layer, pos = (int(x) for x in where.split(","))
                at, code = offset(layer, pos), parse_key(key)
            except ValueError as e:
                print(f"eep: --set {spec}: {e}", file=sys.stderr)
                return 2
            print(f"layer {layer} pos {pos} @ 0x{at:04X}: "
                  f"{name(mem[at])} -> {name(code)}")
            mem[at] = code
        value = apply(mem)
        open(args.file, "w", newline="").write(encode(mem))
        print(f"{args.file}: checksum -> 0x{value:04X}, written")
        return 0

    want, have = checksum(mem), stored(mem)
    if want == have:
        print(f"{args.file}: checksum 0x{have:04X} OK")
        return 0
    if args.fix:
        apply(mem)
        open(args.file, "w", newline="").write(encode(mem))
        print(f"{args.file}: checksum 0x{have:04X} -> 0x{want:04X}, repaired")
        return 0
    print(f"{args.file}: checksum 0x{have:04X}, expected 0x{want:04X}", file=sys.stderr)
    print("the firmware will discard this keymap; rerun with --fix", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
