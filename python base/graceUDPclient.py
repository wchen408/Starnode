import socket
import sys
import json 

def make_packet_dict(msg):
    cool = {"PACKET TYPE": "ACK", "MSG":msg}
    return json.dumps(cool)

def udp_client():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if (len(sys.argv) > 3):
        ip_address = socket.gethostbyname(sys.argv[2])
        port_number = int(sys.argv[3])
    else:
        ip_address = "127.0.0.1"
        port_number = int(sys.argv[2])
    should_break_connection = True
    while should_break_connection:
        user_input = input("PLEASE type IN msg: ")
        user_query = make_packet_dict(user_input)
        udp_socket.sendto(user_query.encode('ASCII'), (ip_address, port_number))
        message_from_server, address_of_server = udp_socket.recvfrom(64000)
        message_from_server = message_from_server.decode()
        obj = json.loads(message_from_server)
        print(obj["MSG"])

if (sys.argv[1] == "TCP"):
    tcp_client()
elif (sys.argv[1] == "UDP"):
    udp_client()
else:
    print("Invalid connection type specified.")