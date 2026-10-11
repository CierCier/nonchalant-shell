# Media packages: video, audio, players
{ pkgs }:

with pkgs; [
  mpvpaper

  ffmpeg
  x264
  playerctl
  yt-dlp

  # Audio
  pipewire
  wireplumber
]
