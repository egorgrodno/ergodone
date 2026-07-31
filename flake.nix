{
  description = "ErgoDone keymap — layer sources and the EEPROM flashing tool";

  inputs = {
    # Pinned to this machine's *system* nixpkgs revision so the dev shell
    # resolves to store paths that are already present and builds with no
    # download. Bump this rev deliberately.
    nixpkgs.url = "github:NixOS/nixpkgs/da5ad661ba4e5ef59ba743f0d112cbc30e474f32";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };

      # Upstream ships this loader only as a 2017 x86-64 binary needing
      # libusb-0.1.so.4, with no RUNPATH and a /lib64 interpreter. autoPatchelfHook
      # rewrites both against the store — libusb-compat-0_1 is what it resolves
      # the library against, and omitting it is why patching by hand never worked.
      # Building it here rather than editing vendor/ in place also means the exec
      # bit comes from `install -m755`, not from whatever mode git happens to hold.
      hid-bootloader-cli = pkgs.stdenv.mkDerivation {
        pname = "hid_bootloader_cli";
        version = "765b6b8";

        src = ./vendor;

        nativeBuildInputs = [ pkgs.autoPatchelfHook ];
        buildInputs = [ pkgs.libusb-compat-0_1 ];

        dontBuild = true;

        installPhase = ''
          runHook preInstall
          install -Dm755 hid_bootloader_cli $out/bin/hid_bootloader_cli
          install -Dm444 ergodone.hex $out/share/ergodone/ergodone.hex
          runHook postInstall
        '';

        meta = {
          description = "HID bootloader loader for the ErgoDone, from tkg-toolkit";
          mainProgram = "hid_bootloader_cli";
          platforms = [ "x86_64-linux" ];
        };
      };

      # Replaces tkg-toolkit's reflash.sh, which clears the screen and waits on a
      # keypress. The loader's own -w flag blocks until the bootloader enumerates,
      # so plugging in the keyboard after starting this is fine.
      flash = pkgs.writeShellApplication {
        name = "flash";
        text = ''
          loader=${hid-bootloader-cli}/bin/hid_bootloader_cli

          if [ "''${1:-}" = "--firmware" ]; then
            target=${hid-bootloader-cli}/share/ergodone/ergodone.hex
          else
            target=''${1:-keymap.eep}
          fi

          if [ ! -f "$target" ]; then
            echo "flash: no such file: $target" >&2
            exit 1
          fi

          # The loader only ever streams bytes; the *keyboard* decides whether they
          # land in EEPROM or in program flash, based on which key combination put
          # it into the bootloader. Writing a .eep while the board is in firmware
          # mode drops 1 KB onto the reset and interrupt vectors at 0x0000 and
          # kills the firmware, so spell out the right combination every time.
          case "$target" in
            *.eep)
              mode="KEYMAP mode — hold ONLY the rightmost key of the top row on the LEFT half"
              ;;
            *.hex)
              mode="FIRMWARE mode — hold the TWO rightmost keys of the top row on the LEFT half"
              ;;
            *)
              echo "flash: expected a .eep or .hex file, got $target" >&2
              exit 1
              ;;
          esac

          echo "$mode,"
          echo "then plug the keyboard in. Wrong mode = bricked firmware; recover with"
          echo "  flash --firmware"
          echo

          # sudo, and by absolute store path so its PATH handling is irrelevant:
          # no udev rule grants this user the bootloader HID device. See README
          # for the rule that removes the need for this.
          exec sudo "$loader" -w -v -mmcu=atmega32u4 "$target"
        '';
      };
    in
    {
      packages.${system} = {
        inherit hid-bootloader-cli flash;
        default = flash;
      };

      # `nix run .#flash [file.eep]` or `nix run .#flash -- --firmware`
      apps.${system} = rec {
        flash = {
          type = "app";
          program = "${self.packages.${system}.flash}/bin/flash";
        };
        default = flash;
      };

      devShells.${system}.default = pkgs.mkShell {
        packages = [ hid-bootloader-cli flash ];

        shellHook = ''
          echo "ergodone  ·  flash keymap.eep:  flash" >&2
          echo "          ·  flash firmware:    flash --firmware" >&2
        '';
      };
    };
}
