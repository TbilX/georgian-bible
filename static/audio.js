// === აუდიო პლეიერი (ადგილობრივი MP3 ფაილები) ===
// YouTube iframe-ის ნაცვლად - სერვერზე დაჰოსტილი MP3 ფაილები
// ოფლაინ მუშაობს Service Worker-ის კეშირების წყალობით

let audioMap = null;
let audioEl = null;          // მთავარი <audio> ელემენტი
let audioElExtra = null;     // შესავალის <audio> ელემენტი
let currentAudioBook = null;
let currentAudioChapter = null;
let audioPlayState = 'stopped'; // stopped, playing, paused, loading

// რომელ რეჟიმში ვართ: 'main' (თავი) ან 'extra' (შესავალი)
let audioMode = 'main';
let extraPlayState = 'stopped';

// === localStorage - დაკვრის პოზიციის შენახვა/აღდგენა ===
// გვერდის რეფრეშის შემდეგ აუდიო იმავე პოზიციაზე გააგრძელებს
const AUDIO_POS_KEY = 'bible_audio_pos';

function _saveAudioPos() {
  if (!currentAudioBook || !currentAudioChapter) return;
  const el = (audioMode === 'extra') ? audioElExtra : audioEl;
  if (!el || !el.currentTime || !el.duration) return;
  try {
    const data = {
      book: currentAudioBook,
      chapter: currentAudioChapter,
      mode: audioMode,
      time: el.currentTime,
      duration: el.duration,
      ts: Date.now()
    };
    localStorage.setItem(AUDIO_POS_KEY, JSON.stringify(data));
  } catch (e) {}
}

function _loadAudioPos() {
  try {
    const raw = localStorage.getItem(AUDIO_POS_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    // 24 საათზე ძველი პოზიცია არ აღვადგინოთ
    if (Date.now() - data.ts > 86400000) {
      localStorage.removeItem(AUDIO_POS_KEY);
      return null;
    }
    return data;
  } catch (e) { return null; }
}

function _clearAudioPos() {
  try { localStorage.removeItem(AUDIO_POS_KEY); } catch (e) {}
}

// პერიოდულად ვინახავთ პოზიციას (დაკვრის დროს)
let posSaveInterval = null;
function _startPosSave() {
  _stopPosSave();
  posSaveInterval = setInterval(_saveAudioPos, 3000);
}
function _stopPosSave() {
  if (posSaveInterval) { clearInterval(posSaveInterval); posSaveInterval = null; }
}

// === გვერდის ჩატვირთვაზე ვწინასწარ ჩატვირთავთ audio_map.json-ს ===
(function preloadAudio() {
  fetch('/static/audio_map.json?v=' + Date.now())
    .then(r => r.json())
    .then(data => {
      audioMap = data;
      // გადავხატოთ წიგნების სია რომ 🎵 იკონები გამოჩნდეს
      // მხოლოდ თუ BOOKS უკვე ჩატვირთულია
      if (typeof BOOKS !== 'undefined' && BOOKS && BOOKS.old && typeof renderBooks === 'function') {
        renderBooks();
      }
    })
    .catch(e => { console.error('audio_map.json ვერ ჩაიტვირთა:', e); audioMap = {}; });
})();

// <audio> ელემენტების შექმნა (lazy - პირველი დაკვრისას)
function _ensureAudioElements() {
  if (!audioEl) {
    audioEl = new Audio();
    audioEl.preload = 'auto';
    audioEl.addEventListener('play', () => {
      if (audioMode === 'main') {
        audioPlayState = 'playing';
        _startProgressLoop();
        _startPosSave();
        updateAudioPlayerUI();
      }
    });
    audioEl.addEventListener('playing', () => {
      // playing event მოდის waiting (ბუფერინგის) შემდეგ - აქ ვბრუნდებით playing-ზე
      if (audioMode === 'main') {
        audioPlayState = 'playing';
        _startProgressLoop();
        _startPosSave();
        updateAudioPlayerUI();
      }
    });
    audioEl.addEventListener('pause', () => {
      if (audioMode === 'main') {
        audioPlayState = 'paused';
        _saveAudioPos();
        updateAudioPlayerUI();
      }
    });
    audioEl.addEventListener('ended', () => {
      if (audioMode === 'main') {
        audioPlayState = 'stopped';
        _stopProgressLoop();
        _stopPosSave();
        _clearAudioPos();
        updateAudioPlayerUI();
      }
    });
    audioEl.addEventListener('waiting', () => {
      if (audioMode === 'main') {
        audioPlayState = 'loading';
        updateAudioPlayerUI();
      }
    });
    audioEl.addEventListener('canplay', () => {
      // canplay - ბუფერინგი დასრულდა, მაგრამ playing event თავისით მოვა
    });
    audioEl.addEventListener('error', (e) => {
      console.error('[Audio] დაკვრის შეცდომა:', e);
      if (audioMode === 'main') {
        audioPlayState = 'stopped';
        updateAudioPlayerUI();
      }
    });
  }

  if (!audioElExtra) {
    audioElExtra = new Audio();
    audioElExtra.preload = 'auto';
    audioElExtra.addEventListener('play', () => {
      if (audioMode === 'extra') {
        extraPlayState = 'playing';
        _startProgressLoop();
        _startPosSave();
        updateAudioPlayerUI();
      }
    });
    audioElExtra.addEventListener('playing', () => {
      if (audioMode === 'extra') {
        extraPlayState = 'playing';
        _startProgressLoop();
        _startPosSave();
        updateAudioPlayerUI();
      }
    });
    audioElExtra.addEventListener('pause', () => {
      if (audioMode === 'extra') {
        extraPlayState = 'paused';
        _saveAudioPos();
        updateAudioPlayerUI();
      }
    });
    audioElExtra.addEventListener('ended', () => {
      if (audioMode === 'extra') {
        extraPlayState = 'stopped';
        _stopProgressLoop();
        _stopPosSave();
        _clearAudioPos();
        updateAudioPlayerUI();
      }
    });
    audioElExtra.addEventListener('waiting', () => {
      if (audioMode === 'extra') {
        extraPlayState = 'loading';
        updateAudioPlayerUI();
      }
    });
    audioElExtra.addEventListener('error', (e) => {
      console.error('[Audio] შესავალის დაკვრის შეცდომა:', e);
      if (audioMode === 'extra') {
        extraPlayState = 'stopped';
        updateAudioPlayerUI();
      }
    });
  }
}

// audio_map.json-ის ჩატვირთვა (fallback)
async function loadAudioMap() {
  if (audioMap) return audioMap;
  try {
    const res = await fetch('/static/audio_map.json?v=' + Date.now());
    audioMap = await res.json();
  } catch (e) {
    console.error('audio_map.json ვერ ჩაიტვირთა:', e);
    audioMap = {};
  }
  return audioMap;
}

// შემოწმება - არის თუ არა აუდიო ხელმისაწვდომი
function hasAudio(bookSlug, chapter) {
  return !!(audioMap && audioMap[bookSlug] && audioMap[bookSlug][String(chapter)]);
}

// აუდიო URL-ის მიღება
// თუ ყველა თავს ერთი და იგივე video ID აქვს (მთლიანი აუდიო),
// ვიყენებთ full.mp3 ფაილს და პოზიციას ვინარჩუნებთ თავებს შორის
function _getAudioUrl(bookSlug, chapter) {
  if (audioMap && audioMap[bookSlug]) {
    const ch = String(chapter);
    const videoId = audioMap[bookSlug][ch];
    // შევამოწმოთ - არის თუ არა ყველა თავი იგივე video ID-ზე
    const allChapters = Object.keys(audioMap[bookSlug]).filter(k => k !== 'intro');
    if (allChapters.length > 1 && allChapters.every(k => audioMap[bookSlug][k] === videoId)) {
      // მთლიანი აუდიო - full.mp3
      return `https://audio.web.net.ge/${bookSlug}/full.mp3`;
    }
  }
  return `https://audio.web.net.ge/${bookSlug}/${chapter}.mp3`;
}

function _getIntroUrl(bookSlug) {
  return `https://audio.web.net.ge/${bookSlug}/intro.mp3`;
}

// წიგნის სახელის მიღება slug-იდან
function _getBookName(bookSlug) {
  if (typeof BOOKS !== 'undefined') {
    const allBooks = [...(BOOKS.old || []), ...(BOOKS.new || [])];
    const found = allBooks.find(b => b.slug === bookSlug);
    if (found) return found.name;
  }
  return bookSlug;
}

// წიგნის ყველა თავის ჩამოტვირთვა (თანმიმდევრულად)
async function downloadAllChapters() {
  if (!currentAudioBook || !audioMap || !audioMap[currentAudioBook]) return;
  const bookName = _getBookName(currentAudioBook);
  const chapters = Object.keys(audioMap[currentAudioBook])
    .filter(k => k !== 'intro')
    .map(k => parseInt(k))
    .sort((a, b) => a - b);
  _downloadChaptersSequential(currentAudioBook, bookName, chapters);
}

// Popup-დან ყველა თავის ჩამოტვირთვა
async function downloadAllChaptersFromPopup() {
  if (!popupBook || !audioMap || !audioMap[popupBook.slug]) return;
  const chapters = popupChapters.slice();
  _downloadChaptersSequential(popupBook.slug, popupBook.name, chapters);
}

// თანმიმდევრული ჩამოტვირთვა - თითო ფაილი მიყოლებით
async function _downloadChaptersSequential(bookSlug, bookName, chapters) {
  if (chapters.length === 0) return;
  if (typeof showToast === 'function') showToast(`ჩამოტვირთვა დაიწყო: ${bookName} (${chapters.length} თავი)...`);

  for (let i = 0; i < chapters.length; i++) {
    const ch = chapters[i];
    const url = _getAudioUrl(bookSlug, ch);
    const dlName = `${bookName} - თავი ${ch}.mp3`;
    try {
      const resp = await fetch(url);
      const blob = await resp.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = dlName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    } catch (e) {
      console.error(`[Audio] ჩამოტვირთვა ვერ მოხერხდა: ${dlName}`, e);
    }
    // მცირე დაყოვნება ფაილებს შორის
    if (i < chapters.length - 1) await new Promise(r => setTimeout(r, 300));
  }
  if (typeof showToast === 'function') showToast(`ჩამოტვირთვა დასრულდა: ${bookName}`);
}

// აუდიო პლეიერის ხედის განახლება
function updateAudioPlayerUI() {
  const player = document.getElementById('audio-player');
  if (!player) return;

  const hasCurrent = currentAudioBook && currentAudioChapter;
  if (!hasCurrent) {
    player.style.display = 'none';
  } else {
    player.style.display = 'flex';
    const playBtn = document.getElementById('audio-play-btn');
    const statusEl = document.getElementById('audio-status');
    const titleEl = document.getElementById('audio-title');

    // წიგნის სახელის მოძებნა
    const bookName = _getBookName(currentAudioBook);
    if (titleEl) titleEl.textContent = `${bookName} ${currentAudioChapter}`;

    const icons = { stopped: '▶', playing: '⏸', paused: '▶', loading: '⏳' };
    if (playBtn) playBtn.textContent = icons[audioPlayState] || '▶';

    if (statusEl) {
      const labels = { stopped: 'შესვენებული', playing: 'უკრებს', paused: 'პაუზა', loading: 'იტვირთება...' };
      statusEl.textContent = labels[audioPlayState] || '';
    }

    // ჩამოსატვირთი ღილაკები
    const dlBtn = document.getElementById('audio-download-btn');
    const dlAllBtn = document.getElementById('audio-download-all-btn');
    if (dlBtn) {
      dlBtn.href = _getAudioUrl(currentAudioBook, currentAudioChapter);
      dlBtn.download = `${bookName} - თავი ${currentAudioChapter}.mp3`;
      dlBtn.style.display = 'inline-flex';
    }
    if (dlAllBtn) {
      dlAllBtn.style.display = audioMap && audioMap[currentAudioBook] ? 'inline-flex' : 'none';
    }
  }

  // მეორე პლეიერი (შესავალი)
  const extraPlayer = document.getElementById('audio-player-extra');
  if (!extraPlayer) return;

  if (!audioMap || !audioMap[currentAudioBook]) {
    extraPlayer.style.display = 'none';
    return;
  }
  const hasIntro = audioMap[currentAudioBook]['intro'];
  if (!hasIntro || currentAudioChapter !== 1) {
    extraPlayer.style.display = 'none';
    return;
  }

  extraPlayer.style.display = 'flex';
  const titleExtra = document.getElementById('audio-title-extra');
  if (titleExtra) titleExtra.textContent = `${currentAudioBook} - შესავალი`;

  const playBtnExtra = document.getElementById('audio-play-btn-extra');
  const statusExtra = document.getElementById('audio-status-extra');
  const icons2 = { stopped: '▶', playing: '⏸', paused: '▶', loading: '⏳' };
  if (playBtnExtra) playBtnExtra.textContent = icons2[extraPlayState] || '▶';
  if (statusExtra) {
    const labels2 = { stopped: 'შესვენებული', playing: 'უკრებს', paused: 'პაუზა', loading: 'იტვირთება...' };
    statusExtra.textContent = labels2[extraPlayState] || '';
  }
}

// Progress loop - დროის და progress bar-ის განახლება
let progressInterval = null;
function _startProgressLoop() {
  _stopProgressLoop();
  progressInterval = setInterval(() => {
    const el = (audioMode === 'extra') ? audioElExtra : audioEl;
    if (!el) return;
    const cur = el.currentTime || 0;
    const dur = el.duration || 0;
    const timeStr = `${_formatTime(cur)} / ${_formatTime(dur)}`;
    const pct = dur > 0 ? (cur / dur) * 100 : 0;

    if (audioMode === 'extra') {
      const timeEl = document.getElementById('audio-time-extra');
      const fill = document.getElementById('audio-progress-fill-extra');
      if (timeEl) timeEl.textContent = timeStr;
      if (fill) fill.style.width = `${pct}%`;
    } else {
      const timeEl = document.getElementById('audio-time');
      const fill = document.getElementById('audio-progress-fill');
      if (timeEl) timeEl.textContent = timeStr;
      if (fill) fill.style.width = `${pct}%`;
    }
  }, 250);
}
function _stopProgressLoop() {
  if (progressInterval) { clearInterval(progressInterval); progressInterval = null; }
}

function _formatTime(sec) {
  if (!sec || isNaN(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// === თავის დაკვრა (მთავარი პლეიერი) ===
function _playAudioChapter(bookSlug, chapter) {
  if (!audioMap || !audioMap[bookSlug]) return;
  const videoId = audioMap[bookSlug][String(chapter)];
  if (!videoId) return;

  _ensureAudioElements();

  // შესავალის შეჩერება
  if (extraPlayState === 'playing' || extraPlayState === 'paused') {
    audioElExtra.pause();
    extraPlayState = 'stopped';
  }

  // popup ფლეიერის შეჩერება (არ დაუკრას 2 ფაილი ერთად)
  _pausePopupPlayer();

  audioMode = 'main';
  audioPlayState = 'loading';
  updateAudioPlayerUI();

  const url = _getAudioUrl(bookSlug, chapter);
  audioEl.src = url;

  // თუ შენახული პოზიცია არსებობს - იმ დროზე გადავა
  const restoreTime = _pendingRestoreTime;
  _pendingRestoreTime = null;

  audioEl.play().then(() => {
    if (restoreTime && restoreTime > 0 && audioEl.duration && restoreTime < audioEl.duration) {
      audioEl.currentTime = restoreTime;
    }
  }).catch(e => {
    console.error('[Audio] დაკვრა ვერ დაიწყო:', e);
    audioPlayState = 'stopped';
    updateAudioPlayerUI();
  });
}

// popup ფლეიერის შეჩერება (როცა თავის აუდიო იწყებს დაკვრას)
function _pausePopupPlayer() {
  if (popupAudioEl && !popupAudioEl.paused) {
    popupAudioEl.pause();
    popupPlayState = 'paused';
    _updatePopupPlayBtn();
    _renderPopupPlaylist();
  }
}

// === შესავალის დაკვრა (extra რეჟიმი) ===
function _playIntro() {
  if (!audioMap || !audioMap[currentAudioBook]) return;
  const introId = audioMap[currentAudioBook]['intro'];
  if (!introId) return;

  _ensureAudioElements();

  // მთავარი პლეიერის შეჩერება
  if (audioPlayState === 'playing' || audioPlayState === 'paused') {
    audioEl.pause();
    audioPlayState = 'stopped';
  }

  audioMode = 'extra';
  extraPlayState = 'loading';
  updateAudioPlayerUI();

  const url = _getIntroUrl(currentAudioBook);
  audioElExtra.src = url;
  audioElExtra.play().catch(e => {
    console.error('[Audio] შესავალი ვერ დაიკრა:', e);
    extraPlayState = 'stopped';
    updateAudioPlayerUI();
  });
}

// გარედან გამოძახება - თავის გახსნისას
function initAudioForChapter(bookSlug, chapter, bookName) {
  if (!audioMap) {
    loadAudioMap().then(() => {
      _initAudioForChapterInner(bookSlug, chapter);
    });
    return;
  }
  _initAudioForChapterInner(bookSlug, chapter);
}

function _initAudioForChapterInner(bookSlug, chapter) {
  if (!hasAudio(bookSlug, chapter)) {
    currentAudioBook = null;
    currentAudioChapter = null;
    audioPlayState = 'stopped';
    extraPlayState = 'stopped';
    // გავაჩეროთ მიმდინარე დაკვრა
    if (audioEl) { audioEl.pause(); audioEl.src = ''; }
    if (audioElExtra) { audioElExtra.pause(); audioElExtra.src = ''; }
    updateAudioPlayerUI();
    return;
  }

  // თუ იგივე თავია - არ გადავატვირთოთ
  if (currentAudioBook === bookSlug && currentAudioChapter === chapter) {
    updateAudioPlayerUI();
    return;
  }

  // თუ იმავე წიგნში ვცვლით თავს და აუდიო იგივეა (მთლიანი აუდიო) - არ გავწყვეტთ დაკვრას
  const isSameAudio = currentAudioBook === bookSlug &&
    audioMap[bookSlug] &&
    audioMap[bookSlug][String(currentAudioChapter)] &&
    audioMap[bookSlug][String(chapter)] &&
    audioMap[bookSlug][String(currentAudioChapter)] === audioMap[bookSlug][String(chapter)];

  if (isSameAudio) {
    // იგივე აუდიო ფაილია - უბრალოდ გავანახლოთ currentAudioChapter
    currentAudioChapter = chapter;
    // პოზიცია არ იცვლება, დაკვრა გრძელდება
    updateAudioPlayerUI();
    return;
  }

  // ახალი თავი - გავაჩეროთ ძველი
  if (audioEl && !audioEl.paused) audioEl.pause();
  if (audioElExtra && !audioElExtra.paused) audioElExtra.pause();

  currentAudioBook = bookSlug;
  currentAudioChapter = chapter;
  audioPlayState = 'stopped';
  extraPlayState = 'stopped';
  audioMode = 'main';

  // შენახული პოზიციის აღდგენა (რეფრეშის შემდეგ)
  const saved = _loadAudioPos();
  if (saved && saved.book === bookSlug && saved.chapter == chapter) {
    // პოზიცია შენახულია - მომხმარებელს ვაჩვენებთ რომ გაგრძელება შესაძლებელია
    // დავაყენებთ ღილაკს ▶-ზე, დაკვრისას კი პოზიციაზე გადავა
    audioPlayState = 'paused'; // paused = ▶ ღილაკი, დაჭერისას გააგრძელებს
    _pendingRestoreTime = saved.time;
  }

  updateAudioPlayerUI();
}

// შენახული პოზიცია - დაკვრისას ამ დროზე გადავა
let _pendingRestoreTime = null;

// === ღილაკები ===
function toggleAudioPlay() {
  if (!currentAudioBook || !currentAudioChapter) return;
  _ensureAudioElements();

  if (audioPlayState === 'playing') {
    audioEl.pause();
  } else if (audioPlayState === 'paused') {
    // popup ფლეიერის შეჩერება (არ დაუკრას 2 ფაილი ერთად)
    _pausePopupPlayer();
    // თუ audio-ს არ აქვს src (რეფრეშის შემდეგ) - თავიდან დავიწყოთ შენახული პოზიციით
    if (!audioEl.src) {
      _playAudioChapter(currentAudioBook, currentAudioChapter);
    } else {
      audioEl.play().catch(e => console.error('[Audio] გაგრძელება ვერ მოხერხდა:', e));
    }
  } else if (audioPlayState === 'loading') {
    // ბუფერინგის დროს დაჭერა - გაჩერება
    audioEl.pause();
    audioPlayState = 'stopped';
    updateAudioPlayerUI();
  } else {
    _playAudioChapter(currentAudioBook, currentAudioChapter);
  }
}

function toggleAudioPlayExtra() {
  if (!audioMap || !audioMap[currentAudioBook]) return;
  const introId = audioMap[currentAudioBook]['intro'];
  if (!introId) return;
  _ensureAudioElements();

  if (extraPlayState === 'playing') {
    audioElExtra.pause();
  } else if (extraPlayState === 'paused') {
    audioElExtra.play().catch(e => console.error('[Audio] შესავალის გაგრძელება ვერ მოხერხდა:', e));
  } else if (extraPlayState === 'loading') {
    audioElExtra.pause();
    extraPlayState = 'stopped';
    updateAudioPlayerUI();
  } else {
    _playIntro();
  }
}

function stopAudio() {
  if (audioEl) { audioEl.pause(); audioEl.currentTime = 0; }
  audioPlayState = 'stopped';
  _stopProgressLoop();
  updateAudioPlayerUI();
}

function stopAudioExtra() {
  if (audioElExtra) { audioElExtra.pause(); audioElExtra.currentTime = 0; }
  extraPlayState = 'stopped';
  _stopProgressLoop();
  updateAudioPlayerUI();
}

function seekAudio(percent) {
  if (!audioEl || !audioEl.duration) return;
  audioEl.currentTime = (percent / 100) * audioEl.duration;
  const fill = document.getElementById('audio-progress-fill');
  if (fill) fill.style.width = `${percent}%`;
}

function seekAudioExtra(percent) {
  if (!audioElExtra || !audioElExtra.duration) return;
  audioElExtra.currentTime = (percent / 100) * audioElExtra.duration;
  const fill = document.getElementById('audio-progress-fill-extra');
  if (fill) fill.style.width = `${percent}%`;
}

// === დაკვრის სიჩქარის კონტროლი ===
// Dropdown მენიუ - ერთ დაჭერაზე ვარჩევ სიჩქარეს

function toggleSpeedMenu(e) {
  e.stopPropagation();
  const menu = document.getElementById('audio-speed-menu');
  const menuExtra = document.getElementById('audio-speed-menu-extra');
  if (menuExtra) menuExtra.style.display = 'none';
  if (!menu) return;
  const isOpen = menu.style.display === 'flex';
  if (isOpen) {
    menu.style.display = 'none';
    return;
  }
  // ღილაკის პოზიცია ეკრანზე
  const btn = document.getElementById('audio-speed');
  const rect = btn.getBoundingClientRect();
  menu.style.display = 'flex';
  // მენიუს სიგანე
  const menuW = menu.offsetWidth;
  const menuH = menu.offsetHeight;
  // სიმეტრიულად ღილაკის ცენტრზე
  let left = rect.left + rect.width / 2 - menuW / 2;
  let top = rect.top - menuH - 8;
  // არ გამოვიდეს ეკრანიდან
  if (left < 8) left = 8;
  if (left + menuW > window.innerWidth - 8) left = window.innerWidth - menuW - 8;
  if (top < 8) top = rect.bottom + 8; // თუ ზემოთ არ ჯდება - ქვემოთ გამოვა
  menu.style.left = left + 'px';
  menu.style.top = top + 'px';
}

function toggleSpeedMenuExtra(e) {
  e.stopPropagation();
  const menu = document.getElementById('audio-speed-menu');
  const menuExtra = document.getElementById('audio-speed-menu-extra');
  if (menu) menu.style.display = 'none';
  if (!menuExtra) return;
  const isOpen = menuExtra.style.display === 'flex';
  if (isOpen) {
    menuExtra.style.display = 'none';
    return;
  }
  const btn = document.getElementById('audio-speed-extra');
  const rect = btn.getBoundingClientRect();
  menuExtra.style.display = 'flex';
  const menuW = menuExtra.offsetWidth;
  const menuH = menuExtra.offsetHeight;
  let left = rect.left + rect.width / 2 - menuW / 2;
  let top = rect.top - menuH - 8;
  if (left < 8) left = 8;
  if (left + menuW > window.innerWidth - 8) left = window.innerWidth - menuW - 8;
  if (top < 8) top = rect.bottom + 8;
  menuExtra.style.left = left + 'px';
  menuExtra.style.top = top + 'px';
}

function setAudioSpeed(rate) {
  if (audioEl) audioEl.playbackRate = rate;
  const btn = document.getElementById('audio-speed');
  if (btn) btn.textContent = rate + 'x';
  const menu = document.getElementById('audio-speed-menu');
  if (menu) menu.style.display = 'none';
}

function setAudioSpeedExtra(rate) {
  if (audioElExtra) audioElExtra.playbackRate = rate;
  const btn = document.getElementById('audio-speed-extra');
  if (btn) btn.textContent = rate + 'x';
  const menu = document.getElementById('audio-speed-menu-extra');
  if (menu) menu.style.display = 'none';
}

// მენიუს დახურვა გვერდზე დაჭერისას
document.addEventListener('click', (e) => {
  const m1 = document.getElementById('audio-speed-menu');
  const m2 = document.getElementById('audio-speed-menu-extra');
  const m3 = document.getElementById('audio-popup-speed-menu');
  if (m1 && !e.target.closest('#audio-speed')) m1.style.display = 'none';
  if (m2 && !e.target.closest('#audio-speed-extra')) m2.style.display = 'none';
  if (m3 && !e.target.closest('.audio-popup-speed-wrap')) m3.style.display = 'none';
});

// === აუდიო Popup Player ===
let popupAudioEl = null;
let popupBook = null;
let popupChapters = [];
let popupCurrentIdx = 0;
let popupPlayState = 'stopped';
let popupProgressInterval = null;
let popupPrevVolume = 1;

// === Popup პოზიციის შენახვა/აღდგენა (რეფრეშის შემდეგ) ===
const POPUP_POS_KEY = 'bible_popup_audio_pos';
let popupPosSaveInterval = null;

function _savePopupPos() {
  if (!popupBook || !popupAudioEl || !popupAudioEl.currentTime || !popupAudioEl.duration) return;
  try {
    const data = {
      bookSlug: popupBook.slug,
      bookName: popupBook.name,
      chapter: popupChapters[popupCurrentIdx],
      time: popupAudioEl.currentTime,
      duration: popupAudioEl.duration,
      ts: Date.now()
    };
    localStorage.setItem(POPUP_POS_KEY, JSON.stringify(data));
  } catch (e) {}
}

function _loadPopupPos() {
  try {
    const raw = localStorage.getItem(POPUP_POS_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (Date.now() - data.ts > 86400000) {
      localStorage.removeItem(POPUP_POS_KEY);
      return null;
    }
    return data;
  } catch (e) { return null; }
}

function _clearPopupPos() {
  try { localStorage.removeItem(POPUP_POS_KEY); } catch (e) {}
}

function _startPopupPosSave() {
  _stopPopupPosSave();
  popupPosSaveInterval = setInterval(_savePopupPos, 3000);
}
function _stopPopupPosSave() {
  if (popupPosSaveInterval) { clearInterval(popupPosSaveInterval); popupPosSaveInterval = null; }
}

// გვერდის დახურვისას/რეფრეშისას პოზიციის შენახვა
window.addEventListener('beforeunload', () => {
  if (popupAudioEl && !popupAudioEl.paused) _savePopupPos();
});

// გვერდის ჩატვირთვაზე - შენახული პოზიციის აღდგენა (მინი ფლეიერი)
(function restorePopupOnLoad() {
  const saved = _loadPopupPos();
  if (!saved || !saved.bookSlug) return;
  // დაველოდოთ audioMap-ის ჩატვირთვას
  function tryRestore() {
    if (!audioMap) {
      setTimeout(tryRestore, 200);
      return;
    }
    if (!audioMap[saved.bookSlug]) return;
    // შევქმნათ popupBook და მინი ფლეიერი (პაუზაში)
    popupBook = { slug: saved.bookSlug, name: saved.bookName || saved.bookSlug };
    // თავების სია audioMap-იდან
    const chapters = Object.keys(audioMap[saved.bookSlug])
      .filter(k => k !== 'intro')
      .map(k => parseInt(k))
      .sort((a, b) => a - b);
    popupChapters = chapters;
    const idx = chapters.indexOf(saved.chapter);
    popupCurrentIdx = idx >= 0 ? idx : 0;
    popupPlayState = 'paused';
    // შევქმნათ audio ელემენტი და დავაყენოთ პოზიცია
    if (!popupAudioEl) {
      popupAudioEl = new Audio();
      popupAudioEl.addEventListener('loadedmetadata', () => {
        if (saved.time > 0 && saved.time < popupAudioEl.duration) {
          popupAudioEl.currentTime = saved.time;
        }
        _updatePopupTime();
      });
      popupAudioEl.addEventListener('timeupdate', () => { _updatePopupProgress(); if (!popupAudioEl.paused && popupPlayState !== 'playing') { popupPlayState = 'playing'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); } });
      popupAudioEl.addEventListener('play', () => { popupPlayState = 'playing'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); });
      popupAudioEl.addEventListener('playing', () => { popupPlayState = 'playing'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); });
      popupAudioEl.addEventListener('pause', () => { popupPlayState = 'paused'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); _savePopupPos(); });
      popupAudioEl.addEventListener('waiting', () => { popupPlayState = 'loading'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); });
      popupAudioEl.addEventListener('canplay', () => { if (!popupAudioEl.paused) { popupPlayState = 'playing'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); } });
      popupAudioEl.addEventListener('ended', () => { _stopPopupPosSave(); audioPopupNext(); });
    }
    const url = _getAudioUrl(saved.bookSlug, saved.chapter);
    popupAudioEl.src = url;
    popupAudioEl.load();
    // გამოვაჩინოთ მინი ფლეიერი (პაუზაში - მომხმარებელმა თავად ჩართოს)
    _showMiniPlayer();
  }
  tryRestore();
})();

function openAudioPopup(book, bookName) {
  if (!audioMap || !audioMap[book.slug]) {
    loadAudioMap().then(() => _openAudioPopup(book, bookName));
  } else {
    _openAudioPopup(book, bookName);
  }
}

function _openAudioPopup(book, bookName) {
  if (!audioMap || !audioMap[book.slug]) return;

  popupBook = book;
  popupBook.name = bookName || book.name;
  popupChapters = book.chapters.filter(ch => hasAudio(book.slug, ch));

  if (popupChapters.length === 0) return;

  // თუ უკვე ვუკრით ამ წიგნის რომელიმე თავს - იმ თავიდან დავიწყოთ
  popupCurrentIdx = 0;
  if (currentAudioBook === book.slug && currentAudioChapter) {
    const idx = popupChapters.indexOf(String(currentAudioChapter));
    if (idx >= 0) popupCurrentIdx = idx;
  }

  // დავხუროთ ძველი პლეიერი და გავხსნათ popup
  stopAudio();
  stopAudioExtra();

  const overlay = document.getElementById('audio-popup-overlay');
  if (!overlay) return;

  // შევავსოთ ინფო
  document.getElementById('audio-popup-book-name').textContent = popupBook.name;
  _updatePopupChapterLabel();

  // შევქმნათ ფლეილისტი
  _renderPopupPlaylist();

  // შევქმნათ audio ელემენტი
  if (!popupAudioEl) {
    popupAudioEl = new Audio();
    popupAudioEl.addEventListener('loadedmetadata', () => _updatePopupTime());
    popupAudioEl.addEventListener('timeupdate', () => { _updatePopupProgress(); if (!popupAudioEl.paused && popupPlayState !== 'playing') { popupPlayState = 'playing'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); } });
    popupAudioEl.addEventListener('ended', () => audioPopupNext());
    popupAudioEl.addEventListener('play', () => { popupPlayState = 'playing'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); _startPopupPosSave(); });
    popupAudioEl.addEventListener('playing', () => { popupPlayState = 'playing'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); _startPopupPosSave(); });
    popupAudioEl.addEventListener('pause', () => { popupPlayState = 'paused'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); _stopPopupPosSave(); _savePopupPos(); });
    popupAudioEl.addEventListener('waiting', () => { popupPlayState = 'loading'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); });
    popupAudioEl.addEventListener('canplay', () => { if (!popupAudioEl.paused) { popupPlayState = 'playing'; _updatePopupPlayBtn(); _renderPopupPlaylist(); _updateMiniPlayer(); } });
  }

  overlay.style.display = 'flex';
  _loadPopupChapter(popupCurrentIdx);
}

function _updatePopupChapterLabel() {
  const el = document.getElementById('audio-popup-chapter-label');
  if (el) el.textContent = `თავი ${popupChapters[popupCurrentIdx]}`;
}

function _renderPopupPlaylist() {
  const container = document.getElementById('audio-popup-playlist');
  if (!container) return;
  container.innerHTML = '';
  popupChapters.forEach((ch, i) => {
    const item = document.createElement('div');
    item.className = 'audio-popup-playlist-item' + (i === popupCurrentIdx ? ' active' : '');
    // იკონი: მიმდინარე თავი თუ უკრებს → ⏸, თუ პაუზაშია → ▶, სხვა თავი → ▶
    let icon = '▶';
    let statusText = '';
    if (i === popupCurrentIdx) {
      if (popupPlayState === 'playing') { icon = '⏸'; statusText = 'უკრებს...'; }
      else if (popupPlayState === 'paused') { icon = '▶'; statusText = 'პაუზა'; }
      else if (popupPlayState === 'loading') { icon = '⏳'; statusText = 'იტვირთება...'; }
    }
    // ჩამოსატვირთი ლინკი
    const dlUrl = _getAudioUrl(popupBook.slug, ch);
    const dlName = `${popupBook.name} - თავი ${ch}.mp3`;
    item.innerHTML = `
      <span class="audio-popup-playlist-item-num">
        <span class="audio-popup-playlist-item-icon">${icon}</span>
        თავი ${ch}
      </span>
      <span class="audio-popup-playlist-item-actions">
        ${statusText ? `<span class="audio-popup-playlist-item-playing">${statusText}</span>` : ''}
        <a href="${dlUrl}" download="${dlName}" class="audio-popup-download" title="ჩამოტვირთვა" onclick="event.stopPropagation()">⬇</a>
      </span>
    `;
    item.onclick = () => {
      // თუ იგივე თავია - მხოლოდ play/pause გადართვა
      if (i === popupCurrentIdx) {
        audioPopupTogglePlay();
      } else {
        popupCurrentIdx = i;
        _loadPopupChapter(i);
        audioPopupTogglePlay();
      }
    };
    container.appendChild(item);
  });
}

function _loadPopupChapter(idx) {
  if (idx < 0 || idx >= popupChapters.length) return;
  popupCurrentIdx = idx;
  const ch = popupChapters[idx];
  const url = _getAudioUrl(popupBook.slug, ch);
  popupAudioEl.src = url;
  popupAudioEl.load();
  _updatePopupChapterLabel();
  _renderPopupPlaylist();
  _updatePopupTime();
  _updatePopupProgress();
}

function audioPopupTogglePlay() {
  if (!popupAudioEl || !popupAudioEl.src) {
    _loadPopupChapter(popupCurrentIdx);
  }
  if (popupPlayState === 'playing') {
    popupAudioEl.pause();
    popupPlayState = 'paused';
  } else {
    // popup-ის დაკვრამდე - inline აუდიოს შეჩერება (არ დაუკრას 2 ფაილი ერთად)
    _pauseInlineAudio();
    popupAudioEl.play().catch(e => console.error('Audio play error:', e));
    popupPlayState = 'loading';
  }
  _updatePopupPlayBtn();
  _renderPopupPlaylist();
  _updateMiniPlayer();
}

// inline (თავის) აუდიოს შეჩერება - როცა popup იწყებს დაკვრას
function _pauseInlineAudio() {
  if (typeof audioEl !== 'undefined' && audioEl && !audioEl.paused) {
    audioEl.pause();
    audioPlayState = 'paused';
    updateAudioPlayerUI();
  }
  if (typeof audioElExtra !== 'undefined' && audioElExtra && !audioElExtra.paused) {
    audioElExtra.pause();
    extraPlayState = 'paused';
    updateAudioPlayerUI();
  }
}

function _updatePopupPlayBtn() {
  const btn = document.getElementById('audio-popup-play');
  if (!btn) return;
  const icons = { stopped: '▶', playing: '⏸', paused: '▶', loading: '⏳' };
  btn.textContent = icons[popupPlayState] || '▶';
}

function audioPopupPrev() {
  if (popupCurrentIdx > 0) {
    _loadPopupChapter(popupCurrentIdx - 1);
    audioPopupTogglePlay();
  }
}

function audioPopupNext() {
  if (popupCurrentIdx < popupChapters.length - 1) {
    _loadPopupChapter(popupCurrentIdx + 1);
    audioPopupTogglePlay();
  } else {
    // ბოლო თავია - გავაჩეროთ
    popupPlayState = 'stopped';
    _updatePopupPlayBtn();
    _renderPopupPlaylist();
  }
}

function _updatePopupTime() {
  const cur = popupAudioEl.currentTime || 0;
  const dur = popupAudioEl.duration || 0;
  const curEl = document.getElementById('audio-popup-time-current');
  const durEl = document.getElementById('audio-popup-time-total');
  if (curEl) curEl.textContent = _formatPopupTime(cur);
  if (durEl) durEl.textContent = _formatPopupTime(dur);
}

function _updatePopupProgress() {
  const cur = popupAudioEl.currentTime || 0;
  const dur = popupAudioEl.duration || 0;
  const pct = dur > 0 ? (cur / dur) * 100 : 0;
  const fill = document.getElementById('audio-popup-progress-fill');
  const handle = document.getElementById('audio-popup-progress-handle');
  if (fill) fill.style.width = pct + '%';
  if (handle) handle.style.left = pct + '%';
  _updatePopupTime();
}

function audioPopupSeek(event) {
  if (!popupAudioEl.duration) return;
  const bar = document.getElementById('audio-popup-progress');
  const rect = bar.getBoundingClientRect();
  const pct = (event.clientX - rect.left) / rect.width;
  popupAudioEl.currentTime = pct * popupAudioEl.duration;
  _updatePopupProgress();
}

function _formatPopupTime(sec) {
  if (!sec || isNaN(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function audioPopupToggleSpeed(event) {
  event.stopPropagation();
  const menu = document.getElementById('audio-popup-speed-menu');
  if (menu) menu.style.display = menu.style.display === 'none' ? 'flex' : 'none';
}

function audioPopupSetSpeed(rate) {
  if (popupAudioEl) popupAudioEl.playbackRate = rate;
  const btn = document.getElementById('audio-popup-speed-btn');
  if (btn) btn.textContent = rate + 'x';
  const menu = document.getElementById('audio-popup-speed-menu');
  if (menu) menu.style.display = 'none';
}

function audioPopupSetVolume(val) {
  if (popupAudioEl) {
    popupAudioEl.volume = val / 100;
    if (val > 0) popupPrevVolume = val / 100;
  }
  _updateVolumeIcon(val);
}

function audioPopupToggleMute() {
  if (!popupAudioEl) return;
  if (popupAudioEl.volume > 0) {
    popupPrevVolume = popupAudioEl.volume;
    popupAudioEl.volume = 0;
    const slider = document.getElementById('audio-popup-volume');
    if (slider) slider.value = 0;
    _updateVolumeIcon(0);
  } else {
    popupAudioEl.volume = popupPrevVolume || 1;
    const slider = document.getElementById('audio-popup-volume');
    if (slider) slider.value = (popupPrevVolume || 1) * 100;
    _updateVolumeIcon((popupPrevVolume || 1) * 100);
  }
}

function _updateVolumeIcon(val) {
  const icon = document.getElementById('audio-popup-volume-icon');
  if (!icon) return;
  if (val == 0) icon.textContent = '🔇';
  else if (val < 50) icon.textContent = '🔉';
  else icon.textContent = '🔊';
}

function closeAudioPopup(event) {
  if (event && event.target && event.target.id !== 'audio-popup-overlay') return;
  const overlay = document.getElementById('audio-popup-overlay');
  if (overlay) overlay.style.display = 'none';
  overlay.classList.remove('minimized-mode');
  const mini = document.getElementById('audio-mini-player');
  if (mini) mini.remove();
  if (popupAudioEl) {
    popupAudioEl.pause();
    popupPlayState = 'stopped';
  }
  _stopPopupPosSave();
  _clearPopupPos();
}

// ცარიელ სივრცეზე დაჭერა - მინიმიზაცია (არ ითიშება!)
function minimizeAudioPopup(event) {
  if (!event || !event.target || event.target.id !== 'audio-popup-overlay') return;
  _minimizePopup();
}

// მინიმიზაცია - overlay იმალება, მინი ფლეიერი ჩნდება ქვედა მარცხენა კუთხეში
function _minimizePopup() {
  const overlay = document.getElementById('audio-popup-overlay');
  if (!overlay) return;
  overlay.style.display = 'none';
  overlay.classList.add('minimized-mode');
  _showMiniPlayer();
}

// მინი ფლეიერის ჩვენება
function _showMiniPlayer() {
  let mini = document.getElementById('audio-mini-player');
  if (!mini) {
    mini = document.createElement('div');
    mini.id = 'audio-mini-player';
    mini.className = 'audio-mini-player';
    mini.innerHTML = `
      <button class="audio-mini-play" id="audio-mini-play" onclick="audioPopupTogglePlay()" title="დაკვრა/პაუზა">▶</button>
      <div class="audio-mini-info" onclick="_restorePopup()" title="გაშვება">
        <span class="audio-mini-title" id="audio-mini-title"></span>
        <span class="audio-mini-chapter" id="audio-mini-chapter"></span>
      </div>
      <button class="audio-mini-expand" onclick="_restorePopup()" title="გაშვება">⤢</button>
      <button class="audio-mini-close" onclick="closeAudioPopup()" title="გამორთვა">✕</button>
    `;
    document.body.appendChild(mini);
  }
  _updateMiniPlayer();
}

// მინი ფლეიერის განახლება
function _updateMiniPlayer() {
  const mini = document.getElementById('audio-mini-player');
  if (!mini) return;
  const playBtn = document.getElementById('audio-mini-play');
  const titleEl = document.getElementById('audio-mini-title');
  const chapterEl = document.getElementById('audio-mini-chapter');
  if (playBtn) {
    const icons = { stopped: '▶', playing: '⏸', paused: '▶', loading: '⏳' };
    playBtn.textContent = icons[popupPlayState] || '▶';
  }
  if (titleEl && popupBook) titleEl.textContent = popupBook.name;
  if (chapterEl) chapterEl.textContent = `თავი ${popupChapters[popupCurrentIdx] || ''}`;
}

// მინი ფლეიერიდან აღდგენა (სრულ ფლეიერზე დაბრუნება)
function _restorePopup() {
  const overlay = document.getElementById('audio-popup-overlay');
  if (!overlay) return;
  overlay.classList.remove('minimized-mode');
  overlay.style.display = 'flex';
  const mini = document.getElementById('audio-mini-player');
  if (mini) mini.remove();
}

// მინიმიზაცია - ფლეილისტის დამალვა/ჩვენება (სრულ ფლეიერში)
function toggleAudioPopupMinimize() {
  _minimizePopup();
}

// === აუდიოს ჩამოსატვირთი სია (About გვერდისთვის) ===
function toggleAudioDownloadList() {
  const list = document.getElementById('audio-download-list');
  const toggle = document.getElementById('audio-download-toggle');
  if (!list) return;
  if (list.style.display === 'none') {
    list.style.display = 'flex';
    if (toggle) toggle.classList.add('expanded');
    if (!list.children.length) renderAudioDownloadList();
  } else {
    list.style.display = 'none';
    if (toggle) toggle.classList.remove('expanded');
  }
}

function renderAudioDownloadList() {
  const container = document.getElementById('audio-download-list');
  if (!container) return;
  if (!audioMap) {
    loadAudioMap().then(() => _renderAudioDownloadList(container));
  } else {
    _renderAudioDownloadList(container);
  }
}

function _renderAudioDownloadList(container) {
  if (!audioMap || !BOOKS) {
    setTimeout(() => _renderAudioDownloadList(container), 200);
    return;
  }
  container.innerHTML = '';

  // წიგნების სია (BOOKS.old + BOOKS.new)
  const allBooks = [...(BOOKS.old || []), ...(BOOKS.new || [])];

  allBooks.forEach(book => {
    if (!audioMap[book.slug]) return;

    const chapters = Object.keys(audioMap[book.slug])
      .filter(k => k !== 'intro')
      .map(k => parseInt(k))
      .sort((a, b) => a - b);

    if (chapters.length === 0) return;

    const bookDiv = document.createElement('div');
    bookDiv.className = 'audio-download-book';

    const header = document.createElement('div');
    header.className = 'audio-download-book-header';
    const apocryphalTag = book.apocryphal ? '<span class="audio-download-apocryphal-tag" title="არაკანონიკური (აპოკრიფი)">არაკანონიკური</span>' : '';
    header.innerHTML = `<span class="audio-download-book-name">${book.name} ${apocryphalTag}</span><span class="audio-download-book-meta"><span class="audio-download-book-count">${chapters.length} თავი</span><button class="audio-download-book-all" onclick="event.stopPropagation(); _downloadChaptersSequential('${book.slug}', '${book.name.replace(/'/g, "\\'")}', [${chapters.join(',')}])" title="მთელი წიგნის ჩამოტვირთვა">⬇⬇ ყველა</button></span>`;
    if (book.apocryphal) bookDiv.classList.add('apocryphal');
    header.onclick = () => {
      bookDiv.classList.toggle('expanded');
    };
    bookDiv.appendChild(header);

    const list = document.createElement('div');
    list.className = 'audio-download-chapters';
    chapters.forEach(ch => {
      const url = _getAudioUrl(book.slug, ch);
      const dlName = `${book.name} - თავი ${ch}.mp3`;
      const link = document.createElement('a');
      link.href = url;
      link.download = dlName;
      link.className = 'audio-download-chapter-link';
      link.innerHTML = `<span>თავი ${ch}</span><span class="audio-download-icon">⬇</span>`;
      link.onclick = (e) => e.stopPropagation();
      list.appendChild(link);
    });
    bookDiv.appendChild(list);

    container.appendChild(bookDiv);
  });
}

// Esc-ით დახურვა
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const overlay = document.getElementById('audio-popup-overlay');
    if (overlay && overlay.style.display !== 'none') {
      closeAudioPopup();
    }
  }
});
