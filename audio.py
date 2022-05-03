import threading
import time
import heapq
import pyaudio
import socket

CHUNK = 5*1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
BUFF_SIZE = 65536
PORT = 8000
MAX_DESYNCRONIZATION = 0.2
MAX_BUFF = 3000

p = pyaudio.PyAudio()
def audio_sender(client):
    global p
    audio_send_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    audio_send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    audio_send_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
    order_num=0
    
    stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)
    data = None
    
    while client.end_call == 0 and client.app.alive:
        if client.call_hold is True or client.mute is True:
            stream.stop_stream()
            client.audio_sender_event.wait(timeout = 2)
            client.audio_sender_event.clear()
            
            continue

        if stream.is_stopped():
            stream.start_stream()

        try:  
            data = stream.read(CHUNK)
        except:
            print("Error")
            time.sleep(0.1)
            continue
        #print("data", len(data))

        header=str(order_num)+'#'+str(time.time())+'#'
        order_num+=1
        header_bytes=bytes(header, 'utf-8')

        audio_send_socket.sendto(header_bytes + data,(client.selected_ip,int(client.selected_data_port)-1))
        time.sleep(CHUNK/RATE)

    audio_send_socket.close()

def audio_receiver(client):
    global p
    id_ultimo_paquete_reproducido = 0
    buffer_circular=[]
    audio_receiver_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    audio_receiver_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)

    audio_receiver_socket.bind((client.my_ip,int(client.my_data_port)-1))
    audio_receiver_socket.settimeout(0.1)
    
    stream_output = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK)
        
    # create socket

    while client.end_call == 0 and client.app.alive:
        if client.call_hold is False and client.deafen is False:
            try:
                data,_= audio_receiver_socket.recvfrom(BUFF_SIZE)
            except socket.timeout:
                #print("No ha llegado audio")
                continue
            data=data.split(b'#')
           
            order_num, timestamp = data[0], data[1]
            order_num = int(order_num.decode('utf-8'))
            timestamp=float(timestamp.decode('utf-8'))
            frame=b"#".join(data[2:])
            if order_num < id_ultimo_paquete_reproducido:
                continue
            
            #stream_output.write(frame)
            

            heapq.heappush(buffer_circular, (order_num,timestamp, frame))

            #Sincronización audio, video
            if len(buffer_circular) > 0:
                first_timestamp = buffer_circular[0][1]
                diff = client.timestamp_last_image - first_timestamp
                print("TIEMPOS VIDEO: ",diff)
                if(abs(diff) < MAX_DESYNCRONIZATION):
                    frame = buffer_circular[0][2]
                    heapq.heappop(buffer_circular)
                    stream_output.write(frame)
                elif diff > MAX_DESYNCRONIZATION:
                    while(len(buffer_circular) > 0):
                        first_timestamp = buffer_circular[0][1]
                        frame = buffer_circular[0][2]
                        stream_output.write(frame)
                        heapq.heappop(buffer_circular)
                        if(client.timestamp_last_image - first_timestamp < MAX_DESYNCRONIZATION):
                            break
                else:
                    if len(buffer_circular) > MAX_BUFF:
                        print("Se recibe audio pero no vídeo. Overflow buffer audio")
                

            
        else:
            
            #clean the buffer
            while client.end_call == 0 and client.app.alive and client.call_hold is True:
                try:
                    _,_ = audio_receiver_socket.recvfrom(60000)
                except socket.timeout:
                    print("Buffer limpio")
                    break
            while client.end_call == 0 and client.app.alive and client.call_hold is True:
                client.audio_receiver_event.wait(timeout=2)
                client.audio_receiver_event.clear()
    
    audio_receiver_socket.close()

"""hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)

thr = threading.Thread(target=audio_receiver, args = (local_ip,))
thr.start()
audio_sender(local_ip)"""
