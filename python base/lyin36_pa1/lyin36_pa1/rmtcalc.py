import socket
import sys

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
        user_input = raw_input("Please type an operation: ")
        if (user_input == "quit" or user_input == "Quit"):
            print("Bye...")
            udp_socket.close()
            should_break_connection = False
        else:
            user_query = user_input
            udp_socket.sendto(user_query.encode('ASCII'), (ip_address, port_number))
            message_from_server, address_of_server = udp_socket.recvfrom(48)
            print(message_from_server)

if (sys.argv[1] == "TCP"):
    tcp_client()
elif (sys.argv[1] == "UDP"):
    udp_client()
else:
    print("Invalid connection type specified.")
