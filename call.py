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
from time import sleep
from conexion_servidor import *

end_call = 0
current_call = 0
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
    callSocket.settimeout(30)
    try:
        callSocket.connect((serverName,int(serverPort)))
    except socket.timeout or ConnectionRefusedError:
        client.app.infoBox("Error", "El usuario " + target_nick + " no está conectado")
        return

    #sentence = "CALLING "+ target_nick + " "+ user_IP + ":"+ str(user_Port)
    sentence = "CALLING "+ client.my_nick + " "+ str(client.my_data_port)
    callSocket.send(sentence.encode())
    try:
        sentence = callSocket.recv(1024)
        sentence = sentence.decode('utf-8')
        print(sentence)
    except socket.timeout:
        client.app.infoBox("Error", "El usuario " + target_nick + " no ha contestado")
        return
    
    if sentence[:13] == "CALL_ACCEPTED":
        print("prelock call")
        splitted=sentence.split(" ")

        if splitted[1]!=target_nick:
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
        thr = threading.Thread(target=manage_call,args = (client,None,))
        thr.start()
    elif sentence[:9] == "CALL_BUSY":
        client.app.infoBox("Error", "El usuario " + target_nick + " está ocupado")
    elif sentence[:11] == "CALL_DENIED":
        client.app.infoBox("Error", "El usuario " + target_nick + " ha rechazado la llamada")
    else:
        client.app.infoBox("Error", "La respuesta no ha sido válida")

def call_waiter(user_Port,client,semaforo):
    global current_call
    global end_call


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
        try:
            connectionSocket, addr = waitingSocket.accept()
        except socket.timeout:
            continue
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
            continue
        if sentence[:7] == "CALLING":
            print("prelock wait")
            semaforo.acquire()
            current_call_value = current_call
            semaforo.release()
            print("postlock wait", current_call_value)
            if current_call_value == 1:
                connectionSocket.send("CALL_BUSY".encode())
                connectionSocket.close()
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
                        connectionSocket.close()
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
                    
                    connectionSocket.send(mensaje.encode())
                    
                    thr = threading.Thread(target=manage_call,args = (client,connectionSocket))
                    thr.start()
                else:
                    mensaje = "CALL_DENIED "+words[1]
                    connectionSocket.send(mensaje.encode())
                    connectionSocket.close()
        else:
            print("Se ha recibido algo que no es")
            connectionSocket.close() 
        
    waitingSocket.close()        



def manage_call(client,connectionSocket):
    global end_call
    global current_call
    global callSocket
    print("Entramos en la llamada")

    if connectionSocket is not None:
        callSocket = connectionSocket

    end_call=0
    client.sender_event = threading.Event()
    client.receiver_event = threading.Event()
    client.call_hold = False
    client.current_frame = np.array([])
    receiver = threading.Thread(target=video_receiver,args = (client,))
    receiver.start()

    sender = threading.Thread(target=video_sender,args = (client,))
    sender.start()

    client.app.showSubWindow("Panel de la llamada")

    #CONTROL DE COMUNICACIONES:
    while client.app.alive and end_call == 0:
        try:
            sentence = callSocket.recv(1024)
        except socket.timeout:
            continue
        sentence = sentence.decode('utf-8')
        print("Se ha recibido:")
        print(sentence)
        print("")
        if sentence[:9] == "CALL_HOLD":
            client.call_hold=True
        elif sentence[:11] == "CALL_RESUME":
            client.call_hold=False
            client.sender_event.set()
        elif sentence[:8] == "CALL_END":
            print("RECIBO CALL END")
            client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
            end_call = 1
            client.sender_event.set()
            
        else:
            print("Se ha recibido algo que no es")
            
    
    client.semaforo.acquire()
    current_call = 0
    client.semaforo.release()

    callSocket.close()
    sender.join()
    receiver.join()
    return



def video_receiver(client):
    global end_call
    frame = None
    resolucion = None
    receiverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiverSocket.bind((client.my_ip,int(client.my_data_port)))
    receiverSocket.settimeout(0.1)
    #receiverSocket.listen()
    #conn, addr = receiverSocket.accept()

    data = b'' ### CHANGED
    #payload_size = struct.calcsize("L") ### CHANGED

    while end_call == 0 and client.app.alive:
        
        if client.call_hold == 0:
            # Retrieve message size
            try:
                data,_ = receiverSocket.recvfrom(60000)
            except socket.timeout:
                print("No llega")
                continue

            data=data.split(b'#')
            order_num, timestamp, resolucion, fps=data[0], data[1], data[2], data[3]
            resolucion = resolucion.decode("utf-8")
            resolucion = resolucion.split("x")
            resolucion = (int(resolucion[0]),int(resolucion[1]))
            real_data=b"#".join(data[4:])
            resolucion_own = (int(resolucion[0]/4),int(resolucion[1]/4))
            frame = cv2.imdecode(np.frombuffer(real_data, np.uint8), 1)
            #print("frame ",frame.size)
            own_video = client.current_frame
            if own_video.size > 0:
                own_video = cv2.resize(own_video,resolucion_own)
                frame_shown = frame
                frame_shown[0:own_video.shape[0],0:own_video.shape[1]] = own_video
            else:
                frame_shown = frame

        else:
            own_video = client.current_frame
            if own_video.size > 0:
                frame_shown = cv2.resize(own_video,(160,120))
            else:
                frame_shown = None

        # Display
        if frame_shown is not None:
            cv2.imshow('frame', frame_shown)
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
        if client.call_hold:
            client.sender_event.wait(timeout = 2)
            client.sender_event.clear()
            continue

        ret, frame = client.enviando.read()
        client.current_frame = frame

        

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
    message = 'CALL_END ' + client.my_nick
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