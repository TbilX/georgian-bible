# აღდგენის ინსტრუქცია

აპლიკაციის ახალ სერვერზე აღსადგინად საჭიროა შემდეგი ნაბიჯები.

## საჭირო რესურსები

1. Linux სერვერი (მინიმუმ 4GB RAM, 20GB დისკი)
2. დომენი და Cloudflare ანგარიში
3. GitHub ანგარიში კოდის ჩამოსატვირთად

## ნაბიჯი 1: სერვერის მომზადება

Oracle Linux / RHEL:
```bash
sudo dnf update -y
sudo dnf install -y python3 python3-pip python3-venv git nginx gunicorn
```

Ubuntu:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nginx gunicorn
```

## ნაბიჯი 2: კოდის ჩამოტვირთვა

```bash
sudo mkdir -p /opt/bible_app
sudo chown $USER:$USER /opt/bible_app
cd /opt/bible_app
git clone https://github.com/TbilX/georgian-bible.git .
```

## ნაბიჯი 3: მონაცემების ჩამოტვირთვა

დიდი მონაცემების ფაილები GitHub Releases-ზეა განთავსებული:

```bash
cd /opt/bible_app
wget https://github.com/TbilX/georgian-bible/releases/download/v1.1-data/bible-data.tar.gz
tar xzf bible-data.tar.gz
rm bible-data.tar.gz
```

არქივი შეიცავს:
- verses.json - ბიბლიის ტექსტი
- verse_index.json - მუხლების ინდექსი (ბერძნული ორიგინალით, grc ველი)
- lexicon.json - ლექსიკონი
- embeddings_labse.npz - AI ძიების მოდელი
- embeddings.npz - მეორე embeddings მოდელი
- bm25_index.pkl - BM25 ინდექსი
- crossrefs_index.json / crossrefs_merged.json / crossrefs_tsk.json - ჯვარედინი მითითებები
- bible_word_groups.json - სიტყვის ჯგუფები
- topical_index.json - თემატური ენციკლოპედია
- topic_names_ka.json / topic_labels_ka.json - თემების ქართული თარგმანი
- crossref_topics_ka.json - ჯვარედინი თემების თარგმანი
- root_translations_ka.json - ძირების თარგმანები

## ნაბიჯი 4: Python გარემო

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## ნაბიჯი 5: Gunicorn და systemd

```bash
sudo cp bible.service /etc/systemd/system/
sudo sed -i "s|/path/to/bible_app|/opt/bible_app|g" /etc/systemd/system/bible.service
sudo systemctl daemon-reload
sudo systemctl enable bible
sudo systemctl start bible
```

## ნაბიჯი 6: Nginx

```bash
sudo cp nginx/bible.conf /etc/nginx/conf.d/
sudo nginx -t
sudo systemctl reload nginx
```

## ნაბიჯი 7: Cloudflare Tunnel

```bash
sudo mkdir -p /etc/cloudflared
sudo cp cloudflared/config.yml /etc/cloudflared/
```

კონფიგურაციაში შეცვალეთ hostname თქვენი დომენის მიხედვით.

## ნაბიჯი 8: სარეზერვო დომენი (EU.org)

უფასო დომენი შესაძლებელია EU.org-ის მეშვეობით:

1. გახსენით https://nic.eu.org
2. შექმენით ანგარიში
3. მოითხოვეთ დომენი (მაგალითად: biblegeo.eu.org)
4. DNS მიუთითეთ Cloudflare-ის nameservers-ზე
5. Cloudflare Dashboard-ში დაამატეთ დომენი
6. Cloudflare Tunnel-ის config.yml-ში დაამატეთ შესაბამისი hostname
7. გადატვირთეთ cloudflared

## ნაბიჯი 9: შემოწმება

```bash
curl http://localhost/
curl http://localhost/api/search/keyword?q=test
sudo systemctl status bible
sudo systemctl status nginx
```

## შენიშვნები

- ML მოდელები (LaBSE) 2.3GB ქეშს იკავებს, საჭიროა თავისუფალი დისკი
- პირველი გაშვება შეიძლება 3-5 წუთი გაგრძელდეს მოდელის ჩატვირთვის გამო
- Audio ფაილები არ არის რეპოზიტორიაში, ცალკე უნდა დააკოპიროთ
- HTML route-ებზე Cache-Control: no-transform აუცილებელია Cloudflare beacon-ის თავიდან ასაცილებლად
