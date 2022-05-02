import threading
import time
import wave
import pyaudio
import socket
import queue

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
BUFF_SIZE = 65536

def audio_sender(client):
    print("Entramos audio sender")
    audio_send_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    audio_send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    audio_send_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)

    #CHUNK = 10*1024
    print("Before pyaudio send")
    time.sleep(1)
    p = pyaudio.PyAudio()
    
    print("Before stream sender")
    stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)
    print("After stream sender")

    data = None

    while client.app.alive:
        data = stream.read(CHUNK)
        audio_send_socket.sendto(data,int(client.selected_data_port)-1)
        time.sleep(CHUNK/RATE)

    audio_send_socket.close()

def audio_receiver(client):
    print("Entramos audio receiver")
    q = queue.Queue(maxsize=2000)
    audio_receiver_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    audio_receiver_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
    print("Before pyaudio recv")
    #time.sleep(1)
    p = pyaudio.PyAudio()
    
    #CHUNK = 10*1024
    print("Before stream receiver")
    stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK)
    print("After stream receiver")
                
    # create socket

    while client.app.alive:
        frame,_= audio_receiver_socket.recvfrom(BUFF_SIZE)
        stream.write(frame)
    
    audio_receiver_socket.close()
    print('Audio closed')
