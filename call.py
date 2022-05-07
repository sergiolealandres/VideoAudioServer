from datetime import datetime, timedelta
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
from audio import audio_receiver, audio_sender
from concurrent.futures import ThreadPoolExecutor
from Crypto.Cipher import AES
from Crypto.Util.Padding import *

from verification import validIP, validPort


current_call = 0
callSocket = None
p, g, x, private, y, key=0,0,0,0,0,0

MIN_FPS = 8
BUFF_REC_VIDEO=60000
SEND_FPS=32
HALF_QUALITY=50
TIMEOUT_ANSWER=10
CONNECTION_TIMEOUT=5
RESPONSE_TIMEOUT=20
BUFF_REC=1024
CALL_SOCKET_TIMEOUT=3
CONTROL_SOCKET_TIMEOUT=1
FRAME_RECIEVER_TIMOUT=0.1
MAX_CONECTIONS=10
EVENT_TIMEOUT=2
LEN_ACCEPTED_CIPHER=4
LEN_CALLING_CIPHER=6
RESOLUTION_OWN=(160,120)
DEFAULT_FPS=24
FILLING_SECS=2
MAX_RETARDO=0.5


def call_user(semaforo,client):
    global current_call
    global callSocket
    global p
    global g
    global x
    global private
    global y
    global key

    semaforo.acquire()
    if(current_call == 1):
        semaforo.release()
        client.app.infoBox("Error", "Finaliza antes tu llamada para realizar otra")
        return
    semaforo.release()

    callSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    callSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    callSocket.settimeout(CONNECTION_TIMEOUT)
    try:
        callSocket.connect((client.selected_ip,int(client.selected_control_port)))
    except socket.timeout:
        client.app.infoBox("Error", "El usuario " + client.selected_nick + " no está conectado")
        return

    except ConnectionRefusedError:
        client.app.infoBox("Error", "El usuario " + client.selected_nick + " no está conectado")
        return
    except OSError:
        client.app.infoBox("Error", "No route to host")
        return

    sentence = "CALLING "+ client.my_nick + " "+ str(client.my_data_port)
    if client.cipher==True:

        p, g, x, private = generate_keys()
        sentence+=" "+ str(p) + " " + str(g) + " " + str(x)

    callSocket.send(sentence.encode())
    callSocket.settimeout(RESPONSE_TIMEOUT)
    try:
        sentence = callSocket.recv(BUFF_REC)
        sentence = sentence.decode('utf-8')

    except socket.timeout:
        client.app.infoBox("Error", "El usuario " + client.selected_nick + " no ha contestado")
        resetear_valores(client)
        callSocket.close()
        return
    except ConnectionResetError:
        client.app.infoBox("Error", "Ha habido un problema con la conexión")
        resetear_valores(client)
        callSocket.close()
        return
    
    if sentence[:13] == "CALL_ACCEPTED":
        

        splitted=sentence.split(" ")

        if len(splitted)<3:
            client.app.infoBox("Error", "La respuesta no ha sido válida")
            callSocket.close()
            return


        if client.cipher==True:

            if len(splitted)==LEN_ACCEPTED_CIPHER:
                y = int(splitted[3])
                key = generate_cipher_key(y,private,p)
                
                key = key.to_bytes(AES.block_size, "little")
                client.cifrador=AES.new(key, AES.MODE_ECB)

            else:
                client.cipher=False
            
        print(splitted[1], client.selected_nick)

        if splitted[1]!=client.selected_nick:
            client.app.infoBox("Error", "Los nicks no coinciden")
            callSocket.close()
            return

        
        client.selected_data_port=splitted[2]

        if validPort(client.selected_data_port)==False:
            client.app.infoBox("Error","Not valid data port")
            callSocket.close()
            return

        client.selected_nick=splitted[1]

        semaforo.acquire()
        if(current_call == 1):
            semaforo.release()
            callSocket.close()
            client.app.infoBox("Error","There is already a call")

        current_call = 1
        semaforo.release()    
        
        thr = threading.Thread(target=manage_call,args = (client,None,))
        thr.start()
    elif sentence[:9] == "CALL_BUSY":
        client.app.infoBox("Error", "El usuario " + client.selected_nick + " está ocupado")
        callSocket.close()
    elif sentence[:11] == "CALL_DENIED":
        client.app.infoBox("Error", "El usuario " + client.selected_nick + " ha rechazado la llamada")
        callSocket.close()
    else:
        client.app.infoBox("Error", "La respuesta no ha sido válida")
        callSocket.close()

def call_waiter(client,semaforo):
    global current_call
    global p
    global g
    global x
    global private
    global y
    global key

    waitingSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    waitingSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    waitingSocket.settimeout(CONTROL_SOCKET_TIMEOUT)
    try:
        waitingSocket.bind((client.my_ip, int(client.my_control_port)))
    except OSError:
        
        client.app.infoBox("Error", "Hay un usuario activo usando el puerto de control "+ str(client.my_control_port))
        client.app.setTabbedFrameDisabledTab("Tabs", "LIST USERS", True)
        client.app.setTabbedFrameDisabledTab("Tabs", "SEARCH USER", True)
        client.app.setTabbedFrameDisabledTab("Tabs", "Registrarse", False)
        waitingSocket.close() 
        return None

    waitingSocket.listen(MAX_CONECTIONS)

    while client.app.alive:
        try:
            connectionSocket, addr = waitingSocket.accept()
        except socket.timeout:
            continue

        try:
            sentence = connectionSocket.recv(BUFF_REC)
        except socket.timeout:
            continue
        sentence = sentence.decode('utf-8')

        words = sentence.split(" ")

        if sentence=='':
            continue
        if sentence[:7] == "CALLING":

            if len(words)<3:
                client.app.infoBox("Error", "Mensaje de calling no válido")
                callSocket.close()
                return

            semaforo.acquire()
            current_call_value = current_call
            semaforo.release()

            if current_call_value == 1:
                connectionSocket.send("CALL_BUSY".encode())
                connectionSocket.close()
                
            else:
                client.app.setLabel("Nick entrante", words[1] + " te esta llamando...")

                client.accepted_call=0
                client.event_call.clear()
                client.app.showSubWindow("LLamada entrante")
                client.event_call.wait(timeout=TIMEOUT_ANSWER)
                client.app.hideSubWindow("LLamada entrante", useStopFunction=False)

                if client.accepted_call==1:
                    try:
                        data=query(words[1])
                    except ServerErrorTimeout:
                        connectionSocket.close()
                        client.app.infoBox("Error", "DS Timeout")
                        continue

                    nick, ip, control_port, versions=data

                    if validPort(control_port)==False:
                        client.app.infoBox("Error","Not valid control port")
                        connectionSocket.close()
                        continue

                    if validIP(ip)==False:
                        client.app.infoBox("Error","Not valid ip")
                        connectionSocket.close()
                        continue

                    if "V0" not in versions and "V1" not in versions:
                        client.app.infoBox("Error","El usuario no soporta ni la V0 ni la V1")
                        connectionSocket.close()
                        continue

                    if validPort(words[2])==False:
                        client.app.infoBox("Error","Not valid data port")
                        connectionSocket.close()
                        continue

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
                    
                    if "V1" in versions and len(words)==LEN_CALLING_CIPHER:
                        client.cipher=True
                        p,g,x = int(words[3]), int(words[4]), int(words[5])
                        y,private=generate_keys_receiver(p,g)
                        key = generate_cipher_key(x,private,p)

                        key = key.to_bytes(AES.block_size, "little")
                        client.cifrador=AES.new(key, AES.MODE_ECB)
                    else:
                        client.cipher=False
                        
                    client.selected_control_port=control_port
                    client.selected_ip=ip
                    client.selected_nick=nick

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

            splitted=sentence.split(" ")

            if len(splitted)<3:
                client.app.infoBox("Error", "La respuesta no ha sido válida")
                connectionSocket.close()
                continue

            if splitted[1]!=client.selected_nick:
                client.app.infoBox("Error", "Los nicks no coinciden")
                connectionSocket.close()
                continue

            client.selected_data_port=splitted[2]

            if validPort(client.selected_data_port)==False:
                client.app.infoBox("Error","Not valid data port")
                connectionSocket.close()
                continue
            
            semaforo.acquire()
            if(current_call == 1):
                semaforo.release()
                connectionSocket.close()
                client.app.infoBox("Error","There is already a call")

            current_call = 1
            semaforo.release()

            if client.cipher==True:

                if len(splitted)==LEN_ACCEPTED_CIPHER:

                    y = splitted[3]
                    key = generate_cipher_key(y,private,p)

                    key = key.to_bytes(AES.block_size, "little")
                    client.cifrador=AES.new(key, AES.MODE_ECB)
                
                else:
                    client.cipher=False
            
            thr = threading.Thread(target=manage_call,args = (client,None,))
            thr.start()
        else:
            connectionSocket.close() 
        
    waitingSocket.close()        



def manage_call(client,connectionSocket):
    
    global current_call
    global callSocket

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
    client.call_time = time.time()

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
    
    callSocket.settimeout(CALL_SOCKET_TIMEOUT)
    client.app.showSubWindow("Panel de la llamada")

    #CONTROL DE COMUNICACIONES:
    while client.app.alive and client.end_call == 0:
        try:
            sentence = callSocket.recv(BUFF_REC)
        except socket.timeout:

            if client.end_call==1:
                return
            continue
            

        sentence = sentence.decode('utf-8')
        
        if sentence == '':

            if client.app.alive:
                client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
            call_end(client)

        if sentence[:9] == "CALL_HOLD":
            client.call_hold=True
        elif sentence[:11] == "CALL_RESUME":
            client.call_hold=False
            client.sender_event.set()
            client.receiver_event.set()
            client.audio_sender_event.set()
            client.audio_receiver_event.set()
        elif sentence[:8] == "CALL_END":
            client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
            client.end_call = 1
            client.sender_event.set()
            client.receiver_event.set()
            client.audio_sender_event.set()
            client.audio_receiver_event.set()
            
            
        elif sentence[:7]=="MESSAGE":

            texto=client.selected_nick+": "+sentence[8:]

            client.chat.append(texto)
            client.app.updateListBox("Chat", client.chat)
    
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

    try:

        receiverSocket.bind((client.my_ip,int(client.my_data_port)))

    except OSError:
        call_end(client)
        receiverSocket.close()
        client.app.infoBox("Error", "Hay otro usuario con esta misma IP utilizando el puerto"+ str(client.my_data_port)+\
            ".Por ello hemos cerrado la llamada")
        client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
        return
            

    receiverSocket.settimeout(FRAME_RECIEVER_TIMOUT)
    buffer_circular=[]
    id_ultimo_paquete_reproducido=0
    tiempo_ultimo_paquete=0
    reproduction_fps=DEFAULT_FPS

    resolucion_own = RESOLUTION_OWN
    data = b''
   

    #LLenado de dos segundos
    def llenar_buffer(buffer_circular,reproduction_fps):
        tiempo_ultimo_paquete = 0
        while client.end_call == 0 and client.app.alive and len(buffer_circular)<FILLING_SECS*reproduction_fps:

            if client.call_hold == 0:
                # Retrieve message size
                try:
                    data,_ = receiverSocket.recvfrom(BUFF_REC_VIDEO)
                except socket.timeout:
                    
                    continue

                if client.cipher==True:

                    data=client.cifrador.decrypt(data)
                    data=unpad(data, AES.block_size)

                
                data=data.split(b'#')
                order_num, timestamp, _, _=data[0], data[1], data[2], data[3]

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

        return reproduction_fps,tiempo_ultimo_paquete
    
    reproduction_fps,tiempo_ultimo_paquete = llenar_buffer(buffer_circular,reproduction_fps)
   
    if(len(buffer_circular)>0):
        control_time=buffer_circular[0][1]


    while client.end_call == 0 and client.app.alive:
        #Set the status bar time
        
        client.app.setStatusbar("Time: "+str(timedelta(seconds=round((time.time()-client.call_time)))),0)
        

        if client.call_hold is False:
            #Set the status bar fps
            client.app.setStatusbar("Fps: "+str(reproduction_fps),1)


            # Retrieve message size
            
            try:
                data,_ = receiverSocket.recvfrom(BUFF_REC_VIDEO)
                received = True
            except socket.timeout:
                
                received = False
                

            if received:
                if client.cipher==True:

                    data=client.cifrador.decrypt(data)
                    data=unpad(data, AES.block_size)

                data=data.split(b'#')

                if len(data)<=4:
                    client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
                    call_end(client)
                    
                    client.app.infoBox("Error", "Hemos cerrado la llamada porque se están recibiendo frames sin cabecera \
                        o con un formato incorrecto de esta")
                
                order_num, timestamp, _, _=data[0], data[1], data[2], data[3]
                
                
                real_data=b"#".join(data[4:])
                
                frame = cv2.imdecode(np.frombuffer(real_data, np.uint8), 1)
                timestamp=float(timestamp.decode('utf-8'))
                order_num=int(order_num.decode('utf-8'))
                
                if order_num < id_ultimo_paquete_reproducido:
                    continue
                
                tiempo = time.time()
                time_diff = tiempo - tiempo_ultimo_paquete
                tiempo_ultimo_paquete = tiempo
                reproduction_fps=max(MIN_FPS,round(1/((0.8/reproduction_fps + time_diff*0.2))))
            
                heapq.heappush(buffer_circular, (order_num, timestamp, frame))
                
            diff = time.time() - control_time - 1/reproduction_fps

            if len(buffer_circular)>0 and client.app.alive:
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

                if diff > MAX_RETARDO:

            
                    while len(buffer_circular) > MAX_RETARDO*reproduction_fps:

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
                    if len(buffer_circular) > 0:
                        control_time=buffer_circular[0][1]
                
        else:
            #clean the buffer
            while client.end_call == 0 and client.app.alive and client.call_hold is True:
                try:
                    _,_ = receiverSocket.recvfrom(BUFF_REC_VIDEO)
                except socket.timeout:
                    if client.call_hold==False:
                        client.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
                        call_end(client)
                        break
            
            #wait until resume
            while client.end_call == 0 and client.app.alive and client.call_hold is True:
                client.receiver_event.wait(timeout=EVENT_TIMEOUT)
                client.receiver_event.clear()
                if(client.end_call == 0 and client.app.alive and client.call_hold is False):
                    buffer_circular = []
                    reproduction_fps,tiempo_ultimo_paquete = llenar_buffer(buffer_circular,reproduction_fps)
                    
                    if(len(buffer_circular)>0):
                        control_time=buffer_circular[0][1]

    receiverSocket.close()

def video_sender(client):

    fps_sending = SEND_FPS
    senderSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    senderSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    order_num=0
    client.enviando = cv2.VideoCapture(client.video_mostrado)

    while(client.end_call == 0):
        if client.call_hold:
            client.sender_event.wait(timeout = EVENT_TIMEOUT)
            client.sender_event.clear()
            continue
        tiempo_inicio = time.time()

        ret, frame = client.enviando.read()
        
        if ret is False:
                  
            client.enviando.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = client.enviando.read()

        if frame is None:
            continue

        client.current_frame = frame
        frame = cv2.resize(frame,client.sender_tuple)
    
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, HALF_QUALITY]

        result, encimg = cv2.imencode('.jpg', frame, encode_param)
        # Serialize frame
        data = encimg.tobytes()

        # Send message length first
        header=str(order_num)+'#'+str(time.time())+'#'+client.resolucion_sender_value+"#"+str(fps_sending)+"#"
        order_num+=1
        header_bytes=bytes(header, 'utf-8')

        paquete=header_bytes + data

        if client.cipher==True:
            paquete=pad(paquete, AES.block_size)
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
    
    message = 'CALL_END ' + client.my_nick
    message = bytes(message, 'utf-8')
    try:
        callSocket.send(message)
    except IOError as e:
        if e.errno == errno.EPIPE:
            client.end_call=1
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
    client.app.setStatusbar("Time: 0",0)
    client.app.setStatusbar("FPS: 0",1)
    client.cipher=False
    client.chat=[]
    client.app.updateListBox("Chat", client.chat)
    client.video_mostrado="imgs/video_por_defecto.gif"

def send_menssage(client, text):

    global callSocket

    mensaje = "MESSAGE "+text
    mensaje=bytes(mensaje,'utf-8')
    try:
        callSocket.send(mensaje)

    except IOError as e:
        if e.errno == errno.EPIPE:
            client.call_end=1
