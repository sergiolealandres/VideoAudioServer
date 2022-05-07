import random
from sympy import *
MIN_RANGE =2**8
MAX_RANGE= 2**12

def generate_keys():

    primes = [i for i in range(MIN_RANGE, MAX_RANGE) if isprime(i)]
    P = random.choice(primes)
    G = random.choice(primRoots(P))
    private=random.randint(MIN_RANGE, MAX_RANGE)
    x = int(pow(G,private,P))
    return P, G, x, private

#CODE IMPORTED https://stackoverflow.com/questions/40190849/efficient-finding-primitive-roots-modulo-n-using-python
def primRoots(theNum):
    o = 1
    roots = []
    r = 2
    while r < theNum:
        k = pow(r, o, theNum)
        while (k > 1):
            o = o + 1
            k = (k * r) % theNum
        if o == (theNum - 1):
            roots.append(r)
        o = 1
        r = r + 1
    return roots

def generate_keys_receiver(P,G):

    private=random.randint(MIN_RANGE, MAX_RANGE)
    y = int(pow(G,private,P))

    return y, private

def generate_cipher_key(sended, private, P):

    return int(pow(sended,private,P))
