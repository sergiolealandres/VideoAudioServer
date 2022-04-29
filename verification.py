

def validIP(ip):

    if ip.count('.')!=3:
        return False

    part1, part2, part3, part4=ip.split('.')

    return validNum(part1) and validNum(part2) and validNum(part3) and validNum(part4)
    

def validNum(num):

    return int(num)>=0 and int(num) <=255

def validPort(port):

    return int(port)>=1024 and int(port)<=49151