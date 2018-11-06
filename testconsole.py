#!/usr/bin/python

CURSOR_UP_ONE = '\x1b[1A'
ERASE_LINE = '\x1b[2K'

print('Text 1\nText 2\nText 3')

inp = ''
while inp != 'END':
    inp = input('Please enter something:')
    print(CURSOR_UP_ONE + ERASE_LINE + inp)
