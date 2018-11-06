import socket
import sys


def udp_server():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if (len(sys.argv) > 3):
        ip_address = socket.gethostbyname(sys.argv[2])
        port_number = int(sys.argv[3])
    else:
        ip_address = "127.0.0.1"
        port_number = int(sys.argv[2])
    udp_socket.bind((ip_address, port_number))
    while True:
        data, addr = udp_socket.recvfrom(33)
        data = data.decode()
        modifiedMessage = "From Luming"
        udp_socket.sendto(modifiedMessage.encode("ASCII"), addr)

if (sys.argv[1] == "TCP"):
    tcp_server()
elif (sys.argv[1] == "UDP"):
    udp_server()
else:
    print "Invalid connection type specified."
