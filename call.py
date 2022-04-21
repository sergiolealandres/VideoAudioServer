import socket
from urllib import response

current_call = 0

def call(target_nick,target_IP, target_port, user_IP,user_Port):
    serverName = target_IP
    serverPort = target_port
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.connect((serverName,serverPort))
    sentence = "CALLING "+ target_nick + " "+ user_IP + ":"+ str(user_Port)
    clientSocket.send(sentence.encode())
    modifiedSentence = clientSocket.recv(1024)


    print("Desde el servidor:", modifiedSentence)
    clientSocket.close()

def wait_call(user_Port,client):
    waitingSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    waitingSocket.bind(('', user_Port))
    waitingSocket.listen(1)
    print("Servidor preparado para recibir")

    while 1:
        connectionSocket, addr = waitingSocket.accept()
        sentence = connectionSocket.recv(1024)
        print("Se ha recibido:")
        print(sentence)
        print("")
        words = sentence.split(" ")
        if sentence[:7] != "CALLING":
            connectionSocket.close()
            continue
        
        else:
            if current_call == 1:
                connectionSocket.send("CALL_BUSY")
                """if client.ask_call(words[1]):
                connectionSocket.send("CALL_ACCEPTED "+words[1])
                manage_call()
                return"""
            else:
                connectionSocket.send("CALL_DENIED "+words[1])

def manage_call():
    print("Not implemented")

wait_call(8000)
        