# Deployment Guide - წმიდა წერილი

## მოთხოვნები

- Python 3.10+
- Linux server (Ubuntu 22.04+ recommended)
- 4GB RAM minimum (LaBSE model)
- 20GB disk space
- Domain name + DNS access

## 1. პროექტის ატვირთვა

```bash
# სერვერზე ატვირთეთ პროექტი
git clone <your-repo> /opt/bible_app
cd /opt/bible_app
```

## 2. Python გარემო

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. მონაცემების გენერაცია (პირველად)

```bash
# თუ მონაცემები არ არის გენერირებული:
python3 extract_bible.py
python3 build_index.py
python3 build_lexicon.py
python3 build_word_groups.py
python3 build_crossrefs.py
python3 build_hybrid_index.py  # ~2 საათი (LaBSE)
```

## 4. Gunicorn გაშვება (ტესტი)

```bash
# ტესტი გაშვებამდე
gunicorn -c gunicorn.conf.py server:app
# შეამოწმეთ: curl http://127.0.0.1:5000/
```

## 5. systemd Service

```bash
# ფაილის კოპირება
sudo cp bible.service /etc/systemd/system/
# გამოსახულების გამოსწორება (path-ები)
sudo nano /etc/systemd/system/bible.service
# შეცვალეთ /path/to/bible_app → /opt/bible_app

sudo systemctl daemon-reload
sudo systemctl enable bible
sudo systemctl start bible
sudo systemctl status bible
```

## 6. Nginx

```bash
sudo apt install nginx -y

# კონფიგურაციის კოპირება
sudo cp nginx.conf /etc/nginx/sites-available/bible
sudo ln -s /etc/nginx/sites-available/bible /etc/nginx/sites-enabled/

# დომენის და path-ების გამოსწორება
sudo nano /etc/nginx/sites-available/bible
# შეცვალეთ yourdomain.com და /path/to/bible_app

sudo nginx -t
sudo systemctl reload nginx
```

## 7. SSL (HTTPS)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
# ავტომატური განახლება დაყენებულია cron-ით
```

## 8. შემოწმება

```bash
# სერვისი
sudo systemctl status bible

# ლოგები
sudo journalctl -u bible -f

# Nginx ლოგები
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# HTTP შემოწმება
curl -I https://yourdomain.com/
curl -I https://yourdomain.com/robots.txt
curl -I https://yourdomain.com/sitemap.xml
curl https://yourdomain.com/b/mate/5/3 | grep og:title
```

## გაშვებული აპლიკაციის მართვა

```bash
# რესტარტი
sudo systemctl restart bible

# გაჩერება
sudo systemctl stop bible

# ლოგების ნახვა
sudo journalctl -u bible --since "1 hour ago"
```

## მონაცემების განახლება

```bash
cd /opt/bible_app
source venv/bin/activate

# გადააკეთეთ ცვლილებები extract_bible.py-ში
python3 extract_bible.py
python3 build_index.py
python3 build_lexicon.py
python3 build_word_groups.py
python3 build_crossrefs.py
python3 build_hybrid_index.py

# სერვისის რესტარტი
sudo systemctl restart bible
```

## ბექაფი

```bash
# მონაცემების ბექაფი
tar -czf bible_data_backup_$(date +%Y%m%d).tar.gz data/

# სერვერიდან ჩამოტვირთვა
scp user@server:/opt/bible_app/bible_data_backup_*.tar.gz ./
```
