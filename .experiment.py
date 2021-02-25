import re


PATT_FW = re.compile(r'fw:\s(.+)\)')
data = """
<html><head></head><body>MegaD-2561 by <a href="http://ab-log.ru">ab-log.ru</a> (fw: 4.48b7)<br><a href="/sec/?cf=1">Config</a><br>-- MODS --<br><a href="/sec/?cf=3">XP1</a><br><a href="/sec/?cf=4">XP2</a><br>-- XT2 --<br><a href="/sec/?pt=30">P30 - OUT</a><br><a href="/sec/?pt=31">P31 - OUT</a><br><a href="/sec/?pt=32">P32 - IN</a><br><a href="/sec/?pt=33">P33 - I2C/SCL</a><br><a href="/sec/?pt=34">P34 - DS</a><br><a href="/sec/?pt=35">P35 - NC</a><br>-- XP5/6 --<br><a href="/sec/?pt=36">P36 - ADC</a><br><a href="/sec/?pt=37">P37 - NC</a></body></html>
<head></head>
<body>MegaD-2561 by <a href="http://ab-log.ru">ab-log.ru</a> (fw: 4.48b7)<br><a href="/sec/?cf=1">Config</a><br>-- MODS --<br><a href="/sec/?cf=3">XP1</a><br><a href="/sec/?cf=4">XP2</a><br>-- XT2 --<br><a href="/sec/?pt=30">P30 - OUT</a><br><a href="/sec/?pt=31">P31 - OUT</a><br><a href="/sec/?pt=32">P32 - IN</a><br><a href="/sec/?pt=33">P33 - I2C/SCL</a><br><a href="/sec/?pt=34">P34 - DS</a><br><a href="/sec/?pt=35">P35 - NC</a><br>-- XP5/6 --<br><a href="/sec/?pt=36">P36 - ADC</a><br><a href="/sec/?pt=37">P37 - NC</a></body>
MegaD-2561 by 
<a href="http://ab-log.ru">ab-log.ru</a>
 (fw: 4.48b7)
<br>
<a href="/sec/?cf=1">Config</a>
<br>
-- MODS --
<br>
<a href="/sec/?cf=3">XP1</a>
<br>
<a href="/sec/?cf=4">XP2</a>
<br>
-- XT2 --
<br>
<a href="/sec/?pt=30">P30 - OUT</a>
<br>
<a href="/sec/?pt=31">P31 - OUT</a>
<br>
<a href="/sec/?pt=32">P32 - IN</a>
<br>
<a href="/sec/?pt=33">P33 - I2C/SCL</a>
<br>
<a href="/sec/?pt=34">P34 - DS</a>
<br>
<a href="/sec/?pt=35">P35 - NC</a>
<br>
-- XP5/6 --
<br>
<a href="/sec/?pt=36">P36 - ADC</a>
<br>
<a href="/sec/?pt=37">P37 - NC</a>
<body>MegaD-2561 by <a href="http://ab-log.ru">ab-log.ru</a> (fw: 4.48b7)<br><a href="/sec/?cf=1">Config</a><br>-- MODS --<br><a href="/sec/?cf=3">XP1</a><br><a href="/sec/?cf=4">XP2</a><br>-- XT2 --<br><a href="/sec/?pt=30">P30 - OUT</a><br><a href="/sec/?pt=31">P31 - OUT</a><br><a href="/sec/?pt=32">P32 - IN</a><br><a href="/sec/?pt=33">P33 - I2C/SCL</a><br><a href="/sec/?pt=34">P34 - DS</a><br><a href="/sec/?pt=35">P35 - NC</a><br>-- XP5/6 --<br><a href="/sec/?pt=36">P36 - ADC</a><br><a href="/sec/?pt=37">P37 - NC</a></body>
<html><head></head><body>MegaD-2561 by <a href="http://ab-log.ru">ab-log.ru</a> (fw: 4.48b7)<br><a href="/sec/?cf=1">Config</a><br>-- MODS --<br><a href="/sec/?cf=3">XP1</a><br><a href="/sec/?cf=4">XP2</a><br>-- XT2 --<br><a href="/sec/?pt=30">P30 - OUT</a><br><a href="/sec/?pt=31">P31 - OUT</a><br><a href="/sec/?pt=32">P32 - IN</a><br><a href="/sec/?pt=33">P33 - I2C/SCL</a><br><a href="/sec/?pt=34">P34 - DS</a><br><a href="/sec/?pt=35">P35 - NC</a><br>-- XP5/6 --<br><a href="/sec/?pt=36">P36 - ADC</a><br><a href="/sec/?pt=37">P37 - NC</a></body></html>
"""
print(PATT_FW.search(data).groups()[0])