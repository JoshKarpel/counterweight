// Starts asciinema-player in each element mkdocs_hooks/casts.py puts where a page has a cast marker.
// Material's instant navigation swaps pages in without reloading, so this runs on each page it shows (document$).
document$.subscribe(() => {
  for (const element of document.querySelectorAll(".asciicast[data-cast]:empty")) {
    AsciinemaPlayer.create(element.dataset.cast, element, {
      autoplay: true,
      loop: true,
      preload: true,
      fit: false,
      terminalFontSize: "14px",
      keystrokeOverlay: true,
    });
  }
});
