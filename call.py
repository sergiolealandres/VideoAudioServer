from email import message
from multiprocessing import Semaphore
import socket
import threading
import pickle
import time
import cv2
import struct
import base64
import numpy as np
from practica3_client import *
end_call = 0
current_call = 0

def call(target_nick,target_IP, target_port, user_IP,user_Port,semaforo,client):
    global current_call

    serverName = target_IP
    serverPort = target_port
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    clientSocket.connect((serverName,int(serverPort)))
    #sentence = "CALLING "+ target_nick + " "+ user_IP + ":"+ str(user_Port)
    sentence = "CALLING "+ client.my_nick + " "+ str(client.my_data_port)
    clientSocket.send(sentence.encode())
    modifiedSentence = clientSocket.recv(1024)
    modifiedSentence = modifiedSentence.decode('utf-8')
    print("Se ha recibido:")
    print(modifiedSentence)
    print("")
    

    if modifiedSentence[:13] == "CALL_ACCEPTED":
        print("prelock call")
        
        semaforo.acquire()
        if(current_call == 1):
            semaforo.release()
            raise Exception("There is already a call")
        current_call = 1
        split=modifiedSentence.split(" ")
        client.selected_data_port=split[2]
        data=query(split[1])
        nick, ip, control_port, versions=data

        client.selected_ip=ip
        semaforo.release()
        print("post-lock call")
        thr = threading.Thread(target=manage_call,args = (clientSocket,client,))
        thr.start()
        return 0

    clientSocket.close()

    if modifiedSentence[:9] == "CALL_BUSY":
        return 1
    else:
        return 2

def call_waiter(user_Port,client,semaforo):

    while True:
        callSocket = wait_call(user_Port,client,semaforo)
        if callSocket is None:
            return
        thr = threading.Thread(target=video_receiver,args = (callSocket,))
        thr.start()
        

def wait_call(user_Port,client,semaforo):
    global current_call

    waitingSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    waitingSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        waitingSocket.bind((client.my_ip, int(client.my_control_port)))
    except OSError:
        
        client.app.infoBox("Error", "Hay un usuario activo usando el puerto de control "+ str(client.my_control_port))

        client.app.setTabbedFrameDisabledTab("Tabs", "LIST USERS", True)
        client.app.setTabbedFrameDisabledTab("Tabs", "SEARCH USER", True)

        return None
       

    #waitingSocket.bind(('', int(user_Port)))
    waitingSocket.listen(1)#aqui hay que poner más para el call_busy
    print("Servidor preparado para recibir")
    

    while client.app.alive:
        print("Empezamos bucle")
        connectionSocket, addr = waitingSocket.accept()
        sentence = connectionSocket.recv(1024)
        sentence = sentence.decode('utf-8')
        print("Se ha recibido:")
        print(sentence)
        print("")
        words = sentence.split(" ")
        print(words)   
            
        if sentence[:7] == "CALLING":
            print("prelock wait")
            semaforo.acquire()
            current_call_value = current_call
            semaforo.release()
            print("postlock wait", current_call_value)
            if current_call_value == 1:
                connectionSocket.send("CALL_BUSY".encode())
                #if client.ask_call(words[1]):
            else:
                client.app.setLabel("Nick entrante", words[1] + " te esta llamando...")
                client.app.showSubWindow("LLamada entrante")
                call_accepted=client.has_call_been_accepted()
                client.app.hideSubWindow("LLamada entrante", useStopFunction=False)
                if call_accepted==1:
                    semaforo.acquire()
                    if(current_call == 1):
                        semaforo.release()
                        connectionSocket.send("CALL_BUSY".encode())
                        continue
                
                    current_call = 1
                    semaforo.release()

                    mensaje = "CALL_ACCEPTED "+client.my_nick+" "+client.my_data_port
                    connectionSocket.send(mensaje.encode())
                    return connectionSocket
                else:
                    mensaje = "CALL_DENIED "+words[1]
                    connectionSocket.send(mensaje.encode())
        elif sentence[:9] == "CALL_HOLD":
            client.notify("CALL_HOLD")
        elif sentence[:11] == "CALL_RESUME":
            client.notify("CALL_RESUME")
        elif sentence[:8] == "CALL_END":
            client.notify("CALL_END")
        else:
            print("Se ha recibido algo que no es")
            connectionSocket.close()



def manage_call(callSocket,client):
    client.hold_call = 0
    client.end_call = 0

    receiver = threading.Thread(target=video_receiver,args = (client,))
    receiver.start()

    sender = threading.Thread(target=video_sender,args = (client,))
    sender.start()

    receiver.join()
    sender.join()

    print("Not implemented")

def video_receiver(client):
    global end_call
    receiverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiverSocket.bind(('',8003))
    #receiverSocket.listen()
    #conn, addr = receiverSocket.accept()

    data = b'' ### CHANGED
    payload_size = struct.calcsize("L") ### CHANGED

    while end_call == 0:

        # Retrieve message size
        data,_ = receiverSocket.recvfrom(60000)

        data=data.split('#')

        #packed_msg_size = data[:payload_size]
        data = data[-1]
        #msg_size = struct.unpack("L", packed_msg_size)[0] ### CHANGED

        # Retrieve all data based on message size
       

        #frame_data = data[:msg_size]
        #data = data[msg_size:]
        frame = cv2.imdecode(np.frombuffer(data, np.uint8), 1)
        # Extract frame
        #decimg = cv2.resize(frae, RESOLUCION_HIGH_VALUE)


        # Display
        cv2.imshow('frame', frame)
        cv2.waitKey(1)


def video_sender(client):
    global end_call
    WIDTH=400
    senderSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    senderSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    order_num=0
    cap = cv2.VideoCapture(0)
    
    while(end_call == 0):
        ret, frame = cap.read()
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            break
    
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, 50]
        result, encimg = cv2.imencode('.jpg', frame, encode_param)
        # Serialize frame
        data = encimg.tobytes()
        #data = pickle.dumps(frame)

        # Send message length first
        header=order_num+'#'+time.time()+'#'+"640+380"+"120"
        header_bytes=header.tobytes()
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        # Then data
        #senderSocket.sendto(message_size + data,('localhost',8003))
        senderSocket.sendto(header_bytes + data,(client.selected_ip,int(client.selected_data_port)))



'''
semaforo = threading.Lock()
#call_waiter(8000,None,semaforo)
#thr = threading.Thread(target=call_waiter,args = (8004,None,semaforo))
#thr.start()

hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
print("Calling...")
print(call("paco",local_ip,8000,local_ip,8001,semaforo,None))
'''