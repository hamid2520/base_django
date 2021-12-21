import unicodedata
import persian

def digit(num):
    return ''.join([str(unicodedata.digit(ch)) for ch in str(num) if ch])

# coding: utf-8

import re

# Attention: while the characters for the strings bellow are
# dislplayed indentically, inside they are represented
# by distinct unicode codepoints

persian_numbers = u'۱۲۳۴۵۶۷۸۹۰'
arabic_numbers  = u'١٢٣٤٥٦٧٨٩٠'
english_numbers = u'1234567890'

numbers_dict = {
    '۰': '0',
    '۱': '1',
    '۲': '2',
    '۳': '3',
    '۴': '4',
    '۵': '5',
    '۶': '6',
    '۷': '7',
    '۸': '8',
    '۹': '9'
}


def to_persian(text):
    return persian.enToPersianNumb(text)

def to_persian_numbers(text):
    for i, j in numbers_dict.items():
        text = text.replace(j, i)
    return text

def to_english(text):
    for i, j in numbers_dict.items():
        text = text.replace(i, j)
    return text

toHex = lambda x:"".join([hex(ord(c))[2:].zfill(2) for c in x])

def fix_chars(text):
    if text is None:
        return None
    return str(text).translate({0x64a:'ی', 0x643:'ک'})


def is_persian_alphanumeric(text):
    return re.match('^[\u0600-\u06FF\s\u200c]+$', text) is not None

def is_persian_alpha(text):
    return re.match('^[آ-ی\s\u200c]+$', text) is not None
