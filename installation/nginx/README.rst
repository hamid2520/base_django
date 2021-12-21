http://docs.gunicorn.org/en/stable/deploy.html

Get Source
==========

$ su
$ cd /usr/local/src/
$ git clone $(git)
$ cd $(project_name)

Install Main Packages
=====================

virtualenv
python3.4
postgresql

Creating Database
=================
sudo su - postgres
-bash-4.3$ createdb baser_test
-bash-4.3$ psql
postgres=# CREATE USER base_user WITH PASSWORD 'emami';
CREATE ROLE
postgres=# ALTER ROLE base_user SET client_encoding TO 'utf8';
ALTER ROLE
postgres=# ALTER ROLE base_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE
postgres=# ALTER ROLE myprojectuser SET timezone TO 'Asia/Tehran';
ERROR:  role "myprojectuser" does not exist
postgres=# ALTER ROLE base_user SET timezone TO 'Asia/Tehran';
ALTER ROLE
postgres=# GRANT ALL PRIVILEGES ON DATABASE base TO base_user;
GRANT

Installation
============
useradd -m base -s /sbin/nologin
usermod -G nginx base
chown base:base /var/base/ -R
virtualenv -p /usr/bin/python3.4 /usr/local/src/env/base
. /usr/local/src/env/base/bin/activate
pip install -U pip
pip install -r requirements.txt
cd base
python production_manage.py migrate
python production_manage.py makemigrations sales accounting callcenter core
python production_manage.py createsuperuser
python production_manage.py collectstatic

add default groups (kiosk, callcenter)
add default users (fs:1234, )

cp ../installation/nginx/base.service /etc/systemd/system/
cp ../installation/nginx/base.conf /etc/nginx/conf.d/
systemctl start postgresql
systemctl start base
systemctl start nginx

Test Ip Phone
=============

configure ip phone
configure freeswitch

configure tftpyd.service
restart tftp
provision ip phone

add extension
