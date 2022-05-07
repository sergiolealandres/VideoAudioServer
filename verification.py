from sympy import minimal_polynomial


MIN_PORT = 1024
MAX_PORT = 49151
MIN_IP = 0
MAX_IP = 255


def validIP(ip):

    if ip.count('.')!=3:
        return False

    part1, part2, part3, part4=ip.split('.')

    return validNum(part1) and validNum(part2) and validNum(part3) and validNum(part4)
    

def validNum(num):

    try:
        num=int(num)
    except ValueError:
        return False

    return num>=MIN_IP and num <=MAX_IP

def validPort(port):

    try:
        port=int(port)
    except ValueError:
        return False

    return port>=MIN_PORT and port<=MAX_PORT

def dont_call_myself(client):

    return client.selected_ip == client.my_ip and client.selected_nick == client.my_nick