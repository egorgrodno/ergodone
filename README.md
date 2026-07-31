# Ergodone Layout

Keymap for an [ErgoDone](https://github.com/Rouji/Ergodone-Setup) running TMK
firmware. The layout is drawn in keyboard-layout-editor, compiled to an EEPROM
image on tkg.io, and written to the keyboard with `nix run .#flash`.

## Flashing

```bash
nix run .#flash                 # write keymap.eep (the usual case)
nix run .#flash -- --firmware   # rewrite the TMK firmware itself
nix run .#flash -- other.eep    # write some other image
```

`direnv allow` also puts `flash` and `hid_bootloader_cli` straight on `PATH`.

The flasher waits for the bootloader, so start it first and plug the keyboard in
afterwards. It runs under `sudo` because no udev rule grants this user the
bootloader device — see below to remove that.

### Bootloader modes — get this right

The keyboard has two bootloader modes, chosen by which keys you hold **while
plugging it in**. `hid_bootloader_cli` only streams bytes; the *keyboard* decides
where they land:

| Hold while plugging in                            | Mode     | Writes to     | Flash this |
| ------------------------------------------------- | -------- | ------------- | ---------- |
| **One** rightmost key, top row, left half          | keymap   | EEPROM        | `.eep`     |
| **Two** rightmost keys, top row, left half         | firmware | program flash | `.hex`     |

Writing a `.eep` while the board is in *firmware* mode puts 1 KB on top of the
reset and interrupt vectors at `0x0000` and kills the firmware. The symptom is a
keyboard that does nothing and drops into the bootloader with no keys held,
because there is no working application left to boot. `flash` prints the
combination it expects, so follow what it says rather than working from memory.

Recovering from that is just the firmware mode plus:

```bash
nix run .#flash -- --firmware   # restore the TMK firmware
nix run .#flash                 # then re-apply the keymap, in keymap mode
```

`ergodone.hex` spans `0x0000`–`0x6A80` and the bootloader lives at `0x7000`, so
the bootloader is never overwritten and the keyboard is always recoverable this
way.

## Editing the layout

1. Draw the layer at <http://www.keyboard-layout-editor.com/>, pasting the
   matching `layers/*.kle` file into the *Raw data* tab.
2. Compile it at <https://tkg.io/> and download `keymap.eep`. Mirrors, should
   that one be down: <https://yang.tkg.io/>,
   <https://tools.lotlab.org/tkg/>, <https://xd.tkg.io/>.
3. Save the raw data back to `layers/*.kle` **and re-export the matching
   `.png`** — they drift apart easily, which is how the number layer spent two
   years showing no F-keys.
4. Flash, then check the result with `showkey -a`.

### Function keys

| Key   | Action                            |
| ----- | --------------------------------- |
| `fn0` | Layer action: Set default layer 0 |
| `fn1` | Layer action: Set default layer 1 |
| `fn2` | Layer action: Momentary layer 2   |

### Layer #0 - base

![base layer](./layers/0-base.png)

### Layer #1 - qwerty

![qwerty layer](./layers/1-qwerty.png)

### Layer #2 - number

![number layer](./layers/2-number.png)

## Flashing without sudo

`hardware.keyboard.qmk.enable` is not enough — `qmk-udev-rules` covers
`1209:2302`, but this keyboard's HID bootloader is `1209:2327`. Add to the NixOS
config instead, then drop the `sudo` from `flash` in `flake.nix`:

```nix
services.udev.extraRules = ''
  SUBSYSTEMS=="usb", ATTRS{idVendor}=="1209", ATTRS{idProduct}=="2327", TAG+="uaccess"
  SUBSYSTEMS=="usb", ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="0478", TAG+="uaccess"
  SUBSYSTEMS=="usb", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2ff4", TAG+="uaccess"
'';
```

Confirm the ID first: with the keyboard in its bootloader, `lsusb` should show
`1209:2327` (it is `1209:2328` when running normally).

## Layout of this repo

| Path            | What it is                                                  |
| --------------- | ----------------------------------------------------------- |
| `keymap.eep`    | The EEPROM image that gets flashed; built by tkg.io          |
| `layers/*.kle`  | keyboard-layout-editor raw data — the layout source          |
| `layers/*.png`  | Renders of the above, for this README                        |
| `vendor/`       | The flashing binary and stock firmware; see `vendor/README.md` |
| `flake.nix`     | Builds the flasher and the dev shell                         |

## Resources

- Halmak keyboard layout <https://github.com/MadRabbit/halmak>
- ErgoDone setup guide <https://github.com/Rouji/Ergodone-Setup>
- tkg-toolkit <https://github.com/Rouji/tkg-toolkit>
