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
import heapq
from conexion_servidor import *
end_call = 0
current_call = 0
connectionSocket = None
callSocket = None

def call(target_nick,target_IP, target_port, user_IP,user_Port,semaforo,client):
    global current_call
    global callSocket
    #global connectionSocket
    serverName = target_IP
    serverPort = target_port

    semaforo.acquire()
    if(current_call == 1):
        semaforo.release()
        client.app.infoBox("Error", "Finaliza antes tu llamada para realizar otra")
        return
    semaforo.release()

    callSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    callSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    callSocket.connect((serverName,int(serverPort)))
    #sentence = "CALLING "+ target_nick + " "+ user_IP + ":"+ str(user_Port)
    sentence = "CALLING "+ client.my_nick + " "+ str(client.my_data_port)
    callSocket.send(sentence.encode())

    '''
    if modifiedSentence[:9] == "CALL_BUSY":
        return 1
    else:
        return 2
    '''

def call_waiter(user_Port,client,semaforo):

    waitingSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    waitingSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    waitingSocket.settimeout(1)
    try:
        waitingSocket.bind((client.my_ip, int(client.my_control_port)))
    except OSError:
        
        client.app.infoBox("Error", "Hay un usuario activo usando el puerto de control "+ str(client.my_control_port))

        client.app.setTabbedFrameDisabledTab("Tabs", "LIST USERS", True)
        client.app.setTabbedFrameDisabledTab("Tabs", "SEARCH USER", True)

        return None

    waitingSocket.listen(10)

    while client.app.alive:
        
        wait_call(user_Port,client,semaforo,waitingSocket)
        
    waitingSocket.close()
        

def wait_call(user_Port,client,semaforo,waitingSocket):
    global current_call
    global connectionSocket
    global end_call
    global callSocket

    #waitingSocket.bind(('', int(user_Port)))
   #aqui hay que poner más para el call_busy
    print("Servidor preparado para recibir")
    
    try:
        connectionSocket, addr = waitingSocket.accept()
    except socket.timeout:
        return

    while client.app.alive:
        print("Empezamos bucle")
        
        print("ITERACION")
        print("SALGO DEL BUCLE") 
        try:
            sentence = connectionSocket.recv(1024)
        except socket.timeout:
            continue
        sentence = sentence.decode('utf-8')
        print("Se ha recibido:")
        print(sentence)
        print("")
        words = sentence.split(" ")
        print(words)   
        if sentence==b'':
            break
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
                    client.accepted_call=0
                    current_call = 1
                    semaforo.release()
                    client.selected_data_port=words[2]
                    data=query(words[1])
                    nick, ip, control_port, versions=data
                    client.selected_control_port=control_port

                    client.selected_ip=ip

                    mensaje = "CALL_ACCEPTED "+client.my_nick+" "+client.my_data_port
                    

                    callSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    callSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    callSocket.connect((client.selected_ip,int(client.selected_control_port)))

                    callSocket.send(mensaje.encode())

                    thr = threading.Thread(target=manage_call,args = (client,))
                    thr.start()
                else:
                    mensaje = "CALL_DENIED "+words[1]
                    connectionSocket.send(mensaje.encode())
        elif sentence[:9] == "CALL_HOLD":
            client.stop_sending_video=True
        elif sentence[:11] == "CALL_RESUME":
            client.stop_sending_video=False
        elif sentence[:8] == "CALL_END":
            print("RECIBO CALL END")
            client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
            end_call = 1
            current_call=0
            break

        elif sentence[:13] == "CALL_ACCEPTED":
            print("prelock call")
            splitted=sentence.split(" ")

            if splitted[1]!=words[1]:
                client.app.infoBox("Error", "Los nicks no coinciden")
                return

            
            semaforo.acquire()
            if(current_call == 1):
                semaforo.release()
                raise Exception("There is already a call")


            current_call = 1
            semaforo.release()


            
            client.selected_data_port=splitted[2]
            data= query(splitted[1])
            nick, ip, control_port, versions=data

            client.selected_ip=ip
            
            print("post-lock call")
            thr = threading.Thread(target=manage_call,args = (client,))
            thr.start()
            
        else:
            print("Se ha recibido algo que no es")
            
            break
    print("SALGO DEL BUCLE")        
    connectionSocket.close()



def manage_call(client):
    global end_call
    end_call=0
    client.stop_sending_video = False
    receiver = threading.Thread(target=video_receiver,args = (client,))
    receiver.start()

    sender = threading.Thread(target=video_sender,args = (client,))
    sender.start()

    client.app.showSubWindow("Panel de la llamada")


def video_receiver(client):
    global end_call
    receiverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiverSocket.bind((client.my_ip,int(client.my_data_port)))
    receiverSocket.settimeout(0.1)
    #receiverSocket.listen()
    #conn, addr = receiverSocket.accept()

    data = b'' ### CHANGED
    #payload_size = struct.calcsize("L") ### CHANGED

    while end_call == 0 and client.app.alive:

        # Retrieve message size
        try:
            data,_ = receiverSocket.recvfrom(60000)
        except socket.timeout:
            continue

        if client.stop_sending_video:
            continue

        data=data.split(b'#')
        order_num, timestamp, resolucion, fps=data[0], data[1], data[2], data[3]

        real_data=b"#".join(data[4:])

        #packed_msg_size = data[:payload_size]
        
        #msg_size = struct.unpack("L", packed_msg_size)[0] ### CHANGED

        # Retrieve all data based on message size
       

        #frame_data = data[:msg_size]
        #data = data[msg_size:]
        frame = cv2.imdecode(np.frombuffer(real_data, np.uint8), 1)
        # Extract frame
        #frame_ = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        #frame__= ImageTk.PhotoImage(Image.fromarray(frame_))

        # Display
        cv2.imshow('frame', frame)
        cv2.waitKey(1)
    cv2.destroyAllWindows()
    print("termino de recibir video")
    receiverSocket.close()

def video_sender(client):
    global end_call
    WIDTH=400
    senderSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    senderSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    order_num=0

    client.enviando = cv2.VideoCapture(client.video_mostrado)

    while(end_call == 0):
        if client.stop_sending_video:
            continue

        ret, frame = client.enviando.read()

        

        if ret is False:
                  
            client.enviando.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = client.enviando.read()
        if frame is None:
            continue
    
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, 50]
        #print(frame, encode_param)
        result, encimg = cv2.imencode('.jpg', frame, encode_param)
        # Serialize frame
        data = encimg.tobytes()
        #data = pickle.dumps(frame)

        # Send message length first
        header=str(order_num)+'#'+str(time.time())+'#'+client.resolucion+"#"+"36"+"#"
        order_num+=1
        header_bytes=bytes(header, 'utf-8')

        #print(len(data))
        #print(client.selected_ip, client.selected_data_port)
        # Then data
        #senderSocket.sendto(message_size + data,('localhost',8003))
        senderSocket.sendto(header_bytes + data,(client.selected_ip,int(client.selected_data_port)))
    senderSocket.close()


def call_end(client):
    global current_call
    global callSocket
    global end_call
    client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
    end_call=1
    time.sleep(0.5)
    message = 'CALL_END' + client.my_nick
    message = bytes(message, 'utf-8')
    callSocket.send(message)
    current_call=0
    print("lo mando")

def parar_llamada(client):

    global callSocket
    message = 'CALL_HOLD ' + client.my_nick
    message = bytes(message, 'utf-8')
    callSocket.send(message)

    
def continuar_llamada(client):

    global callSocket
    message = 'CALL_RESUME ' + client.my_nick
    message = bytes(message, 'utf-8')
    callSocket.send(message)


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