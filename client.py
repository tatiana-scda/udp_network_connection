#!/usr/bin/env python3

import random
import socket
import hashlib
import time
import bitstring
import sys
from threading import Timer
from threading import Lock
from collections import defaultdict

janelaLock = Lock()
arquivo_entrada             = sys.argv[1]
ip_port                     = sys.argv[2]
tamanho_janela              = int(sys.argv[3])
timeout                     = int(sys.argv[4])
md5_erro                    = float(sys.argv[5])

janela                       = {}  
fim_janela                   = 1
inicio_janela                = 1

HOST = ip_port[0:ip_port.find(':')]
PORT = int(ip_port[ip_port.find(':')+1:])
udp  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dest = (HOST, PORT)

def calculaMD5ACK(pacote):
    m   = hashlib.md5()
    m.update(pacote[0:20])
    md5 = m.digest()
    return pacote[20:36] == md5

def calculaMD5(pacote, comeco):
    global md5_erro
    m                        = hashlib.md5()
    m.update(pacote)
    md5                      = m.digest()
    pacote[comeco:comeco+16] = md5

    rand = random.random()
    if rand < md5_erro:
        print(md5_erro, rand)
        print('CORROMPE')
        pacote[comeco+15] = (pacote[comeco+15] + 1) % 256
    return pacote

def bateuTimer(seq_num):
    global timeout

    print("bateu timer ", seq_num)
    janelaLock.acquire()
    enviaPacote(seq_num)
    janela[seq_num]['timer'] = Timer(timeout, bateuTimer, [seq_num])
    janela[seq_num]['timer'].start()
    janelaLock.release()
    
def enviaPacote(seq_num):
    global dest, udp, janelaLock
    if seq_num not in janela:
        print('Aborting send! seq_num acked!!!!!!!!!!!!')
        return
    pacote = criadorPacote(seq_num, janela[seq_num]['sec'], janela[seq_num]['nsec'], janela[seq_num]['msg'])
    udp.sendto(pacote, dest)
    #print("o pacote é", pacote)


def criadorPacote(num_seq, timestamp_seg, timestamp_nanoseg, mensagem):
    pacote        = bytearray([])
    pacote[0:8]   = bitstring.BitArray(uint=num_seq, length=64).bytes
    pacote[8:16]  = bitstring.BitArray(uint=timestamp_seg, length=64).bytes
    pacote[16:20] = bitstring.BitArray(uint=timestamp_nanoseg, length=32).bytes
    pacote[20:22] = bitstring.BitArray(uint=len(mensagem), length=16).bytes
    pacote.extend(map(ord, mensagem))
    pacote        = calculaMD5(pacote, 22+len(mensagem))
    return pacote

def recebeACK():
    global udp

    pacote  = udp.recvfrom(36)[0]
    correto = calculaMD5ACK(pacote) #se o md5 funcionar para o pacote
    seq_num  = pacote[0:8]
    seq_num  = int.from_bytes(seq_num, byteorder='big', signed=False) #bytearray para int
    return (seq_num, correto)

# def enviarPacote(dest, pacote):
#     global udp, timeout, janelaCheia

#     while (janelaCheia < tamanho_janela):
#         #criacao do pacote
#         pacote            = criadorPacote(id_pacote, timestamp_sec, timestamp_nanosec, mensagem)
#         udp.sendto(pacote, dest) #envia_pacote

#         for i in range (len(arquivo_entrada)):
#             while janelaDeslizante[i] != True:
#                 recebendoPacote(janelaDeslizante, arquivo_entrada, udp, dest, timeout) #incrementa janela
#     # except Exception as e:
    #     if janelaDeslizante[i]:
    #     enviarPacote(udp, dest, timeout)


def janelaDeslizante():
    global tamanho_janela, udp, dest, timeout, fim_janela, inicio_janela, janelaLock
    seq_num = 1
    with open(arquivo_entrada, "r") as file:
        for mensagem in file:
            mensagem          = mensagem.rstrip()
            #id_esperando = primeiroSemACK(janelaDeslizante)
            tamanho           = len(mensagem)
            timestamp         = time.time() #para o seg e nanoseg serem da mesma base
            timestamp_sec     = int(timestamp)
            timestamp_nanosec = int((timestamp % 1)*(10 ** 9))
            
            if (fim_janela - inicio_janela == tamanho_janela):
                janelaLock.acquire()
                del janela[inicio_janela]
                inicio_janela  += 1
                janelaLock.release()

            janela[seq_num] = {'msg': mensagem, 'sec': timestamp_sec, 'nsec': timestamp_nanosec, 'acked': False}
            fim_janela += 1

            enviaPacote(seq_num)

            janela[seq_num]['timer'] = Timer(timeout, bateuTimer, [seq_num])
            janela[seq_num]['timer'].start()

            seq_num += 1

            if (fim_janela - inicio_janela == tamanho_janela):
                while(not janela[inicio_janela]['acked']):
                    print("janela travada no ", inicio_janela)
                    seq_ack, correto = recebeACK()
                    if (correto):
                        print("Recebi ACK", seq_ack)
                        janela[seq_ack]['acked'] = True
                        janela[seq_ack]['timer'].cancel()
                        print("cancelou timer", seq_ack)
                    else:
                        print("md5 errado no ack", seq_ack)
                print("destravou")
                
    while (inicio_janela != fim_janela): 
        while(not janela[inicio_janela]['acked']):
            seq_ack, correto = recebeACK()
            if (correto):
                print("Recebi ACK", seq_ack)
                janela[seq_ack]['acked'] = True
                janela[seq_ack]['timer'].cancel()
                print("cancelou timer", seq_ack)
            else:
                print("md5 errado no ack", seq_ack)
        
        inicio_janela  += 1
    print("Envio completo! Fechando UDP :)")
    udp.close()

##### EXECUCAO DO PROGRAMA #####    
janelaDeslizante()