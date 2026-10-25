/* A separate, read-only surface. Book text is always rendered as text. */
const main = document.getElementById('reader-main');
let currentBook = null;
let currentKey = null;
let navigation = 0;

function node(tag, attributes = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith('on')) element.addEventListener(key.slice(2), value);
    else element.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined && child !== false) {
      element.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
  }
  return element;
}

function preference(key, value) {
  try {
    if (value !== undefined) localStorage.setItem(key, value);
    return localStorage.getItem(key);
  } catch { return null; }
}

const theme = preference('forage-theme');
if (['light', 'dark'].includes(theme)) document.documentElement.dataset.theme = theme;
let fontSize = Number(preference('forage-reader-size')) || 20;
fontSize = Math.min(28, Math.max(16, fontSize));
document.documentElement.style.setProperty('--reading-size', `${fontSize}px`);
document.getElementById('reader-theme').addEventListener('click', () => {
  const dark = document.documentElement.dataset.theme === 'dark' ||
    (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'light' : 'dark';
  preference('forage-theme', dark ? 'light' : 'dark');
});

async function getJSON(path) {
  const response = await fetch(path, {credentials: 'same-origin'});
  if (!response.ok) {
    let message = 'The reading edition could not be opened. Please try again.';
    try { message = (await response.json()).detail || message; } catch { /* use fallback */ }
    throw new Error(message);
  }
  return response.json();
}

function link(text, href, primary = false) {
  return node('a', {href, class: `reader-button${primary ? ' primary' : ''}`, 'data-reader-link': true}, text);
}

function download(book) {
  return node('a', {href: book.download_url, class: 'reader-button', download: `${book.book_id}-abridged.txt`}, 'Download plain text');
}

function lengthLabel(book) {
  return `${book.word_count.toLocaleString()} words · Abridged edition`;
}

function license(book) {
  const credit = book.license;
  return node('details', {class: 'reading-license'},
    node('summary', {}, `Copyright & license · ${credit.short_name}`),
    node('p', {}, credit.copyright),
    node('p', {}, node('a', {href: credit.url, rel: 'license'}, `${credit.name} (${credit.short_name})`)),
    node('p', {}, credit.permissions), node('p', {}, credit.scope),
    node('p', {}, 'Attribution: ', credit.attribution));
}

async function library(turn) {
  const {books} = await getJSON('/api/books/reading');
  if (turn !== navigation) return;
  currentBook = null; currentKey = null;
  document.title = 'Abridged Too Far — reading library';
  const intro = node('section', {class: 'library-intro'},
    node('p', {class: 'eyebrow'}, 'The reading room'), node('h1', {}, 'A shorter way into a good book.'),
    node('p', {}, 'Read an abridged edition here, or download the complete abridgment as plain text to take with you.'));
  const grid = node('div', {class: 'reading-grid'}, books.map(book => node('article', {class: 'reading-card'},
    node('h2', {}, node('a', {href: book.reading_url, 'data-reader-link': true}, book.title)),
    book.author ? node('p', {class: 'author'}, `by ${book.author}`) : null,
    node('p', {class: 'book-length'}, lengthLabel(book)),
    node('div', {class: 'card-actions'}, link('Read book', book.reading_url, true),
      node('a', {href: book.download_url, download: `${book.book_id}-abridged.txt`}, 'Download .txt')))));
  main.replaceChildren(intro, books.length ? grid : node('p', {class: 'reader-status'}, 'Completed reading editions will appear here when they are available.'));
}

function chapterURL(book, id) {
  const url = new URL(book.reading_url, location.origin);
  url.searchParams.set('c', id);
  return url.pathname + url.search;
}

function showChapter(book, requested) {
  const index = Math.max(0, book.chapters.findIndex(chapter => chapter.id === requested));
  const chapter = book.chapters[index];
  if (!chapter) throw new Error('This reading edition has no text.');
  history.replaceState({}, '', chapterURL(book, chapter.id));
  currentKey = `${book.book_id}:${book.publication_revision || ''}:${book.edition_id}`;
  document.title = `${book.title} — ${chapter.title} — Abridged Too Far`;
  const picker = node('select', {id: 'reader-chapter', 'aria-labelledby': 'reader-contents-label', onchange: e => go(chapterURL(book, e.target.value))},
    book.chapters.map(item => node('option', {value: item.id, selected: item.id === chapter.id}, item.title)));
  const smaller = node('button', {type: 'button', 'aria-label': 'Smaller text'}, 'A−');
  const larger = node('button', {type: 'button', 'aria-label': 'Larger text'}, 'A+');
  const resize = delta => {
    fontSize = Math.max(16, Math.min(28, fontSize + delta));
    preference('forage-reader-size', String(fontSize));
    document.documentElement.style.setProperty('--reading-size', `${fontSize}px`);
    smaller.disabled = fontSize === 16; larger.disabled = fontSize === 28;
  };
  smaller.addEventListener('click', () => resize(-2)); larger.addEventListener('click', () => resize(2)); resize(0);
  const heading = node('header', {class: 'book-heading'},
    node('p', {class: 'eyebrow'}, 'Abridged edition'), node('h1', {}, book.title),
    book.author ? node('p', {class: 'author'}, `by ${book.author}`) : null,
    node('p', {class: 'book-length'}, `${book.word_count.toLocaleString()} words · Abridged Too Far`));
  const tools = node('div', {class: 'reading-tools'},
    node('label', {class: 'chapter-picker'}, node('span', {id: 'reader-contents-label'}, 'Contents'), picker),
    node('div', {class: 'type-controls', role: 'group', 'aria-label': 'Text size'}, smaller, larger), download(book));
  const prose = node('article', {class: 'reading-prose', 'aria-labelledby': 'reading-chapter-title'},
    node('h2', {id: 'reading-chapter-title'}, chapter.title), chapter.paragraphs.map(text => node('p', {}, text)));
  const nav = node('nav', {class: 'chapter-navigation', 'aria-label': 'Book navigation'},
    index > 0 ? link('← Previous', chapterURL(book, book.chapters[index - 1].id)) : link('← Library', '/read'),
    node('span', {}, book.chapters.length > 1 ? `${index + 1} of ${book.chapters.length}` : 'The complete book'),
    index + 1 < book.chapters.length ? link('Next →', chapterURL(book, book.chapters[index + 1].id), true) : link('Back to library', '/read'));
  main.replaceChildren(heading, tools, prose, nav, license(book));
}

async function render() {
  const turn = ++navigation;
  const match = location.pathname.match(/^\/read\/([^/]+)\/?$/);
  let bookId = null;
  main.setAttribute('aria-busy', 'true');
  try {
    if (!match) {
      main.replaceChildren(node('p', {class: 'reader-status', role: 'status'}, 'Opening the library…'));
      await library(turn);
    } else {
      bookId = decodeURIComponent(match[1]);
      const params = new URLSearchParams(location.search);
      const key = `${bookId}:${params.get('revision') || ''}:${params.get('version') || ''}`;
      if (!currentBook || key !== currentKey) {
        main.replaceChildren(node('p', {class: 'reader-status', role: 'status'}, 'Opening the book…'));
        const selection = new URLSearchParams();
        for (const name of ['revision', 'version', 'channel']) if (params.has(name)) selection.set(name, params.get(name));
        const book = await getJSON(`/api/books/${encodeURIComponent(bookId)}/reading?${selection}`);
        if (turn !== navigation) return;
        currentBook = book;
      }
      if (turn !== navigation) return;
      showChapter(currentBook, params.get('c'));
    }
  } catch (error) {
    if (turn !== navigation) return;
    currentBook = null; currentKey = null;
    document.title = 'Reading edition unavailable — Abridged Too Far';
    main.replaceChildren(node('section', {class: 'reader-error', role: 'alert'},
      node('h1', {}, 'We couldn’t open this edition.'), node('p', {}, error.message),
      bookId ? link('Open latest edition', `/read/${encodeURIComponent(bookId)}`) : null,
      link('Return to library', '/read')));
  } finally {
    if (turn === navigation) main.setAttribute('aria-busy', 'false');
  }
}

function go(path) {
  history.pushState({}, '', path);
  window.scrollTo(0, 0);
  render().then(() => main.focus({preventScroll: true}));
}

document.addEventListener('click', event => {
  const anchor = event.target.closest('a[data-reader-link]');
  if (!anchor || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault(); go(anchor.getAttribute('href'));
});
window.addEventListener('popstate', () => { window.scrollTo(0, 0); render(); });
render();
