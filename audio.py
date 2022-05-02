import threading
import time
import wave
import pyaudio
import socket
import queue

CHUNK = 10*1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
BUFF_SIZE = 65536
PORT = 8000

p = pyaudio.PyAudio()
def audio_sender(client):
    global p
    print("Entramos audio sender")
    audio_send_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    audio_send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    audio_send_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
    order_num=0
    #CHUNK = 10*1024
    print("Before pyaudio send")
    #time.sleep(1)
    #p = pyaudio.PyAudio()
    
    print("Before stream sender")
    stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)
    print("After stream sender")

    data = None
    
    while client.end_call == 0 and client.app.alive:
        if client.call_hold:
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
        print("data", len(data))

        header=str(order_num)+'#'+str(time.time())+'#'
        order_num+=1
        header_bytes=bytes(header, 'utf-8')

        audio_send_socket.sendto(header_bytes + data,(client.selected_ip,int(client.selected_data_port)-1))
        time.sleep(CHUNK/RATE)

    audio_send_socket.close()

def audio_receiver(client):
    global p
    print("Entramos audio receiver")

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
        if client.call_hold is False:
            try:
                data,_= audio_receiver_socket.recvfrom(BUFF_SIZE)
            except socket.timeout:
                print("No ha llegado audio")
                continue
            data=data.split(b'#')
            
            order_num, timestamp =data[0], data[1]
            frame=b"#".join(data[2:])
           
            print("frame1",len(frame))
            stream_output.write(frame)
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

