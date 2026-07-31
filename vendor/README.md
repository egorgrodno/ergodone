# Vendored files

Both files are byte-for-byte copies from `tkg-toolkit`, taken with `git show` so
they are the pristine upstream blobs rather than anything patched in place.

| File                 | Upstream path                    | sha256    |
| -------------------- | -------------------------------- | --------- |
| `hid_bootloader_cli` | `linux/bin/hid_bootloader_cli`   | `af792bd…` |
| `ergodone.hex`       | `common/firmware/ergodone.hex`   | `caed5e9…` |

- Upstream: <https://github.com/Rouji/tkg-toolkit>
- Revision: `765b6b8f170eafe6d002802a571900c131cc73f2` (2017-11-30)
- Personal fork: <https://github.com/egorgrodno/tkg-toolkit>

`hid_bootloader_cli` is only shipped as a prebuilt x86-64 binary linked against
`libusb-0.1.so.4`, so `flake.nix` runs it through `autoPatchelfHook`. Never
patch it in the working tree — `autoPatchelf` rewrites the ELF in place, which
leaves the checkout dirty and pins it to a garbage-collectable glibc.

It is kept instead of nixpkgs' `teensy-loader-cli` because it recognises three
bootloader USB ID pairs — `1209:2327` (this keyboard), `16c0:0478` (Teensy
HalfKay) and `03eb:2067` (LUFA HID). `teensy_loader_cli` recognises only
`16c0:0478`.

The rest of `tkg-toolkit` — the mac and windows toolchains, the other 37
firmware images, and the interactive `setup.sh`/`reflash.sh` scripts — is not
needed here and is available at the revision above.
