import locale, re
#locale.setlocale(locale.LC_ALL, 'fa_IR')   there was an error in this code
from .jdatetime import datetime as dt
from datetime import datetime as gdt
from dateutil.parser import parse
from time import mktime


def datetime(mydate, microsecond=False):
    if mydate:
        p = parse(str(mydate))
        jdt = dt.fromgregorian(datetime=p)
        if microsecond:
            return '%02d-%02d-%02d %02d:%02d:%02d.%d' % (jdt.year, jdt.month, jdt.day, jdt.hour, jdt.minute, jdt.second, jdt.microsecond)
        else:
            return '%02d-%02d-%02d %02d:%02d:%02d' % (
            jdt.year, jdt.month, jdt.day, jdt.hour, jdt.minute, jdt.second)
    else:
        return None

def date(mydate):
    if mydate:
        p = parse(str(mydate))
        jdt = dt.fromgregorian(datetime=p)
        return '%02d-%02d-%02d' % (jdt.year, jdt.month, jdt.day)
    else:
        return None
    
def time(mydate):
    if mydate:
        p = parse(str(mydate))
        jdt = dt.fromgregorian(datetime=p)
        return '%02d:%02d:%02d' % (jdt.hour, jdt.minute, jdt.second)
    else:
        return None
    
def greDatetime(datetime=None, time=True, no_sec=True):
    if not time:
        format = '%Y-%m-%d'
    else:
        if no_sec:
            format = '%Y-%m-%d %H:%M'
        else:
            format = '%Y-%m-%d %H:%M:%S'

    if datetime:
        guessed_format = '%Y-%m-%d %H:%M:%S'

        strlen = len(datetime)

        if re.match('^\d{4}-\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2}', datetime) is not None:
            strlen = 19
        elif re.match('^\d{4}-\d{1,2}-\d{1,2}', datetime) is not None:
            strlen = 10

        if strlen == 16:
            guessed_format = '%Y-%m-%d %H:%M'
        elif strlen == 19:
            guessed_format = '%Y-%m-%d %H:%M:%S'
        elif strlen == 10:
            guessed_format = '%Y-%m-%d'
        year = int(datetime[:4])
        if year < 1700:
            buff = dt.strptime(datetime, guessed_format)
            buff = buff.togregorian()
        else:
            buff = gdt.strptime(datetime, guessed_format)
        return buff.strftime(format)
    return None

# set j to True to return jalali datatime
def nowDatetime(j=False):
    sal = gdt.now()
    nd = gdt.strftime(sal, '%Y-%m-%d %H:%M:%S')
    if j:
        return datetime(nd)
    return nd

# modify code style, dont use camel case
now_datetime = nowDatetime

# this used for publication date of RSS's items
# returns datetime.datetime
def parse_pubdate(pubdate):
    return parse(str(pubdate))
    
def parse_pubdate_to_gre(pubdate):
    return parse_pubdate(pubdate).strftime('%Y-%m-%d %H:%M:%S')
    
def totimestamp(dtt):
    return int(mktime(dtt.timetuple()))

def pubdate_to_timestamp(pubdate):
    pubdate = parse_pubdate_to_gre(pubdate)
    return totimestamp(parse_pubdate(pubdate))


def strftime(format, date=None, datetime=None):
    if date != None:
        fg = dt.fromgregorian(date=date)
    elif datetime != None:
        fg = dt.fromgregorian(datetime=date)
    return fg.strftime(format)

def to_jalali_weekday(date):
    weekday = date.isoweekday()
    if weekday >= 6:
        return weekday % 6 +1
    return weekday + 2