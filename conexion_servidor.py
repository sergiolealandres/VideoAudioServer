import socket

serverName = 'vega.ii.uam.es'
serverPort = 8000
TIME_OUT=1
buffsize=4096
def register(nick, ip, port, password, versions):
    
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.connect((serverName,serverPort))

    sentence = 'REGISTER '+ nick +' '+ ip +' '+ port+' '+ password+' '+versions
    clientSocket.send(sentence.encode())
    answer = clientSocket.recv(1024)
    clientSocket.close()
    if answer[:10].decode('utf-8')=='OK WELCOME':
        return True
    return False


def query(nick):

    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.connect((serverName,serverPort))
    sentence = 'QUERY '+ nick
    clientSocket.send(sentence.encode())
    answer = clientSocket.recv(1024)

    answer=answer.decode('utf-8')
   
    if answer is None or 'NOK USER_UNKNOWN' == answer[:16]:
        print('Error en query')
        clientSocket.close()
        return None

    answer=answer[14:]
    
    data=answer.split(' ')
    clientSocket.close()
    
    return data[0], data[1], data[2], data[3]

def list_users():
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.connect((serverName,serverPort))
    sentence = 'LIST_USERS'
    clientSocket.send(sentence.encode())
    answer=b''
    clientSocket.settimeout(1)
    while True:   
        try:
            answer += clientSocket.recv(buffsize)
        except socket.timeout:
            break
        
    answer=answer.decode('utf-8')
    
    
    if answer is None or 'OK USERS_LIST' != answer[:13]:
        print('Error en list')
        clientSocket.close()
        return []

    answer = answer[14:]
    ptr = answer.index(' ')

    answer = answer[ptr+1:]

    answer = answer.split('#')
    
    list_users=[]

    for entry in answer:
        entry=entry.split(' ')
        if len(entry)!=4:
            continue
        nick,ip,puerto,timestamp=entry

        if(len(nick)==0):
            continue
        list_users.append((nick,ip,puerto,timestamp))



    clientSocket.close()
    return list_users

def quit():
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.connect((serverName,serverPort))
    sentence = 'QUIT'
    clientSocket.send(sentence.encode())
    modifiedSentence = clientSocket.recv(1024)
    print('Desde el servidor:', modifiedSentence)
    clientSocket.close()
