import board
import busio
import adafruit_tca9548a
import socket
import json
import time
import matplotlib.pyplot as plt

# Inicializa o barramento I2C
i2c = busio.I2C(board.SCL, board.SDA,frequency=100000)

# Inicializa o multiplexador TCA9548A
mux = adafruit_tca9548a.TCA9548A(i2c)

#criar uma função para eviar os dados lidos via socket ou salvar em arquivo
def enviar_dados_udp(dados):
    """
    Envia os dados dos sensores via UDP (mais rápido que TCP)
    UDP não garante entrega, mas é muito mais rápido para streaming de dados de sensores
    """
    HOST = '192.168.0.19'  # IP do computador receptor
    PORT = 5000
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            dados_json = json.dumps(dados).encode('utf-8')
            s.sendto(dados_json, (HOST, PORT))
    except Exception as e:
        print(f"Erro ao enviar dados: {e}")
 
contadordesensores=0
array_sensores=[]
grafico_tempo_real=True

def ler_sensores():
    """
    Lê os dados de sensores conectados em cada canal do multiplexador
    """
    sensores_data = {}
    
    # Itera por cada canal do multiplexador (0-7)
    for canal in range(8):
        dispositivos2 = []
        try:
            if mux[canal].try_lock():
                print(f"Dispositivos no canal {canal}: ", end="")
                for addr in range(0x03, 0x78):  # Full I2C address range
                    if addr == 0x70:  # Skip multiplexer itself
                        continue
                    try:
                        mux[canal].writeto(addr, bytes([0]))  # Test write
                        print(f"0x{addr:02X} ", end="")
                        dispositivos2.append(addr)
                    except OSError:
                        pass
                print()
                mux[canal].unlock()
            print(f"Lendo canal {canal}...")
            
            # Seleciona o canal do multiplexador
            i2c_canal = mux[canal]
            
  
            # garantir que não consideramos 0x70 por segurança
            dispositivos3 = [d for d in dispositivos2 if d != 0x6F]

            print(f"  Dispositivos encontrados no canal -- dispositivos2: {[hex(d) for d in dispositivos2]}")

            if dispositivos3 :
                # print(f"  Dispositivos encontrados -------: {[hex(d) for d in dispositivos3]}")
                sensores_data[canal] = {
                    'dispositivos': dispositivos3,
                    'dados': []
                }
                # Tenta ler dados do sensor ISM330DHCX
                '''arquivo_saida = open("dados_sensores.txt", "a")'''

                tempo=0
                numerodopacote=0
                tempo_inicial = time.time()
             
                while(True and tempo<20):  # Lê por 30 segundos para este exemplo
                    for endereco in dispositivos3:
                        tempo+=0.5

                        try:            
                            from adafruit_lsm6ds.ism330dhcx import ISM330DHCX as Sensor
 

                            print(f"  Lendo sensor ISM330DHCX no endereço {hex(endereco)}...")
                            # Não tentar instanciar se por algum motivo endereco for 0x70 
                            if endereco == 0x70:
                                print(f"    Ignorando endereço do multiplexador {hex(endereco)}")
                                continue
                         
                            if( canal == 4 and endereco == 0x6b):
                                tt=0
                                for i in range(100):
                                    tt+=0.1
                                    sensor = Sensor(i2c_canal, address=endereco)
                                    xx, yy, zz = sensor.acceleration    
                                    criaGraficoTempoReal(tt,xx, yy, zz)
                                print(f" encontrei o sensor no endereço {hex(endereco)}, mas ele não é o ISM330DHCX, ignorando...")
                                continue
                            

                             
                            sensor = Sensor(i2c_canal, address=endereco)
                            # print(f"    Sensor inicializado com sucesso no endereço {hex(endereco)}")
                                # Lê aceleração e giroscópio
                            accel_x, accel_y, accel_z = sensor.acceleration
                            gyro_x, gyro_y, gyro_z = sensor.gyro

                            tempo_atual = time.time()-tempo_inicial
                            numerodopacote+=1
               
               
                            contadordesensores+=1

 
                            
                            if( canal==3 and    not grafico_tempo_real):
                                print("sensor plotado:", canal, hex(endereco))
                                print(f"    Aceleração: X={accel_x:.2f}, Y={accel_y:.2f}, Z={accel_z:.2f} m/s²")
                                print(f"    Giroscópio: X={gyro_x:.2f}, Y={gyro_y:.2f}, Z={gyro_z:.2f} rad/s")
                                #construi um grafico em tempo real
                                #plt.plot(accel_x, accel_y, 'ro')  # Exemplo simples
                                # ...existing code...
                                
                                plt.plot(tempo, accel_x, 'ro-', label=f'Gyro X +{contadordesensores}')  # linha vermelha com círculos
                                plt.plot(tempo, accel_y, 'gx-', label=f'Gyro Y +{contadordesensores}')  # linha verde com X
                                plt.plot(tempo, accel_z, 'b^-', label=f'Gyro Z +{contadordesensores}')  # linha azul com triângulos
                                # ...existing code...  
                                plt.pause(0.05)  # Pausa para atualizar o gráfico
                             
                            #break  # Sai do loop após uma leitura para este exemplo
                        except Exception as e:
                            print(f"    Erro ao ler sensor {hex(endereco)}: {e}")
                    
            else:
                print(f"  Nenhum dispositivo encontrado")
                
        except Exception as e:
            print(f"  Erro no canal {canal}: {e}")
    
    return sensores_data

def criaGraficoTempoReal(tt,xx, yy, zz):
   # plt.ion()  # Modo interativo para atualização em tempo real
    plt.plot(tt, xx, 'ro-', label='Gyro X')  # linha vermelha com círculos
    plt.plot(tt, yy, 'gx-', label='Gyro Y')  # linha verde com X
    plt.plot(tt, zz, 'b^-', label='Gyro Z')  # linha azul com triângulos
    plt.title("Dados do Sensor ISM330DHCX - Canal 3")
    plt.xlabel("Tempo (s)")
    plt.ylabel("Valor")
    plt.pause(0.05)
    

def main():
    print("Iniciando leitura dos sensores no multiplexador...")
    print("-" * 50)
    tempoinicial = time.time()  
    print("Tempo inicial:", tempoinicial   )
    dados = ler_sensores()
    tempofinal = time.time()
    print("Tempo final:", tempofinal)
    print("Tempo total de execução:", tempofinal - tempoinicial)
    print("-" * 50)
    print(f"\nResumo: {len(dados)} canais com dispositivos conectados")
    print(f"Total de sensores lidos: {contadordesensores}")
   
     
    return dados

if __name__ == "__main__":
    # Configuração de pinos digitais (exemplo)
    # led = DigitalInOut(board.LED)
    # led.direction = digitalio.Direction.OUTPUT
    
    main()
