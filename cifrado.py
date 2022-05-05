import random
from sympy import *


def generate_keys():

    primes = [i for i in range(2**8, 2**12) if isprime(i)]
    P = random.choice(primes)
    G = random.choice(primRoots(P))
    private=random.randint(2**8, 2**12)
    x = int(pow(G,private,P))
    return P, G, x, private

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

    private=random.randint(2**8, 2**12)
    y = int(pow(G,private,P))

    return y, private

def generate_cipher_key(sended, private, P):

    return int(pow(sended,private,P))
