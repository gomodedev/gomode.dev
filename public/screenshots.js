// Keep full-size links in sync with the image selected by each responsive picture.
for (const image of document.querySelectorAll('a[href^="/screenshots/"] picture img')) {
  const link = image.closest("a");
  const sync = () => {
    if (image.currentSrc) link.href = image.currentSrc;
  };
  image.addEventListener("load", sync);
  sync();
}
