/* === ბიბლიის ვებ-აპლიკაცია - ფუნქციონალი === */

let BOOKS = null;
let currentBook = null;
let currentChapter = null;
let currentVerses = null;
let currentHighlightQuery = ''; // ძიების სიტყვის მარკირება თავის ხედში
let currentHighlightForms = []; // გაფართოებული ფორმები (სერვერიდან)
let currentVersePopup = null;
let searchMode = 'ai';
let currentListType = null; // 'bookmarks' | 'comments' - რომელი სიიდან იყო გამოძახებული editListComment
var bookmarks = JSON.parse(localStorage.getItem('bible_bookmarks') || '[]');
// მიგრაცია - ძველი bookmarks-ებისთვის pinned: true
bookmarks.forEach(b => { if (b.pinned === undefined) b.pinned = true; });
window.bookmarks = bookmarks;

// localStorage-ის უსაფრთხო ჩაწერა (QuotaExceededError-ის დამუშავება)
function safeLocalStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (e) {
    if (e.name === 'QuotaExceededError') {
      showToast('⚠️ საცავი სავსეა. ვერ შეინახება. გაასუფთავეთ ძველი მონაცემები ან გამოიყენეთ ექსპორტი.', 'error');
    } else {
      console.error('localStorage error:', e);
    }
    return false;
  }
}

// სანიშნეების შენახვა - ანახლებს როგორც localStorage-ს, ასევე window.bookmarks-ს
function persistBookmarks() {
  window.bookmarks = bookmarks;
  safeLocalStorageSet('bible_bookmarks', JSON.stringify(bookmarks));
}

// storage event listener - ორ ტაბში ერთდროული ცვლილების სინქრონიზაცია
let storageSyncTimer = null;
window.addEventListener('storage', function(e) {
  if (e.key === 'bible_bookmarks' && e.newValue) {
    // debounce - სწრაფი ცვლილებებისას არ გაეშვება ყოველ ჯერზე
    clearTimeout(storageSyncTimer);
    storageSyncTimer = setTimeout(() => {
      try {
        const newBookmarks = JSON.parse(e.newValue);
        // განვაახლოთ ლოკალური ცვლადი მხოლოდ თუ რეალურად შეიცვალა
        if (JSON.stringify(newBookmarks) !== JSON.stringify(bookmarks)) {
          bookmarks.length = 0;
          newBookmarks.forEach(b => bookmarks.push(b));
          window.bookmarks = bookmarks;
          // განვაახლოთ UI თუ სანიშნეების პანელი ღიაა
          if (typeof renderBookmarks === 'function' && document.getElementById('bookmarks-panel')?.classList.contains('open')) {
            renderBookmarks();
          }
          if (typeof updateDashboardCounts === 'function') updateDashboardCounts();
        }
      } catch (err) {
        console.error('storage sync error:', err);
      }
    }, 300);
  }
});

// === ინიციალიზაცია ===
document.addEventListener('DOMContentLoaded', async () => {
  // თემა
  const theme = localStorage.getItem('bible_theme') || 'light';
  document.body.setAttribute('data-theme', theme);
  updateThemeIcon();

  // შრიფტის ზომა
  const fontSize = localStorage.getItem('bible_font_size') || '18';
  document.documentElement.style.setProperty('--font-size', fontSize + 'px');

  // line-height (კითხვის კომფორტი)
  const lineHeight = localStorage.getItem('bible_line_height') || '1.85';
  document.documentElement.style.setProperty('--verse-line-height', lineHeight);

  // შრიფტის ტიპი
  const fontFamily = localStorage.getItem('bible_font_family') || 'serif';
  if (fontFamily === 'sans') {
    document.documentElement.style.setProperty('--font-serif', 'var(--font-sans)');
  }

  // ფორმატირების ღილაკების ვიზუალური სტატუსის სინქრონიზაცია
  syncFormattingButtons();

  // sidebar საწყისი მდგომარეობა - დამალული, ღილაკ ☰-ზე დაჭერით იხსნება
  setSidebarMode('hidden');

  // მარცხენა ზოლის hover-ით peek და click-ით გახსნა
  const sidebar = document.getElementById('sidebar');
  const sidebarEdge = document.getElementById('sidebar-edge');
  if (sidebar && sidebarEdge) {
    sidebarEdge.addEventListener('mouseenter', () => {
      if (sidebarMode === 'all') return;
      sidebar.classList.add('peek');
      sidebarEdge.classList.add('peek');
    });
    sidebarEdge.addEventListener('mouseleave', () => {
      sidebar.classList.remove('peek');
      sidebarEdge.classList.remove('peek');
    });
    sidebarEdge.addEventListener('click', () => {
      setSidebarMode('all');
    });
  }

  // წიგნების ჩატვირთვა
  await loadBooks();
  await loadStats();
  if (!BOOKS) return; // API ხელმისაწვდომი არ არის - გავაგრძელოთ მხოლოდ ბაზისური ფუნქციონალი
  setupEventListeners();
  populateBookFilter();
  renderHomeBookmarks();
  restoreColorLabels();
  renderBookRibbon();
  updateDashboardCounts();

  // URL routing - თუ ბმულში არის #/book/chapter[/verse] ან #search/... ან #lexicon
  const route = parseHash();
  if (route && BOOKS) {
    // შევამოწმოთ წიგნი არსებობს
    const allBooks = [...(BOOKS.old || []), ...(BOOKS.new || [])];
    if (allBooks.some(b => b.slug === route.bookSlug)) {
      openChapter(route.bookSlug, route.chapter, { scrollToVerse: route.verse });
      // მთავარ გვერდზე წიგნის თავების სიის გახსნა და აქტიური თავის მონიშვნა
      _openHomeBookChapters(route.bookSlug, route.chapter);
    }
  }

  // Service worker-ის რეგისტრაცია (PWA) + აგრესიული განახლება
  if ("serviceWorker" in navigator) {
    // ვინახავთ რა იყო controller რეგისტრაციის წინ - პირველ ვიზიტზე null-ია
    const hadController = !!navigator.serviceWorker.controller;
    let refreshing = false;

    // controllerchange - როცა ახალი SW აქტიური ხდება, გვერდი განახლდება
    // მხოლოდ update-ისთვის (არა პირველი ინსტალაციისთვის - clients.claim() აკეთებს ამას)
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (!refreshing && hadController) {
        refreshing = true;
        location.reload();
      }
    });

    navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" }).then((reg) => {
      // ახალი SW რომ ჩამოვიდეს - ვაგზავნით SKIP_WAITING-ს რომ მაშინვე გააქტიურდეს
      reg.addEventListener("updatefound", () => {
        const newSW = reg.installing;
        if (newSW) {
          newSW.addEventListener("statechange", () => {
            if (newSW.state === "installed" && navigator.serviceWorker.controller) {
              // ახალი SW დაინსტალირდა და waiting-შია - ვაძლევთ ბრძანებას გააქტიურდეს
              newSW.postMessage({ type: "SKIP_WAITING" });
            }
            // პირველი ინსტალაცია - SW-მ clients.claim()-ით უკვე დაიკავა კონტროლი
            // reload არ სჭირდება - ეს იწვევდა Lighthouse redirect პრობლემას
          });
        }
      });

      // თუ უკვე არის waiting SW (მაგ. ძველი სესიიდან) - მაშინვე ვააქტიურებთ
      if (reg.waiting) {
        reg.waiting.postMessage({ type: "SKIP_WAITING" });
      }

      // ყოველ ჩატვირთვაზე შემოწმება
      reg.update();
    }).catch((err) => {
      console.warn("[PWA] Service worker ვერ დარეგისტრირდა:", err);
    });

    // SW-ის მესიჯი განახლების შესახებ (backup controllerchange-სთვის)
    navigator.serviceWorker.addEventListener("message", (e) => {
      if (e.data && e.data.type === "SW_UPDATED" && !refreshing && hadController) {
        refreshing = true;
        location.reload();
      }
    });
  }
});

function populateBookFilter() {
  const select = document.getElementById('filter-book');
  if (!select || !BOOKS) return;
  select.innerHTML = '<option value="">ყველა</option>';
  const optgroup1 = document.createElement('optgroup');
  optgroup1.label = 'ძველი აღთქმა';
  BOOKS.old.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b.slug;
    opt.textContent = b.name;
    optgroup1.appendChild(opt);
  });
  const optgroup2 = document.createElement('optgroup');
  optgroup2.label = 'ახალი აღთქმა';
  BOOKS.new.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b.slug;
    opt.textContent = b.name;
    optgroup2.appendChild(opt);
  });
  select.appendChild(optgroup1);
  select.appendChild(optgroup2);
  // კასტომ dropdown-ის განახლება თუ უკვე ინიციალიზებულია
  if (select._refreshCustom) select._refreshCustom();
}

function setupEventListeners() {
  // ძიების input
  const searchInput = document.getElementById('search-input');
  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') doSearch();
  });

  // ძიების რეჟიმი
  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      searchMode = btn.dataset.mode;
    });
  });

  // ☰ მარცხნივ - sidebar-ის გახსნა/დახურვა (წიგნები)
  document.getElementById('menu-toggle').addEventListener('click', (e) => {
    e.stopPropagation();
    // თუ sidebar გაშლილია - შეკეცვა; თუ დამალული - ყველა წიგნის ჩვენება
    if (sidebarMode === 'hidden') {
      setSidebarMode('all');
    } else {
      setSidebarMode('hidden');
    }
  });

  // "თავფურცელი" logo - დაკლიკებაზე მხოლოდ home-ზე დაბრუნება
  // sidebar-ის გახსნა/დახურვა მხოლოდ ☰ ღილაკით
  const logoBtn = document.getElementById('logo-btn');
  if (logoBtn) {
    logoBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      goHome();
    });
  }

  // "78 წიგნი · 37,780 მუხლი" - დაკლიკებაზე ყველა წიგნის გაშლა/შეკეცვა
  const bookToggle = document.getElementById('book-toggle');
  if (bookToggle) {
    bookToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleSidebarMode('all');
    });
  }

  // "კანონიკური: 67 წიგნი" - დაკლიკებაზე მხოლოდ კანონიკური წიგნების გაშლა/შეკეცვა
  const canonToggle = document.getElementById('canonical-toggle');
  if (canonToggle) {
    canonToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleCanonicalBooks();
    });
  }

  // "ძველი აღთქმა: 40 წიგნი" - დაკლიკებაზე მხოლოდ OT კანონიკური წიგნები
  const otToggle = document.getElementById('ot-toggle');
  if (otToggle) {
    otToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleOTCanonical();
    });
  }

  // "ახალი აღთქმა: 27 წიგნი" - დაკლიკებაზე მხოლოდ NT წიგნები
  const ntToggle = document.getElementById('nt-toggle');
  if (ntToggle) {
    ntToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleNTOnly();
    });
  }

  // "არაკანონიკური: 11 წიგნი" - დაკლიკებაზე მხოლოდ არაკანონიკური წიგნები
  const noncanonToggle = document.getElementById('noncanon-toggle');
  if (noncanonToggle) {
    noncanonToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleNonCanonical();
    });
  }

  // ⋮ მარჯვნივ - მენიუს დროპდაუნი (მობილური)
  document.getElementById('mobile-menu-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    document.getElementById('mobile-menu').classList.toggle('show');
  });

  // გარე კლიკზე დახურვა
  document.addEventListener('click', (e) => {
    const mobileMenu = document.getElementById('mobile-menu');
    const mobileBtn = document.getElementById('mobile-menu-btn');
    if (mobileMenu && mobileMenu.classList.contains('show') &&
        !mobileMenu.contains(e.target) && !mobileBtn.contains(e.target)) {
      mobileMenu.classList.remove('show');
    }
  });

  // ☰-ით გახსნილი sidebar-ის დახურვა ცარიელ ადგილზე დაკლიკებისას
  document.addEventListener('click', (e) => {
    const sidebar = document.getElementById('sidebar');
    const menuToggle = document.getElementById('menu-toggle');
    const edge = document.getElementById('sidebar-edge');
    if (sidebar && !sidebar.classList.contains('sidebar-hidden') &&
        !sidebar.contains(e.target) && !menuToggle.contains(e.target) &&
        !(edge && edge.contains(e.target))) {
      setSidebarMode('hidden');
    }
  });

  // ესკეიპი პოპაპის დასახურად (უნივერსალური handler-ი ქვემოთაა)
}

// === წიგნების ჩატვირთვა ===
async function loadBooks() {
  try {
    const res = await fetch('/api/books');
    if (!res.ok) return; const _t = await res.text(); if (!_t) return; BOOKS = JSON.parse(_t);
    // დაველოდოთ audioMap-ის ჩატვირთვას რომ 🎵 იკონები გამოჩნდეს
    if (typeof loadAudioMap === 'function') {
      await loadAudioMap();
    }
    renderBooks();
  } catch (e) {
    // ჩუმად გამოტოვება

  }
}

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return; const _t = await res.text(); if (!_t) return; const s = JSON.parse(_t);
    const fmt = n => n.toLocaleString('ka-GE');
    const el = id => document.getElementById(id);
    const set = (id, text) => { const e = el(id); if (e) e.innerHTML = text; };
    set('book-toggle', `${s.total_books} წიგნი · ${fmt(s.total_verses)} მუხლი`);
    set('canonical-toggle', `კანონიკური: ${s.canonical_books} წიგნი · ${fmt(s.canonical_verses)} მუხლი`);
    set('ot-toggle', `ძველი აღთქმა: ${s.ot_books} წიგნი · ${fmt(s.ot_verses)} მუხლი`);
    set('nt-toggle', `ახალი აღთქმა: ${s.nt_books} წიგნი · ${fmt(s.nt_verses)} მუხლი`);
    set('noncanon-toggle', `არაკანონიკური <span class="apocryphal-note">(ἀπόκρυφος/აპოკრიფი)</span>: ${s.noncanon_books} წიგნი · ${fmt(s.noncanon_verses)} მუხლი`);
  } catch (e) {
    // ჩუმად გამოტოვება

  }
}

function renderBooks() {
  const oldContainer = document.getElementById('books-old');
  const newContainer = document.getElementById('books-new');

  oldContainer.innerHTML = '';
  newContainer.innerHTML = '';

  BOOKS.old.forEach(book => oldContainer.appendChild(createBookElement(book)));
  BOOKS.new.forEach(book => newContainer.appendChild(createBookElement(book)));
}

// === Sidebar რეჟიმები ===
// sidebarMode: 'hidden' | 'all' | 'canonical' | 'ot' | 'nt' | 'noncanonical'
let sidebarMode = 'hidden';

function setSidebarMode(mode) {
  const sidebar = document.getElementById('sidebar');
  const edge = document.getElementById('sidebar-edge');
  const sections = document.querySelectorAll('.sidebar-section');
  const otSection = sections[0];
  const ntSection = sections[1];

  // peek/manuel-ის და inline left-ის შეწყვეტა გახსნის/დახურვისას
  sidebar.classList.remove('peek', 'manual');
  sidebar.style.left = '';
  if (edge) {
    edge.classList.remove('peek', 'manual');
  }

  // ყველა წიგნის და სექციის აღდგენა
  document.querySelectorAll('.book-item').forEach(el => el.style.display = '');
  if (otSection) otSection.style.display = '';
  if (ntSection) ntSection.style.display = '';

  if (mode === 'hidden') {
    sidebar.classList.add('sidebar-hidden');
    document.body.classList.add('sidebar-collapsed');
    sidebarMode = 'hidden';
    document.querySelectorAll('.book-toggle').forEach(el => el.classList.remove('active'));
    // ფოკუსის დაბრუნება აქტიურ toggle-ზე (კლავიატურით მომხმარებლისთვის)
    const activeToggle = document.activeElement && document.activeElement.classList.contains('book-toggle')
      ? document.activeElement
      : document.getElementById('book-toggle');
    if (activeToggle && document.activeElement === document.body) {
      activeToggle.focus({ preventScroll: true });
    }
    return;
  }

  // გაშლა - ფილტრაცია რეჟიმის მიხედვით
  sidebar.classList.remove('sidebar-hidden');
  document.body.classList.remove('sidebar-collapsed');

  if (mode === 'canonical') {
    // მხოლოდ კანონიკური - არაკანონიკური დამალული
    document.querySelectorAll('.book-item.apocryphal').forEach(el => el.style.display = 'none');
  } else if (mode === 'ot') {
    // მხოლოდ OT კანონიკური - არაკანონიკური დამალული + NT სექცია დამალული
    document.querySelectorAll('.book-item.apocryphal').forEach(el => el.style.display = 'none');
    if (ntSection) ntSection.style.display = 'none';
  } else if (mode === 'nt') {
    // მხოლოდ NT - OT სექცია დამალული
    if (otSection) otSection.style.display = 'none';
  } else if (mode === 'noncanonical') {
    // მხოლოდ არაკანონიკური - კანონიკური დამალული, NT სექცია დამალული (არაკანონიკური მხოლოდ OT-შია)
    document.querySelectorAll('.book-item:not(.apocryphal)').forEach(el => el.style.display = 'none');
    if (ntSection) ntSection.style.display = 'none';
  }
  // 'all' - ყველაფერი ჩანს (აღდგენილია ზემოთ)

  sidebarMode = mode;

  // active state-ის განახლება toggle-ებზე
  const toggleMap = {
    'all': 'book-toggle',
    'canonical': 'canonical-toggle',
    'ot': 'ot-toggle',
    'nt': 'nt-toggle',
    'noncanonical': 'noncanon-toggle'
  };
  document.querySelectorAll('.book-toggle').forEach(el => el.classList.remove('active'));
  if (toggleMap[mode]) {
    const el = document.getElementById(toggleMap[mode]);
    if (el) el.classList.add('active');
  }

  // ფოკუსის გადატანა sidebar-ის შიგნით (კლავიატურით მომხმარებლისთვის)
  // მხოლოდ თუ ფოკუსი არ არის უკვე sidebar-ის შიგნით
  if (!sidebar.contains(document.activeElement)) {
    const firstBook = sidebar.querySelector('.book-item:not([style*="display: none"])');
    if (firstBook) {
      // მცირე დაყოვნება - რომ CSS transition დასრულდეს
      setTimeout(() => firstBook.focus({ preventScroll: true }), 50);
    } else {
      const firstInput = sidebar.querySelector('input');
      if (firstInput) setTimeout(() => firstInput.focus({ preventScroll: true }), 50);
    }
  }
}

// დაკლიკების ლოგიკა - იგივე რეჟიმზე კვლავ დაკლიკება = შეკეცვა
function toggleSidebarMode(mode) {
  if (sidebarMode === mode) {
    setSidebarMode('hidden');
  } else {
    setSidebarMode(mode);
  }
}

// ძველი ფუნქციები - თავსებადი
function toggleCanonicalBooks() { toggleSidebarMode('canonical'); }
function toggleOTCanonical() { toggleSidebarMode('ot'); }
function toggleNTOnly() { toggleSidebarMode('nt'); }
function toggleNonCanonical() { toggleSidebarMode('noncanonical'); }

function createBookElement(book) {
  const div = document.createElement('div');
  div.className = 'book-item';
  if (book.apocryphal) div.classList.add('apocryphal');
  div.dataset.bookName = book.name.toLowerCase();
  div.dataset.bookSlug = book.slug;
  div.setAttribute('role', 'button');
  div.setAttribute('tabindex', '0');
  div.setAttribute('aria-label', book.name + (book.apocryphal ? ' (არაკანონიკური)' : ''));

  // სახელი
  const nameSpan = document.createElement('span');
  nameSpan.className = 'book-name-text';
  nameSpan.textContent = book.name;
  div.appendChild(nameSpan);

  if (book.apocryphal) {
    const tag = document.createElement('span');
    tag.className = 'apocryphal-tag';
    tag.textContent = ' არაკანონიკური';
    div.appendChild(tag);
  }

  // აუდიო იკონი (🎵) - თუ წიგნს აქვს აუდიო
  if (typeof hasAudio === 'function' && hasAudio(book.slug, book.chapters[0])) {
    const audioBtn = document.createElement('span');
    audioBtn.className = 'book-audio-icon';
    audioBtn.textContent = '🎵';
    audioBtn.title = 'აუდიო ფლეიერი';
    audioBtn.onclick = (e) => {
      e.stopPropagation();
      if (typeof openAudioPopup === 'function') {
        openAudioPopup(book, book.name);
      }
    };
    div.appendChild(audioBtn);
  }

  div.onclick = () => toggleBookChapters(book, div);
  // კლავიატურით გახსნა (Enter/Space)
  div.onkeydown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleBookChapters(book, div);
    }
  };
  return div;
}

// === წიგნების სერჩი ===
function filterBooks(testament) {
  const input = document.getElementById('book-search-' + testament);
  if (!input) return;
  const query = input.value.trim().toLowerCase();
  const container = document.getElementById('books-' + testament);
  if (!container) return;

  const items = container.querySelectorAll('.book-item');
  items.forEach(item => {
    const name = item.dataset.bookName || '';
    if (!query) {
      // ცარიელი სერჩი - ყველა ვაჩვენოთ, ხაზგასმის გარეშე
      item.classList.remove('hidden-by-search');
      const nameSpan = item.querySelector('.book-name-text');
      if (nameSpan) nameSpan.innerHTML = item.dataset.bookName ? capitalizeFirst(item.dataset.bookName) : nameSpan.textContent;
    } else if (name.includes(query)) {
      item.classList.remove('hidden-by-search');
      // ხაზგასმა
      const nameSpan = item.querySelector('.book-name-text');
      if (nameSpan) {
        const origName = item.dataset.bookName;
        const idx = origName.indexOf(query);
        if (idx >= 0) {
          nameSpan.innerHTML =
            escapeHtml(origName.substring(0, idx)) +
            '<span class="search-match">' + escapeHtml(origName.substring(idx, idx + query.length)) + '</span>' +
            escapeHtml(origName.substring(idx + query.length));
        }
      }
    } else {
      item.classList.add('hidden-by-search');
    }
  });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function escapeAttr(s) {
  return String(s).replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// === Focus management (accessibility) ===
// ფოკუსის გადატანა modal/popup-ში გახსნისას
function moveFocusInto(container) {
  if (!container) return;
  const focusable = container.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (focusable.length > 0) {
    focusable[0].focus();
  } else {
    // თუ არ არის focusable element, container-ს ვაქცევთ focusable-ად
    container.setAttribute('tabindex', '-1');
    container.focus();
  }
}

// Focus trap - Tab უნდა დარჩეს modal-ის შიგნით
let focusTrapHandler = null;
function enableFocusTrap(container) {
  if (focusTrapHandler) document.removeEventListener('keydown', focusTrapHandler);
  focusTrapHandler = (e) => {
    if (e.key !== 'Tab') return;
    const focusable = container.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first || document.activeElement === container) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };
  document.addEventListener('keydown', focusTrapHandler);
}

function disableFocusTrap() {
  if (focusTrapHandler) {
    document.removeEventListener('keydown', focusTrapHandler);
    focusTrapHandler = null;
  }
}

// ძველი ქართულის ასოების ნორმალიზაცია highlighting-სთვის
// ანიჭებს თითოეულ სიმბოლოს character class-ს რომ დაიჭიროს ეკვივალენტური ფორმები
// ჱ→ე, ჲ→ი, ჳ→ვ, ჴ→ხ, ჵ→ო
function normalizeOldGeorgianForRegex(term) {
  const map = {
    'ე': '[ეჱ]', 'ჱ': '[ეჱ]',
    'ი': '[იჲ]', 'ჲ': '[იჲ]',
    'ვ': '[ვჳ]', 'ჳ': '[ვჳ]',
    'ხ': '[ხჴ]', 'ჴ': '[ხჴ]',
    'ო': '[ოჵ]', 'ჵ': '[ოჵ]',
  };
  let result = '';
  for (const ch of term) {
    if (map[ch]) {
      // escape არ სჭირდება character class-ის შიგნით ქართულ ასოებს
      result += map[ch];
    } else {
      result += escapeRegex(ch);
    }
  }
  return result;
}

function capitalizeFirst(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

function toggleBookChapters(book, element, opts = {}) {
  // ვამოწმებთ - არის თუ არა ამ წიგნის თავები უკვე გახსნილი
  let chaptersDiv = element.nextElementSibling;
  const isOpen = chaptersDiv && chaptersDiv.classList.contains('book-chapters') && chaptersDiv.classList.contains('show');

  // დავხუროთ ყველა სხვა გახსნილი თავები
  document.querySelectorAll('.book-chapters.show').forEach(c => c.classList.remove('show'));
  // მოვნიშნოთ აქტიური წიგნი
  document.querySelectorAll('.book-item.active').forEach(b => b.classList.remove('active'));

  // თუ ეს წიგნი უკვე გახსნილი იყო - უბრალოდ დავხუროთ და გამოვხვიდეთ
  if (isOpen) {
    return;
  }

  // მოვნიშნოთ ეს წიგნი აქტიურად
  element.classList.add('active');

  // თუ თავების სია უკვე შექმნილია (მაგრამ დახურული) - გავხსნათ
  if (chaptersDiv && chaptersDiv.classList.contains('book-chapters')) {
    chaptersDiv.classList.add('show');
    // ავტომატურად გავხსნათ თავი 1 (თუ skipAutoOpen არ არის)
    if (!opts.skipAutoOpen) openChapter(book.slug, book.chapters[0]);
    return;
  }

  // შევქმნათ თავების სია
  chaptersDiv = document.createElement('div');
  chaptersDiv.className = 'book-chapters';
  book.chapters.forEach(ch => {
    const num = document.createElement('span');
    num.className = 'chapter-num';
    num.textContent = ch;
    num.onclick = (e) => {
      e.stopPropagation();
      openChapter(book.slug, ch);
    };
    chaptersDiv.appendChild(num);
  });
  element.after(chaptersDiv);
  chaptersDiv.classList.add('show');
  // ავტომატურად გავხსნათ თავი 1 (თუ skipAutoOpen არ არის)
  if (!opts.skipAutoOpen) openChapter(book.slug, book.chapters[0]);
}

// === თავის გახსნა ===
async function openChapter(bookSlug, chapter, opts = {}) {
  showView('chapter-view');

  // თარგმანის რეჟიმის ინიციალიზაცია (მობილურზე ავტომატური)
  initTranslationMode();

  // ძიების სიტყვის მარკირება თუ გადმოცემულია
  currentHighlightQuery = opts.highlightQuery || '';
  currentHighlightForms = opts.highlightForms || [];

  try {
    const res = await fetch(`/api/chapter/${bookSlug}/${chapter}`);
    const data = await res.json();
    currentBook = data.book_slug;
    currentChapter = data.chapter;
    currentVerses = data.verses;
    document.getElementById('chapter-title').textContent = `${data.book} ${data.chapter}`;
    renderChapter();
    renderQuickNav(bookSlug, data.book, data.chapter);
    setupScrollTracking();
    // URL-ის განახლება (თუ pushState არ არის გამორთული)
    if (!opts.skipURL) {
      updateURL(bookSlug, chapter);
    }
    // მუხლზე სკროლი თუ მოთხოვნილია (პრიორიტეტი პოზიციის აღდგენაზე)
    if (opts.scrollToVerse) {
      setTimeout(() => scrollToVerse(opts.scrollToVerse, opts.scrollToVerseEnd), 200);
    } else {
      // პოზიციის აღდგენა თუ იგივე თავია
      const lastPos = restoreReadingPosition();
      if (lastPos && lastPos.book === bookSlug && lastPos.chapter === chapter && lastPos.scroll) {
        setTimeout(() => {
          const container = document.getElementById('verses-container');
          if (container) container.scrollTop = lastPos.scroll;
          else window.scrollTo(0, lastPos.scroll);
        }, 100);
      }
    }
    // აუდიო პლეიერის ინიციალიზაცია
    if (typeof initAudioForChapter === 'function') {
      initAudioForChapter(bookSlug, data.chapter, data.book);
    }
    // განმარტების ბლოკის ინიციალიზაცია
    if (typeof initCommentaryForChapter === 'function') {
      initCommentaryForChapter(bookSlug, data.chapter, data.book);
    }
  } catch (e) {
    console.error('თავის ჩატვირთვა ვერ მოხერხდა:', e);
    showToast('თავის ჩატვირთვა ვერ მოხერხდა. სცადეთ თავიდან.');
  }
}

// === URL Routing ===
function updateURL(bookSlug, chapter, verse) {
  const hash = verse
    ? `#/${bookSlug}/${chapter}/${verse}`
    : `#/${bookSlug}/${chapter}`;
  if (location.hash !== hash) {
    history.pushState({ bookSlug, chapter, verse }, '', hash);
  }
}

function scrollToVerse(verseNum, verseEnd) {
  const rows = document.querySelectorAll('.verse-row');
  let firstMatch = null;
  for (const row of rows) {
    const v = Number(row.dataset.verse);
    // ინტერვალის შემთხვევაში - მოვნიშნოთ დიაპაზონი
    const inRange = verseEnd
      ? (v >= Number(verseNum) && v <= Number(verseEnd))
      : (v === Number(verseNum));
    if (inRange) {
      if (!firstMatch) firstMatch = row;
      row.style.transition = 'background-color 0.5s';
      const orig = row.style.backgroundColor;
      row.style.backgroundColor = 'rgba(201, 169, 110, 0.3)';
      // ინტერვალის შემთხვევაში - უფრო ხანგრძლივ მონიშვნა
      const duration = verseEnd ? 4000 : 2000;
      setTimeout(() => { row.style.backgroundColor = orig; }, duration);
    }
  }
  // სკროლი პირველ მატჩზე
  if (firstMatch) {
    firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function parseHash() {
  const h = location.hash.replace(/^#\/?/, '');
  if (!h) return null;

  // search: #search/query/mode[?t=testament&b=book&l=limit&r=rerank]
  if (h.startsWith('search/')) {
    const parts = h.split('/');
    const q = decodeURIComponent(parts[1] || '');
    // mode შეიძლება შეიცავდეს ? ფილტრებს
    const modeAndFilters = parts[2] || 'ai';
    const [mode, filterStr] = modeAndFilters.split('?');
    if (q) {
      document.getElementById('search-input').value = q;
      // რეჟიმის აღდგენა
      searchMode = mode;
      document.querySelectorAll('.mode-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === mode);
      });
      // ფილტრების აღდგენა URL-დან + კასტომ dropdown-ების განახლება
      if (filterStr) {
        const params = new URLSearchParams(filterStr);
        const t = params.get('t');
        const b = params.get('b');
        const tr = params.get('tr');
        const l = params.get('l');
        const r = params.get('r');
        if (t) {
          const el = document.getElementById('filter-testament');
          if (el) { el.value = t; if (el._refreshCustom) el._refreshCustom(); }
        }
        if (b) {
          const el = document.getElementById('filter-book');
          if (el) { el.value = b; if (el._refreshCustom) el._refreshCustom(); }
        }
        if (tr) {
          const el = document.getElementById('filter-translation');
          if (el) { el.value = tr; if (el._refreshCustom) el._refreshCustom(); }
        }
        if (l) {
          const el = document.getElementById('filter-limit');
          if (el) { el.value = l; if (el._refreshCustom) el._refreshCustom(); }
        }
        if (r === '0') { const el = document.getElementById('filter-rerank'); if (el) el.checked = false; }
      }
      performSearch(q, mode);
    }
    return null;
  }

  // lexicon: #lexicon ან #lexicon/letter
  if (h === 'lexicon' || h.startsWith('lexicon')) {
    if (typeof openLexicon === 'function') openLexicon();
    return null;
  }

  // topical: #topical/<slug>
  if (h.startsWith('topical/')) {
    const topicSlug = h.split('/')[1];
    if (topicSlug) {
      // topical.js შეიძლება ჯერ არ ჩატვირთულიყო (defer მიმდევრობა)
      const tryOpen = (attempts) => {
        if (typeof openTopicalPanel === 'function') {
          openTopicalPanel();
          if (typeof openTopicDetail === 'function') {
            setTimeout(() => openTopicDetail(topicSlug), 300);
          }
        } else if (attempts > 0) {
          setTimeout(() => tryOpen(attempts - 1), 100);
        }
      };
      tryOpen(10);
    }
    return null;
  }

  // chapter: #book/chapter[/verse]
  const parts = h.split('/');
  if (parts.length < 2) return null;
  return {
    bookSlug: decodeURIComponent(parts[0]),
    chapter: parseInt(parts[1]),
    verse: parts[2] ? parseInt(parts[2]) : null,
  };
}

window.addEventListener('popstate', (e) => {
  if (e.state && e.state.bookSlug) {
    // chapter-ზე დაბრუნება
    openChapter(e.state.bookSlug, e.state.chapter, { skipURL: true, scrollToVerse: e.state.verse });
  } else if (e.state && e.state.view === 'search') {
    // search-ზე დაბრუნება - პოზიციის აღდგენით
    showView('search-view', { restoreScroll: true });
  } else if (e.state && e.state.view === 'lexicon') {
    showView('lexicon-view', { restoreScroll: true });
    if (e.state.letter && typeof selectLexiconLetter === 'function') {
      selectLexiconLetter(e.state.letter);
    }
  } else {
    // მთავარ გვერდზე დაბრუნება
    showView('home-view', { restoreScroll: true });
  }
});

// hashchange - როცა URL hash იცვლება პირდაპირ (ბმულზე კლიკი, ხელით შეყვანა)
window.addEventListener('hashchange', () => {
  const h = location.hash.replace(/^#\/?/, '');
  if (!h) return;
  // lexicon: #lexicon/letter
  if (h.startsWith('lexicon')) {
    const letter = h.startsWith('lexicon/') ? decodeURIComponent(h.split('/')[1]) : null;
    if (typeof openLexicon === 'function') {
      // თუ უკვე lexicon-view-ზე არ ვართ, გავხსნათ
      if (document.getElementById('lexicon-view').style.display !== 'block') {
        openLexicon();
      } else if (letter && typeof selectLexiconLetter === 'function') {
        selectLexiconLetter(letter);
      }
    }
    return;
  }
  // search: #search/...
  if (h.startsWith('search/')) {
    parseHash();
    return;
  }
  // chapter: #book/chapter
  const route = parseHash();
  if (route) {
    const allBooks = [...(BOOKS.old || []), ...(BOOKS.new || [])];
    if (allBooks.some(b => b.slug === route.bookSlug)) {
      openChapter(route.bookSlug, route.chapter, { scrollToVerse: route.verse });
    }
  }
});

// სწრაფი ნავიგაცია - თავების ღილაკები მთავარ გვერდზე
function renderQuickNav(bookSlug, bookName, activeChapter) {
  const container = document.getElementById('chapter-quick-nav');
  if (!container) return;
  container.innerHTML = '';

  // ვპოვნით წიგნს BOOKS-ში
  const allBooks = [...(BOOKS.old || []), ...(BOOKS.new || [])];
  const book = allBooks.find(b => b.slug === bookSlug);
  if (!book || !book.chapters || book.chapters.length === 0) return;

  // ჭდე
  const label = document.createElement('span');
  label.className = 'qn-label';
  label.textContent = `${bookName} · თავები:`;
  container.appendChild(label);

  // თავების ღილაკები
  book.chapters.forEach(ch => {
    const num = document.createElement('span');
    num.className = 'qn-num';
    if (ch === activeChapter) num.classList.add('active');
    // 151-ე ფსალმუნი - არაკანონიკური
    if (bookSlug === 'fsalmunni' && ch === 151) {
      num.classList.add('qn-apocrypha');
      num.title = 'არაკანონიკურია';
    }
    num.textContent = ch;
    num.onclick = () => openChapter(bookSlug, ch);
    container.appendChild(num);
  });

  // მთავარ გვერდზე თავების სიაშიც მოვნიშნოთ აქტიური თავი
  _syncHomeChapterActive(bookSlug, activeChapter);
}

// მთავარ გვერდზე თავების სიაში აქტიური თავის მონიშვნა
function _syncHomeChapterActive(bookSlug, activeChapter) {
  document.querySelectorAll('.book-chapters.show .chapter-num.active').forEach(n => n.classList.remove('active'));
  const chaptersDiv = document.querySelector('.book-chapters.show');
  if (!chaptersDiv) return;
  const nums = chaptersDiv.querySelectorAll('.chapter-num');
  nums.forEach(n => {
    if (parseInt(n.textContent) === activeChapter) {
      n.classList.add('active');
    }
  });
}

// რეფრეშის შემდეგ მთავარ გვერდზე წიგნის თავების სიის გახსნა და აქტიური თავის მონიშვნა
function _openHomeBookChapters(bookSlug, activeChapter) {
  const allBooks = [...(BOOKS.old || []), ...(BOOKS.new || [])];
  const book = allBooks.find(b => b.slug === bookSlug);
  if (!book) return;
  // ვპოვნით წიგნის ელემენტს მთავარ გვერდზე
  const bookItems = document.querySelectorAll('.book-item');
  for (const item of bookItems) {
    if (item.textContent.trim().includes(book.name) || item.dataset.slug === bookSlug) {
      // გავხსნათ თავების სია skipAutoOpen-ით (არ გავხსნათ თავი 1 ავტომატურად)
      const next = item.nextElementSibling;
      if (!next || !next.classList.contains('book-chapters')) {
        toggleBookChapters(book, item, { skipAutoOpen: true });
      } else {
        next.classList.add('show');
        item.classList.add('active');
      }
      // მოვნიშნოთ აქტიური თავი
      _syncHomeChapterActive(bookSlug, activeChapter);
      break;
    }
  }
}

function renderChapter() {
  const container = document.getElementById('verses-container');
  const showOld = document.getElementById('show-old').checked;
  const showNew = document.getElementById('show-new').checked;
  const parallel = document.getElementById('parallel-view').checked;

  if (!parallel || !showOld || !showNew) {
    container.classList.add('single');
  } else {
    container.classList.remove('single');
  }

  container.innerHTML = '';
  currentVerses.forEach(v => {
    const row = document.createElement('div');
    row.className = 'verse-row';
    row.dataset.verse = v.verse;

    // შევამოწმოთ არის თუ არა ეს მუხლი ჩანიშნული / დაკომენტარებული
    const bm = bookmarks.find(b =>
      b.bookSlug === currentBook &&
      Number(b.chapter) === Number(currentChapter) &&
      Number(b.verseNum) === Number(v.verse)
    );
    const isBookmarked = !!(bm && bm.pinned);
    const hasComment = !!(bm && bm.comment && bm.comment.trim());
    const hasTags = !!(bm && bm.tags && bm.tags.length > 0);
    if (isBookmarked) row.classList.add('bookmarked');

    // ძიების სიტყვის მარკირება თუ გადმოცემულია
    // სიტყვის დონის კვლევა: ყველა სიტყვა კლიკაბელურია (wrapWordsInSpans)
    let newText = currentHighlightQuery ? markQueryTerms(v.new, currentHighlightQuery, currentHighlightForms) : escapeHtml(v.new);
    if (typeof wrapWordsInSpans === 'function') {
      newText = wrapWordsInSpans(newText);
    }
    let oldText = (showOld && v.old) ? (currentHighlightQuery ? markQueryTerms(v.old, currentHighlightQuery, currentHighlightForms) : escapeHtml(v.old)) : '';
    if (oldText && typeof wrapWordsInSpans === 'function') {
      oldText = wrapWordsInSpans(oldText);
    }

    if (showNew) {
      const newCell = document.createElement('div');
      newCell.className = 'verse-cell';
      newCell.dataset.verse = v.verse;
      const icons = [];
      if (hasComment) icons.push(`<span class="verse-bm-icon verse-comment-icon" onclick="event.stopPropagation(); showCommentBubble(this, ${v.verse})">💬</span>`);
      if (hasTags && typeof window.getVerseTagIcon === 'function') icons.push(window.getVerseTagIcon(currentBook, currentChapter, v.verse));
      if (isBookmarked) icons.push(`<span class="verse-bm-icon" title="ჩანიშნულია - დააკლიკე მოსახსნად" onclick="event.stopPropagation(); toggleBookmarkDirect('${currentBook}', ${currentChapter}, ${v.verse})">📌</span>`);
      newCell.innerHTML = `<span class="verse-num">${v.verse}</span><span class="verse-text">${newText}</span>${icons.join('')}`;
      newCell.onclick = (e) => handleVerseClick(e, v);
      row.appendChild(newCell);
    }

    if (showOld && v.old) {
      const oldCell = document.createElement('div');
      oldCell.className = 'verse-cell';
      oldCell.dataset.verse = v.verse;
      oldCell.innerHTML = `<span class="verse-num">${v.verse}</span><span class="verse-text old">${oldText}</span>`;
      oldCell.onclick = (e) => handleVerseClick(e, v);
      row.appendChild(oldCell);
    }

    container.appendChild(row);
  });

  // ფერადი მარკირების გადატარება
  applyHighlightsToChapter();

  // სიტყვის დონის კვლევა: event delegation-ის დაყენება
  if (typeof setupWordClickDelegation === 'function') {
    setupWordClickDelegation();
  }
}

// 3-გზის თარგმანის გადამრთველი
function setTranslationMode(mode, skipRender = false) {
  const showOld = document.getElementById('show-old');
  const showNew = document.getElementById('show-new');
  const parallel = document.getElementById('parallel-view');
  document.querySelectorAll('.trans-btn').forEach(btn => {
    const active = btn.dataset.mode === mode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active);
  });
  if (mode === 'new') {
    showNew.checked = true; showOld.checked = false; parallel.checked = false;
  } else if (mode === 'old') {
    showNew.checked = false; showOld.checked = true; parallel.checked = false;
  } else {
    showNew.checked = true; showOld.checked = true; parallel.checked = true;
  }
  localStorage.setItem('bible_trans_mode', mode);
  // skipRender=true მხოლოდ checkbox-ებს ანახლებს (openChapter-ის დროს, სერვერის პასუხამდე)
  if (!skipRender) renderChapter();
}

// მობილურზე ავტომატური ერთსვეტიანი რეჟიმი (პირველ ვიზიტზე)
// არ იძახებს renderChapter-ს - მხოლოდ checkbox-ებს ანახლებს
function initTranslationMode() {
  const saved = localStorage.getItem('bible_trans_mode');
  if (saved) {
    setTranslationMode(saved, true);
  } else if (window.innerWidth <= 900) {
    setTranslationMode('new', true);
  }
}

// === ნავიგაცია ===
async function prevChapter() {
  if (!currentBook || !currentChapter) return;
  const book = findBook(currentBook);
  if (!book) return;
  const idx = book.chapters.indexOf(currentChapter);
  if (idx > 0) {
    openChapter(currentBook, book.chapters[idx - 1]);
  } else {
    // წინა წიგნის ბოლო თავი
    const prevBook = findPrevBook(currentBook);
    if (prevBook && prevBook.chapters.length > 0) {
      openChapter(prevBook.slug, prevBook.chapters[prevBook.chapters.length - 1]);
    }
  }
}

async function nextChapter() {
  if (!currentBook || !currentChapter) return;
  const book = findBook(currentBook);
  if (!book) return;
  const idx = book.chapters.indexOf(currentChapter);
  if (idx < book.chapters.length - 1) {
    openChapter(currentBook, book.chapters[idx + 1]);
  } else {
    // მომდევნო წიგნის პირველი თავი
    const nextBook = findNextBook(currentBook);
    if (nextBook) {
      openChapter(nextBook.slug, nextBook.chapters[0]);
    }
  }
}

function findBook(slug) {
  return [...BOOKS.old, ...BOOKS.new].find(b => b.slug === slug);
}

function findPrevBook(slug) {
  const all = [...BOOKS.old, ...BOOKS.new];
  const idx = all.findIndex(b => b.slug === slug);
  return idx > 0 ? all[idx - 1] : null;
}

function findNextBook(slug) {
  const all = [...BOOKS.old, ...BOOKS.new];
  const idx = all.findIndex(b => b.slug === slug);
  return idx < all.length - 1 ? all[idx + 1] : null;
}

// === ძიება ===
async function doSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;
  await performSearch(q, searchMode);
}

async function quickSearch(q) {
  document.getElementById('search-input').value = q;
  await performSearch(q, 'ai');
}

async function performSearch(q, mode) {
  showView('search-view');
  // ფილტრების წაკითხვა
  const testament = document.getElementById('filter-testament')?.value || '';
  const book = document.getElementById('filter-book')?.value || '';
  const translation = document.getElementById('filter-translation')?.value || '';
  const limitEl = document.getElementById('filter-limit');
  let limit = limitEl?.value || '20';
  if (mode === 'keyword') {
    limit = Math.max(50, parseInt(limit) || 500);
  }
  const rerank = document.getElementById('filter-rerank')?.checked ? 'true' : 'false';

  // history-ში შენახვა - ფილტრების ჩათვლით
  const searchState = { view: 'search', query: q, mode, testament, book, translation, limit, rerank };
  const filterParams = new URLSearchParams();
  if (testament) filterParams.set('t', testament);
  if (book) filterParams.set('b', book);
  if (translation) filterParams.set('tr', translation);
  if (limit && limit !== '20') filterParams.set('l', limit);
  if (rerank === 'false') filterParams.set('r', '0');
  const filterStr = filterParams.toString();
  const hash = `#search/${encodeURIComponent(q)}/${mode}${filterStr ? '?' + filterStr : ''}`;
  if (!history.state || history.state.view !== 'search' || history.state.query !== q) {
    history.pushState(searchState, '', hash);
  }
  document.getElementById('search-title').textContent = `ძიება: "${q}"`;
  // ჩატვირთვის ინდიკატორი - spinner + ტექსტი
  const modeLabel = mode === 'ai' ? 'აზრითი ძიება' : 'სიტყვიერი ძიება';
  document.getElementById('search-results').innerHTML = `
    <div class="search-loader">
      <div class="search-spinner"></div>
      <p>${modeLabel} მიმდინარეობს...</p>
      <p class="search-loader-sub">AI მოდელი ეძებს აზრობრივ შესატყვისებს, შეიძლება გასტანდეს 1-3 წამი</p>
    </div>`;

  // ფილტრების წაკითხვა (უკვე ზემოთ წავიკითხეთ, მაგრამ keyword რეჟიმისთვის გავზარდოთ limit)
  if (mode === 'keyword') {
    limit = Math.max(50, parseInt(limit) || 500);
  }

  try {
    const endpoint = mode === 'ai' ? '/api/search/ai' : '/api/search/keyword';
    const params = new URLSearchParams({
      q: q,
      limit: limit,
      testament: testament,
      book: book,
      translation: translation,
      rerank: rerank,
    });
    const res = await fetch(`${endpoint}?${params}`);
    const data = await res.json();

    // სიტყვიერ რეჟიმში - სრული სტატისტიკა და მარკირება
    if (mode === 'keyword') {
      renderKeywordSearchResults(data, q);
    } else {
      renderSearchResults(data.results, mode, q);
      const info = document.getElementById('search-info');
      if (info) {
        let methodText = 'ჰიბრიდული (BM25 + LaBSE + RRF + Cross-Encoder)';
        if (data.method) methodText = data.method;
        // exact_count-ის ჩვენება — რამდენი ზუსტი match იპოვა
        let exactText = '';
        if (data.exact_count !== undefined && data.exact_count > 0) {
          exactText = ` · ზუსტი match: ${data.exact_count} მუხლი`;
        }
        info.textContent = `${data.total} შედეგი${exactText} · მეთოდი: ${methodText}`;
      }
    }
  } catch (e) {
    console.error('ძიების შეცდომა:', e);
    document.getElementById('search-results').innerHTML = '<p style="color:red;text-align:center;padding:20px;">ძიება ვერ მოხერხდა. შეამოწმეთ ინტერნეტკავშირი და სცადეთ თავიდან.</p>';
    showToast('ძიება ვერ მოხერხდა. სცადეთ თავიდან.');
  } finally {
    // უსაფრთხოებისთვის: თუ რაიმე მიზეზით spinner დარჩა, დავმალოთ
    const loader = document.querySelector('.search-loader');
    if (loader) loader.remove();
  }
}

function renderKeywordSearchResults(data, q) {
  const container = document.getElementById('search-results');
  const info = document.getElementById('search-info');

  // გაფართოებული ფორმების შენახვა თავის ხედში გადასატანად
  const expandedForms = data.expanded_forms || [];

  if (data.total === 0) {
    if (info) info.textContent = '';
    container.innerHTML = `<p style="text-align:center;color:var(--text-muted);padding:40px;">სიტყვა "${escapeHtml(q)}" ვერ მოიძებნა</p>`;
    return;
  }

  // სტატისტიკის ზოლი
  if (info) {
    const showingText = data.showing && data.showing < data.total
      ? ` <span class="stat-showing">(ვაჩვენებთ ${data.showing}-დან ${data.total})</span>`
      : '';
    // გაფართოების ინფორმაცია
    let expansionHtml = '';
    if (data.expanded_count && data.expanded_count > 1 && data.expanded_forms) {
      const forms = data.expanded_forms.slice(0, 15);
      const more = data.expanded_count > 15 ? ` <span class="stat-more">+${data.expanded_count - 15}</span>` : '';
      expansionHtml = `<div class="stat-expansion">
        <span class="stat-expansion-label">🔤 გაფართოებული ფორმები (${data.expanded_count}):</span>
        <span class="stat-forms">${forms.map(f => escapeHtml(f)).join(', ')}${more}</span>
      </div>`;
    }
    info.innerHTML = `
      <div class="search-stats">
        <div class="stat-item">
          <span class="stat-num">${data.total_occurrences}</span>
          <span class="stat-label">სიტყვის რაოდენობა</span>
        </div>
        <div class="stat-item">
          <span class="stat-num">${data.total}</span>
          <span class="stat-label">მუხლი</span>
        </div>
        <div class="stat-item">
          <span class="stat-num">${data.total_chapters}</span>
          <span class="stat-label">თავი</span>
        </div>
      </div>
      <div class="stat-query">🔍 "${escapeHtml(q)}" ${showingText}</div>
      ${expansionHtml}`;
  }

  // თავების სია - დალაგებული რაოდენობის მიხედვით
  let html = '';

  // expandedForms-ის JSON-ის HTML-safe encode-ვა (base64 ან data attribute)
  const formsJSON = JSON.stringify(expandedForms).replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  if (data.chapters && data.chapters.length > 0) {
    html += '<div class="chapters-overview">';
    html += '<h3 class="overview-title">📚 თავების სია</h3>';
    html += '<div class="chapters-grid">';
    data.chapters.forEach(ch => {
      html += `
        <button class="chapter-pill" data-book="${escapeAttr(ch.book_slug)}" data-chapter="${ch.chapter}" data-query="${escapeAttr(q)}" data-forms="${formsJSON}">
          <span class="pill-name">${escapeHtml(ch.book)} ${ch.chapter}</span>
          <span class="pill-count">${ch.occurrences}× · ${ch.verse_count} მუხლი</span>
        </button>`;
    });
    html += '</div>';
    html += '</div>';
  }

  // მუხლების სია - მარკირებული
  html += '<div class="verses-section">';
  html += '<h3 class="overview-title">📝 მუხლები</h3>';
  data.results.forEach(r => {
    const occBadge = r.occurrences > 1
      ? `<span class="occ-badge">${r.occurrences}×</span>`
      : '';
    html += `
      <div class="search-result" data-book="${escapeAttr(r.book_slug)}" data-chapter="${r.chapter}" data-query="${escapeAttr(q)}" data-forms="${formsJSON}" data-verse="${r.verse}">
        <div class="result-ref">${escapeHtml(r.book)} ${r.chapter}:${r.verse} ${occBadge}</div>
        <div class="result-text">${r.new_marked}</div>
        ${r.old_marked ? `<div class="result-text old">${r.old_marked}</div>` : ''}
      </div>`;
  });
  html += '</div>';

  container.innerHTML = html;

  // Event delegation for keyword search results (data attributes)
  // ამოვიცილოთ ძველი listeners თავიდან დასაყენებლად
  container.onclick = (e) => {
    const item = e.target.closest('[data-book]');
    if (!item) return;
    const book = item.dataset.book;
    const chapter = parseInt(item.dataset.chapter);
    const query = item.dataset.query;
    const verse = item.dataset.verse ? parseInt(item.dataset.verse) : undefined;
    let forms = [];
    try {
      forms = item.dataset.forms ? JSON.parse(item.dataset.forms) : [];
    } catch (err) { forms = []; }
    const opts = { highlightQuery: query, highlightForms: forms };
    if (verse) opts.scrollToVerse = verse;
    openChapter(book, chapter, opts);
  };
}

function renderSearchResults(results, mode, query) {
  const container = document.getElementById('search-results');
  if (results.length === 0) {
    container.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:40px;">არაფერი მოიძებნა</p>';
    return;
  }

  container.innerHTML = '';
  results.forEach(r => {
    const div = document.createElement('div');
    div.className = 'search-result';
    let scoreHtml = '';
    if (mode === 'ai' && r.score) {
      const pct = Math.round(r.score * 100);
      scoreHtml = `<span class="result-score">${pct}% მსგავსება</span>`;
    }
    // AI რეჟიმში სიტყვების მარკირება კლიენტზე
    const newText = (mode === 'ai' && query) ? markQueryTerms(r.new, query) : escapeHtml(r.new);
    const oldText = (mode === 'ai' && query && r.old) ? markQueryTerms(r.old, query) : escapeHtml(r.old || '');
    // AI რეჟიმში ფორმები არ გვაქვს, მაგრამ query-ს სიტყვებს ვმარკირებთ
    div.innerHTML = `
      <div class="result-ref">${escapeHtml(r.book)} ${r.chapter}:${r.verse} ${scoreHtml}</div>
      <div class="result-text">${newText}</div>
      ${oldText ? `<div class="result-text old">${oldText}</div>` : ''}
    `;
    div.onclick = () => openChapter(r.book_slug, r.chapter, { highlightQuery: query, scrollToVerse: r.verse });
    container.appendChild(div);
  });
}

// სიტყვების მარკირება ტექსტში (AI რეჟიმისთვის)
// უსაფრთხო მიდგომა: ერთიანი regex ყველა ტერმისთვის, ერთი გადაყვანა
// არ აფუჭებს HTML-ს, რადგან თითოეულ მატჩზე მხოლოდ ერთხელ ხდება <mark>-ის ჩასმა
function markQueryTerms(text, query, forms) {
  if (!text || !query) return text;
  let result = escapeHtml(text);
  // ვაგროვებთ ყველა ტერმს - query-ს სიტყვები + გაფართოებული ფორმები
  const terms = new Set();
  query.trim().split(/\s+/).filter(t => t.length >= 2).forEach(t => terms.add(t));
  if (forms && forms.length) {
    forms.forEach(f => { if (f && f.length >= 2) terms.add(f); });
  }
  if (terms.size === 0) return result;

  // დავლაგოთ სიგრძის მიხედვით (გრძელი ფორმები ჯერ) რომ არ დაირღვეს მოკლე ფორმებით
  const sortedTerms = [...terms].sort((a, b) => b.length - a.length);
  // ერთიანი regex: (term1|term2|term3)
  const patterns = sortedTerms.map(term => normalizeOldGeorgianForRegex(term));
  const combinedRegex = new RegExp('(' + patterns.join('|') + ')', 'gi');
  // ერთი replace - არ შეიძლება უკვე ჩასმულ <mark>-ში მოხვდეს
  result = result.replace(combinedRegex, '<mark>$1</mark>');
  return result;
}

// === მუხლის პოპაპი ===
function showVersePopup(bookSlug, chapter, verse) {
  // თუ verse არის ციფრი - მოვძებნოთ სრული ობიექტი currentVerses-დან
  if (typeof verse === 'number') {
    const found = currentVerses?.find(x => x.verse === verse);
    if (found) verse = found;
    else return;
  }
  const bubble = document.getElementById('comment-bubble');
  if (bubble) {
    const textarea = bubble.querySelector('.comment-bubble-edit-area');
    if (textarea) {
      if (!confirm('💬 კომენტარი არ არის შენახული. გსურს გაგრძელება?\n\nOK - გააგრძელე და დაკარგე ცვლილებები\nCancel - დარჩი და შეინახე')) {
        return;
      }
    }
    bubble.remove();
  }
  currentVersePopup = { bookSlug, chapter, verse };
  const popup = document.getElementById('verse-popup');
  const content = document.getElementById('popup-verse');
  const book = findBook(bookSlug)?.name || bookSlug;
  const isBm = bookmarks.some(b =>
    b.bookSlug === bookSlug &&
    Number(b.chapter) === Number(chapter) &&
    Number(b.verseNum) === Number(verse.verse) &&
    b.pinned
  );
  // ცარიელ ადგილას დაკლიკებით დახურვა (backdrop)
  popup.onclick = (e) => {
    if (e.target === popup) closePopup();
  };
  content.innerHTML = `
    <h3 style="color:var(--primary);margin-bottom:14px;font-family:var(--font-sans);font-size:18px;">${book} ${chapter}:${verse.verse}</h3>
    <p style="margin-bottom:14px;font-size:17px;line-height:1.8;">${typeof wrapWordsInSpans === 'function' ? wrapWordsInSpans(escapeHtml(verse.new)) : escapeHtml(verse.new)}</p>
    ${verse.old ? `<p style="color:var(--text-old);font-size:16px;line-height:1.8;opacity:0.85;">${typeof wrapWordsInSpans === 'function' ? wrapWordsInSpans(escapeHtml(verse.old)) : escapeHtml(verse.old)}</p>` : ''}
  `;
  // მარკერების პალიტრა - ცალკე კონტეინერში ("ჩემი" ტაბში)
  const paletteContainer = document.getElementById('popup-highlight-palette');
  if (paletteContainer) {
    paletteContainer.innerHTML = `
      <div class="highlight-palette" id="highlight-palette">
        <span class="highlight-palette-label">მარკერები:</span>
        <div class="highlight-palette-row">
          ${HIGHLIGHT_COLORS.slice(0,4).map(c => `<button class="highlight-color-btn ${c.class}" title="${escapeAttr(getColorLabel(c.id))}" onclick="toggleHighlight(${verse.verse}, '${c.id}'); refreshHighlightPalette(${verse.verse})"></button>`).join('')}
        </div>
        <div class="highlight-palette-row">
          ${HIGHLIGHT_COLORS.slice(4,8).map(c => `<button class="highlight-color-btn ${c.class}" title="${escapeAttr(getColorLabel(c.id))}" onclick="toggleHighlight(${verse.verse}, '${c.id}'); refreshHighlightPalette(${verse.verse})"></button>`).join('')}
        </div>
        <div class="highlight-palette-row">
          ${HIGHLIGHT_COLORS.slice(8,12).map(c => `<button class="highlight-color-btn ${c.class}" title="${escapeAttr(getColorLabel(c.id))}" onclick="toggleHighlight(${verse.verse}, '${c.id}'); refreshHighlightPalette(${verse.verse})"></button>`).join('')}
          <button class="highlight-clear-btn" onclick="clearHighlight(${verse.verse}); refreshHighlightPalette(${verse.verse})">✕</button>
        </div>
      </div>
    `;
  }
  // ღილაკის ტექსტი - დამატება თუ მოხსნა
  const bmBtn = document.querySelector('.popup-actions button[onclick="bookmarkVerse()"]');
  if (bmBtn) bmBtn.innerHTML = isBm ? '📌 მოხსნა' : '📌 სანიშნე';
  // კომენტარის ველი - თუ უკვე ჩანიშნულია, ვაჩვენოთ არსებული კომენტარი
  const commentInput = document.getElementById('popup-comment');
  if (commentInput) {
    const existing = bookmarks.find(b =>
      b.bookSlug === bookSlug && b.chapter === chapter && b.verseNum === verse.verse
    );
    commentInput.value = existing?.comment || '';
    commentInput.placeholder = isBm ? 'კომენტარი (რედაქტირება - ✏️ სანიშნეების პანელში)' : 'კომენტარი სანიშნისთვის (არასავალდებულო)...';
  }
  popup.style.display = 'flex';

  // Accessibility: focus გადატანა popup-ში + focus trap
  moveFocusInto(popup);
  enableFocusTrap(popup);

  // თაგების რენდერი - tags.js-ის გამოყენებით
  window._currentVersePopup = { bookSlug, chapter, verse };
  if (typeof window.renderPopupTags === 'function') {
    window.renderPopupTags(bookSlug, chapter, verse.verse);
  }
  // მარკირების პალიტრის active მდგომარეობის განახლება
  refreshHighlightPalette(verse.verse);

  // ტაბების რესეტი - "ტექსტი" ნაგულისხმევი
  popupResearchLoaded = false;
  const crDiv = document.getElementById('research-crossrefs');
  const tpDiv = document.getElementById('research-topics');
  if (crDiv) crDiv.innerHTML = '';
  if (tpDiv) tpDiv.innerHTML = '';
  switchPopupTab('text');
}

// === პოპაპის ტაბები ===
let popupResearchLoaded = false;

function switchPopupTab(tabName) {
  document.querySelectorAll('.popup-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  document.querySelectorAll('.popup-tab-content').forEach(content => {
    content.classList.toggle('active', content.id === 'tab-' + tabName);
  });
  // კვლევის ტაბი - lazy loading
  if (tabName === 'research' && !popupResearchLoaded && currentVersePopup) {
    loadPopupResearch();
  }
}

async function loadPopupResearch() {
  if (!currentVersePopup) return;
  const loading = document.getElementById('research-loading');
  const crossrefsDiv = document.getElementById('research-crossrefs');
  const topicsDiv = document.getElementById('research-topics');
  if (!loading || !crossrefsDiv || !topicsDiv) return;

  loading.style.display = 'block';
  crossrefsDiv.innerHTML = '';
  topicsDiv.innerHTML = '';
  popupResearchLoaded = true;

  const { bookSlug, chapter, verse } = currentVersePopup;

  try {
    // Cross references
    const crRes = await fetch('/api/crossrefs/' + bookSlug + '/' + chapter + '/' + verse.verse + '?limit=10&min_confidence=50');
    const crData = await crRes.json().catch(() => null);

    if (crData && crData.crossrefs && crData.crossrefs.length > 0) {
      let html = '<div class="research-section-title">🔗 დაკავშირებული მუხლები (' + crData.shown + '/' + crData.total + ')</div>';
      for (let i = 0; i < crData.crossrefs.length; i++) {
        const ref = crData.crossrefs[i];
        const label = ref.vs === ref.ve
          ? escapeHtml(ref.book_name) + ' ' + ref.chapter + ':' + ref.vs
          : escapeHtml(ref.book_name) + ' ' + ref.chapter + ':' + ref.vs + '-' + ref.ve;
        const sourceIcon = ref.source === 'both' ? '★★' : (ref.source === 'tsk' ? '★' : '');
        const sourceTitle = ref.source === 'both' ? 'ორმაგი სანდოობა' : (ref.source === 'tsk' ? 'TSK' : 'OpenBible');
        const topicKa = ref.topic_ka || '';
        const topicLabel = topicKa || (ref.topic && ref.topic !== 'general' && ref.topic !== 'reciprocal' ? ref.topic : '');
        html += '<div class="research-item" onclick="closePopup(); openChapter(\'' + escapeAttr(ref.book) + '\', ' + ref.chapter + ', { scrollToVerse: ' + ref.vs + ' })">'
          + '<div class="research-item-ref">' + label + '</div>'
          + '<div class="research-item-meta">'
          + (sourceIcon ? '<span class="research-item-source" title="' + escapeAttr(sourceTitle) + '">' + sourceIcon + '</span>' : '')
          + (topicLabel ? '<span class="research-item-topic">' + escapeHtml(topicLabel) + '</span>' : '')
          + '</div>'
          + (ref.text_preview ? '<div class="research-item-preview">' + escapeHtml(ref.text_preview) + '</div>' : '')
          + '</div>';
      }
      crossrefsDiv.innerHTML = html;
    } else {
      crossrefsDiv.innerHTML = '<div class="research-section-title">🔗 დაკავშირებული მუხლები</div><div class="research-empty">არ მოიძებნა</div>';
    }

    // თემები
    const topics = await loadVerseTopics(bookSlug, chapter, verse.verse);
    if (topics && topics.length > 0) {
      let html = '<div class="research-section-title">📚 თემები (' + topics.length + ')</div>';
      for (let i = 0; i < topics.length; i++) {
        const t = topics[i];
        const sourceIcon = t.source === 'nave' ? '📖' : '📑';
        html += '<div class="research-topic-item" onclick="closePopup(); openTopicalPanel(); openTopicDetail(\'' + escapeAttr(t.slug) + '\')">'
          + '<span class="research-topic-icon">' + sourceIcon + '</span>'
          + '<span class="research-topic-name">' + escapeHtml(t.name) + '</span>'
          + '<span class="research-topic-count">' + t.verse_count + '</span>'
          + '</div>';
      }
      topicsDiv.innerHTML = html;
    } else {
      topicsDiv.innerHTML = '<div class="research-section-title">📚 თემები</div><div class="research-empty">არ მოიძებნა</div>';
    }
  } catch (e) {
    crossrefsDiv.innerHTML = '<div class="research-empty">ჩატვირთვის შეცდომა</div>';
  } finally {
    loading.style.display = 'none';
  }
}

function closePopup() {
  document.getElementById('verse-popup').style.display = 'none';
  disableFocusTrap();
  currentVersePopup = null;
  const dd = document.getElementById('tag-dropdown');
  if (dd) dd.remove();
  // კომენტარის ბუშტის დახურვა (დაუსრულებელი რედაქტირების შემოწმებით)
  const bubble = document.getElementById('comment-bubble');
  if (bubble) {
    const textarea = bubble.querySelector('.comment-bubble-edit-area');
    if (textarea) {
      if (!confirm('💬 კომენტარი არ არის შენახული. გსურს გაგრძელება?\n\nOK - გააგრძელე და დაკარგე ცვლილებები\nCancel - დარჩი და შეინახე')) {
        return;
      }
    }
    bubble.remove();
  }
}

// === Cross-references ჩატვირთვა popup-ში ===
async function loadCrossRefs(bookSlug, chapter, verseNum) {
  const section = document.getElementById('crossrefs-section');
  const container = document.getElementById('crossrefs-container');
  if (!section || !container) return;

  section.style.display = 'none';
  container.style.display = 'none';
  container.innerHTML = '';
  document.getElementById('crossrefs-toggle-icon').textContent = '▶';

  try {
    const res = await fetch(
      '/api/crossrefs/' + bookSlug + '/' + chapter + '/' + verseNum + '?limit=10&min_confidence=50'
    );
    if (!res.ok) return;
    const data = await res.json();
    if (!data.crossrefs || data.crossrefs.length === 0) return;

    section.style.display = 'block';
    document.getElementById('crossrefs-title-text').textContent =
      'დაკავშირებული მუხლები (' + data.shown + '/' + data.total + ')';

    let html = '';
    for (let i = 0; i < data.crossrefs.length; i++) {
      const ref = data.crossrefs[i];
      const label = ref.vs === ref.ve
        ? escapeHtml(ref.book_name) + ' ' + ref.chapter + ':' + ref.vs
        : escapeHtml(ref.book_name) + ' ' + ref.chapter + ':' + ref.vs + '-' + ref.ve;

      // სანდოობის ინდიკატორი
      const sourceIcon = ref.source === 'both' ? '★★' : (ref.source === 'tsk' ? '★' : '');
      const sourceTitle = ref.source === 'both' ? 'ორმაგი სანდოობა (TSK + OpenBible)'
        : (ref.source === 'tsk' ? 'TSK - აკადემიური' : 'OpenBible.info');

      // თემატური კატეგორია - ქართული თარგმანი topic_ka-დან, fallback ინგლისურზე
      const topicKa = ref.topic_ka || '';
      const topicLabel = topicKa || (ref.topic && ref.topic !== 'general' && ref.topic !== 'reciprocal'
        ? ref.topic : '');
      const typeLabel = ref.type === 'reciprocal' ? '↔ ორმხრივი' : '';

      html += '<div class="crossref-item" '
        + 'onclick="closePopup(); openChapter(\'' + escapeAttr(ref.book) + '\', ' + ref.chapter + ', { scrollToVerse: ' + ref.vs + ' })">'
        + '<div class="crossref-label">'
        + '<span class="crossref-ref">' + label + '</span>'
        + '<span class="crossref-meta">'
        + (sourceIcon ? '<span class="crossref-source" title="' + escapeAttr(sourceTitle) + '">' + sourceIcon + '</span>' : '')
        + (topicLabel ? '<span class="crossref-topic">' + escapeHtml(topicLabel) + '</span>' : '')
        + (typeLabel ? '<span class="crossref-type">' + typeLabel + '</span>' : '')
        + '</span>'
        + '</div>';
      if (ref.text_preview) {
        html += '<div class="crossref-preview">' + escapeHtml(ref.text_preview) + '</div>';
      }
      html += '</div>';
    }
    container.innerHTML = html;
  } catch (e) {
    // ჩუმად - cross-refs არ არის კრიტიკული
  }
}

function toggleCrossRefs() {
  const container = document.getElementById('crossrefs-container');
  const icon = document.getElementById('crossrefs-toggle-icon');
  if (!container) return;
  if (container.style.display === 'none') {
    container.style.display = 'block';
    icon.textContent = '▼';
  } else {
    container.style.display = 'none';
    icon.textContent = '▶';
  }
}

// === მუხლის თემები popup-ში ===

async function loadVerseTopicsInPopup(bookSlug, chapter, verseNum) {
  const section = document.getElementById('topics-section');
  const container = document.getElementById('topics-container');
  if (!section || !container) return;

  section.style.display = 'none';
  container.style.display = 'none';
  container.innerHTML = '';
  document.getElementById('topics-toggle-icon').textContent = '▶';

  try {
    const topics = await loadVerseTopics(bookSlug, chapter, verseNum);
    if (!topics || topics.length === 0) return;

    section.style.display = 'block';
    document.getElementById('topics-title-text').textContent =
      '📚 თემები (' + topics.length + ')';

    let html = '';
    for (let i = 0; i < topics.length; i++) {
      const t = topics[i];
      const sourceIcon = t.source === 'nave' ? '📖' : '📑';
      html += '<div class="topic-tag-item" onclick="closePopup(); openTopicalPanel(); openTopicDetail(\'' + escapeAttr(t.slug) + '\')">'
        + '<span class="topic-tag-icon">' + sourceIcon + '</span>'
        + '<span class="topic-tag-name">' + escapeHtml(t.name) + '</span>'
        + '<span class="topic-tag-count">' + t.verse_count + '</span>'
        + '</div>';
    }
    container.innerHTML = html;
  } catch (e) {
    // ჩუმად
  }
}

function toggleVerseTopics() {
  const container = document.getElementById('topics-container');
  const icon = document.getElementById('topics-toggle-icon');
  if (!container) return;
  if (container.style.display === 'none') {
    container.style.display = 'block';
    icon.textContent = '▼';
  } else {
    container.style.display = 'none';
    icon.textContent = '▶';
  }
}

// მოკლე კომენტარის ბუშტი - მუხლთან ახლოს
function showCommentBubble(anchor, verseNum) {
  // ვშლით ძველ ბუშტს
  const old = document.getElementById('comment-bubble');
  if (old) { old.remove(); return; }

  if (!currentVerses) return;
  const v = currentVerses.find(x => x.verse === verseNum);
  if (!v) return;

  const bm = bookmarks.find(b =>
    b.bookSlug === currentBook &&
    Number(b.chapter) === Number(currentChapter) &&
    Number(b.verseNum) === Number(verseNum)
  );
  if (!bm || !bm.comment) return;

  const bubble = document.createElement('div');
  bubble.id = 'comment-bubble';
  bubble.className = 'comment-bubble';
  bubble.innerHTML = `
    <div class="comment-bubble-header">შენი კომენტარი</div>
    <div class="comment-bubble-text">${escapeHtml(bm.comment)}</div>
    <div class="comment-bubble-actions">
      <button class="comment-bubble-edit" onclick="event.stopPropagation(); editBubbleComment(${verseNum})">✏️ რედაქტირება</button>
      <button class="comment-bubble-del" onclick="event.stopPropagation(); deleteBubbleComment(${verseNum})">🗑 წაშლა</button>
    </div>
  `;
  document.body.appendChild(bubble);

  // პოზიცია - anchor-ის ქვემოთ, წვეტით
  const rect = anchor.getBoundingClientRect();
  const bubbleWidth = 320;
  let left = rect.left - 20;
  if (left + bubbleWidth > window.innerWidth - 10) left = window.innerWidth - bubbleWidth - 10;
  if (left < 10) left = 10;
  bubble.style.top = (rect.bottom + 8) + 'px';
  bubble.style.left = left + 'px';

  // დახურვა კლიკზე
  setTimeout(() => {
    const handler = (e) => {
      if (e.target !== bubble && !bubble.contains(e.target)) {
        bubble.remove();
        document.removeEventListener('click', handler);
      }
    };
    document.addEventListener('click', handler);
  }, 50);
}

// ბუშტში კომენტარის რედაქტირება - იმავე ბუშტში, ბრაუზერის prompt-ის გარეშე
function editBubbleComment(verseNum) {
  const idx = bookmarks.findIndex(b =>
    b.bookSlug === currentBook &&
    Number(b.chapter) === Number(currentChapter) &&
    Number(b.verseNum) === Number(verseNum)
  );
  if (idx < 0) return;
  const bubble = document.getElementById('comment-bubble');
  if (!bubble) return;
  const current = bookmarks[idx].comment || '';

  // ვცვლით ტექსტის ველი textarea-ით
  const textEl = bubble.querySelector('.comment-bubble-text');
  const actionsEl = bubble.querySelector('.comment-bubble-actions');
  if (!textEl || !actionsEl) return;

  const textarea = document.createElement('textarea');
  textarea.className = 'comment-bubble-edit-area';
  textarea.maxLength = 99;
  textarea.value = current;
  textarea.rows = 3;
  textarea.placeholder = 'კომენტარი...';
  textEl.replaceWith(textarea);
  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);

  // ვცვლით ღილაკებს
  actionsEl.innerHTML = `
    <button class="comment-bubble-save" onclick="event.stopPropagation(); saveBubbleComment(${verseNum})">✒️ შენახვა</button>
    <button class="comment-bubble-cancel" onclick="event.stopPropagation(); cancelBubbleEdit(${verseNum})">✕ გაუქმება</button>
  `;
}

// ბუშტში რედაქტირების შენახვა
function saveBubbleComment(verseNum) {
  const idx = bookmarks.findIndex(b =>
    b.bookSlug === currentBook &&
    Number(b.chapter) === Number(currentChapter) &&
    Number(b.verseNum) === Number(verseNum)
  );
  if (idx < 0) return;
  const bubble = document.getElementById('comment-bubble');
  if (!bubble) return;
  const textarea = bubble.querySelector('.comment-bubble-edit-area');
  if (!textarea) return;
  const trimmed = textarea.value.trim().substring(0, 99);
  bookmarks[idx].comment = trimmed;
  persistBookmarks();
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === bookmarks[idx].bookSlug && currentChapter === bookmarks[idx].chapter) renderChapter();
  showToast(trimmed ? '💬 კომენტარი შეინახა' : '💬 კომენტარი წაიშალა');
  bubble.remove();
}

// ბუშტში რედაქტირების გაუქმება
function cancelBubbleEdit(verseNum) {
  const bubble = document.getElementById('comment-bubble');
  if (bubble) bubble.remove();
}

// ბუშტში კომენტარის წაშლა
function deleteBubbleComment(verseNum) {
  const idx = bookmarks.findIndex(b =>
    b.bookSlug === currentBook &&
    Number(b.chapter) === Number(currentChapter) &&
    Number(b.verseNum) === Number(verseNum)
  );
  if (idx < 0) return;
  const ref = bookmarks[idx].ref;
  if (!confirm(`⚠️ დარწმუნებული ხარ?\n\n💬 კომენტარი წაიშლება მუხლიდან "${ref}".\n\nეს მოქმედება შეუქცევადია!`)) return;
  bookmarks[idx].comment = '';
  persistBookmarks();
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === bookmarks[idx].bookSlug && currentChapter === bookmarks[idx].chapter) renderChapter();
  const bubble = document.getElementById('comment-bubble');
  if (bubble) bubble.remove();
  showToast('💬 კომენტარი წაიშალა');
}

function copyVerse() {
  if (!currentVersePopup) return;
  const { bookSlug, chapter, verse } = currentVersePopup;
  const book = findBook(bookSlug)?.name || bookSlug;
  const text = `${book} ${chapter}:${verse.verse}\n${verse.new}\n${verse.old ? verse.old : ''}`;
  navigator.clipboard.writeText(text).then(() => showToast('📋 დაკოპირდა'));
}

function copyVerseWithSource() {
  if (!currentVersePopup) return;
  const { bookSlug, chapter, verse } = currentVersePopup;
  const book = findBook(bookSlug)?.name || bookSlug;
  const text = `"${verse.new}"\n\n- ${book} ${chapter}:${verse.verse}\n📜 წმიდა წერილი`;
  navigator.clipboard.writeText(text).then(() => showToast('📜 დაკოპირდა წყაროთი'));
}

function bookmarkVerse() {
  if (!currentVersePopup) return;
  const { bookSlug, chapter, verse } = currentVersePopup;
  const book = findBook(bookSlug)?.name || bookSlug;
  const ref = `${book} ${chapter}:${verse.verse}`;

  // შევამოწმოთ არის თუ არა უკვე ჩანიშნული (bookSlug + chapter + verseNum-ით)
  const idx = bookmarks.findIndex(b =>
    b.bookSlug === bookSlug &&
    Number(b.chapter) === Number(chapter) &&
    Number(b.verseNum) === Number(verse.verse)
  );
  if (idx >= 0 && bookmarks[idx].pinned) {
    // უკვე ჩანიშნულია (pinned=true) - დასტური მოხსნამდე
    const bm = bookmarks[idx];
    const hasOther = (bm.comment && bm.comment.trim()) || (bm.tags && bm.tags.length > 0);
    if (hasOther) {
      const parts = [`📌 სანიშნე: ${ref}`];
      if (bm.comment && bm.comment.trim()) parts.push(`💬 კომენტარი დარჩება`);
      if (bm.tags && bm.tags.length > 0) parts.push(`🏷️ თაგები დარჩება (${bm.tags.length})`);
      if (!confirm(`⚠️ დარწმუნებული ხარ?\n\n${parts.join('\n')}\n\nმხოლოდ 📌 სანიშნე მოიხსნება.\nთაგები და კომენტარი შენახული დარჩება.`)) return;
      // მხოლოდ pinned მოხსნა - თაგები/კომენტარი რჩება
      bookmarks[idx].pinned = false;
      persistBookmarks();
      showToast('📌 მოიხსნა სანიშნე');
    } else {
      // არაფერი აქვს - სრულად წაშლა
      if (!confirm(`⚠️ დარწმუნებული ხარ?\n\n📌 სანიშნე: ${ref}\n\nეს მოქმედება შეუქცევადია!`)) return;
      bookmarks.splice(idx, 1);
      persistBookmarks();
      showToast('📌 მოიხსნა სანიშნე');
    }
    renderHomeBookmarks();
    updateDashboardCounts();
    if (currentBook === bookSlug && currentChapter === chapter) renderChapter();
    closePopup();
    return;
  } else if (idx >= 0 && !bookmarks[idx].pinned) {
    // არსებობს კომენტარი/თაგით (pinned=false) - დავამატოთ pinned
    bookmarks[idx].pinned = true;
    persistBookmarks();
    showToast('📌 დაემატა სანიშნეებში');
    renderHomeBookmarks();
    updateDashboardCounts();
    if (currentBook === bookSlug && currentChapter === chapter) renderChapter();
    closePopup();
    return;
  }

  const commentInput = document.getElementById('popup-comment');
  const comment = commentInput ? commentInput.value.trim().substring(0, 99) : '';

  bookmarks.push({
    ref,
    bookSlug,
    chapter,
    verseNum: verse.verse,
    new: verse.new,
    old: verse.old,
    comment,
    tags: [],
    pinned: true,
    date: new Date().toISOString(),
  });
  persistBookmarks();
  if (commentInput) commentInput.value = '';
  showToast('📌 დაემატა სანიშნეებში');
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === bookSlug && currentChapter === chapter) renderChapter();
  closePopup();
}

// მხოლოდ კომენტარის შენახვა - სანიშნის გარეშე
function saveCommentOnly() {
  if (!currentVersePopup) return;
  const { bookSlug, chapter, verse } = currentVersePopup;
  const book = findBook(bookSlug)?.name || bookSlug;
  const ref = `${book} ${chapter}:${verse.verse}`;
  const commentInput = document.getElementById('popup-comment');
  const comment = commentInput ? commentInput.value.trim().substring(0, 99) : '';

  // ვეძებთ არსებულ ჩანაწერს
  const idx = bookmarks.findIndex(b =>
    b.bookSlug === bookSlug &&
    Number(b.chapter) === Number(chapter) &&
    Number(b.verseNum) === Number(verse.verse)
  );

  if (!comment) {
    // ცარიელი კომენტარი - წაშლა თუ არსებობს მხოლოდ კომენტარი (სანიშნის გარეშე)
    if (idx >= 0 && !bookmarks[idx].hasOwnProperty('pinned')) {
      // ვტოვებთ ჩანაწერს, უბრალოდ ვასუფთავებთ კომენტარს
      bookmarks[idx].comment = '';
    }
    showToast('💬 კომენტარი წაიშალა');
  } else if (idx >= 0) {
    // არსებობს - ვანახლებთ კომენტარს
    bookmarks[idx].comment = comment;
    showToast('💬 კომენტარი შეინახა');
  } else {
    // არ არსებობს - ვამატებთ მხოლოდ კომენტარით (სანიშნის გარეშე)
    bookmarks.push({
      ref,
      bookSlug,
      chapter,
      verseNum: verse.verse,
      new: verse.new,
      old: verse.old,
      comment,
      tags: [],
      pinned: false,
      date: new Date().toISOString(),
    });
    showToast('💬 კომენტარი შეინახა');
  }

  persistBookmarks();
  if (commentInput) commentInput.value = '';
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === bookSlug && currentChapter === chapter) renderChapter();
  // თაგების ველის განახლება
  if (typeof window.renderPopupTags === 'function') {
    window.renderPopupTags(bookSlug, chapter, verse.verse);
  }
}

// პირდაპირი ჩართვა/გამორთვა პოპაპის გარეშე (ჭიკარტის იკონოზე დაკლიკებით)
function toggleBookmarkDirect(bookSlug, chapter, verseNum) {
  const book = findBook(bookSlug)?.name || bookSlug;
  const ref = `${book} ${chapter}:${verseNum}`;
  const idx = bookmarks.findIndex(b =>
    b.bookSlug === bookSlug &&
    Number(b.chapter) === Number(chapter) &&
    Number(b.verseNum) === Number(verseNum)
  );
  if (idx >= 0 && bookmarks[idx].pinned) {
    // ჩანიშნულია - მხოლოდ pinned მოხსნა
    const bm = bookmarks[idx];
    const hasOther = (bm.comment && bm.comment.trim()) || (bm.tags && bm.tags.length > 0);
    if (hasOther) {
      if (!confirm(`⚠️ დარწმუნებული ხარ?\n\n📌 სანიშნე: ${ref}\n\nმხოლოდ 📌 მოიხსნება. თაგები და კომენტარი დარჩება.`)) return;
      bookmarks[idx].pinned = false;
    } else {
      if (!confirm(`⚠️ დარწმუნებული ხარ?\n\n📌 სანიშნე: ${ref}\n\nეს მოქმედება შეუქცევადია!`)) return;
      bookmarks.splice(idx, 1);
    }
    persistBookmarks();
    showToast('📌 მოიხსნა სანიშნე');
  } else if (idx >= 0) {
    // არსებობს თაგი/კომენტარი - დავამატოთ pinned
    bookmarks[idx].pinned = true;
    persistBookmarks();
    showToast('📌 დაემატა სანიშნეებში');
  } else {
    // ახალი bookmark
    const v = currentVerses?.find(x => x.verse === verseNum);
    bookmarks.push({
      ref,
      bookSlug,
      chapter,
      verseNum,
      new: v?.new || '',
      old: v?.old || '',
      comment: '',
      tags: [],
      pinned: true,
      date: new Date().toISOString(),
    });
    persistBookmarks();
    showToast('📌 დაემატა სანიშნეებში');
  }
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === bookSlug && currentChapter === chapter) renderChapter();
}

function shareVerse() {
  if (!currentVersePopup) return;
  const { bookSlug, chapter, verse } = currentVersePopup;
  const book = findBook(bookSlug)?.name || bookSlug;
  const text = `${book} ${chapter}:${verse.verse}\n${verse.new}`;
  // /b/ ბმული უზრუნველყოფს დინამიურ OG თეგებს მესენჯერებში
  const url = `${location.origin}/b/${bookSlug}/${chapter}/${verse.verse}`;

  if (navigator.share) {
    navigator.share({ title: `${book} ${chapter}:${verse.verse}`, text, url });
  } else {
    navigator.clipboard.writeText(`${text}\n\n${url}`).then(() => showToast('📋 დაკოპირდა ტექსტი + ბმული'));
  }
}

// === სანიშნეები ===
let currentPanelTab = 'bookmarks';

function toggleBookmarks() {
  const panel = document.getElementById('bookmarks-panel');
  if (panel.style.display === 'none') {
    renderAllPanels();
    panel.style.display = 'block';
    // localStorage გამაფრთხილებელი - მხოლოდ პირველ 3 ვიზიტზე ან თუ არ არის დახურული
    const warning = document.getElementById('bm-localstorage-warning');
    if (warning) {
      const dismissed = localStorage.getItem('ls_warning_dismissed');
      const visitCount = parseInt(localStorage.getItem('visit_count') || '0');
      if (dismissed === '1' && visitCount > 3) {
        warning.style.display = 'none';
      } else {
        warning.style.display = 'flex';
      }
    }
  } else {
    panel.style.display = 'none';
  }
}

function dismissLsWarning() {
  const warning = document.getElementById('bm-localstorage-warning');
  if (warning) warning.style.display = 'none';
  localStorage.setItem('ls_warning_dismissed', '1');
}

function switchPanelTab(tab) {
  currentPanelTab = tab;
  document.querySelectorAll('.panel-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tab);
  });
  document.querySelectorAll('.panel-tab-content').forEach(c => {
    c.classList.remove('active');
  });
  const contentMap = { bookmarks: 'bookmarks-list', highlights: 'highlights-list', comments: 'comments-list' };
  const actions = document.getElementById('bm-panel-actions');
  if (contentMap[tab]) {
    document.getElementById(contentMap[tab]).classList.add('active');
  }
  // ექსპორტ/იმპორტი მხოლოდ სანიშნეების ტაბში
  actions.style.display = tab === 'bookmarks' ? 'flex' : 'none';
}

function renderAllPanels() {
  renderBookmarks();
  renderHighlightsList();
  renderCommentsList();
  updateTabCounts();
}

function updateTabCounts() {
  document.getElementById('tab-count-bm').textContent = bookmarks.filter(b => b.pinned).length;
  const hl = getHighlights();
  document.getElementById('tab-count-hl').textContent = Object.keys(hl).length;
  document.getElementById('tab-count-cm').textContent = bookmarks.filter(b => b.comment && b.comment.trim()).length;
}

function renderBookmarksPanel() {
  renderAllPanels();
}

function renderBookmarks() {
  const list = document.getElementById('bookmarks-list');
  // თაგების ფილტრის ზოლი - tags.js-დან
  let filterHtml = '';
  if (typeof window.getTagFilterHtml === 'function') {
    filterHtml = window.getTagFilterHtml();
  }

  const pinnedBookmarks = bookmarks.filter(b => b.pinned);
  if (pinnedBookmarks.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📌</div>
        <h3>ჯერ სანიშნე არ გაქვს</h3>
        <p>მუხლის დასამატებლად გახსენი ნებისმიერი თავი და დააჭირე 📌 ხატულას მუხლის გვერდით.</p>
        <button class="empty-state-btn" onclick="quickStartReading()">წაიკითხე ბიბლია</button>
      </div>`;
    return;
  }

  // ფილტრი - მხოლოდ pinned
  let filtered = bookmarks.map((b, i) => ({ b, i })).filter(({ b }) => b.pinned);
  const tf = (typeof window.getCurrentTagFilter === 'function') ? window.getCurrentTagFilter() : null;
  if (tf) {
    filtered = filtered.filter(({ b }) => (b.tags || []).includes(tf));
  }

  if (filtered.length === 0) {
    list.innerHTML = filterHtml + `<p style="color:var(--text-muted);text-align:center;padding:20px;">თაგი "${escapeHtml(tf)}" არ არის</p>`;
    return;
  }

  list.innerHTML = filterHtml;
  filtered.forEach(({ b, i }) => {
    const div = document.createElement('div');
    div.className = 'bookmark-item';
    div.dataset.idx = i;
    const commentHtml = b.comment
      ? `<div class="bookmark-comment">💬 ${escapeHtml(b.comment)}</div>`
      : '';
    const tagsHtml = (typeof window.getBookmarkTagsHtml === 'function')
      ? window.getBookmarkTagsHtml(i)
      : ((b.tags && b.tags.length > 0)
        ? `<div class="bm-item-tags">${b.tags.map(t => `<span class="bm-item-tag">#${escapeHtml(t)}</span>`).join('')}</div>`
        : '');
    div.innerHTML = `
      <div class="bookmark-top">
        <div class="bookmark-ref">${escapeHtml(b.ref)}</div>
        <button class="bookmark-del" onclick="removeBookmark(${i})" title="წაშლა">🗑</button>
      </div>
      <div class="bookmark-text">${escapeHtml((b.new || '').substring(0, 100))}${(b.new || '').length > 100 ? '…' : ''}</div>
      ${commentHtml}
      ${tagsHtml}
      <button class="bookmark-edit-btn" onclick="editBookmarkComment(${i})">✏️ კომენტარი</button>
    `;
    div.onclick = (e) => {
      if (e.target.tagName !== 'BUTTON' && !e.target.classList.contains('bm-item-tag')) {
        openChapter(b.bookSlug, b.chapter, { scrollToVerse: b.verseNum });
        toggleBookmarks();
      }
    };
    list.appendChild(div);
  });
}

// === ფერად მონიშნული მუხლების სია ===
function renderHighlightsList() {
  const list = document.getElementById('highlights-list');
  if (!list) return;
  const hl = getHighlights();
  const keys = Object.keys(hl);
  if (keys.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🎨</div>
        <h3>ფერად მონიშნული მუხლი არ არის</h3>
        <p>მუხლის ფერად მოსანიშნად გახსენი ნებისმიერი თავი, დააჭირე მუხლს და აირჩიე ფერი.</p>
        <button class="empty-state-btn" onclick="quickStartReading()">წაიკითხე ბიბლია</button>
      </div>`;
    return;
  }
  // ფერის მიხედვით დაჯგუფება (მომხმარებლის მიერ დასახელებული)
  const colorLabels = {};
  ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].forEach(c => colorLabels[c] = getColorLabel(c));
  // სორტირება ფერის მიხედვით
  const colorOrder = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
  keys.sort((a, b) => {
    const ca = colorOrder.indexOf(hl[a]);
    const cb = colorOrder.indexOf(hl[b]);
    if (ca !== cb) return ca - cb;
    return a.localeCompare(b);
  });
  let html = '';
  let lastColor = null;
  for (const key of keys) {
    const color = hl[key];
    const [bookSlug, chapter, verseNum] = key.split(':');
    const book = findBook(bookSlug);
    const bookName = book?.name || bookSlug;
    if (color !== lastColor) {
      html += `<div style="font-size:12px;color:var(--text-muted);margin:12px 0 6px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">${escapeHtml(colorLabels[color] || color)}</div>`;
      lastColor = color;
    }
    // მუხლის ტექსტის მოძებნა - bookmarks-დან ანი პირდაპირ
    const bm = bookmarks.find(b => b.bookSlug === bookSlug && Number(b.chapter) === Number(chapter) && Number(b.verseNum) === Number(verseNum));
    const text = bm?.new || '';
    html += `<div class="highlight-item hl-${color}" onclick="openChapter('${bookSlug}', ${chapter}, { scrollToVerse: ${verseNum} })">
      <div class="highlight-item-ref">
        <span>${escapeHtml(bookName)} ${chapter}:${verseNum}</span>
        <button class="highlight-del" onclick="event.stopPropagation(); removeHighlightByKey('${escapeAttr(key)}')">🗑</button>
      </div>
      ${text ? `<div class="highlight-item-text">${escapeHtml(text.substring(0, 120))}${text.length > 120 ? '…' : ''}</div>` : ''}
    </div>`;
  }
  list.innerHTML = html;
}

function removeHighlightByKey(key) {
  const hl = getHighlights();
  const [bookSlug, chapter, verseNum] = key.split(':');
  const book = findBook(bookSlug)?.name || bookSlug;
  const ref = `${book} ${chapter}:${verseNum}`;
  const color = hl[key];
  const colorLabel = getColorLabel(color);
  if (!confirm(`⚠️ დარწმუნებული ხარ?\n\n"${ref}" - მარკირება "${colorLabel}" ფერში წაიშლება.\n\nეს მოქმედება შეუქცევადია!`)) return;
  delete hl[key];
  saveHighlights(hl);
  renderHighlightsList();
  updateTabCounts();
  applyHighlightsToChapter();
  showToast('🎨 მარკირება მოიხსნა');
}

// === დაკომენტარებული მუხლების სია ===
function renderCommentsList() {
  const list = document.getElementById('comments-list');
  if (!list) return;
  const commented = bookmarks.filter(b => b.comment && b.comment.trim());
  if (commented.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">💬</div>
        <h3>დაკომენტარებული მუხლი არ არის</h3>
        <p>მუხლზე კომენტარის დასამატებლად გახსენი ნებისმიერი თავი, დააჭირე 📌-ს და აირჩიე „კომენტარი“.</p>
        <button class="empty-state-btn" onclick="quickStartReading()">წაიკითხე ბიბლია</button>
      </div>`;
    return;
  }
  // უახლესი პირველი
  commented.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  let html = '';
  commented.forEach(b => {
    const idx = bookmarks.indexOf(b);
    html += `<div class="comment-item" onclick="openChapter('${b.bookSlug}', ${b.chapter}, { scrollToVerse: ${b.verseNum} }); toggleBookmarks();">
      <div class="comment-item-ref">${escapeHtml(b.ref)}</div>
      <div class="comment-item-text">${escapeHtml((b.new || '').substring(0, 80))}${(b.new || '').length > 80 ? '…' : ''}</div>
      <div class="comment-item-comment">💬 ${escapeHtml(b.comment)}</div>
      <button class="bookmark-edit-btn" onclick="event.stopPropagation(); editBookmarkComment(${idx})">✏️ რედაქტირება</button>
    </div>`;
  });
  list.innerHTML = html;
}

function editBookmarkComment(i) {
  const bm = bookmarks[i];
  if (!bm) return;
  const item = document.querySelector(`.bookmark-item[data-idx="${i}"]`);
  if (!item) return;
  const commentEl = item.querySelector('.bookmark-comment');
  const editBtn = item.querySelector('.bookmark-edit-btn');
  if (!commentEl || !editBtn) return;

  const current = bm.comment || '';
  const textarea = document.createElement('textarea');
  textarea.className = 'inline-comment-edit';
  textarea.maxLength = 99;
  textarea.rows = 2;
  textarea.value = current;
  textarea.placeholder = 'კომენტარი...';
  commentEl.replaceWith(textarea);
  textarea.focus();

  editBtn.outerHTML = `
    <button class="bookmark-edit-btn" onclick="saveInlineComment(${i})">✒️ შენახვა</button>
    <button class="bookmark-edit-btn" onclick="renderBookmarks()">✕ გაუქმება</button>
  `;
}

function saveInlineComment(i) {
  const bm = bookmarks[i];
  if (!bm) return;
  const item = document.querySelector(`.bookmark-item[data-idx="${i}"]`);
  if (!item) return;
  const textarea = item.querySelector('.inline-comment-edit');
  if (!textarea) return;
  const trimmed = textarea.value.trim().substring(0, 99);
  bm.comment = trimmed;
  persistBookmarks();
  renderBookmarks();
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === bm.bookSlug && currentChapter === bm.chapter) renderChapter();
  showToast(trimmed ? '💬 კომენტარი შეინახა' : '💬 კომენტარი წაიშალა');
}

function removeBookmark(i) {
  const removed = bookmarks[i];
  if (!removed) return;
  // მხოლოდ pinned-ის მოხსნა - თაგები/კომენტარი რჩება
  const hasOther = (removed.comment && removed.comment.trim()) || (removed.tags && removed.tags.length > 0);
  if (hasOther) {
    const parts = [`📌 სანიშნე: ${removed.ref}`];
    if (removed.comment && removed.comment.trim()) parts.push(`💬 კომენტარი დარჩება`);
    if (removed.tags && removed.tags.length > 0) parts.push(`🏷️ თაგები დარჩება (${removed.tags.length})`);
    if (!confirm(`⚠️ დარწმუნებული ხარ?\n\n${parts.join('\n')}\n\nმხოლოდ 📌 მოიხსნება.`)) return;
    bookmarks[i].pinned = false;
  } else {
    if (!confirm(`⚠️ დარწმუნებული ხარ?\n\n📌 სანიშნე: ${removed.ref}\n\nეს მოქმედება შეუქცევადია!`)) return;
    bookmarks.splice(i, 1);
  }
  persistBookmarks();
  renderBookmarks();
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === removed.bookSlug && currentChapter === removed.chapter) {
    renderChapter();
  }
  showToast('წაიშალა');
}


// === მთავარი გვერდის სანიშნეები ===
function renderHomeBookmarks() {
  const container = document.getElementById('home-bookmarks');
  if (!container) return;
  // თუ პანელი ღიაა - განვაახლოთ ტაბებიც
  const panel = document.getElementById('bookmarks-panel');
  if (panel && panel.style.display === 'block') {
    renderAllPanels();
  }
  // დაშბორდის ციფრების განახლება
  updateDashboardCounts();

  if (bookmarks.filter(b => b.pinned).length === 0) {
    container.innerHTML = `
      <div class="home-bookmarks-empty">
        <p>📌 ჯერ სანიშნეები არ გაქვთ</p>
        <p class="hint">დააკლიკე მუხლს და დაამატე 📌 სანიშნე - შეგიძლია კომენტარიც დაურთო</p>
        <div class="home-backup-row">
          <button class="home-backup-btn" onclick="exportUserData()" title="სრული ბექაფი - სანიშნეები, მარკირება, კომენტარები, ჩანაწერები">💾 ბექაფის ჩამოწერა</button>
          <button class="home-backup-btn" onclick="document.getElementById('import-bookmarks-input').click()" title="ფაილიდან მონაცემების აღდგენა">📂 ბექაფის ატვირთვა</button>
        </div>
      </div>`;
    return;
  }

  // დავაჯგუფოთ წიგნი+თავის მიხედვით
  const groups = {};
  bookmarks.forEach(b => {
    const key = `${b.bookSlug}:${b.chapter}`;
    if (!groups[key]) groups[key] = { bookSlug: b.bookSlug, chapter: b.chapter, items: [] };
    groups[key].items.push(b);
  });

  const groupArr = Object.values(groups).sort((a, b) => {
    const an = a.items[0].date || '';
    const bn = b.items[0].date || '';
    return bn.localeCompare(an);
  });

  let html = '<h3 class="home-bm-title">📌 ჩემი სანიშნეები</h3>';
  html += '<div class="home-bm-grid">';
  groupArr.forEach(g => {
    const bookName = findBook(g.bookSlug)?.name || g.bookSlug;
    const verses = g.items.map(it => it.verseNum).sort((a, b) => a - b);
    const verseStr = verses.length === 1
      ? `${bookName} ${g.chapter}:${verses[0]}`
      : `${bookName} ${g.chapter}:${verses[0]}–${verses[verses.length - 1]} (${verses.length})`;
    html += `
      <button class="home-bm-card" onclick="openChapter('${g.bookSlug}', ${g.chapter}, { scrollToVerse: ${verses[0]} })">
        <div class="home-bm-ref">${verseStr}</div>
        <div class="home-bm-count">${g.items.length} მუხლი</div>
      </button>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

// === თემა ===
function toggleTheme() {
  const current = document.body.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.body.setAttribute('data-theme', next);
  localStorage.setItem('bible_theme', next);
  updateThemeIcon();
}

function updateThemeIcon() {
  const theme = document.body.getAttribute('data-theme');
  const btn = document.querySelector('[onclick="toggleTheme()"]');
  if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

// === შრიფტის ზომა ===
function toggleFont() {
  const current = parseInt(localStorage.getItem('bible_font_size') || '18');
  const sizes = [15, 16, 17, 18, 19, 20, 22, 24];
  const idx = sizes.indexOf(current);
  const next = sizes[(idx + 1) % sizes.length];
  document.documentElement.style.setProperty('--font-size', next + 'px');
  localStorage.setItem('bible_font_size', next);
  showToast(`შრიფტი: ${next}px`);
  syncFormattingButtons();
}

// line-height ცვლა (კითხვის კომფორტისთვის)
function toggleLineHeight() {
  const heights = [1.5, 1.65, 1.75, 1.85, 2.0, 2.2];
  const current = parseFloat(localStorage.getItem('bible_line_height') || '1.85');
  const idx = heights.indexOf(current);
  const next = heights[(idx + 1) % heights.length];
  document.documentElement.style.setProperty('--verse-line-height', next);
  localStorage.setItem('bible_line_height', next);
  showToast(`სტრიქონებს შორის: ${next}`);
  syncFormattingButtons();
}

// შრიფტის ტიპის ცვლა (სერიფი / სანს-სერიფი)
function toggleFontFamily() {
  const families = ['serif', 'sans'];
  const current = localStorage.getItem('bible_font_family') || 'serif';
  const idx = families.indexOf(current);
  const next = families[(idx + 1) % families.length];
  const root = document.documentElement;
  if (next === 'sans') {
    root.style.setProperty('--font-serif', 'var(--font-sans)');
  } else {
    root.style.setProperty('--font-serif', "'Noto Serif Georgian', 'Sylfaen', 'Georgia', 'Times New Roman', serif");
  }
  localStorage.setItem('bible_font_family', next);
  showToast(next === 'sans' ? 'შრიფტი: თანამედროვე' : 'შრიფტი: კლასიკური');
  syncFormattingButtons();
}

// ფორმატირების ღილაკების ვიზუალური სტატუსის სინქრონიზაცია
// აჩვენებს მიმდინარე მნიშვნელობას მობილურ მენიუში არსებულ ღილაკებზე
function syncFormattingButtons() {
  const fontSize = localStorage.getItem('bible_font_size') || '18';
  const lineHeight = localStorage.getItem('bible_line_height') || '1.85';
  const fontFamily = localStorage.getItem('bible_font_family') || 'serif';

  // მობილურ მენიუში ღილაკების მეორე <span>-ის განახლება
  const fontBtn = document.querySelector('[onclick*="toggleFont"]');
  if (fontBtn) {
    const span = fontBtn.querySelectorAll('span')[1];
    if (span) span.textContent = `შრიფტის ზომა (${fontSize}px)`;
  }
  const lhBtn = document.querySelector('[onclick*="toggleLineHeight"]');
  if (lhBtn) {
    const span = lhBtn.querySelectorAll('span')[1];
    if (span) span.textContent = `სტრიქონებს შორის (${lineHeight})`;
  }
  const ffBtn = document.querySelector('[onclick*="toggleFontFamily"]');
  if (ffBtn) {
    const span = ffBtn.querySelectorAll('span')[1];
    if (span) span.textContent = fontFamily === 'sans' ? 'შრიფტის ტიპი (თანამედროვე)' : 'შრიფტის ტიპი (კლასიკური)';
  }
}

function closeMobileMenu() {
  const menu = document.getElementById('mobile-menu');
  if (menu) menu.classList.remove('show');
}

// Esc კლავიში - უნივერსალური დახურვა (პრიორიტეტის მიხედვით)
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  // 1. list-overlay (ზედა პრიორიტეტი)
  const ov = document.getElementById('list-overlay');
  if (ov && ov.style.display === 'flex') { closeListOverlay(); return; }
  // 2. verse-popup
  const popup = document.getElementById('verse-popup');
  if (popup && popup.style.display === 'flex') { closePopup(); return; }
  // 3. about-modal
  const about = document.getElementById('about-modal');
  if (about && about.style.display === 'flex') { closeAbout(); return; }
  // 4. beginner-modal
  const beginner = document.getElementById('beginner-modal');
  if (beginner && beginner.style.display === 'block') { closeBeginner(); return; }
  // 5. word-study panel
  const wordPanel = document.getElementById('word-panel');
  if (wordPanel && wordPanel.style.display === 'flex') { if (typeof closeWordPanel === 'function') closeWordPanel(); return; }
  // 6. topical panel
  const topical = document.getElementById('topical-panel');
  if (topical && topical.style.display === 'flex') { if (typeof closeTopicalPanel === 'function') closeTopicalPanel(); return; }
  // 7. study-pad
  const studyPad = document.getElementById('study-pad-panel');
  if (studyPad && studyPad.style.display === 'flex') { if (typeof closeStudyPad === 'function') closeStudyPad(); return; }
  // 8. bookmarks panel
  const bmPanel = document.getElementById('bookmarks-panel');
  if (bmPanel && bmPanel.classList.contains('open')) { bmPanel.classList.remove('open'); return; }
});

// === Book Ribbon (ბოლო წაკითხულ ადგილას დაბრუნება) ===
let scrollSaveTimer = null;

function saveReadingPosition() {
  if (!currentBook || !currentChapter) return;
  if (document.getElementById('chapter-view').style.display === 'none') return;
  const pos = {
    book: currentBook,
    chapter: currentChapter,
    scroll: document.getElementById('verses-container')?.scrollTop || window.scrollY,
    timestamp: Date.now(),
  };
  safeLocalStorageSet('last_reading_pos', JSON.stringify(pos));

  // ბოლო 5 ადგილის ისტორია
  let history = JSON.parse(localStorage.getItem('reading_history') || '[]');
  history = history.filter(h => !(h.book === pos.book && h.chapter === pos.chapter));
  history.unshift(pos);
  history = history.slice(0, 5);
  safeLocalStorageSet('reading_history', JSON.stringify(history));
}

function restoreReadingPosition() {
  const pos = localStorage.getItem('last_reading_pos');
  if (!pos) return null;
  try {
    return JSON.parse(pos);
  } catch { return null; }
}

// scroll-ის თვალყურის დევნება
function setupScrollTracking() {
  const target = document.getElementById('verses-container') || window;
  target.addEventListener('scroll', () => {
    clearTimeout(scrollSaveTimer);
    scrollSaveTimer = setTimeout(saveReadingPosition, 800);
  });
}

// Book ribbon-ის ჩვენება მთავარ გვერდზე
function renderBookRibbon() {
  const pos = restoreReadingPosition();
  const ribbon = document.getElementById('book-ribbon');
  if (!ribbon || !pos) return;
  // pos.book არის სტრინგი (slug), არა ობიექტი
  const book = findBook(pos.book);
  const bookName = book?.name || pos.book || '';
  if (!bookName) return;
  const timeAgo = formatTimeAgo(pos.timestamp);
  ribbon.innerHTML = `
    <span class="book-ribbon-icon">📌</span>
    <span class="book-ribbon-text">განაგრძე კითხვა: <strong>${escapeHtml(bookName)} ${pos.chapter}</strong></span>
    <span class="book-ribbon-time">${timeAgo}</span>
  `;
  ribbon.classList.add('visible');
  ribbon.onclick = () => {
    openChapter(pos.book, pos.chapter);
  };
}

function formatTimeAgo(ts) {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (days > 0) return `${days} დღის წინ`;
  if (hours > 0) return `${hours} სთ წინ`;
  if (mins > 0) return `${mins} წთ წინ`;
  return 'ახლახან';
}

// მუხლზე კლიკის დამუშავება - მხოლოდ popup (პანელი არ იხსნება)
function handleVerseClick(e, verse) {
  // თუ bookmark icon-ზე დააკლიკა - არ ვუშვებთ აქ
  if (e.target.classList.contains('verse-bm-icon')) return;
  // თუ სიტყვაზე (.word) დააკლიკა - სიტყვის პანელი იხსნება (word-study.js)
  if (e.target.closest('.word')) return;
  // მუხლის popup - ანოტაციის ხელსაწყოები (მარკერი, კომენტარი, სანიშნე, კოპირება...)
  showVersePopup(currentBook, currentChapter, verse);
}

// === დამხმარე ===
let currentViewId = 'home-view';
let savedScrollPositions = {};

function showView(viewId, opts = {}) {
  // კომენტარის ბუშტი - დაუსრულებელი რედაქტირების შემოწმება
  const bubble = document.getElementById('comment-bubble');
  if (bubble) {
    const textarea = bubble.querySelector('.comment-bubble-edit-area');
    if (textarea) {
      // რედაქტირებაა - ვკითხოთ
      const verseNum = textarea.closest('#comment-bubble')?.dataset?.verseNum;
      if (!confirm('💬 კომენტარი არ არის შენახული. გსურს გაგრძელება?\n\nOK - გააგრძელე და დაკარგე ცვლილებები\nCancel - დარჩი და შეინახე')) {
        return; // არ გადავდივართ
      }
    }
    bubble.remove();
  }
  // მუხლის popup-ის დახურვა ნავიგაციისას (თუ გახსნილია)
  const popup = document.getElementById('verse-popup');
  if (popup && popup.style.display === 'flex') {
    popup.style.display = 'none';
    currentVersePopup = null;
    const dd = document.getElementById('tag-dropdown');
    if (dd) dd.remove();
  }
  // აუდიოს შეჩერება თუ chapter-view-იდან სხვაგან გადავდივართ
  if (currentViewId === 'chapter-view' && viewId !== 'chapter-view') {
    if (typeof stopAudio === 'function') stopAudio();
  }
  // მიმდინარე view-ის scroll პოზიციის შენახვა
  if (currentViewId && currentViewId !== viewId) {
    const oldEl = document.getElementById(currentViewId);
    if (oldEl) {
      savedScrollPositions[currentViewId] = window.scrollY;
    }
  }
  ['home-view', 'chapter-view', 'search-view', 'lexicon-view'].forEach(id => {
    document.getElementById(id).style.display = id === viewId ? 'block' : 'none';
  });
  currentViewId = viewId;
  // პოზიციის აღდგენა თუ მოთხოვნილია
  if (opts.restoreScroll && savedScrollPositions[viewId] !== undefined) {
    setTimeout(() => window.scrollTo(0, savedScrollPositions[viewId]), 50);
  } else if (!opts.skipScrollReset) {
    window.scrollTo(0, 0);
  }
}

function goHome() {
  showView('home-view');
  history.pushState({ view: 'home' }, '', location.pathname);
  renderHomeBookmarks();
  renderBookRibbon();
  // აუდიო პლეიერის დამალვა
  if (typeof stopAudio === 'function') stopAudio();
  currentAudioBook = null;
  currentAudioChapter = null;
  if (typeof updateAudioPlayerUI === 'function') updateAudioPlayerUI();
}

// დამწყებთათვის გზამკვლევი
function openBeginner() {
  const modal = document.getElementById('beginner-modal');
  if (modal) {
    modal.style.display = 'block';
    moveFocusInto(modal);
    enableFocusTrap(modal);
  }
}
function closeBeginner() {
  const modal = document.getElementById('beginner-modal');
  if (modal) modal.style.display = 'none';
  disableFocusTrap();
}

// სწრაფი დაწყება - ახალი აღთქმის სახარებიდან (იოანე)
function quickStartReading() {
  // თუ მომხმარებელს აქვს ბოლო წაკითხული ადგილი, იქ დავაბრუნოთ
  const lastPos = localStorage.getItem('last_reading_pos');
  if (lastPos) {
    try {
      const pos = JSON.parse(lastPos);
      if (pos.bookSlug && pos.chapter) {
        // გადავამოწმოთ წიგნის არსებობა (slug შეიძლება იყოს მოძველებული/წაშლილი)
        const book = (typeof findBook === 'function') ? findBook(pos.bookSlug) : null;
        if (book) {
          openChapter(pos.bookSlug, parseInt(pos.chapter));
          return;
        }
        // თუ წიგნი ვერ მოიძებნა - გადავიდეთ fallback-ზე
        console.warn('quickStartReading: წიგნი ვერ მოიძებნა:', pos.bookSlug);
      }
    } catch (e) {
      console.warn('quickStartReading: lastPos parse შეცდომა:', e);
    }
  }
  // Fallback - იოანეს სახარებიდან დავიწყოთ
  try {
    openChapter('ioane', 1);
  } catch (e) {
    console.error('quickStartReading: ioane fallback ვერ მოხერხდა:', e);
    showToast('კითხვის დაწყება ვერ მოხერხდა. სცადეთ წიგნების სიიდან არჩევა.');
  }
}

function showToast(msg, actionLabel, actionFn) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  // undo ღილაკის დამატება
  const oldBtn = toast.querySelector('.toast-action');
  if (oldBtn) oldBtn.remove();
  if (actionLabel && actionFn) {
    const btn = document.createElement('button');
    btn.className = 'toast-action';
    btn.textContent = actionLabel;
    btn.onclick = () => { actionFn(); toast.classList.remove('show'); };
    toast.appendChild(btn);
  }
  toast.classList.add('show');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), 4000);
}
/* === ლექსიკონი === */


// === მთავარი დაშბორდის ფუნქციები ===

// ფერის სახელის შენახვა/აღდგენა
function saveColorLabel(color, value) {
  const labels = JSON.parse(localStorage.getItem('bible_color_labels') || '{}');
  labels[color] = value;
  safeLocalStorageSet('bible_color_labels', JSON.stringify(labels));
}

function restoreColorLabels() {
  const labels = JSON.parse(localStorage.getItem('bible_color_labels') || '{}');
  ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].forEach(c => {
    const el = document.getElementById('dash-label-' + c);
    if (el && labels[c]) el.value = labels[c];
  });
}

function getColorLabel(color) {
  const labels = JSON.parse(localStorage.getItem('bible_color_labels') || '{}');
  return labels[color] || color;
}

function updateDashboardCounts() {
  const hl = getHighlights();
  const counts = { jan:0, feb:0, mar:0, apr:0, may:0, jun:0, jul:0, aug:0, sep:0, oct:0, nov:0, dec:0 };
  for (const k in hl) {
    if (counts[hl[k]] !== undefined) counts[hl[k]]++;
  }
  for (const c in counts) {
    const el = document.getElementById('dash-count-' + c);
    if (el) el.textContent = counts[c];
  }
  const cmCount = bookmarks.filter(b => b.comment && b.comment.trim()).length;
  const cmEl = document.getElementById('dash-count-comments');
  if (cmEl) cmEl.textContent = cmCount;
  const bmEl = document.getElementById('dash-count-bookmarks');
  if (bmEl) bmEl.textContent = bookmarks.filter(b => b.pinned).length;
  renderDashboardTags();
}


function closeListOverlay() {
  const ov = document.getElementById('list-overlay');
  if (ov) ov.remove();
}

function showListOverlay(titleHtml, itemsHtml) {
  closeListOverlay();
  // კომენტარის ბუშტის დახურვა
  const bubble = document.getElementById('comment-bubble');
  if (bubble) {
    const textarea = bubble.querySelector('.comment-bubble-edit-area');
    if (textarea) {
      if (!confirm('💬 კომენტარი არ არის შენახული. გსურს გაგრძელება?\n\nOK - გააგრძელე და დაკარგე ცვლილებები\nCancel - დარჩი და შეინახე')) {
        return;
      }
    }
    bubble.remove();
  }
  const ov = document.createElement('div');
  ov.id = 'list-overlay';
  ov.className = 'list-overlay';
  ov.onclick = (e) => { if (e.target === ov) closeListOverlay(); };
  ov.innerHTML = `<div class="list-overlay-content">
    <button class="close-btn" onclick="closeListOverlay()">✕</button>
    <div class="list-overlay-title">${titleHtml}</div>
    <div>${itemsHtml}</div>
  </div>`;
  document.body.appendChild(ov);
}

function openColorList(color) {
  const hl = getHighlights();
  const colorHex = { jan:'#b0c4de', feb:'#4a6fa5', mar:'#78c850', apr:'#ff9ec7', may:'#5dd55d', jun:'#ffdf57', jul:'#ff9933', aug:'#f06464', sep:'#daa520', oct:'#d2691e', nov:'#9370db', dec:'#6a8caf' };
  const colorLabel = getColorLabel(color);
  const keys = Object.keys(hl).filter(k => hl[k] === color);
  if (keys.length === 0) {
    showListOverlay(`<span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:${colorHex[color]};vertical-align:middle;"></span> ${colorLabel}`, '<div class="list-overlay-empty">ამ ფერად მონიშნული მუხლი არ არის</div>');
    return;
  }
  keys.sort();
  let html = '';
  for (const key of keys) {
    const [bookSlug, chapter, verseNum] = key.split(':');
    const book = findBook(bookSlug);
    const bookName = book?.name || bookSlug;
    const bm = bookmarks.find(b => b.bookSlug === bookSlug && Number(b.chapter) === Number(chapter) && Number(b.verseNum) === Number(verseNum));
    const text = bm?.new || '';
    html += `<div class="list-item" style="border-left-color:${colorHex[color]};" onclick="closeListOverlay(); openChapter('${bookSlug}', ${chapter}, { scrollToVerse: ${verseNum} })">
      <div class="list-item-ref">${escapeHtml(bookName)} ${chapter}:${verseNum}</div>
      ${text ? `<div class="list-item-text">${escapeHtml(text.substring(0, 150))}${text.length > 150 ? '…' : ''}</div>` : ''}
    </div>`;
  }
  showListOverlay(`<span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:${colorHex[color]};vertical-align:middle;margin-right:6px;"></span>${colorLabel} <span style="color:var(--text-muted);font-size:14px;">(${keys.length})</span>`, html);
}

function openCommentsList() {
  currentListType = 'comments';
  const commented = bookmarks.filter(b => b.comment && b.comment.trim());
  if (commented.length === 0) {
    showListOverlay('💬 კომენტარები', '<div class="list-overlay-empty">დაკომენტარებული მუხლი არ არის</div>');
    return;
  }
  commented.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  let html = '';
  commented.forEach(b => {
    const idx = bookmarks.indexOf(b);
    const tagsHtml = (b.tags && b.tags.length) ? `<div class="list-item-tags">${b.tags.map(t => `<span class="list-item-tag" data-idx="${idx}" data-tag="${escapeHtml(t)}">#${escapeHtml(t)} ×</span>`).join('')}</div>` : '';
    html += `<div class="list-item list-item-editable" style="border-left-color:var(--primary-light);" data-idx="${idx}" data-type="comment">
      <div class="list-item-ref">${escapeHtml(b.ref)}</div>
      <div class="list-item-text">${escapeHtml((b.new || '').substring(0, 100))}${(b.new || '').length > 100 ? '…' : ''}</div>
      <div class="list-item-comment" id="list-comment-${idx}">💬 ${escapeHtml(b.comment)}</div>
      ${tagsHtml}
      <div class="list-item-actions">
        <button onclick="event.stopPropagation(); openChapter('${b.bookSlug}', ${b.chapter}, { scrollToVerse: ${b.verseNum} })">➡️ გახსნა</button>
        <button onclick="event.stopPropagation(); editListComment(${idx})">✏️ რედაქტირება</button>
        <button class="list-item-del" onclick="event.stopPropagation(); deleteListComment(${idx})">🗑 წაშლა</button>
      </div>
    </div>`;
  });
  showListOverlay(`💬 კომენტარები <span style="color:var(--text-muted);font-size:14px;">(${commented.length})</span>`, html);
}

// სიაში კომენტარის რედაქტირება (inline)
function editListComment(idx) {
  const bm = bookmarks[idx];
  if (!bm) return;
  const commentEl = document.getElementById('list-comment-' + idx);
  if (!commentEl) return;
  const textarea = document.createElement('textarea');
  textarea.className = 'inline-comment-edit';
  textarea.maxLength = 99;
  textarea.rows = 2;
  textarea.value = bm.comment || '';
  textarea.placeholder = 'კომენტარი...';
  textarea.id = 'list-comment-edit-' + idx;
  commentEl.replaceWith(textarea);
  textarea.focus();
  // ღილაკების განახლება
  const item = document.querySelector(`.list-item[data-idx="${idx}"]`);
  if (item) {
    const actions = item.querySelector('.list-item-actions');
    if (actions) {
      actions.innerHTML = `
        <button onclick="event.stopPropagation(); openChapter('${bm.bookSlug}', ${bm.chapter}, { scrollToVerse: ${bm.verseNum} })">➡️ გახსნა</button>
        <button onclick="event.stopPropagation(); saveListComment(${idx})">✒️ შენახვა</button>
        <button onclick="event.stopPropagation(); cancelListCommentEdit(${idx})">✕ გაუქმება</button>
      `;
    }
  }
}

function saveListComment(idx) {
  const bm = bookmarks[idx];
  if (!bm) return;
  const textarea = document.getElementById('list-comment-edit-' + idx);
  if (!textarea) return;
  const trimmed = textarea.value.trim().substring(0, 99);
  bm.comment = trimmed;
  persistBookmarks();
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === bm.bookSlug && currentChapter === bm.chapter) renderChapter();
  showToast(trimmed ? '💬 კომენტარი შეინახა' : '💬 კომენტარი წაიშალა');
  // დაბრუნდეს იმ სიაზე, საიდან იყო გამოძახებული
  if (currentListType === 'bookmarks') openBookmarksList();
  else openCommentsList();
}

// კომენტარის რედაქტირების გაუქმება - დაბრუნდეს იმ სიაზე, საიდან იყო გამოძახებული
function cancelListCommentEdit(idx) {
  if (currentListType === 'bookmarks') openBookmarksList();
  else openCommentsList();
}

function deleteListComment(idx) {
  const bm = bookmarks[idx];
  if (!bm) return;
  if (!confirm(`⚠️ დარწმუნებული ხარ?\n\n💬 კომენტარი წაიშლება მუხლიდან "${bm.ref}".\n\nეს მოქმედება შეუქცევადია!`)) return;
  bm.comment = '';
  persistBookmarks();
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === bm.bookSlug && currentChapter === bm.chapter) renderChapter();
  showToast('💬 კომენტარი წაიშალა');
  // დაბრუნდეს იმ სიაზე, საიდან იყო გამოძახებული
  if (currentListType === 'bookmarks') openBookmarksList();
  else openCommentsList();
}

// სიაში თაგის წაშლა

function openBookmarksList() {
  currentListType = 'bookmarks';
  const pinned = bookmarks.filter(b => b.pinned);
  if (pinned.length === 0) {
    showListOverlay('📌 სანიშნეები', '<div class="list-overlay-empty">სანიშნე არ არის</div>');
    return;
  }
  const sorted = [...pinned].sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  let html = '';
  sorted.forEach(b => {
    const idx = bookmarks.indexOf(b);
    const commentHtml = (b.comment && b.comment.trim()) ? `<div class="list-item-comment" id="list-comment-${idx}">💬 ${escapeHtml(b.comment)}</div>` : '';
    const tagsHtml = (b.tags && b.tags.length) ? `<div class="list-item-tags">${b.tags.map(t => `<span class="list-item-tag" data-idx="${idx}" data-tag="${escapeHtml(t)}">#${escapeHtml(t)} ×</span>`).join('')}</div>` : '';
    html += `<div class="list-item list-item-editable" data-idx="${idx}" data-type="bookmark">
      <div class="list-item-ref">${escapeHtml(b.ref)}</div>
      <div class="list-item-text">${escapeHtml((b.new || '').substring(0, 120))}${(b.new || '').length > 120 ? '…' : ''}</div>
      ${commentHtml}
      ${tagsHtml}
      <div class="list-item-actions">
        <button onclick="event.stopPropagation(); openChapter('${b.bookSlug}', ${b.chapter}, { scrollToVerse: ${b.verseNum} })">➡️ გახსნა</button>
        ${b.comment ? `<button onclick="event.stopPropagation(); editListComment(${idx})">✏️ კომენტარი</button>` : `<button onclick="event.stopPropagation(); editListComment(${idx})">💬 კომენტარი</button>`}
        <button class="list-item-del" onclick="event.stopPropagation(); deleteListBookmark(${idx})">🗑 წაშლა</button>
      </div>
    </div>`;
  });
  showListOverlay(`📌 სანიშნეები <span style="color:var(--text-muted);font-size:14px;">(${pinned.length})</span>`, html);
}

function deleteListBookmark(idx) {
  const bm = bookmarks[idx];
  if (!bm) return;
  const parts = [`📌 სანიშნე: ${bm.ref}`];
  if (bm.comment && bm.comment.trim()) parts.push(`💬 კომენტარი`);
  if (bm.tags && bm.tags.length > 0) parts.push(`🏷️ თაგები: ${bm.tags.length}`);
  if (!confirm(`⚠️ დარწმუნებული ხარ?\n\nწაიშლება:\n${parts.join('\n')}\n\nეს მოქმედება შეუქცევადია!`)) return;
  bookmarks.splice(idx, 1);
  persistBookmarks();
  renderHomeBookmarks();
  updateDashboardCounts();
  if (currentBook === bm.bookSlug && currentChapter === bm.chapter) renderChapter();
  showToast('წაიშალა');
  openBookmarksList();
}

// === კასტომ dropdown (მობილურზე ქვემოთ გამოჩნდება) ===

function initCustomSelect(selectEl) {
  if (!selectEl || selectEl.dataset.customized) return;
  selectEl.dataset.customized = '1';

  // შევქმნათ კასტომ ვრაპერი
  const wrapper = document.createElement('div');
  wrapper.className = 'custom-select';
  wrapper.style.maxWidth = selectEl.style.maxWidth || getComputedStyle(selectEl).maxWidth || '200px';

  // trigger
  const trigger = document.createElement('div');
  trigger.className = 'custom-select-trigger';

  // menu
  const menu = document.createElement('div');
  menu.className = 'custom-select-menu';

  // ვაგროვებთ options-ს
  function buildMenu() {
    menu.innerHTML = '';
    const opts = selectEl.querySelectorAll('option, optgroup');
    let currentGroup = null;
    opts.forEach(el => {
      if (el.tagName === 'OPTGROUP') {
        const label = document.createElement('div');
        label.className = 'custom-select-option optgroup-label';
        label.textContent = el.label;
        menu.appendChild(label);
        currentGroup = el;
      } else if (el.tagName === 'OPTION') {
        const opt = document.createElement('div');
        opt.className = 'custom-select-option';
        if (el.value === selectEl.value) opt.classList.add('selected');
        opt.textContent = el.textContent;
        opt.dataset.value = el.value;
        opt.onclick = (e) => {
          e.stopPropagation();
          selectEl.value = el.value;
          trigger.textContent = el.textContent;
          wrapper.classList.remove('open');
          // გავუშვათ onchange
          selectEl.dispatchEvent(new Event('change'));
          // განვაახლოთ selected
          menu.querySelectorAll('.custom-select-option').forEach(o => o.classList.remove('selected'));
          opt.classList.add('selected');
        };
        menu.appendChild(opt);
      }
    });
  }

  // საწყისი მნიშვნელობა
  function updateTrigger() {
    const selected = selectEl.options[selectEl.selectedIndex];
    trigger.textContent = selected ? selected.textContent : '';
  }

  buildMenu();
  updateTrigger();

  trigger.onclick = (e) => {
    e.stopPropagation();
    // დავხუროთ სხვა ღია dropdown-ები
    document.querySelectorAll('.custom-select.open').forEach(s => {
      if (s !== wrapper) s.classList.remove('open');
    });
    wrapper.classList.toggle('open');
    if (wrapper.classList.contains('open')) {
      // ჭკვიანური პოზიციონირება - თუ ქვემოთ არ არის სივრცე, ზემოთ გამოჩნდება
      const rect = trigger.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      if (spaceBelow < 250 && rect.top > 250) {
        menu.style.top = 'auto';
        menu.style.bottom = 'calc(100% + 2px)';
      } else {
        menu.style.top = 'calc(100% + 2px)';
        menu.style.bottom = 'auto';
      }
      // განვაახლოთ selected მდგომარეობა
      menu.querySelectorAll('.custom-select-option').forEach(o => {
        o.classList.toggle('selected', o.dataset.value === selectEl.value);
      });
    }
  };

  wrapper.appendChild(trigger);
  wrapper.appendChild(menu);
  selectEl.style.display = 'none';
  selectEl.parentNode.insertBefore(wrapper, selectEl.nextSibling);

  // გარე კლიკზე დახურვა
  document.addEventListener('click', (e) => {
    if (!wrapper.contains(e.target)) wrapper.classList.remove('open');
  });

  // სელექტის ღილაკზე არ გავხსნათ ნატივი
  selectEl.addEventListener('mousedown', (e) => {
    if (wrapper.contains(e.target)) e.preventDefault();
  });

  // როცა select-ის მნიშვნელობა იცვლება პროგრამულად
  const observer = new MutationObserver(() => {
    buildMenu();
    updateTrigger();
  });
  observer.observe(selectEl, { childList: true, subtree: true });

  // ფუნქცია განახლებისთვის გარედან
  selectEl._refreshCustom = () => { buildMenu(); updateTrigger(); };
}

function initAllCustomSelects() {
  // ძიების ფილტრები
  ['filter-testament', 'filter-book', 'filter-translation', 'filter-limit'].forEach(id => {
    const el = document.getElementById(id);
    if (el) initCustomSelect(el);
  });
  // ლექსიკონის ფილტრები
  ['lexicon-scope', 'lexicon-book'].forEach(id => {
    const el = document.getElementById(id);
    if (el) initCustomSelect(el);
  });
}

// DOM-ის ჩატვირთვის შემდეგ
document.addEventListener('DOMContentLoaded', () => {
  // ცოტა დაგვიანებით რომ filter-book უკვე შევსებული იყოს
  setTimeout(initAllCustomSelects, 500);
  // Swipe ჟესტების ინიციალიზაცია
  setupSwipeNavigation();
});

// === Swipe ჟესტები თავების ნავიგაციისთვის ===

function setupSwipeNavigation() {
  const chapterView = document.getElementById('chapter-view');
  if (!chapterView) return;

  let touchStartX = 0;
  let touchStartY = 0;
  let touchEndX = 0;
  let touchEndY = 0;
  let touchStartTime = 0;
  let isTracking = false;

  // მინიმალური მანძილი swipe-ის ამოსაცნობად
  const SWIPE_MIN_DISTANCE = 50;
  // მაქსიმალური ვერტიკალური გადახრა (რომ swipe არ აგვირიოს ვერტიკალურ სქროლში)
  const SWIPE_MAX_VERTICAL = 80;
  // მაქსიმალური დრო swipe-ისთვის (ms)
  const SWIPE_MAX_TIME = 600;

  chapterView.addEventListener('touchstart', (e) => {
    // მხოლოდ ერთი თითი
    if (e.touches.length !== 1) return;
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    touchStartTime = Date.now();
    isTracking = true;
  }, { passive: true });

  chapterView.addEventListener('touchend', (e) => {
    if (!isTracking) return;
    isTracking = false;

    touchEndX = e.changedTouches[0].clientX;
    touchEndY = e.changedTouches[0].clientY;

    const deltaX = touchEndX - touchStartX;
    const deltaY = touchEndY - touchStartY;
    const elapsed = Date.now() - touchStartTime;

    // შემოწმება - არის თუ არა ჰორიზონტალური swipe
    if (Math.abs(deltaX) < SWIPE_MIN_DISTANCE) return;
    if (Math.abs(deltaY) > SWIPE_MAX_VERTICAL) return;
    if (elapsed > SWIPE_MAX_TIME) return;

    // არ ვაგრძელოთ თუ მომხმარებელი სქროლავს ჰორიზონტალურად (მაგ. ფერადი მარკირების სქროლი)
    const scrollable = e.target.closest('.highlight-palette, .chapter-quick-nav, .book-ribbon, .search-results, .crossrefs-list');
    if (scrollable) return;

    // არ ვაგრძელოთ თუ პოპაპი ან პანელი გახსნილია
    const popup = document.getElementById('verse-popup');
    if (popup && popup.style.display !== 'none') return;
    const wordPanel = document.getElementById('word-panel');
    if (wordPanel && wordPanel.style.display !== 'none') return;
    const studyPad = document.getElementById('study-pad-panel');
    if (studyPad && studyPad.style.display !== 'none') return;
    const bookmarksPanel = document.getElementById('bookmarks-panel');
    if (bookmarksPanel && bookmarksPanel.style.display !== 'none') return;

    if (deltaX > 0) {
      // მარჯვნიდან მარცხნივ - წინა თავი
      prevChapter();
    } else {
      // მარცხნიდან მარჯვნივ - მომდევნო თავი
      nextChapter();
    }
  }, { passive: true });
}

// ===== პროექტის შესახებ მოდალი =====
function openAbout() {
  const m = document.getElementById('about-modal');
  if (m) {
    m.style.display = 'flex';
    moveFocusInto(m);
    enableFocusTrap(m);
    // აუდიო ჩამოსატვირთი სიის შევსება
    if (typeof renderAudioDownloadList === 'function') renderAudioDownloadList();
  }
}

function closeAbout() {
  const m = document.getElementById('about-modal');
  if (m) m.style.display = 'none';
  disableFocusTrap();
}

// ESC-ით დახურვა - უნივერსალურ handler-ი ზემოთაა (line ~2182)
