import asyncio
from bs4 import BeautifulSoup
import aiohttp

host = '192.168.88.14/sec'




# page = '''
# <html><head><style>input,select{margin:1px}</style></head><body><a href="/sec/?cf=3">Back</a><br>P7/ON<br><a href="/sec/?pt=7&amp;cmd=7:1">ON</a> <a href="/sec/?pt=7&amp;cmd=7:0">OFF</a><br><form action="/sec/"><input type="hidden" name="pn" value="7">Type <select name="pty"><option value="255">NC</option><option value="0">In</option><option value="1" selected="">Out</option><option value="3">DSen</option><option value="4">I2C</option></select><br>Default: <select name="d"><option value="0" selected="">0</option><option value="1">1</option></select><br>Mode <select name="m"><option value="0" selected="">SW</option><option value="3">SW LINK</option><option value="2">DS2413</option></select><br>Group <input name="grp" size="2" value=""><br><input type="submit" value="Save"></form></body></html>
# <head><style>input,select{margin:1px}</style></head>
# <body><a href="/sec/?cf=3">Back</a><br>P7/ON<br><a href="/sec/?pt=7&amp;cmd=7:1">ON</a> <a href="/sec/?pt=7&amp;cmd=7:0">OFF</a><br><form action="/sec/"><input type="hidden" name="pn" value="7">Type <select name="pty"><option value="255">NC</option><option value="0">In</option><option value="1" selected="">Out</option><option value="3">DSen</option><option value="4">I2C</option></select><br>Default: <select name="d"><option value="0" selected="">0</option><option value="1">1</option></select><br>Mode <select name="m"><option value="0" selected="">SW</option><option value="3">SW LINK</option><option value="2">DS2413</option></select><br>Group <input name="grp" size="2" value=""><br><input type="submit" value="Save"></form></body>
# <a href="/sec/?cf=3">Back</a>
# <br>
# P7/ON
# <br>
# <a href="/sec/?pt=7&amp;cmd=7:1">ON</a>
# <a href="/sec/?pt=7&amp;cmd=7:0">OFF</a>
# <br>
# <form action="/sec/"><input type="hidden" name="pn" value="7">Type <select name="pty"><option value="255">NC</option><option value="0">In</option><option value="1" selected="">Out</option><option value="3">DSen</option><option value="4">I2C</option></select><br>Default: <select name="d"><option value="0" selected="">0</option><option value="1">1</option></select><br>Mode <select name="m"><option value="0" selected="">SW</option><option value="3">SW LINK</option><option value="2">DS2413</option></select><br>Group <input name="grp" size="2" value=""><br><input type="submit" value="Save"></form>
# <body><a href="/sec/?cf=3">Back</a><br>P7/ON<br><a href="/sec/?pt=7&amp;cmd=7:1">ON</a> <a href="/sec/?pt=7&amp;cmd=7:0">OFF</a><br><form action="/sec/"><input type="hidden" name="pn" value="7">Type <select name="pty"><option value="255">NC</option><option value="0">In</option><option value="1" selected="">Out</option><option value="3">DSen</option><option value="4">I2C</option></select><br>Default: <select name="d"><option value="0" selected="">0</option><option value="1">1</option></select><br>Mode <select name="m"><option value="0" selected="">SW</option><option value="3">SW LINK</option><option value="2">DS2413</option></select><br>Group <input name="grp" size="2" value=""><br><input type="submit" value="Save"></form></body>
# <html><head><style>input,select{margin:1px}</style></head><body><a href="/sec/?cf=3">Back</a><br>P7/ON<br><a href="/sec/?pt=7&amp;cmd=7:1">ON</a> <a href="/sec/?pt=7&amp;cmd=7:0">OFF</a><br><form action="/sec/"><input type="hidden" name="pn" value="7">Type <select name="pty"><option value="255">NC</option><option value="0">In</option><option value="1" selected="">Out</option><option value="3">DSen</option><option value="4">I2C</option></select><br>Default: <select name="d"><option value="0" selected="">0</option><option value="1">1</option></select><br>Mode <select name="m"><option value="0" selected="">SW</option><option value="3">SW LINK</option><option value="2">DS2413</option></select><br>Group <input name="grp" size="2" value=""><br><input type="submit" value="Save"></form></body></html>
# '''
# tree = BeautifulSoup(page, features="lxml")
# pty = tree.find('select', attrs={'name': 'pty'}).find(selected=True)['value']
# m = tree.find('select', attrs={'name': 'm'})
# if m:
#     m = m.find(selected=True)['value']
#
# print(pty, m)

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(
        scan_port(0)
    )