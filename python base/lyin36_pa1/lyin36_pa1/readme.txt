● Your name and email address
Luming Yin, lyin36@gatech.edu and lumingyin@gatech.edu

● Class name, date and assignment title
Class name: CS 3251 - Computer Networking I
Date: September 24, 2018
Assignment Title: "Programming Assignment 1: Basics of Socket Programming"

● Detailed instructions for compiling/running your client and server programs
There's no need to compile my client and server programs since it is written in Python 2, an interpreted language.

=== FOR CLIENT PROGRAM ===
To run my client program in UDP that talks to a UDP server running on localhost on port 13001, run:
$ python rmtcalc.py UDP 13001

To run my client program in UDP that talks to another UDP server running on a different machine on port 13001, run:
$ python rmtcalc.py UDP replaceWithActualServerAddress.cc.gatech.edu 13001

=== FOR SERVER PROGRAM ===
To run my UDP server program listening at port 13001 at the local host, run:
$ python rmtcalc-srv.py UDP 13001

=== FOR USING THE CLIENT ===
Type in a corrected format mathematical operation, in the format of:
2 + 1
-2 - -4.5
3 * 6
45 / 8
-9 * 24.0
Note: You need to seperate the first number and operand with a space character. You also need to seperate the operand and the second number with a space character. The client does not handle malformed input, since the assignment PDF indicates "you do not need to worry about cases of mis-formatted inputs, redundant blank spaces".

● Any known bugs or limitations of your program
There are no known bugs or limitations of my program.