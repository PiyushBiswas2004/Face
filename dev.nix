{
  packages = with pkgs; [
    python3
    python3Packages.pip
    cope  # Since the error mentions cope
    # Other packages...
  ];
}