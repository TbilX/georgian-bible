# Gunicorn configuration for Bible App
# გაშვება: gunicorn -c gunicorn.conf.py server:app

import multiprocessing
import os

# მუშაობის რაოდენობა (CPU ბირთვების მიხედვით)
workers = multiprocessing.cpu_count() * 2 + 1
# მაქსიმალური დაკავშირებები ერთ worker-ზე
worker_connections = 1000
# timeout - LaBSE მოდელის ჩატვირთვას დრო სჭირდება
timeout = 120
# გაშვების მისამართი
bind = "127.0.0.1:5000"
# დალოგვა
accesslog = "/tmp/bible_gunicorn_access.log"
errorlog = "/tmp/bible_gunicorn_error.log"
loglevel = "warning"
# პრელოუდი - მოდელი ჩაიტვირთება ერთხელ ყველა worker-ში
preload_app = True
# გრძელვადიანი მუშაობისთვის
max_requests = 1000
max_requests_jitter = 50
# გადატვირთვის შემთხვევაში ავტომატური რესტარტ
restart = True
