{
  description = "Nonchalant Shell — a Niri-first Wayland desktop shell built with Quickshell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    quickshellPackages.url = "github:NixOS/nixpkgs/7fd4004d0511991fff3a0524856a9be09e28c5f0";
  };

  outputs = { self, nixpkgs, quickshellPackages, ... }:
    let
      nonchalantLib = import ./nix/lib.nix { inherit nixpkgs; };
      version = nixpkgs.lib.removeSuffix "\n" (builtins.readFile ./version);
    in {
      nixosModules.default = { pkgs, lib, ... }: {
        imports = [ ./nix/modules ];
        programs.nonchalant.enable = lib.mkDefault true;
        programs.nonchalant.package = lib.mkDefault self.packages.${pkgs.system}.default;
      };

      packages = nonchalantLib.forAllSystems (system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfree = true;
          };

          runtimePkgs = import quickshellPackages { inherit system; };
          compositorTests = import ./nix/compositor-tests.nix { pkgs = runtimePkgs; source = self; };
          lib = nixpkgs.lib;

          Nonchalant = import ./nix/packages {
            inherit pkgs runtimePkgs lib self system version;
          };
        in {
          default = Nonchalant;
          Nonchalant = Nonchalant;
          compositor-tests = compositorTests.runner;
        }
      );

      devShells = nonchalantLib.forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          Nonchalant = self.packages.${system}.default;
          runtimePkgs = import quickshellPackages { inherit system; };
          compositorTests = import ./nix/compositor-tests.nix { pkgs = runtimePkgs; source = self; };
        in {
          compositor-test = compositorTests.shell;
          default = pkgs.mkShell {
            packages = [ Nonchalant ];
            shellHook = ''
              export QML2_IMPORT_PATH="${Nonchalant}/lib/qt-6/qml:$QML2_IMPORT_PATH"
              export QML_IMPORT_PATH="$QML2_IMPORT_PATH"
              echo "Nonchalant Shell dev environment loaded."
            '';
          };
        }
      );

      checks = nonchalantLib.forAllSystems (system:
        let
          pkgs = import quickshellPackages { inherit system; };
        in {
          compositor-codecs = pkgs.runCommand "nonchalant-compositor-codecs" {
            nativeBuildInputs = [ pkgs.nodejs ];
          } ''
            cd ${self}
            node --test tests/compositor/test_*.js
            touch $out
          '';
        }
      );

      apps = nonchalantLib.forAllSystems (system:
        let
          Nonchalant = self.packages.${system}.default;
        in {
          default = {
            type = "app";
            program = "${Nonchalant}/bin/nonchalant";
          };
        }
      );
    };
}
