(function () {
  const keywordInput = document.getElementById('keyword-input');
  const keywordSets = document.getElementById('keyword-sets');
  const randomBtn = document.getElementById('random-btn');
  const shuffleBtn = document.getElementById('shuffle-btn');
  const comboSize = document.getElementById('combo-size');

  function shuffle(arr) {
    const copy = [...arr];
    for (let i = copy.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
  }

  function generateCombos() {
    const words = keywordInput.value
      .split(/\s+/)
      .map((w) => w.trim())
      .filter(Boolean);

    const size = Math.max(1, parseInt(comboSize.value || '1', 10));
    const mixed = shuffle(words);
    const combos = [];

    for (let i = 0; i < mixed.length; i += size) {
      combos.push(mixed.slice(i, i + size).join(' '));
    }

    keywordSets.value = combos.join('\n');
  }

  if (randomBtn) {
    randomBtn.addEventListener('click', function (e) {
      e.preventDefault();
      generateCombos();
    });
  }

  if (shuffleBtn) {
    shuffleBtn.addEventListener('click', function (e) {
      e.preventDefault();
      const lines = keywordSets.value
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean);
      keywordSets.value = shuffle(lines).join('\n');
    });
  }
})();
