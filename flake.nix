{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        pythonPs = pkgs.python3.withPackages (ps: with ps; [ pyusb ]);
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            pythonPs
          ];
        };
      }
    );
}
