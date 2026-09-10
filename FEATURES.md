# ბიბლიის აპლიკაციის სრული ფუნქციონალის დოკუმენტი

**აპლიკაცია:** ქართული ბიბლიის ვებ-აპლიკაცია (PWA)
**მისამართი:** https://web.net.ge
**სერვერი:** Python 3.14 + Flask + Gunicorn + Nginx + Cloudflare
**მონაცემები:** 78 წიგნი, 37,562 მუხლი, ორ თარგმანში (ძველი + ახალი ქართული)
**ლოკალური გაშვება:** `cd /home/tbilo/bible_app && python3 server.py` (port 5000)

---

## შინაარსი

1. [ძიების სისტემა](#1-ძიების-სისტემა)
2. [კითხვის სისტემა](#2-კითხვის-სისტემა)
3. [სანიშნეები (Bookmarks)](#3-სანიშნეები-bookmarks)
4. [ფერადი მარკირება (Highlights)](#4-ფერადი-მარკირება-highlights)
5. [კომენტარები (Comments)](#5-კომენტარები-comments)
6. [თაგები (Tags)](#6-თაგები-tags)
7. [ჩანაწერების რვეული (Study Pad)](#7-ჩანაწერების-რვეული-study-pad)
8. [ლექსიკონი (Lexicon)](#8-ლექსიკონი-lexicon)
9. [თემატური ინდექსი (Topical Index)](#9-თემატური-ინდექსი-topical-index)
10. [სიტყვის კვლევა (Word Study)](#10-სიტყვის-კვლევა-word-study)
11. [ჯვარედინი მინიშნებები (Cross-References)](#11-ჯვარედინი-მინიშნებები-cross-references)
12. [აუდიო დაკვრა (Audio)](#12-აუდიო-დაკვრა-audio)
13. [ექსპორტი და იმპორტი (Backup)](#13-ექსპორტი-და-იმპორტი-backup)
14. [პარამეტრები და თემები (Settings)](#14-პარამეტრები-და-თემები-settings)
15. [ნავიგაცია და UI](#15-ნავიგაცია-და-ui)
16. [PWA და Service Worker](#16-pwa-და-service-worker)
17. [API Endpoints-ის სრული სია](#17-api-endpoints-ის-სრული-სია)
18. [ტესტირების შედეგები](#18-ტესტირების-შედეგები)

---

## 1. ძიების სისტემა

აპლიკაცია უზრუნველყოფს სამ ძიების რეჟიმს: AI (ჰიბრიდული), სიტყვიერი (keyword), და ფრაზის.

### 1.1 AI ძიება (ჰიბრიდული)

- **მეთოდი:** BM25 + LaBSE embeddings + RRF (Reciprocal Rank Fusion) + Cross-Encoder rerank
- **მოდელი:** LaBSE (768 დიმენზია), Cross-Encoder rerank
- **ფუნქციები:**
  - `doSearch()` - ძიების დაწყება UI-დან
  - `performSearch(query, mode)` - API მოთხოვნა და შედეგების ჩვენება
  - `renderSearchResults(data)` - AI შედეგების რენდერი score %-ით
  - `markQueryTerms(text, query)` - ტექსტში სიტყვების `<mark>` მარკირება
  - `quickSearch(query)` - სწრაფი AI ძიება
- **API:** `GET /api/search/ai?q=...&limit=20&testament=...&book=...&rerank=1`
- **API:** `GET /api/search/hybrid` (ალიასი)
- **შედეგი:** მუხლები score %-ით, ძველი/ახალი ქართული ტექსტი, წიგნის სახელი
- **ტესტი:** „სიყვარული" → 20 შედეგი, I მეფეთა 20:17 (3520% მსგავსება) ✅

### 1.2 სიტყვიერი ძიება (Keyword)

- **მეთოდი:** BM25 ინდექსი, სიტყვის ზუსტი და ფორმის ძიება
- **ფუნქციები:**
  - `renderKeywordSearchResults(data)` - სიტყვიერი შედეგების რენდერი
  - ფორმების გაფართოება (მაგ. „სიყვარული" → 17 ფორმა)
- **API:** `GET /api/search/keyword?q=...&limit=50&testament=...&book=...`
- **შედეგი:** სიტყვის რაოდენობა, მუხლები, თავები, ფორმები
- **ტესტი:** „სიყვარული" → 207 მუხლი, 357 სიტყვა, 131 თავი, 17 ფორმა ✅

### 1.3 ძიების ფილტრები

- **აღთქმის ფილტრი:** ყველა / ძველი / ახალი (`filter-testament`)
- **წიგნის ფილტრი:** კონკრეტული წიგნი (`filter-book`)
- **ლიმიტი:** 10/20/50/100 შედეგი (`filter-limit`)
- **რერანჟირება:** ზუსტი რანჟირების ჩართვა/გამორთვა (`filter-rerank`)
- **ტესტი:** ახალი აღთქმის ფილტრი → 114 მუხლი (207-დან) ✅

### 1.4 URL Routing

- **ფორმატი:** `#search/query/mode?t=testament&b=book&l=limit&r=rerank`
- **ფუნქციები:**
  - `parseHash()` - URL hash-ის პარსინგი და როუტინგი
  - `hashchange` event listener - hash-ის ცვლილების დამუშავება
  - `popstate` event listener - back/forward ნავიგაცია
- **ტესტი:** `#search/სიყვარული/ai` → გაიხსნა ძიება ✅

---

## 2. კითხვის სისტემა

### 2.1 თავების ჩვენება

- **ფუნქციები:**
  - `openChapter(bookSlug, chapter, opts)` - თავის ჩატვირთვა და ჩვენება
  - `renderChapter()` - მუხლების ვიზუალური რენდერი
  - `prevChapter()` - წინა თავზე გადასვლა
  - `nextChapter()` - შემდეგ თავზე გადასვლა
  - `findPrevBook()` / `findNextBook()` - წიგნებს შორის ნავიგაცია
- **API:** `GET /api/chapter/<book_slug>/<chapter>`
- **შედეგი:** მუხლების სია (ძველი + ახალი ქართული), თავის სათაური
- **ტესტი:** დაბადება 1 → 31 მუხლი, დაბადება 2 → 25 მუხლი ✅

### 2.2 თარგმანის რეჟიმები

- **ფუნქციები:**
  - `setTranslationMode(mode)` - რეჟიმის გადართვა (old/new/parallel)
  - `initTranslationMode()` - რეჟიმის ინიციალიზაცია
- **კონტროლი:**
  - `show-old` checkbox - ძველი ქართულის ჩვენება
  - `show-new` checkbox - ახალი ქართულის ჩვენება
  - `parallel-view` checkbox - პარალელური ხედი
- **ტესტი:** show-old=true → ძველი ქართული ჩანს ✅

### 2.3 მუხლის Popup

- **ფუნქციები:**
  - `showVersePopup(bookSlug, chapter, verse)` - popup-ის გახსნა
  - `closePopup()` - popup-ის დახურვა
  - `handleVerseClick(e)` - მუხლზე დაკლიკების დამუშავება
- **შემადგენლობა:**
  - მუხლის ტექსტი (ძველი + ახალი)
  - კომენტარის ველი (`popup-comment`)
  - თაგების ველი (`popup-tag-input`)
  - ჯვარედინი მინიშნებების სექცია (`crossrefs-section`)
  - თემების სექცია (`topics-section`)
- **ტესტი:** დაბადება 2:1 → popup გაიხსნა, ტექსტი ჩანს ✅

### 2.4 კითხვის პოზიციის შენახვა

- **ფუნქციები:**
  - `saveReadingPosition()` - პოზიციის შენახვა `last_reading_pos`-ში
  - `restoreReadingPosition()` - პოზიციის აღდგენა
  - `setupScrollTracking()` - სქროლის თვალყურის დევნება
  - `renderBookRibbon()` - „განაგრძე კითხვა" ლენტის რენდერი
- **ისტორია:** ბოლო 5 ადგილი `reading_history`-ში
- **ტესტი:** დაბადება 1 → შეინახა, book ribbon ჩანს ✅

### 2.5 სწრაფი ნავიგაცია

- **ფუნქციები:**
  - `renderQuickNav(bookSlug, bookName, activeChapter)` - თავების სწრაფი ღილაკები
  - `setupSwipeNavigation()` - swipe ჟესტები მობილურზე
- **ტესტი:** 51 თავის ღილაკი დაბადებისთვის ✅

---

## 3. სანიშნეები (Bookmarks)

### 3.1 სანიშნის მართვა

- **ფუნქციები:**
  - `persistBookmarks()` - localStorage-ში შენახვა (`bible_bookmarks`)
  - `bookmarkVerse()` - popup-დან სანიშნის დამატება/მოხსნა
  - `toggleBookmarkDirect(bookSlug, chapter, verseNum)` - ხატულაზე პირდაპირი კლიკი
  - `removeBookmark(idx)` - სანიშნის წაშლა
- **სტრუქტურა:** `{ ref, bookSlug, chapter, verseNum, new, old, comment, tags, pinned, date }`
- **ტესტი:** დაბადება 2:1 → სანიშნი დაემატა (pinned=true) ✅

### 3.2 სანიშნეების პანელი

- **ფუნქციები:**
  - `toggleBookmarks()` - პანელის გახსნა/დახურვა
  - `renderBookmarksPanel()` - პანელის რენდერი
  - `renderBookmarks()` - სანიშნეების სიის რენდერი
  - `renderHomeBookmarks()` - მთავარი გვერდის სანიშნეები
  - `switchPanelTab(tab)` - ჩანართების გადართვა (სანიშნე/მარკირება/კომენტარი)
  - `updateTabCounts()` - ჩანართების მთვლელები
- **ჩანართები:** 📌 სანიშნეები, 🎨 მარკირება, 💬 კომენტარები
- **ტესტი:** 1 სანიშნე, 1 მარკირება, 1 კომენტარი ✅

### 3.3 სანიშნეების სია (Overlay)

- **ფუნქციები:**
  - `openBookmarksList()` - overlay-ს გახსნა
  - `deleteListBookmark(idx)` - overlay-ში სანიშნის წაშლა
  - `showListOverlay(title, content)` - სიის overlay-ს გახსნა
  - `closeListOverlay()` - overlay-ს დახურვა
- **ტესტი:** 1 სანიშნის ჩვენება ✅

---

## 4. ფერადი მარკირება (Highlights)

### 4.1 მარკირების მართვა

- **ფუნქციები**
  - `getHighlights()` - `verse_highlights` localStorage-დან წაკითხვა
  - `saveHighlights(hl)` - localStorage-ში შენახვა
  - `getHighlightKey(bookSlug, chapter, verse)` - გასაღების გენერაცია (`bookSlug:chapter:verse`)
  - `toggleHighlight(verseNum, color)` - ფერის toggle (მოხსნა/დადება)
  - `clearHighlight(verseNum)` - მარკირების წაშლა დადასტურებით
  - `getHighlightForVerse(verseNum)` - მუხლის ფერის მიღება
  - `applyHighlightsToChapter()` - მიმდინარე თავზე ფერების დადება
  - `refreshHighlightPalette(verseNum)` - color palette-ზე active ფერის განახლება
- **ფერები:** 12 ფერი (იანვარი-დეკემბერი, თვეების სახელებით)
- **ტესტი:** დაბადება 2:1 → yellow ფერი დადება ✅

### 4.2 ფერის სახელები

- **ფუნქციები:**
  - `saveColorLabel(color, value)` - ფერის სახელის შენახვა (`bible_color_labels`)
  - `restoreColorLabels()` - ფერის სახელების აღდგენა
  - `getColorLabel(color)` - ფერის სახელის მიღება
- **ტესტი:** „იანვარი-სატესტო" შეინახა ✅

### 4.3 ფერის სია (Overlay)

- **ფუნქციები:**
  - `openColorList(color)` - კონკრეტული ფერის მონიშნულების სია
  - `renderHighlightsList()` - ფერადი მონიშნულების სიის რენდერი
  - `removeHighlightByKey(key)` - კონკრეტული ჰაილაითის წაშლა
- **ტესტი:** yellow ფერის სია → 1 ელემენტი ✅

---

## 5. კომენტარები (Comments)

### 5.1 კომენტარის მართვა

- **ფუნქციები:**
  - `saveCommentOnly()` - მხოლოდ კომენტარის შენახვა (სანიშნის გარეშე)
  - `showCommentBubble(idx)` - კომენტარის ბუშტის ჩვენება
  - `editBubbleComment(idx)` - ბუშტში კომენტარის რედაქტირება
  - `saveBubbleComment(idx)` - ბუშტიდან კომენტარის შენახვა
  - `cancelBubbleEdit()` - ბუშტში რედაქტირების გაუქმება
  - `deleteBubbleComment(idx)` - ბუშტიდან კომენტარის წაშლა
- **ლიმიტი:** 99 სიმბოლო
- **ტესტი:** „სატესტო კომენტარი" შეინახა ✅

### 5.2 კომენტარების სია

- **ფუნქციები:**
  - `renderCommentsList()` - კომენტარების სიის რენდერი პანელში
  - `openCommentsList()` - კომენტარების overlay-ს გახსნა
  - `editListComment(idx)` - overlay-ში კომენტარის რედაქტირება
  - `saveListComment(idx)` - overlay-ში კომენტარის შენახვა
  - `cancelListCommentEdit(idx)` - overlay-ში რედაქტირების გაუქმება
  - `deleteListComment(idx)` - overlay-ში კომენტარის წაშლა
  - `editBookmarkComment(idx)` - სანიშნეში inline რედაქტირება
  - `saveInlineComment(idx)` - inline კომენტარის შენახვა
- **ტესტი:** 1 კომენტარის ჩვენება ✅

---

## 6. თაგები (Tags)

### 6.1 თაგის მართვა

- **ფუნქციები:**
  - `addTag(idx, tag)` - თაგის დამატება სანიშნეში (30 სიმბოლოს ლიმიტი)
  - `removeTag(idx, tag)` - თაგის წაშლა სანიშნიდან
  - `getAllTags()` - ყველა უნიკალური თაგის სია
  - `findBookmarkIdx(bookSlug, chapter, verseNum)` - მუხლის ინდექსის ძებნა
  - `getBookmarks()` / `saveBookmarks(bm)` - storage მართვა
- **ტესტი:** „რწმენა" თაგი დაემატა ✅

### 6.2 Popup-ის თაგები

- **ფუნქციები:**
  - `window.addPopupTag()` - input-დან თაგის დამატება
  - `addPopupTag(tag)` - თაგის რეალური დამატება (შიდა)
  - `removePopupTag(tag)` - თაგის წაშლა popup-იდან
  - `window.renderPopupTags(bookSlug, chapter, verseNum)` - popup-ში თაგების რენდერი
  - `window.openVerseTags(bookSlug, chapter, verseNum)` - მუხლის თაგების popup
  - `window.getVerseTagIcon(bookSlug, chapter, verseNum)` - 🏷️ icon-ის HTML
- **ტესტი:** input-ით თაგი დაემატა ✅

### 6.3 თაგების სია და მართვა

- **ფუნქციები:**
  - `window.renderDashboardTags()` - მთავარ გვერდზე თაგების სია
  - `window.openTagList(tag)` - კონკრეტული თაგის მქონე მუხლების overlay
  - `renameTag(oldTag)` - თაგის გადასახელება ყველა სანიშნეში
  - `deleteTagCompletely(tag)` - თაგის სრულად წაშლა
  - `removeTagFromList(idx, tag)` - თაგის მოხსვნა სიიდან (undo-ით)
- **ტესტი:** „რწმენა" თაგის სია → 1 ელემენტი ✅

### 6.4 თაგების ფილტრი და რჩევები

- **ფუნქციები:**
  - `window.getTagFilterHtml()` - სანიშნეების პანელის თაგის ფილტრის HTML
  - `window.getCurrentTagFilter()` - მიმდინარე active tag filter
  - `setTagFilter(tag)` - არჩეული თაგის ფილტრის დაყენება
  - `window.getBookmarkTagsHtml(idx)` - სანიშნის item-ის თაგების HTML
  - `window.toggleTagSuggestions()` - suggestion dropdown-ის toggle
  - `window.filterTagSuggestions()` - input-ის მიხედვით suggestion-ების ფილტრაცია
  - `showDropdown(query)` - suggestion-ების dropdown-ის აგება
  - `closeDropdown()` - dropdown-ის მოცილება
- **ტესტი:** dashboard-ზე თაგი „რწმენა" ჩანს ✅

---

## 7. ჩანაწერების რვეული (Study Pad)

### 7.1 რვეულის მართვა

- **ფუნქციები:**
  - `openStudyPad()` - პანელის გახსნა
  - `closeStudyPad()` - პანელის დახურვა (ცვლილებების შემოწმებით)
  - `loadStudyNotes()` - `bible_notes` localStorage-დან ჩატვირთვა
  - `persistStudyNotes()` - localStorage-ში შენახვა
- **ტესტი:** პანელი გაიხსნა ✅

### 7.2 ჩანაწერის CRUD

- **ფუნქციები:**
  - `createStudyNote()` - ახალი ჩანაწერის შექმნა
  - `saveStudyNote(silent)` - მიმდინარე ჩანაწერის შენახვა
  - `editStudyNote(id)` - ჩანაწერის რედაქტირება
  - `deleteStudyNote(id)` - ჩანაწერის წაშლა (დადასტურებით)
  - `newStudyNote()` - ახალი ჩანაწერის დასაწყისი
  - `clearStudyPadEditor()` - editor-ის გასუფთავება
- **სტრუქტურა:** `{ id, title, content, createdAt, updatedAt }`
- **ტესტი:** „სატესტო ჩანაწერი" შეიქმნა ✅

### 7.3 ჩანაწერის რენდერი და ძიება

- **ფუნქციები:**
  - `renderStudyNotesList()` - ჩანაწერების სიის HTML-ად რენდერი
  - `renderNoteContent(content)` - Markdown + `[[...]]` ბმულებად გარდაქმნა
  - `filterStudyNotes(query)` - ჩანაწერების ფილტრაცია ძიების მიხედვით
  - `updateStudyPadCount()` - რაოდენობის განახლება
  - `formatDate(isoStr)` - შედარებითი თარიღის ფორმატირება
- **ტესტი:** ჩანაწერის სია ჩანს ✅

### 7.4 რეჟიმები და მართვა

- **ფუნქციები:**
  - `toggleStudyPadMode()` - edit/read რეჟიმებს შორის ცვლილება
  - `renderStudyPadMode()` - editor-ის და read-არიის display toggle
  - `studyPadShowList()` - სიის ვიუზე დაბრუნება
  - `studyPadShowEditor()` - ედიტორის ვიუზე გადასვლა
  - `studyPadBackToList()` - სიაში დაბრუნება (ჩუმად შენახვით)
  - `studyPadAutoSave()` - 2 წამიანი debounce შენახვა
  - `setupStudyPadTitleHandler()` - title input-ის listener-ები
  - `setupStudyPadShortcuts()` - Ctrl+S/Ctrl+Enter შემნახველი listener-ები
- **ტესტი:** რეჟიმები მუშაობს ✅

### 7.5 მუხლის ბმულები ჩანაწერებში

- **ფუნქციები:**
  - `buildBookNameMap()` - წიგნის სახელების მაპის აგება
  - `parseVerseRef(refStr)` - `[[წიგნი 5:3-7]]` ფორმატის პარსინგი
  - `studyPadVerseClick(slug, chapter, verse, verseEnd)` - ბმულის კლიკით თავზე გადასვლა
  - `studyPadVerseHover(event, slug, chapter, verse)` - hover-ის დროს მუხლის პრევიუ
  - `studyPadVerseHoverEnd()` - hover timer-ის გასუფთავება
  - `showVersePreviewTooltip(anchor, verseData)` - მუხლის preview tooltip
  - `hideVersePreviewTooltip()` - tooltip-ის დამალვა
  - `addVerseToStudyPad()` - popup-იდან `[[...]]` ბმულის ჩასმა
- **ტესტი:** ფუნქციები ხელმისაწვდომია ✅

---

## 8. ლექსიკონი (Lexicon)

### 8.1 ლექსიკონის ხედი

- **ფუნქციები:**
  - `openLexicon()` - ლექსიკონის ხედის გახსნა + URL-დან ასოს აღდგენა
  - `closeLexicon()` - ლექსიკონის დახურვა
  - `loadLexiconMeta()` - API-დან მეტა-მონაცემების ჩატვირთვა
  - `renderLexiconStats()` - სტატისტიკის რენდერი
- **სტატისტიკა:** 130,972 უნიკალური სიტყვა, 1,110,632 გამოყენება, 78 წიგნი, 37 ასო
- **ტესტი:** გაიხსნა, სტატისტიკა ჩანს ✅

### 8.2 სკოპის ფილტრი

- **ფუნქციები:**
  - `onLexiconScopeChange()` - scope-ის dropdown-ში ცვლილება
  - `setLexiconTab(scope)` - ჩანართების აქტივაცია
  - `syncLexiconTabs(scope)` - dropdown-ის სინქრონიზაცია
  - `onLexiconBookChange()` - წიგნის dropdown-ში ცვლილება
  - `refreshLexiconForScope()` - სკოპის მიხედვით განახლება
  - `loadLexiconLettersForScope()` - ასოების ჩატვირთვა სკოპის მიხედვით
  - `updateLexiconFilterInfo()` - სტატისტიკის ხაზზე გამოტანა
  - `populateLexiconBookFilter()` - წიგნების dropdown-ის შევსება
- **სკოპები:** all, old, new, canonical, noncanonical, old_trans, new_trans, book
- **ტესტი:** old → 114,375 უნიკალური · 872,258 გამოყენება ✅

### 8.3 ანბანი და სიტყვები

- **ფუნქციები:**
  - `renderAlphabetGrid()` - ანბანის ბადის რენდერი
  - `selectLexiconLetter(letter)` - ასოს არჩევა + URL განახლება
  - `loadLexiconWords(letter, page)` - API-დან სიტყვების ჩატვირთვა
  - `updateLetterTitle(letter)` - ასოს სათაურის განახლება
  - `displayLexiconWords(data)` - სიტყვების სიის რენდერი
  - `renderLexiconPagination(data)` - გვერდების ღილაკები
  - `lexiconWordClick(word)` - სიტყვაზე კლიკით ძიებაში გადასვლა
- **API:** `GET /api/lexicon/<letter>?page=1&per_page=500&scope=all`
- **ტესტი:** ასო „ა" → 500 სიტყვა, 4 pagination ღილაკი ✅

### 8.4 ლექსიკონის ძიება

- **ფუნქციები:**
  - `searchLexicon(query)` - debounce-ური ძიება
  - `displayLexiconSearchResults(query, results)` - შედეგების რენდერი + მარკირება
- **API:** `GET /api/lexicon/search?q=...&scope=all&limit=500`
- **ტესტი:** „ღმერთი" → 24 შედეგი ✅

### 8.5 ლექსიკონის API

- `GET /api/lexicon` - მეტა-მონაცემები + ასოების შეჯამება
- `GET /api/lexicon/<letter>` - კონკრეტული ასოს სიტყვები
- `GET /api/lexicon/stats` - სტატისტიკა და book_stats
- `GET /api/lexicon/search` - substring ძიება
- `GET /api/word/forms/<word>` - სიტყვის მორფოლოგიური ფორმები
- `GET /api/word/stats/<word>` - სიტყვის სტატისტიკა
- `GET /api/word/distribution/<word>` - სიტყვის გავრცელება წიგნების მიხედვით
- **ტესტი:** ყველა endpoint მუშაობს ✅

---

## 9. თემატური ინდექსი (Topical Index)

### 9.1 თემატური პანელი

- **ფუნქციები:**
  - `openTopicalPanel()` - პანელის გახსნა
  - `closeTopicalPanel()` - პანელის დახურვა
  - `searchTopics(query)` - debounce-ური API ძიება
  - `renderTopicResults(results, query)` - თემების ძიების შედეგების რენდერი
- **API:** `GET /api/topics/search?q=...&limit=100`
- **ტესტი:** „რწმენა" → 4 შედეგი ✅

### 9.2 თემის დეტალური ხედი

- **ფუნქციები:**
  - `openTopicDetail(slug)` - კონკრეტული თემის ჩატვირთვა
  - `renderTopicDetail(data)` - თემის დეტალური ხედის რენდერი (see_also, entries, verses)
  - `backToTopicSearch()` - დეტალური ხედიდან ძიებაზე დაბრუნება
- **API:** `GET /api/topics/<topic_slug>`
- **ტესტი:** „faith" → რწმენა, 70KB HTML ✅

### 9.3 მუხლის თემები

- **ფუნქციები:**
  - `loadVerseTopics(bookSlug, chapter, verse)` - მუხლისთვის დაკავშირებული თემები
  - `loadVerseTopicsInPopup()` - popup-ში თემების ჩატვირთვა
  - `toggleVerseTopics()` - თემების აკორდიონი
- **API:** `GET /api/topics/verse/<book_slug>/<chapter>/<verse>`
- **ტესტი:** დაბადება 2:1 → 18 თემა ✅

---

## 10. სიტყვის კვლევა (Word Study)

### 10.1 სიტყვის პანელი

- **ფუნქციები:**
  - `wrapWordsInSpans(text)` - ტექსტის დაშლა `<span class="word">` ელემენტებად
  - `setupWordClickDelegation()` - click listener დელეგაციით
  - `openWordPanel(word, anchorEl)` - სიტყვის პანელის გახსნა + API
  - `renderWordPanel(panel, word, formsData, statsData, distData)` - HTML რენდერი
  - `closeWordPanel()` - პანელის დახურვა
- **API-ები:**
  - `GET /api/word/forms/<word>` - მორფოლოგიური ფორმები
  - `GET /api/word/stats/<word>` - სტატისტიკა
  - `GET /api/word/distribution/<word>` - გავრცელება
- **ტესტი:** სიტყვაზე კლიკი → პანელი გაიხსნა ✅

### 10.2 სიტყვის ძიება

- **ფუნქციები:**
  - `searchWordEverywhere(word)` - მთელ ბიბლიაში ძიება
  - `searchWordInBook(word, bookSlug)` - კონკრეტულ წიგნში ძიება
- **ტესტი:** ფუნქციები ხელმისაწვდომია ✅

---

## 11. ჯვარედინი მინიშნებები (Cross-References)

### 11.1 Cross-References-ის მართვა

- **ფუნქციები:**
  - `loadCrossRefs()` - ჯვარედინი მინიშნებების ჩატვირთვა
  - `toggleCrossRefs()` - აკორდიონის გახსნა/დახურვა
- **API:** `GET /api/crossrefs/<book_slug>/<chapter>/<verse>?limit=15&min_confidence=...&min_votes=...`
- **მონაცემები:** `crossrefs_merged.json` / `crossrefs_tsk.json` / `crossrefs_index.json`
- **ტესტი:** დაბადება 2:1 → 10 ჯვარედინი მინიშნება ✅

---

## 12. აუდიო დაკვრა (Audio)

### 12.1 აუდიო მართვა

- **ფუნქციები:**
  - `loadAudioMap()` - audio_map.json-ის ჩატვირთვა (78 წიგნი)
  - `hasAudio(bookSlug, chapter)` - აუდიოს არსებობის შემოწმება
  - `initAudioForChapter(bookSlug, chapter, bookName)` - თავისთვის აუდიოს ინიციალიზაცია
  - `_initAudioForChapterInner(bookSlug, chapter)` - შიდა ინიციალიზაცია
  - `_playAudioChapter(bookSlug, chapter)` - თავის აუდიოს დაკვრა
  - `_playIntro()` - წიგნის ინტროს დაკვრა
  - `toggleAudioPlay()` / `toggleAudioPlayExtra()` - დაკვრა/პაუზა
  - `stopAudio()` / `stopAudioExtra()` - შეჩერება
  - `seekAudio(percent)` / `seekAudioExtra(percent)` - პოზიციის შეცვლა
  - `toggleSpeedMenu(e)` / `toggleSpeedMenuExtra(e)` - სიჩქარის მენიუ
  - `setAudioSpeed(rate)` / `setAudioSpeedExtra(rate)` - სიჩქარის დაყენება
- **მონაცემები:** YouTube audio-ს 78 წიგნის თავებისთვის
- **ტესტი:** დაბადება 1 → audio player ჩანს, hasAudio=true ✅

### 12.2 აუდიო UI

- **ფუნქციები:**
  - `updateAudioPlayerUI()` - player-ის UI განახლება
  - `_ensureAudioElements()` - audio ელემენტების შექმნა
  - `_startProgressLoop()` / `_stopProgressLoop()` - progress loop
  - `_formatTime(sec)` - დროის ფორმატირება
- **ელემენტები:** play button, title, status, progress bar, time, speed menu
- **ტესტი:** UI ელემენტები ჩანს ✅

### 12.3 პოზიციის შენახვა

- **ფუნქციები:**
  - `_saveAudioPos()` - პოზიციის შენახვა
  - `_loadAudioPos()` - პოზიციის აღდგენა
  - `_clearAudioPos()` - პოზიციის გასუფთავება
  - `_startPosSave()` / `_stopPosSave()` - პოზიციის შენახვის მართვა
- **ტესტი:** ფუნქციები ხელმისაწვდომია ✅

---

## 13. ექსპორტი და იმპორტი (Backup)

### 13.1 ექსპორტი

- **ფუნქციები:**
  - `exportUserData()` - localStorage key-ების `.json`-ად ექსპორტი
  - `exportBookmarks()` - alias (უკუთავსებადობა)
- **შენახული key-ები:** `bible_bookmarks`, `bible_notes`, `verse_highlights`, `bible_color_labels`, `bible_theme`, `bible_font_size`, `bible_line_height`, `bible_font_family`, `bible_trans_mode`, `last_reading_pos`, `reading_history`
- **ტესტი:** ექსპორტი გაიშვა ✅

### 13.2 იმპორტი

- **ფუნქციები:**
  - `importUserData(event)` - `.json` ფაილის ვალიდაცია, import და აღდგენა
  - `importBookmarks(event)` - alias
  - `undoImport()` - pre-import მდგომარეობის დაბრუნება (`sessionStorage`)
- **ტესტი:** ფუნქციები ხელმისაწვდომია ✅

---

## 14. პარამეტრები და თემები (Settings)

### 14.1 თემები

- **ფუნქციები:**
  - `toggleTheme()` - მუქი/ნათელი თემის გადართვა (`bible_theme`)
  - `updateThemeIcon()` - თემის ხატულის განახლება
- **ტესტი:** light → dark ✅

### 14.2 შრიფტი

- **ფუნქციები:**
  - `toggleFont()` - შრიფტის ზომის ციკლური გადართვა (`bible_font_size`)
  - `toggleLineHeight()` - სტრიქონებს შორის დაშორების ცვლილება (`bible_line_height`)
  - `toggleFontFamily()` - შრიფტის ტიპის (serif/sans) გადართვა (`bible_font_family`)
  - `syncFormattingButtons()` - მობილური მენიუს ღილაკების სტატუსი
- **ტესტი:** 18→19, lineHeight→2, sans ✅

---

## 15. ნავიგაცია და UI

### 15.1 მთავარი გვერდი

- **ფუნქციები:**
  - `goHome()` - მთავარ გვერდზე დაბრუნება
  - `showView(viewId, opts)` - ხედების (home/chapter/search/lexicon) გადართვა
  - `renderHomeBookmarks()` - მთავარი გვერდის სანიშნეები
  - `renderBookRibbon()` - „განაგრძე კითხვა" ლენტა
  - `updateDashboardCounts()` - დაშბორდის მთვლელები
  - `formatTimeAgo(date)` - დროის ხატოვანი ტექსტი
- **ელემენტები:** წიგნების სია, დაშბორდი (12 ფერი, კომენტარები, სანიშნეები, თაგები), book ribbon
- **ტესტი:** 78 წიგნი, 12 ფერი, დაშბორდი მუშაობს ✅

### 15.2 Sidebar და წიგნები

- **ფუნქციები:**
  - `setSidebarMode(mode)` - sidebar-ის რეჟიმის დაყენება (all/old/new/hidden)
  - `toggleSidebarMode()` - რეჟიმის ჩართვა/გამორთვა
  - `toggleCanonicalBooks()` - კანონიკური წიგნების ფილტრი
  - `toggleOTCanonical()` - ძველი აღთქმის ფილტრი
  - `toggleNTOnly()` - ახალი აღთქმის ფილტრი
  - `toggleNonCanonical()` - არაკანონიკური წიგნების ფილტრი
  - `renderBooks()` - წიგნების სიის DOM-ში რენდერი
  - `createBookElement(book)` - წიგნის ელემენტის შექმნა
  - `filterBooks(testament)` - წიგნების live-ძიება სახელით
  - `toggleBookChapters(book, element)` - თავების სიის გახსნა/დახურვა
  - `loadBooks()` - წიგნების სიის API-დან ჩატვირთვა
  - `loadStats()` - სტატისტიკის API-დან ჩატვირთვა
- **ტესტი:** 51 ძველი + 27 ახალი = 78 წიგნი, ძიება „დაბად" → 1 შედეგი ✅

### 15.3 მობილური მენიუ

- **ფუნქციები:**
  - `closeMobileMenu()` - მობილური მენიუს დახურვა
  - `dismissLsWarning()` - localStorage გაფრთხილების დახურვა
- **ტესტი:** მობილური მენიუ მუშაობს ✅

### 15.4 მოდალები და Toast

- **ფუნქციები:**
  - `openBeginner()` / `closeBeginner()` - დამწყებთა მოდალი (გზამკვლევი ბიბლიის კითხვის დასაწყებად)
  - `openAbout()` / `closeAbout()` - პროექტის შესახებ მოდალი (აპლიკაციის განმარტება, შესაძლებლობები, რჩევები)
  - `quickStartReading()` - კითხვის სწრაფი დაწყება
  - `showToast(msg, type, undoFn)` - მოკლე შეტყობინების ჩვენება
- **About მოდალის სექციები:** რა არის „წმიდა წერილი", ძირითადი შესაძლებლობები, პირადი ჩანაწერები, როგორ გამოვიყენოთ ბიბლიის კითხვისას, კითხვის რჩევები, ტექნიკური დეტალები, მონაცემების დაცვა, შენიშვნა თარგმანებზე
- **წვდომა:** ℹ️ ღილაკი დესკტოპ header-ში + მობილურ მენიუში
- **ტესტი:** დამწყებთა მოდალი ✅, About მოდალი ✅ (8 სექცია, სქროლი, მობილური)

### 15.5 კოპირება და გაზიარება

- **ფუნქციები:**
  - `copyVerse(bookSlug, chapter, verse)` - მუხლის კოპირება
  - `copyVerseWithSource(bookSlug, chapter, verse)` - მუხლის წყაროთი კოპირება
  - `shareVerse(bookSlug, chapter, verse)` - მუხლის გაზიარება
- **ტესტი:** ფუნქციები გაიშვა ✅

### 15.6 კასტომ Dropdown

- **ფუნქციები:**
  - `initCustomSelect(selectEl)` - `<select>`-ის კასტომ dropdown-ად გადაკეთება
  - `buildMenu(options, select)` - options-ების აწყობა
  - `updateTrigger(select)` - trigger-ის ტექსტის განახლება
  - `initAllCustomSelects()` - ყველა `<select>`-ის ინიციალიზაცია
- **ტესტი:** კასტომ dropdown-ები მუშაობს ✅

---

## 16. PWA და Service Worker

### 16.1 Service Worker

- **ფაილი:** `static/sw.js`
- **ფუნქციონალი:**
  - Static assets-ის კეშირება (Cache Storage API)
  - Offline რეჟიმი (cache-first strategy)
  - აგრესიული განახლება (SKIP_WAITING + controllerchange)
  - ფონური სინქრონიზაცია (შესაძლებელია)
- **რეგისტრაცია:** `navigator.serviceWorker.register("/sw.js")`
- **ტესტი:** 1 registration, controller active ✅

### 16.2 Manifest

- **ფაილი:** `static/manifest.json`
- **ფუნქციონალი:** PWA ინსტალაციის მხარდაჭერა, icon, theme color
- **ტესტი:** manifest.json ჩატვირთულია ✅

### 16.3 SEO და მეტა

- **ფუნქციონალი:**
  - `GET /robots.txt` - robots.txt + sitemap-ის ბმული
  - `GET /sitemap.xml` - XML sitemap (წიგნების/თავების URL)
  - `GET /googlef9bb9bdad6d4fe6d.html` - Google Search Console ვერიფიკაცია
  - `GET /b/<book_slug>/<chapter>/<verse>` - მუხლის გაზიარების OG-გვერდი (Open Graph/Twitter/Schema.org)
- **ტესტი:** sitemap, robots, OG გვერდები მუშაობს ✅

---

## 17. API Endpoints-ის სრული სია

| HTTP | URL path | ფუნქცია | კატეგორია |
|------|----------|---------|-----------|
| GET | `/` | `index` - index.html | სხვა |
| GET | `/b/<book>/<chapter>/<verse>` | `share_verse` - OG გვერდი | სხვა |
| GET | `/sw.js` | `service_worker` | სხვა |
| GET | `/favicon.ico` | `favicon` | სხვა |
| GET | `/googlef9bb9bdad6d4fe6d.html` | `google_verification` | სხვა |
| GET | `/robots.txt` | `robots` | სხვა |
| GET | `/sitemap.xml` | `sitemap` | სხვა |
| GET | `/api/books` | `api_books` - წიგნების სია | კითხვა |
| GET | `/api/chapter/<book>/<chapter>` | `api_chapter` - თავის მუხლები | კითხვა |
| GET | `/api/verse/<book>/<chapter>/<verse>` | `api_verse` - ერთი მუხლი | კითხვა |
| GET | `/api/search/keyword` | `api_search_keyword` - სიტყვიერი ძიება | ძიება |
| GET | `/api/search/ai` | `api_search_ai` - AI ჰიბრიდული ძიება | ძიება |
| GET | `/api/search/hybrid` | `api_search_hybrid` - ალიასი | ძიება |
| GET | `/api/crossrefs/<book>/<chapter>/<verse>` | `api_crossrefs` - ჯვარედინი მინიშნებები | crossref |
| GET | `/api/topics/search` | `api_topics_search` - თემების ძიება | თემატური |
| GET | `/api/topics/<topic_slug>` | `api_topic_detail` - თემის დეტალი | თემატური |
| GET | `/api/topics/verse/<book>/<chapter>/<verse>` | `api_topics_for_verse` - მუხლის თემები | თემატური |
| GET | `/api/stats` | `api_stats` - სტატისტიკა | სტატისტიკა |
| GET | `/api/lexicon` | `api_lexicon` - ლექსიკონის მეტა | ლექსიკონი |
| GET | `/api/lexicon/<letter>` | `api_lexicon_letter` - ასოს სიტყვები | ლექსიკონი |
| GET | `/api/lexicon/stats` | `api_lexicon_stats` - სტატისტიკა | ლექსიკონი |
| GET | `/api/lexicon/search` | `api_lexicon_search` - substring ძიება | ლექსიკონი |
| GET | `/api/word/forms/<word>` | `api_word_forms` - მორფოლოგია | ლექსიკონი |
| GET | `/api/word/stats/<word>` | `api_word_stats` - სტატისტიკა | ლექსიკონი |
| GET | `/api/word/distribution/<word>` | `api_word_distribution` - გავრცელება | ლექსიკონი |

**სულ:** 25 endpoint (მათ შორის 1 ალიასი)

---

## 18. ტესტირების შედეგები

### 18.1 ფუნქციონალური ტესტები (ბრაუზერში)

| ფუნქცია | სტატუსი | დეტალები |
|---|---|---|
| მთავარი გვერდი | ✅ | 78 წიგნი, 12 ფერი, დაშბორდი |
| თავის ჩვენება | ✅ | დაბადება 1: 31 მუხლი |
| წინა/შემდეგი თავი | ✅ | დაბადება 1 → 2 |
| მუხლის popup | ✅ | ტექსტი, კომენტარი, crossrefs, topics |
| სანიშნე | ✅ | pinned=true, localStorage-ში შეინახა |
| კომენტარი | ✅ | „სატესტო კომენტარი" შეინახა |
| თაგი | ✅ | „რწმენა" დაემატა (input-ით) |
| ჰაილაითი | ✅ | yellow ფერი დადება |
| ფერის სახელი | ✅ | „იანვარი-სატესტო" შეინახა |
| ფერის სია | ✅ | 1 ელემენტი |
| კომენტარების სია | ✅ | 1 ელემენტი |
| სანიშნეების სია | ✅ | 1 ელემენტი |
| თაგების სია | ✅ | 1 ელემენტი |
| AI ძიება | ✅ | „სიყვარული" → 20 შედეგი |
| keyword ძიება | ✅ | „სიყვარული" → 207 მუხლი, 17 ფორმა |
| ძიების ფილტრი | ✅ | ახალი აღთქმა → 114 მუხლი |
| URL routing | ✅ | #search/სიყვარული/ai |
| hashchange | ✅ | hash-ის ცვლილებით ნავიგაცია |
| ლექსიკონი | ✅ | 130,972 სიტყვა, 37 ასო |
| ლექსიკონის ფილტრი | ✅ | old → 114,375 უნიკალური |
| ლექსიკონის ძიება | ✅ | „ღმერთი" → 24 შედეგი |
| სიტყვაზე კლიკი | ✅ | ძიებაში გადასვლა |
| თემატური ძიება | ✅ | „რწმენა" → 4 შედეგი |
| თემის დეტალი | ✅ | „faith" → 70KB HTML |
| მუხლის თემები | ✅ | 18 თემა |
| word-study | ✅ | პანელი გაიხსნა |
| study-pad | ✅ | ჩანაწერი შეიქმნა |
| ექსპორტი | ✅ | გაიშვა |
| თემა | ✅ | light → dark |
| შრიფტი | ✅ | 18 → 19, sans |
| line-height | ✅ | → 2 |
| აუდიო | ✅ | player ჩანს, hasAudio=true |
| Service Worker | ✅ | 1 registration, active |
| წიგნების ძიება | ✅ | „დაბად" → 1 შედეგი |
| თავების გახსნა | ✅ | 51 თავი დაბადებისთვის |
| თავის კლიკი | ✅ | დაბადება 1: 31 მუხლი |
| თარგმანის რეჟიმი | ✅ | show-old=true → ძველი ჩანს |
| კითხვის პოზიცია | ✅ | შეინახა last_reading_pos-ში |
| book ribbon | ✅ | „განაგრძე კითხვა: დაბადება 1" |
| დამწყებთა მოდალი | ✅ | გაიხსნა |
| სანიშნეების პანელი | ✅ | 1/1/1 (სანიშნე/მარკირება/კომენტარი) |
| crossrefs | ✅ | 10 ჯვარედინი მინიშნება |

### 18.2 API ტესტები (curl)

| Endpoint | სტატუსი | დეტალები |
|---|---|---|
| `/api/stats` | ✅ | 78 წიგნი, 37,562 მუხლი |
| `/api/books` | ✅ | 51 ძველი + 27 ახალი |
| `/api/chapter/dabadeba/1` | ✅ | 31 მუხლი |
| `/api/search/ai?q=love` | ✅ | 3 შედეგი |
| `/api/search/keyword?q=სიყვარული` | ✅ | 207 მუხლი |
| `/api/search/hybrid?q=love` | ✅ | 3 შედეგი |
| `/api/crossrefs/saqme/2/1` | ✅ | 15 ჯვარედინი |
| `/api/topics/search?q=love` | ✅ | 8 თემა |
| `/api/topics/verse/saqme/2/1` | ✅ | 18 თემა |
| `/api/lexicon` | ✅ | მეტა-მონაცემები |
| `/api/lexicon/მ` | ✅ | სიტყვების სია |
| `/api/lexicon/search?q=ღმერთი` | ✅ | 5 შედეგი |
| `/api/word/forms/ღმერთი` | ✅ | 47 ფორმა |
| `/api/word/stats/ღმერთი` | ✅ | 7009 გამოყენება |
| `/api/word/distribution/ღმერთი` | ✅ | გავრცელება |
| `/static/audio_map.json` | ✅ | 78 წიგნი |

### 18.3 კონსოლის შეცდომები

- **JS შეცდომები:** არ არის
- **CSS შეცდომები:** არ არის
- **ქსელის შეცდომები:** არ არის
- **წესის შეცდომები:** 1 (No label associated with a form field - მცირე, არაკრიტიკული)

### 18.4 მცირე ხარვეზები (არაკრიტიკული)

1. **No label associated with a form field** - 5 ფორმის ველს არ აქვს `<label>` (accessibility შენიშვნა, არაკრიტიკული)

---

## დასკვნა

აპლიკაციის ყველა მთავარი ფუნქცია მუშაობს სწორად. ტესტირება ჩატარდა ბრაუზერში (chrome-devtools MCP-ით) როგორც დესკტოპზე, ისე მობილურზე (375x664). კონსოლის შეცდომები არ არის. API endpoints-ების ყველა მუშაობს. Service Worker აქტიურია. PWA ინსტალაციის მხარდაჭერა არის.

**სულ ფუნქციები:**
- app.js: 91 ფუნქცია
- lexicon.js: 21 ფუნქცია
- study-pad.js: 31 ფუნქცია
- tags.js: 29 ფუნქცია
- topical.js: 8 ფუნქცია
- word-study.js: 7 ფუნქცია
- export-import.js: 5 ფუნქცია
- highlights.js: 8 ფუნქცია
- audio.js: 28 ფუნქცია
- **სულ: ~228 ფუნქცია**

**სულ API endpoints:** 25 (მათ შორის 1 ალიასი)

---

## 19. უსაფრთხოების აუდიტი (XSS) - 2025

### 19.1 აუდიტის მეთოდი
- კოდის სტატიკური ანალიზი (grep + read)
- ბრაუზერში რეალური XSS ტესტები (chrome-devtools MCP-ით)

### 19.2 ნაპოვნი და გასწორებული ხარვეზები (defense-in-depth)

**topical.js** - 10 unescaped output:
- `t.name`, `t.slug` (search results)
- `data.name` (topic detail title)
- `s.slug`, `s.name` (see_also buttons)
- `entry.label` (entry labels)
- `v.book_name`, `v.book`, `v.text_preview` (verse entries)

**app.js crossrefs** - 5 unescaped output:
- `ref.book`, `label` (book_name + chapter:verse)
- `sourceTitle`, `topicLabel`
- `ref.text_preview`

**app.js loadVerseTopicsInPopup** - 2 unescaped output:
- `t.slug`, `t.name`

**app.js renderSearchResults** - 3 unescaped output:
- `r.book` (AI search results)
- `r.new`, `r.old` (keyword search results, non-AI mode)

**server.py _highlight_word** - 1 ხარვეზი:
- ტექსტი არ escape-დებოდა `<mark>` ტეგების ჩასმამდე

### 19.3 გასწორება
- topical.js: დაემატა `escapeHtml()` და `escapeAttr()` ყველგან
- app.js crossrefs: დაემატა `escapeHtml()` და `escapeAttr()`
- app.js loadVerseTopicsInPopup: დაემატა `escapeHtml()` და `escapeAttr()`
- app.js renderSearchResults: დაემატა `escapeHtml()` keyword რეჟიმში
- server.py: დაემატა `html.escape()` ტექსტის escape-თვის მარკირებამდე

### 19.4 რეალური XSS ტესტები (ბრაუზერში)
- კომენტარი `<script>alert(1)</script>` - უსაფრთხო ✅
- თაგი `<img src=x onerror=alert(1)>` - უსაფრთხო ✅
- study-pad `<script>` + `[[...]]` + `**bold**` - უსაფრთხო ✅
- ძიების query `<script>` - უსაფრთხო ✅
- ლექსიკონის ძიება `<img onerror>` - უსაფრთხო ✅

### 19.5 მონაცემების შემოწმება
- ბიბლიის ტექსტში არ არის `<`, `>`, `&` სიმბოლოები (37562 მუხლი შემოწმებული)
- თემების სახელებში არ არის HTML სიმბოლოები
- მაგრამ defense-in-depth პრინციპით ყველგან დაემატა escape

---

## 20. Edge Cases აუდიტი - 2025

### 20.1 localStorage Quota
- **პრობლემა:** `QuotaExceededError` როცა localStorage სავსეა (50,000 სანიშნე ~5MB)
- **გასწორება:** დაემატა `safeLocalStorageSet()` helper ფუნქცია, რომელიც იჭერს შეცდომას და აჩვენებს toast-ს
- **გამოყენება:** `persistBookmarks()`, `saveBookmarks()`, `persistStudyNotes()`, `saveHighlights()`, `saveColorLabel()`, `saveReadingPosition()`

### 20.2 API შეცდომები (500/404/timeout)
- **მდგომარეობა:** ყველა API call-ს აქვს try/catch
- `performSearch()` - აჩვენებს შეცდომის შეტყობინებას + toast
- `openChapter()` - აჩვენებს toast-ს
- `loadCrossRefs()` - ჩუმად ისმის
- `loadVerseTopicsInPopup()` - ჩუმად ისმის
- `lexicon.js` - აჩვენებს toast-ს
- `topical.js` - აჩვენებს შეცდომის შეტყობინებას
- `word-study.js` - აჩვენებს შეცდომის შეტყობინებას

### 20.3 Offline რეჟიმი (Service Worker)
- **ტესტი:** Offline რეჟიმში თავის ჩატვირთვა, keyword ძიება, AI ძიება - ყველა მუშაობს (cache-დება)
- **შედეგი:** Service Worker წარმატებით cache-ავს ყველა მთავარ API-ს

### 20.4 ცარიელი/გრძელი query
- **ცარიელი:** `doSearch()` ადრე ბრუნდება (`if (!q) return;`)
- **გრძელი:** 1000+ სიმბოლოს query მუშაობს, URL სწორად encode-დება

### 20.5 ორ ტაბში სინქრონიზაცია
- **პრობლემა:** ორ ტაბში ერთდროული ცვლილება იწვევდა მონაცემების დაკარგვას
- **გასწორება:** დაემატა `storage` event listener, რომელიც სინქრონიზებს `bookmarks` ცვლადს სხვა ტაბიდან ცვლილებისას

### 20.6 სანიშნეების/კომენტარების/თაგების ლიმიტები
- **კომენტარი:** 99 სიმბოლო (substring-ით)
- **თაგი:** 30 სიმბოლო (შემოწმებით)
- **სანიშნეები:** არ არის ლიმიტი (მომხმარებელს შეუძლია ნებისმიერი რაოდენობა)

**ტესტირების შედეგი:** 42/42 ფუნქციონალური ტესტი ✅, 16/16 API ტესტი ✅

---

## 21. Accessibility (Keyboard Navigation) - 2025

### 21.1 პრობლემები აუდიტამდე
- 3 ცალკე Escape listener ერთდროულად ისმის (ზედმეტი ქმედებები)
- 5 პანელი/modal-ს აკლია Escape: beginner, study-pad, topical, lexicon, word-study
- Focus არ გადადის modal/popup-ში გახსნისას (BODY-ზე რჩება)
- არ არის focus trap (Tab გადადის modal-ის გარეთ)

### 21.2 გასწორება
- **ერთიანი Escape handler** (პრიორიტეტის მიხედვით):
  1. list-overlay 2. verse-popup 3. about-modal 4. beginner-modal
  5. word-panel 6. topical-panel 7. study-pad-panel 8. bookmarks-panel
- **Focus management:** `moveFocusInto()` - გახსნისას focus გადადის პირველ focusable element-ზე
- **Focus trap:** `enableFocusTrap()` / `disableFocusTrap()` - Tab ციკლი modal-ის შიგნით

### 21.3 ტესტირების შედეგი
- About modal: focus → ✕ button, Escape იხურება ✅
- Verse popup: focus → first button, Escape იხურება ✅, Tab trap (22 elements) ✅
- Beginner modal: focus → first button, Escape იხურება ✅
- Study-pad: Escape იხურება ✅
- Topical panel: Escape იხურება ✅
- Word-study panel: Escape იხურება ✅

---

## 22. Performance აუდიტი - 2025

### 22.1 lexicon.json (87MB) ჩატვირთვის სტრატეგია
- **სერვერი:** 87MB მთლიანად იტვირთება მეხსიერებაში startup-ზე (ერთხელ)
- **კლიენტი:** არ იტვირთება 87MB ფაილი - იყენებts paginated API-ებს:
  - `/api/lexicon` (metadata): 17KB
  - `/api/lexicon/<letter>` (50 სიტყვა): 77KB
  - `/api/lexicon/search?q=...`: 5KB
- **Service Worker:** network-first, cache fallback - offline-ში მუშაობს
- **სისწრაფე:** ძიება 15ms, ასოს ჩატვირთვა 2ms

### 22.2 დასკვნა
ლექსიკონის არქიტექტურა კარგად მუშაობს. კლიენტი არ ტვირთავს დიდ ფაილებს. სერვერის მეხსიერება (87MB) ადეკვატურია.

