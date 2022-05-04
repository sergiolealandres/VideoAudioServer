from email import message
import errno
from glob import glob
import heapq
from multiprocessing import Semaphore
import random
import socket
import threading
import pickle
import time
import cv2
import struct
import base64
import numpy as np
from time import sleep
from cifrado import *
from conexion_servidor import *
from PIL import Image, ImageTk
from audio import *
from concurrent.futures import ThreadPoolExecutor
from Crypto.Cipher import AES
from Crypto.Util.Padding import *


current_call = 0
callSocket = None
MIN_FPS = 8
p, g, x, private, y, key=0,0,0,0,0,0



def call(target_nick,target_IP, target_port, user_IP,user_Port,semaforo,client):
    global current_call
    global callSocket
    global p
    global g
    global x
    global private
    global y
    global key
    
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
    callSocket.settimeout(5)
    try:
        callSocket.connect((serverName,int(serverPort)))
    except socket.timeout:
        client.app.infoBox("Error", "El usuario " + target_nick + " no está conectado")
        return

    except ConnectionRefusedError:
        client.app.infoBox("Error", "El usuario " + target_nick + " no está conectado")
        return

    sentence = "CALLING "+ client.my_nick + " "+ str(client.my_data_port)
    if client.cipher==True:

        p, g, x, private = generate_keys()
        sentence+=" "+ str(p) + " " + str(g) + " " + str(x)

    callSocket.send(sentence.encode())
    callSocket.settimeout(20)
    try:
        sentence = callSocket.recv(1024)
        sentence = sentence.decode('utf-8')
        print(sentence)
    except socket.timeout:
        client.app.infoBox("Error", "El usuario " + target_nick + " no ha contestado")
        return
    
    if sentence[:13] == "CALL_ACCEPTED":
        

        splitted=sentence.split(" ")

        if client.cipher==True:

            if len(splitted)==4:
                y = int(splitted[3])
                key = generate_cipher_key(y,private,p)
                print("MI CLAVE ES", key)
                key = key.to_bytes(16, "little")
                client.cifrador=AES.new(key, AES.MODE_ECB)

            else:
                client.cipher=False
            


        if splitted[1]!=target_nick:
            client.app.infoBox("Error", "Los nicks no coinciden")
            callSocket.close()
            return

        
        semaforo.acquire()
        if(current_call == 1):
            semaforo.release()
            callSocket.close()
            raise Exception("There is already a call")


        current_call = 1
        semaforo.release()


        
        client.selected_data_port=splitted[2]
        client.selected_nick=splitted[1]
        data= query(splitted[1])
        nick, ip, control_port, versions=data

        client.selected_ip=ip
        
        print("post-lock call")
        thr = threading.Thread(target=manage_call,args = (client,None,))
        thr.start()
    elif sentence[:9] == "CALL_BUSY":
        client.app.infoBox("Error", "El usuario " + target_nick + " está ocupado")
        callSocket.close()
    elif sentence[:11] == "CALL_DENIED":
        client.app.infoBox("Error", "El usuario " + target_nick + " ha rechazado la llamada")
        callSocket.close()
    else:
        client.app.infoBox("Error", "La respuesta no ha sido válida")
        callSocket.close()

def call_waiter(user_Port,client,semaforo):
    global current_call
    global p
    global g
    global x
    global private
    global y
    global key


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
        if sentence=='':
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
                
            else:
                client.app.setLabel("Nick entrante", words[1] + " te esta llamando...")

                client.accepted_call=0
                client.event_call.clear()


                client.app.showSubWindow("LLamada entrante")
                client.event_call.wait(timeout=10)
                client.app.hideSubWindow("LLamada entrante", useStopFunction=False)

                if client.accepted_call==1:
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
                    client.selected_nick, ip, control_port, versions=data

                    if "V1" in versions and len(words)==6:
                        client.cipher=True
                        p,g,x = int(words[3]), int(words[4]), int(words[5])
                        y,private=generate_keys_receiver(p,g)
                        key = generate_cipher_key(x,private,p)
                        print("MI CLAVE ES", key)
                        key = key.to_bytes(16, "little")
                        client.cifrador=AES.new(key, AES.MODE_ECB)
                        


                    client.selected_control_port=control_port

                    client.selected_ip=ip

                    mensaje = "CALL_ACCEPTED "+client.my_nick+" "+client.my_data_port

                    if client.cipher==True:

                        mensaje += " " + str(y)
                    
                    connectionSocket.send(mensaje.encode())
                    
                    thr = threading.Thread(target=manage_call,args = (client,connectionSocket))
                    thr.start()
                else:
                    mensaje = "CALL_DENIED "+words[1]
                    connectionSocket.send(mensaje.encode())
                    connectionSocket.close()
        elif sentence[:13] == "CALL_ACCEPTED":
            print("prelock call")
            splitted=sentence.split(" ")

            if splitted[1]!=client.selected_nick:
                client.app.infoBox("Error", "Los nicks no coinciden")
                callSocket.close()
                return

            
            semaforo.acquire()
            if(current_call == 1):
                semaforo.release()
                callSocket.close()
                raise Exception("There is already a call")


            current_call = 1
            semaforo.release()

            if client.cipher==True:

                if len(splitted)==4:

                    y = splitted[3]
                    key = generate_cipher_key(y,private,p)
                    print("MI CLAVE ES", key)
                    key = key.to_bytes(16, "little")
                    client.cifrador=AES.new(key, AES.MODE_ECB)
                
                else:

                    client.cipher=False

            
            client.selected_data_port=splitted[2]
            data= query(splitted[1])
            nick, ip, control_port, versions=data

            client.selected_ip=ip
            
            print("post-lock call")
            thr = threading.Thread(target=manage_call,args = (client,None,))
            thr.start()
        else:
            print("Se ha recibido algo que no es")
            connectionSocket.close() 
        
    waitingSocket.close()        



def manage_call(client,connectionSocket):
    
    global current_call
    global callSocket
    print("Entramos en la llamada")

    if connectionSocket is not None:
        callSocket = connectionSocket

    client.end_call= 0
    client.mute = False
    client.deafen = False
    client.timestamp_last_image = 0
    client.sender_event = threading.Event()
    client.receiver_event = threading.Event()
    client.audio_sender_event = threading.Event()
    client.audio_receiver_event = threading.Event()

    client.call_hold = False
    client.current_frame = np.array([])
    client.cap.release()
    receiver = threading.Thread(target=video_receiver,args = (client,))

    sender = threading.Thread(target=video_sender,args = (client,))

    audio_send = threading.Thread(target=audio_sender,args = (client,))

    audio_recv = threading.Thread(target=audio_receiver,args = (client,))
    
    receiver.start()
    sender.start()
    audio_recv.start()
    audio_send.start()
    

    client.app.showSubWindow("Panel de la llamada")

    #CONTROL DE COMUNICACIONES:
    while client.app.alive and client.end_call == 0:
        try:
            sentence = callSocket.recv(1024)
        except socket.timeout:
            continue

        
        

        sentence = sentence.decode('utf-8')
        
        if sentence == '':
            continue
        print("Se ha recibido:")
        print(sentence)
        print("")
        if sentence[:9] == "CALL_HOLD":
            client.call_hold=True
        elif sentence[:11] == "CALL_RESUME":
            client.call_hold=False
            client.sender_event.set()
            client.receiver_event.set()
            client.audio_sender_event.set()
            client.audio_receiver_event.set()
        elif sentence[:8] == "CALL_END":
            print("RECIBO CALL END")
            client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
            client.end_call = 1
            client.sender_event.set()
            client.receiver_event.set()
            client.audio_sender_event.set()
            client.audio_receiver_event.set()
            
            
        elif sentence[:7]=="MESSAGE":

            print(client.selected_nick)
            print("eeeee")
            texto=client.selected_nick+": "+sentence[8:]+"\n\n"
            print(texto)
            print("eeeee")
            client.app.setTextArea("Chat", texto, end=True, callFunction=False)
            #client.app.setMessage("Chat", client.chat)

    
    client.semaforo.acquire()
    current_call = 0
    client.semaforo.release()

    callSocket.close()
    sender.join()
    receiver.join()
    resetear_valores(client)

    if(client.camera_conected == 1):
        client.cap = cv2.VideoCapture(0)
        client.app.registerEvent(client.capturaVideo)
    else:
        client.cap = cv2.VideoCapture(client.imagen_no_camera)
    return



def video_receiver(client):


    
    frame = None
    resolucion = None
    receiverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiverSocket.bind((client.my_ip,int(client.my_data_port)))
    receiverSocket.settimeout(0.1)
    buffer_circular=[]
    id_ultimo_paquete_reproducido=0
    tiempo_ultimo_paquete=0
    reproduction_fps=24
    fps_enviados_segundo=0
   

    
    data = b'' ### CHANGED
   

    #LLenado de dos segundos
    def llenar_buffer(buffer_circular,reproduction_fps):
        tiempo_ultimo_paquete = 0
        while client.end_call == 0 and client.app.alive and len(buffer_circular)<2*reproduction_fps:

            if client.call_hold == 0:
                # Retrieve message size
                try:
                    data,_ = receiverSocket.recvfrom(60000)
                except socket.timeout:
                    #print("No llega")
                    continue
                

                if client.cipher==True:

                    data=client.cifrador.decrypt(data)
                    data=unpad(data, 16)

                
                data=data.split(b'#')
                order_num, timestamp, resolucion, fps=data[0], data[1], data[2], data[3]

                real_data=b"#".join(data[4:])
                frame = cv2.imdecode(np.frombuffer(real_data, np.uint8), 1)
                timestamp=float(timestamp.decode('utf-8'))
                order_num=int(order_num.decode('utf-8'))

                if tiempo_ultimo_paquete != 0:
                    tiempo = time.time()
                    time_diff = tiempo - tiempo_ultimo_paquete
                    tiempo_ultimo_paquete=tiempo
                else:
                    time_diff = 1/reproduction_fps
                    tiempo_ultimo_paquete = time.time()

                reproduction_fps=max(MIN_FPS,round(1/((0.8/reproduction_fps + time_diff*0.2))))
                heapq.heappush(buffer_circular, (order_num,timestamp, frame))
                #print("llenando",len(buffer_circular),reproduction_fps)
        return reproduction_fps,tiempo_ultimo_paquete
    
    reproduction_fps,tiempo_ultimo_paquete = llenar_buffer(buffer_circular,reproduction_fps)
   
    if(len(buffer_circular)>0):
        control_time=buffer_circular[0][1]


    while client.end_call == 0 and client.app.alive:
        if client.call_hold is False:
            # Retrieve message size
            try:
                data,_ = receiverSocket.recvfrom(60000)
            except socket.timeout:
                #print("No llega")
                continue

            if client.cipher==True:

                data=client.cifrador.decrypt(data)
                data=unpad(data, 16)

            data=data.split(b'#')

            if len(data)<=4:
                call_end(client)
            
            order_num, timestamp, resolucion, fps=data[0], data[1], data[2], data[3]
            resolucion = resolucion.decode("utf-8")
            resolucion = resolucion.split("x")
            resolucion = (int(resolucion[0]),int(resolucion[1]))
            
            real_data=b"#".join(data[4:])
            resolucion_own = (160,120)
            frame = cv2.imdecode(np.frombuffer(real_data, np.uint8), 1)
            timestamp=float(timestamp.decode('utf-8'))
            order_num=int(order_num.decode('utf-8'))
            
            if order_num < id_ultimo_paquete_reproducido:
                continue
            
            tiempo = time.time()
            time_diff = tiempo - tiempo_ultimo_paquete
            tiempo_ultimo_paquete = tiempo
            reproduction_fps=max(MIN_FPS,round(1/((0.8/reproduction_fps + time_diff*0.2))))
           
            heapq.heappush(buffer_circular, (order_num,timestamp, frame))
            
            diff = time.time() - control_time - 1/reproduction_fps
            #print("fps: ",reproduction_fps,fps,len(buffer_circular),diff)
            if len(buffer_circular)>0:
                if diff < 0:
                    continue

                elif diff >= 0:
                    
                    control_time += 1/reproduction_fps
                    frame=buffer_circular[0][2]
                    id_ultimo_paquete_reproducido= buffer_circular[0][0]
                    client.timestamp_last_image = buffer_circular[0][1]
                    heapq.heappop(buffer_circular)
               

                own_video = client.current_frame
                if own_video.size > 0:
                    frame=cv2.resize(frame, client.resolucion_tuple)
                    own_video = cv2.resize(own_video,resolucion_own)
                    frame_shown = frame
                    frame_shown[0:own_video.shape[0],0:own_video.shape[1]] = own_video
                else:
                    frame_shown = cv2.resize(frame, client.resolucion_tuple)
                    

                # Display
                if frame_shown is not None:

                    
                    
                    cv2_im = cv2.cvtColor(frame_shown, cv2.COLOR_BGR2RGB)
                    img_tk = ImageTk.PhotoImage(Image.fromarray(cv2_im))
                    client.app.setImageData("Video mostrado", img_tk, fmt='PhotoImage') 

                if diff >0.5:

            
                    while len(buffer_circular) > 0.5*reproduction_fps:

                        frame=buffer_circular[0][2]
                        client.timestamp_last_image = buffer_circular[0][1]
                        id_ultimo_paquete_reproducido= buffer_circular[0][0]
                        heapq.heappop(buffer_circular)
                

                        own_video = client.current_frame
                        if own_video.size > 0:
                            frame_shown = cv2.resize(frame, client.resolucion_tuple)
                            own_video = cv2.resize(own_video,resolucion_own)
                            frame_shown[0:own_video.shape[0],0:own_video.shape[1]] = own_video
                        else:
                            frame_shown = cv2.resize(frame, client.resolucion_tuple)

                        # Display
                        if frame_shown is not None:
                            cv2_im = cv2.cvtColor(frame_shown, cv2.COLOR_BGR2RGB)
                            img_tk = ImageTk.PhotoImage(Image.fromarray(cv2_im))
                            client.app.setImageData("Video mostrado", img_tk, fmt='PhotoImage')

                    control_time=buffer_circular[0][1]



        else:
            #clean the buffer
            while client.end_call == 0 and client.app.alive and client.call_hold is True:
                try:
                    _,_ = receiverSocket.recvfrom(60000)
                except socket.timeout:
                    #print("No llega")
                    break
            
            print("CAAAAAAAAAAAAAAAAAAAALlllllllllllll HHHHHHHHHHHHHHHHOOOOOOOOOOOOOOOOOOLLLLLLLLLLLLLLLD")
            #wait until resume
            while client.end_call == 0 and client.app.alive and client.call_hold is True:
                client.receiver_event.wait(timeout=2)
                client.receiver_event.clear()
                if(client.end_call == 0 and client.app.alive and client.call_hold is False):
                    buffer_circular = []
                    reproduction_fps,tiempo_ultimo_paquete = llenar_buffer(buffer_circular,reproduction_fps)
                    
                    if(len(buffer_circular)>0):
                        control_time=buffer_circular[0][1]

        

    client.app.setImage("Video mostrado", client.imagen_no_camera)
    print("termino de recibir video")
    receiverSocket.close()

def video_sender(client):

    fps_sending = 32
    senderSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    senderSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print(int((client.selected_data_port)))
    
    order_num=0

    client.enviando = cv2.VideoCapture(client.video_mostrado)

    while(client.end_call == 0):
        if client.call_hold:
            client.sender_event.wait(timeout = 2)
            client.sender_event.clear()
            continue
        tiempo_inicio = time.time()

        #client.setImageResolution(client.resolucion_sender)

        ret, frame = client.enviando.read()
        
        if ret is False:
                  
            client.enviando.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = client.enviando.read()
        if frame is None:
            continue

        client.current_frame = frame
        frame = cv2.resize(frame,client.sender_tuple)
    
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, 50]
        #print(frame, encode_param)
        result, encimg = cv2.imencode('.jpg', frame, encode_param)
        # Serialize frame
        data = encimg.tobytes()
        #data = pickle.dumps(frame)

        # Send message length first

        
        header=str(order_num)+'#'+str(time.time())+'#'+client.resolucion_sender_value+"#"+str(fps_sending)+"#"
        order_num+=1
        header_bytes=bytes(header, 'utf-8')

        paquete=header_bytes + data

        if client.cipher==True:
            print("CIFRO")
            paquete=pad(paquete, 16)
            paquete=client.cifrador.encrypt(paquete)


        time_diff = time.time() - tiempo_inicio
        if time_diff < 1.0/fps_sending:
            time.sleep(1.0/fps_sending - time_diff)
        


        senderSocket.sendto(paquete,(client.selected_ip,int(client.selected_data_port)))
    
    client.enviando.release()
    senderSocket.close()


def call_end(client):
    global current_call
    global callSocket
    
    client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
    
    message = 'CALL_END ' + client.my_nick
    message = bytes(message, 'utf-8')
    try:
        callSocket.send(message)
    except IOError as e:
        if e.errno == errno.EPIPE:
            client.call_end=1
    client.end_call=1
    client.sender_event.set()
    client.receiver_event.set()
    client.sender_event.set()
    client.receiver_event.set()
    

def parar_llamada(client):

    global callSocket
    client.call_hold = True
    message = 'CALL_HOLD ' + client.my_nick
    message = bytes(message, 'utf-8')
    try:
        callSocket.send(message)
        print("envio parar")
    except IOError as e:
        if e.errno == errno.EPIPE:
            client.call_end=1

    
def continuar_llamada(client):

    global callSocket
    message = 'CALL_RESUME ' + client.my_nick
    message = bytes(message, 'utf-8')
    try:
        callSocket.send(message)

    except IOError as e:
        if e.errno == errno.EPIPE:
            client.call_end=1

    client.call_hold = False
    client.sender_event.set()
    client.receiver_event.set()
    client.sender_event.set()
    client.receiver_event.set()

def resetear_valores(client):

    client.selected_nick, client.selected_ip, client.selected_control_port, \
        client.selected_data_port,client.selected_version=None,None, None,None,None
    client.searched_user=False
    client.app.setEntry("User\t\t", "")
    client.app.setLabel("UserInfo", "")
    client.cipher=False
    client.app.clearTextArea("Chat", False)

def send_menssage(client, text):

    global callSocket

    mensaje = "MESSAGE "+text
    try:
        callSocket.send(mensaje)

    except IOError as e:
        if e.errno == errno.EPIPE:
            client.call_end=1

