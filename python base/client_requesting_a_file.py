import socket
import sys
import os
#import base64

msgSize = 1024
def udp_client_sending(ip_address='127.0.01', port_number=5000):

    #default without params is TCP 
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if (len(sys.argv) > 3):
        ip_address = socket.gethostbyname(sys.argv[2])
        port_number = int(sys.argv[3])
    else:
        ip_address = "127.0.0.1"
        port_number = 5000
    keep_connection = True
    while keep_connection:
        print("client started up" )
        user_filename = 'beauty.jpeg'
        if(os.path.isfile("new_" + user_filename)):
            os.remove("new_" + user_filename)
            print("removed")

        #user_filename = str(input("Please type a filename:")).encode('ASCII')
        udp_socket.sendto(user_filename.encode('ASCII'), (ip_address, port_number))
        # # file_len, srvr_addr = udp_socket.recvfrom(msgSize)
        # # print(file_len)
        # # udp_socket.sendto("yes".encode('ASCII'), (ip_address, port_number))
        #we are promised it fits in 1 packet
        dummy = True
        test = bytearray()
        msg_from_srvr, srvr_addr = udp_socket.recvfrom(msgSize)
        f = open("new_" + user_filename, 'wb')
        while (msg_from_srvr != test or dummy == True):
            dummy = False
            file_data = msg_from_srvr
            f.write(file_data)
            msg_from_srvr, srvr_addr = udp_socket.recvfrom(msgSize)   
            print(msg_from_srvr)  
            print(test)
            
        print(msg_from_srvr)
        print(len(msg_from_srvr))
        f.close()
        keep_connection = False
    udp_socket.close()

udp_client_sending()