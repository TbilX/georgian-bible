# ბიბლია იკითხე - სრული აღწერა

## რა გვაქვს

ქართული ბიბლიის ვებ-აპლიკაცია - ძველი და ახალი ქართული თარგმანები + ბიბლიის ორიგინალი ბერძნული ტექსტი (Septuagint / SBLGNT), AI ძიებით.

---

## მონაცემები

| პარამეტრი | მნიშვნელობა |
|---|---|
| სულ წიგნები | **78** (66 კანონიკური + 12 არაკანონიკური) |
| სულ მუხლები | **37,562** |
| კანონიკური | 66 წიგნი · 31,473 მუხლი |
| ძველი აღთქმა | 39 წიგნი · 23,519 მუხლი |
| ახალი აღთქმა | 27 წიგნი · 7,954 მუხლი |
| არაკანონიკური (აპოკრიფი) | 12 წიგნი · 6,089 მუხლი |

### თარგმანების წყარო
- **ძველი ქართული:** მცხეთური ხელნაწერი + ბიბლიის თარგმნის ინსტიტუტი
- **ახალი ქართული:** გიორგი მთაწმინდელისეული + ბაჩანა ბრეგვაძე
- **ბიბლიის ორიგინალი (ბერძნული):** Septuagint (Rahlfs) ძვ. აღთქმა + SBL Greek NT ახ. აღთქმა - ~35,700 მუხლი

### წიგნების კლასიფიკაცია
- კანონიკური vs არაკანონიკური - `orthodoxy.ge`-ის მიხედვით
- არაკანონიკური წიგნები (12): II ეზრა, III ეზრა, ტობითი, ივდითი, სიბრძნე სოლომონისა, სიბრძნე ზირაქისა, ბარუქი, ეპისტოლე იერემიასი, I-IV მაკაბელთა
- - რომაული ნუმერაცია (I, II, III, IV) წიგნების სახელებში
- კანონიკური თანმიმდევრობა (არა ანბანის მიხედვით)

---

## ძიება

### ორი რეჟიმი
1. **აზრით** (AI) - სემანტიკური ძიება, აზრის მიხედვით
2. **სიტყვით** (BM25) - ლექსიკური, ზუსტი სიტყვებით

### AI ძიების არქიტექტურა (4 ფენა)
1. **BM25** (ლექსიკური) - ზუსტი სიტყვები, ტოკენიზაცია ქართულისთვის
2. **LaBSE Dense** (სემანტიკური) - 768-განზომილებიანი ვექტორები, 37,562 მუხლი
3. **RRF Fusion** - ორი რანჟირებული სიის გაერთიანება (Reciprocal Rank Fusion, k=60)
4. **Cross-Encoder Reranking** - საბოლოო ზუსტი რანჟირება (mmarco-mMiniLMv2, მრავალენოვანი)

### ძიების ფილტრები
- **აღთქმის მიხედვით:** ყველა / ძველი / ახალი
- **წიგნის მიხედვით:** კონკრეტული წიგნი
- **რაოდენობა:** 10 / 20 / 50 / 100 შედეგი
- **ზუსტი რანჟირება:** ჩა/გამორთვა

---

## ნავიგაცია

- **საიდბარი:** ძველი და ახალი აღთქმა, წიგნების სია
- **წიგნების ძიება:** ორივე აღთქმაში ფილტრაცია სახელით
- **თავების გახსნა/დახურვა:** წიგნზე დაკლიკებით
- **სწრაფი ნავიგაცია:** თავების ნომრები თავის ხედში
- **წინა/მომდევნო თავი:** ღილაკები თავის ზედა ნაწილში
- **წინა/მომდევნო წიგნი:** ბოლო თავიდან გადადის მომდევნო წიგნის პირველ თავზე

---

## მუხლების ხედი

- **პარალელური ხედი:** ძველი და ახალი ქართული გვერდიგვერდ
- **ცალკე ხედები:** მხოლოდ ძველი ან მხოლოდ ახალი თარგმანი
- **ორიგინალის ხედი:** ☑️ "ორიგინალი" ჩართვისას ბერძნული ტექსტი ემატება მესამე სვეტად - ყველა წიგნში
- **მუხლის პოპაპი:** დაკლიკებით გამოდის ცალკე ფანჯარა
  - 📋 კოპირება
  - 🔖 სანიშნე (კომენტარით)
  - 📤 გაზიარება (Web Share API ან კოპირება)

---

## სანიშნეები

- **ლოკალური შენახვა:** `localStorage` (ბრაუზერში)
- **ჭიკარტის ვიზუალი:** ჩანიშნულ მუხლებზე მარცხენა ზოლი და 🔖 იკონო
- **კომენტარი:** თითოეულ სანიშნეზე შესაძლებელია კომენტარის დართვა
- **კომენტარის რედაქტირება:** ✏️ ღილაკი სანიშნეების პანელში
- **მოხსნის დასტური:** ყოველ მოხსნამდე გამოდის შეკითხვა
- **სწრაფი მოხსნა:** 🔖 იკონოზე დაკლიკება პირდაპირ მოხსნის სანიშნეს
- **ექსპორტი:** 💾 ფაილში შენახვა (JSON)
- **იმპორტი:** 📂 ფაილიდან აღდგენა (დუბლიკატების გარეშე)
- **მთავარ გვერდზე ბლოკი:** სანიშნეების დინამიკური ბარათები, დაჯგუფებული წიგნი+თავი

---

## ინტერფეისი

- **ღამის რეჟიმი:** 🌙 ღილაკი, შენახული localStorage-ში
- **შრიფტის ზომა:** Aa ღილაკი, შენახული localStorage-ში
- **მობილური მხარდაჭერა:** რესპონსიული დიზაინი, საიდბარის toggle
- **PWA:** manifest.json, theme-color
- **ტოსტები:** შეტყობინებები ოპერაციების შესახებ

---

## API endpoints

| Endpoint | ფუნქცია |
|---|---|
| `GET /` | მთავარი გვერდი |
| `GET /api/books` | წიგნების სია |
| `GET /api/chapter/<slug>/<n>` | თავის მუხლები |
| `GET /api/verse/<slug>/<ch>/<v>` | ერთი მუხლი |
| `GET /api/search/ai?q=...` | AI ძიება (hybrid + rerank) |
| `GET /api/search/keyword?q=...` | სიტყვიერი ძიება (BM25) |
| `GET /api/search/hybrid?q=...` | AI ძიების alias |
| `GET /api/stats` | სტატისტიკა |

---

## ტექნოლოგიები

| კომპონენტი | ტექნოლოგია |
|---|---|
| Backend | Flask (Python) |
| AI მოდელები | sentence-transformers (LaBSE, Cross-Encoder) |
| ძიება | BM25 + LaBSE + RRF + Cross-Encoder |
| Frontend | HTML + CSS + JavaScript (vanilla) |
| მონაცემები | JSON + NumPy (.npz) + Pickle |
| შენახვა | localStorage (სანიშნეები, თემა, შრიფტი) |

---

## ფაილების სტრუქტურა

```
ბიბლია იკითხე/              273MB
├── server.py                  Flask სერვერი (486 ხაზი)
├── static/                    ვებ-ფრონტენდი
│   ├── index.html             181 ხაზი
│   ├── app.js                 792 ხაზი (40 ფუნქცია)
│   └── style.css              862 ხაზი
├── data/          242MB       მონაცემები + ინდექსები
│   ├── verses.json            37,562 მუხლი
│   ├── verse_index.json       მეტამონაცემები
│   ├── embeddings_labse.npz   768-dim × 37,562
│   └── bm25_index.pkl         BM25 ინდექსი
├── source_html/   31MB        საწყისი HTML (1390 ფაილი)
├── extract_bible.py           HTML → verses.json
├── build_index.py             embeddings + verse_index
├── build_hybrid_index.py      BM25 + LaBSE
└── fix_names.py               სახელების გასწორება
```

სულ **3,444 ხაზი** კოდი.

---

## გაშვება

```bash
cd "ბიბლია იკითხე"
python3 server.py
```

ბრაუზერში: http://localhost:5000

---

# Read the Bible - full description

## What it is

Georgian Bible web application - old and new Georgian translations plus the original Greek text of the Bible (Septuagint / SBLGNT), with AI search.

---

## Data

| Parameter | Value |
|---|---|
| Total books | **78** (66 canonical + 12 non-canonical) |
| Total verses | **37,562** |
| Canonical | 66 books · 31,473 verses |
| Old Testament | 39 books · 23,519 verses |
| New Testament | 27 books · 7,954 verses |
| Non-canonical (Apocrypha) | 12 books · 6,089 verses |

### Translation sources
- **Old Georgian:** Mtskheta manuscript + Bible Translation Institute
- **New Georgian:** Giorgi Mtatsmindeli + Bachana Bregvadze
- **Bible original (Greek):** Septuagint (Rahlfs) for OT + SBL Greek NT for NT - ~35,700 verses

### Book classification
- Canonical vs non-canonical - according to `orthodoxy.ge`
- Non-canonical books (12): II Ezra, III Ezra, Tobit, Judith, Wisdom of Solomon, Wisdom of Sirach, Baruch, Epistle of Jeremiah, I-IV Maccabees
- Roman numerals (I, II, III, IV) in book titles
- Canonical order (not alphabetical)

---

## Search

### Two modes
1. **By meaning** (AI) - semantic search, finds by idea rather than exact words
2. **By word** (BM25) - lexical search with exact words

### AI search architecture (4 layers)
1. **BM25** (lexical) - exact words, Georgian-aware tokenization
2. **LaBSE Dense** (semantic) - 768-dimensional vectors, 37,562 verses
3. **RRF Fusion** - merges two ranked lists (Reciprocal Rank Fusion, k=60)
4. **Cross-Encoder Reranking** - final precise ranking (mmarco-mMiniLMv2, multilingual)

### Search filters
- **By testament:** all / old / new
- **By book:** specific book
- **Amount:** 10 / 20 / 50 / 100 results
- **Exact ranking:** on/off

---

## Navigation

- **Sidebar:** Old and New Testament book lists
- **Book search:** filter by name in both testaments
- **Expand/collapse chapters:** click on a book
- **Quick navigation:** chapter numbers in the chapter view
- **Previous/next chapter:** buttons at the top of the chapter
- **Previous/next book:** from the last chapter it moves to the next book's first chapter

---

## Verse view

- **Parallel view:** old and new Georgian side by side
- **Single views:** only old or only new translation
- **Original view:** when the "ორიგინალი" checkbox is enabled, the Greek text appears as a third column in every book
- **Verse popup:** click a verse to open a separate window
  - Copy
  - Bookmark (with comment)
  - Share (Web Share API or copy)

---

## Bookmarks

- **Local storage:** `localStorage` (in the browser)
- **Visual marker:** bookmarked verses get a left border and a pin icon
- **Comment:** each bookmark can have a comment
- **Comment editing:** pencil button in the bookmarks panel
- **Removal confirmation:** a prompt appears before every removal
- **Quick removal:** clicking the pin icon removes the bookmark directly
- **Export:** save to file (JSON)
- **Import:** restore from file (no duplicates)
- **Home page block:** dynamic bookmark cards grouped by book+chapter

---

## Interface

- **Dark mode:** moon button, saved in localStorage
- **Font size:** Aa button, saved in localStorage
- **Mobile support:** responsive design, sidebar toggle
- **PWA:** manifest.json, theme-color
- **Toasts:** operation notifications

---

## API endpoints

| Endpoint | Function |
|---|---|
| `GET /` | Home page |
| `GET /api/books` | Book list |
| `GET /api/chapter/<slug>/<n>` | Chapter verses |
| `GET /api/verse/<slug>/<ch>/<v>` | Single verse |
| `GET /api/search/ai?q=...` | AI search (hybrid + rerank) |
| `GET /api/search/keyword?q=...` | Keyword search (BM25) |
| `GET /api/search/hybrid?q=...` | AI search alias |
| `GET /api/stats` | Statistics |

---

## Technologies

| Component | Technology |
|---|---|
| Backend | Flask (Python) |
| AI models | sentence-transformers (LaBSE, Cross-Encoder) |
| Search | BM25 + LaBSE + RRF + Cross-Encoder |
| Frontend | HTML + CSS + JavaScript (vanilla) |
| Data | JSON + NumPy (.npz) + Pickle |
| Storage | localStorage (bookmarks, theme, font) |

---

## File structure

```
ბიბლია იკითხე/              273MB
├── server.py                  Flask server (486 lines)
├── static/                    Web frontend
│   ├── index.html             181 lines
│   ├── app.js                 792 lines (40 functions)
│   └── style.css              862 lines
├── data/          242MB       Data + indexes
│   ├── verses.json            37,562 verses
│   ├── verse_index.json       Metadata
│   ├── embeddings_labse.npz   768-dim × 37,562
│   └── bm25_index.pkl         BM25 index
├── source_html/   31MB        Source HTML (1390 files)
├── extract_bible.py           HTML → verses.json
├── build_index.py             embeddings + verse_index
├── build_hybrid_index.py      BM25 + LaBSE
└── fix_names.py               Name fixes
```

Total **3,444 lines** of code.

---

## Running

```bash
cd "ბიბლია იკითხე"
python3 server.py
```

In the browser: http://localhost:5000

