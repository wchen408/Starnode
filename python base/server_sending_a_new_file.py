#client sends name to server and receives back photo 
#serializing and sending photos

#send length of file; send file. 
import socket
import sys
import threading #
import os #check if file exists
#import base64

msgSize = 1024
def findAndSendFile(sock, addr, filename):
    print("filename is:", filename)
    
    #file = sock.recv(1024)
    if(os.path.isfile(filename)):
        #ascii
        #sock.sendto(str(os.path.getsize(filename)).encode('ASCII'), addr)
        print("waiting for response")
        #ascii
        #userResponse, user_addr = sock.recvfrom(msgSize).decode()
        #if("n" not in userResponse):
        print("user will send file now")
        try: 
            with open(filename, 'rb') as f: #rb is read binary
                bytesToSend = f.read(1024) # amount to send over network
                test = bytearray()
                #if image is larger than 1024
                while(len(bytesToSend) >= 0 and bytesToSend != test):
                    print(bytesToSend)
                    sock.sendto(bytesToSend, addr)
                    bytesToSend = f.read(1024)
                    print(len(bytesToSend))
            sock.sendto(test, addr)
            print("user has send file")
        except Exception as e:
            print(e)
            print("woops. file not legit")
    else:
        print("this file is not here")
        
#        sock.close()

def udp_server():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # if (len(sys.argv) > 3):
    #     ip_address = socket.gethostbyname(sys.argv[2])
    #     port_number = int(sys.argv[3])
    # else:
    ip_address = "127.0.0.1"
    port_number = int(5000)
    udp_socket.bind((ip_address, port_number)) #server binding to port
    while True:
        print("server waiting for a filename ;)")
        filename, addr = udp_socket.recvfrom(1024)
        findAndSendFile(udp_socket, addr, filename.decode())

    

udp_server()