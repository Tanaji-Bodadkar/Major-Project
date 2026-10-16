(() => {
  const storageKey = 'carbon-platform-theme';
  const choices = [...document.querySelectorAll('[data-theme-choice]')];

  function applyTheme(theme, persist = true) {
    const selected = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = selected;

    choices.forEach((button) => {
      const active = button.dataset.themeChoice === selected;
      button.setAttribute('aria-pressed', String(active));
    });

    if (persist) {
      try {
        localStorage.setItem(storageKey, selected);
      } catch (_) {}
    }
  }

  choices.forEach((button) => {
    button.addEventListener('click', () => applyTheme(button.dataset.themeChoice));
  });

  applyTheme(document.documentElement.dataset.theme, false);
})();

