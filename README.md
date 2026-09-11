# ქართული ბიბლია

ქართული ბიბლიის ვებ-აპლიკაცია ორ თარგმანში: ძველი და ახალი ქართული, პარალელური ტექსტებით, ძიებით, ლექსიკონით და თემატური ენციკლოპედიით.

## დომენები

- https://web.net.ge/ - მთავარი დომენი
- https://biblegeo.eu.org/ - სარეზერვო (უფასო, EU.org)

## შესაძლებლობები

- ორ თარგმანში პარალელური ტექსტი (ძველი და ახალი ქართული)
- AI ძიება (LaBSE + BM25 ჰიბრიდული მიდგომა)
- საკვალიფიკაციო ძიება (keyword, phrase, AND რეჟიმები)
- ლექსიკონი და თემატური ენციკლოპედია
- ჯვარედინი მითითებები (TSK + დამატებითი)
- აუდიო წაკითხვა
- სანიშნეები, თაგები, ფერადი მარკირება
- PWA - offline მუშაობა Service Worker-ით

## ტექნოლოგიები

- Backend: Python Flask + Gunicorn
- Frontend: Vanilla JS, PWA Service Worker
- Web Server: Nginx
- Tunnel: Cloudflare Tunnel
- ML: LaBSE (sentence-transformers), BM25 (rank-bm25)
- Server: Oracle Cloud ARM64

## სტრუქტურა

- server.py - Flask აპლიკაციის მთავარი ფაილი
- gunicorn.conf.py - Gunicorn კონფიგურაცია
- bible.service - systemd service
- requirements.txt - Python დამოკიდებულებები
- static/ - frontend ფაილები (JS, CSS, HTML, fonts)
- data/ - ბიბლიის მონაცემები (JSON, NPZ, PKL)
- scripts/ - მონაცემების აგების სკრიპტები
- nginx/ - Nginx კონფიგურაცია
- cloudflared/ - Cloudflare Tunnel კონფიგურაცია
- docs/ - დოკუმენტაცია

## აღდგენა

დეტალური ინსტრუქცია აპლიკაციის აღსადგინად იხილეთ RESTORATION.md ფაილში.

## ლიცენზია

ბიბლიის ტექსტი - საზოგადოებრივი დომენი. კოდი - MIT.
Test GPG signing
