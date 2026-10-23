(() => {
  const slides = [...document.querySelectorAll('.slide')];
  if (!slides.length) return;
  let current = 0;
  let revealed = 0;
  const maximum = () => Math.max(0, ...[...slides[current].querySelectorAll('.step[data-s]')].map(el => Number(el.dataset.s) || 0));
  function paint() {
    document.body.classList.add('step-navigation');
    slides.forEach((slide, index) => slide.classList.toggle('on', index === current));
    slides[current].querySelectorAll('.step[data-s]').forEach(el => el.classList.toggle('shown', Number(el.dataset.s) <= revealed));
    history.replaceState(null, '', `#${current + 1}`);
  }
  function show(index, all = false) {
    current = Math.max(0, Math.min(slides.length - 1, index));
    revealed = all ? maximum() : 0;
    paint();
  }
  function next() { if (revealed < maximum()) { revealed++; paint(); } else show(current + 1); }
  function previous() { if (revealed > 0) { revealed--; paint(); } else show(current - 1, true); }
  document.addEventListener('keydown', event => {
    if (event.target.closest('input,textarea,select,[contenteditable="true"]')) return;
    if (['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'].includes(event.key)) { event.preventDefault(); next(); }
    else if (['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'].includes(event.key)) { event.preventDefault(); previous(); }
    else if (event.key === 'Home') { event.preventDefault(); show(0); }
    else if (event.key === 'End') { event.preventDefault(); show(slides.length - 1, true); }
  });
  document.addEventListener('click', event => {
    if (event.target.closest('a,button,input,textarea,select')) return;
    if (event.clientX < innerWidth / 3) previous(); else next();
  });
  addEventListener('hashchange', () => show(Number(location.hash.slice(1)) - 1 || 0));
  show(Number(location.hash.slice(1)) - 1 || 0);
})();
