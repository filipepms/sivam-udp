import threading

import helper as h
import time
import sys
import ahrs
import numpy as np
import os
import pandas as pd
from scipy.spatial.transform import Rotation
import qwiic_i2c
import smbus2
from flask import Flask, jsonify,request,render_template,send_from_directory
from threading import Thread
from helper import quat2sto_single, sto2quat
import signal 
#import socket
#def send_command_to_nexus(xml_command: str, host='10.4.10.74', port=801):
#    """Send an XML command to Nexus Remote Control server."""
#    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#        s.connect((host, port))
#        s.sendall(xml_command.encode('utf-8'))
#        response = s.recv(1024)
#        print("Response:", response.hex())
#        return response
#start_xml = '''<Nexus><Command>Start</Command></Nexus>'''
#stop_xml = '''<Nexus><Command>Stop</Command></Nexus>'''

# Variáveis globais para controle do botão via web
web_button_pressed = False
web_button_enabled = False
web_calibrate_requested = False  
nome_paciente=''

sensores_status = {}


ip_computador_conectado = ''
# Configuração do Flask
app = Flask(__name__)

@app.route('/calibrate', methods=['GET', 'POST'])
def trigger_calibration():
    """Endpoint para disparar a calibração remotamente"""
    global web_calibrate_requested
    web_calibrate_requested = True

    dados = request.get_json()
    nome_enviado = dados.get('nome')
    
    diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta

    with open(os.path.join(diretorio, 'nomes.txt'), 'w') as f: #abrir arquivo do direto atual para escrita, se não existir ele cria, se existir ele sobrescreve o arquivo com o novo nome do paciente recebido via web
        f.write(nome_enviado)
    return jsonify({
        'status': 'success',
        'message': 'Calibração dos sensores solicitada via web'
    }), 200

def check_web_calibrate():
    """Verifica se a calibração foi solicitada pelo usuário"""
    global web_calibrate_requested
    if web_calibrate_requested:
        web_calibrate_requested = False
        return True
    return False

@app.route('/')
def index():
    """Página principal"""
    global ip_computador_conectado
    ip_computador_conectado = request.remote_addr
    print(f"IP do computador conectado: {ip_computador_conectado}")
    diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta

    #escrever o IP do computador conectado em um arquivo de texto para que o ik_streaming possa ler e usar esse IP para enviar os dados via UDP
    with open(os.path.join(diretorio, 'endereco_ip.txt'), 'w') as f: #abrir arquivo do direto atual para escrita, se não existir ele cria, se existir ele sobrescreve o arquivo com o novo IP do computador conectado      
        f.write(ip_computador_conectado)
    return render_template('index.html')

@app.route('/novo_ip')
def grava_ip():
    """Página principal"""
    global ip_computador_conectado
    ip_computador_conectado = request.remote_addr
    print(f"IP do computador conectado: {ip_computador_conectado}")
    diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta

    #escrever o IP do computador conectado em um arquivo de texto para que o ik_streaming possa ler e usar esse IP para enviar os dados via UDP
    with open(os.path.join(diretorio, 'endereco_ip.txt'), 'w') as f: #abrir arquivo do direto atual para escrita, se não existir ele cria, se existir ele sobrescreve o arquivo com o novo IP do computador conectado      
        f.write(ip_computador_conectado)
    return jsonify({'message': 'IP OK'})


 

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Arquivos do Raspberry Pi</title>
</head>
<body>
    <h1>Arquivos Disponíveis</h1>
    <ul>
        {% for arquivo in arquivos %}
            <li>
                {{ arquivo }} 
                <a href="{{ url_for('baixar_arquivo', nome_arquivo=arquivo) }}">
                    <button>Download</button>
                </a>
            </li>
        {% endfor %}
    </ul>
</body>
</html>
"""
@app.route('/sto_calibracao',methods=['POST'])
def envia_sto_calibracao():
    diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta
    dados = request.get_json()
    nome_enviado = dados.get('nome')
    with open(os.path.join(diretorio, 'nomes.txt'), 'w') as f: #abrir arquivo do direto atual para escrita, se não existir ele cria, se existir ele sobrescreve o arquivo com o novo nome do paciente recebido via web
        f.write(nome_enviado)
    print("\n\n")
    print("-"*50)
    print(nome_enviado)
    nome_arquivo=nome_enviado+"tiny_file.sto"
   #nome_enviado="settings.txt"
    return send_from_directory(diretorio, nome_arquivo, as_attachment=True)



@app.route('/listar_arquivos', methods=['GET'])
def listar_arquivos():
    diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta
    caminho=os.path.join(diretorio, "recordings/debug")
    # os.listdir pega todos os nomes de arquivos na pasta
    arquivos = os.listdir(caminho)
    # Filtra para mostrar apenas arquivos, ignorando pastas por enquanto
    arquivos = [f for f in arquivos if os.path.isfile(os.path.join(caminho, f))]
    
    return render_template('template_download.html', arquivos=arquivos)

@app.route('/download/<nome_arquivo>')
def baixar_arquivo(nome_arquivo):
    diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta
    caminho=os.path.join(diretorio, "recordings/debug")
    # send_from_directory é a forma segura do Flask enviar arquivos
    return send_from_directory(caminho, nome_arquivo, as_attachment=True)

@app.route('/calibrate', methods=['POST'])
def calibrate():
    """Endpoint para iniciar calibração dos sensores"""
    # Aqui você pode adicionar a lógica para calibrar os sensores
    # Por exemplo, chamar uma função de calibração ou atualizar o status dos sensores
    print("teste de persistencia da variavel de armazenamento do ip do computador conectado", ip_computador_conectado   )
    print("Iniciando calibração dos sensores...")
    return jsonify({'message': 'Calibração iniciada com sucesso!'})

@app.route('/teste', methods=['GET'])
def teste():
    """Endpoint de teste"""
    print('teste de persistencia da variavel de armazenamento do ip do computador conectado', ip_computador_conectado   )
    return jsonify({'ip_computador_conectado': ip_computador_conectado})

@app.route('/sensor_status', methods=['POST'])
def sensor_status():
    conectados=[]
    """Endpoint para atualizar o status dos sensores"""
    dados = request.get_json()
    sensor_name = dados.get('sensor')
    status = dados.get('status')
     #verificar status de todos os sensores e imprimir
    print("-----------> Status dos Sensores <-----------", sensores_status)
    i=0
    for sensor, status in sensores_status.items():
        conectados.append({'sensor': sensor, 'status': status})
        print(f"Sensor: {sensor}, Status: {status}")
    
    return jsonify({'conectados': conectados, 'message': f'Status do sensor {sensor_name} atualizado para {status}'})

    #codigo em javaScript para enviar o status do sensor para a página web
    #fetch('/sensor_status', {
    #    method: 'POST',
    #    headers: {
    #        'Content-Type': 'application/json'                       #    },
    #    body: JSON.stringify({sensor: 'nome_do_sensor', status     : 'initialized'})
    #})


@app.route('/button/press', methods=['GET', 'POST'])
def press_button():
    """Endpoint para simular pressão do botão"""
    global web_button_pressed
    global nome_paciente
    dados=request.get_json()
    nome_recebido=dados.get('nome')
    nome_paciente = nome_recebido
    diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta

    with open(os.path.join(diretorio, 'nomes.txt'), 'w') as f: #abrir arquivo do direto atual para escrita, se não existir ele cria, se existir ele sobrescreve o arquivo com o novo nome do paciente recebido via web
        f.write(nome_recebido)
    if web_button_enabled:
        web_button_pressed = True
        return jsonify({
            'status': 'success',
            'message': 'Botão pressionado via web',
            'timestamp': time.time()
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': 'Controle web não está habilitado'
        }), 400

def pegaNome():
    return nome_paciente

@app.route('/recalibrate', methods=['POST'])
def recalibrate():
    """Endpoint para recalibrar os sensores"""
    #local para reiniciar o script (o service)

    print("Iniciando recalibração dos sensores...")
    return jsonify({'message': 'Recalibração iniciada com sucesso!','status': 'success'})


def puxar_tomada():
    """Espera 1 segundo e envia um sinal de encerramento para o processo pai"""
    time.sleep(1)
    print("Sinalizando encerramento do processo pai para o systemd reiniciar...")
    
    # os.getppid() pega o PID do processo principal (pai)
    # signal.SIGTERM pede para ele ser encerrado imediatamente
    os.kill(os.getppid(), signal.SIGKILL)

@app.route('/desligar_sivam', methods=['POST'])
def desligar_sivam():
    """Endpoint para desligar o sistema""" 
    #desliga completamente o RPI, cuidado ao usar essa função, ela irá desligar o RPI e será necessário ligar manualmente novamente
    print("Desligando o sistema...")
    response = jsonify({
        'desliga': 'OK',
        'timestamp': time.time()
    }), 200
    threading.Thread(target=desliga).start()
    #os.system("sudo shutdown -h now")
    return response
 
def desliga():
    time.sleep(1)  # Espera um pouco para garantir que a resposta seja enviada antes de desligar
    """Função para desligar o sistema, pode ser chamada de dentro do código para desligar o RPI"""
    print("Desligando o sistema...")
    os.system("sudo shutdown -h now")


@app.route('/reiniciasistema', methods=['GET'])
def reinicia_sistema(): 
    """Endpoint para reiniciar o sistema"""
    #time.sleep(1)
    #os._exit(1)  # Isso irá encerrar o processo atual, e se estiver rodando como um serviço, ele deve reiniciar automaticamente
    threading.Thread(target=puxar_tomada).start()

    return jsonify({'message': 'Sistema reiniciado com sucesso!','status': 'success'})

@app.route('/button/status', methods=['GET'])
def button_status():
    """Endpoint para verificar status do botão"""
    return jsonify({
        'web_enabled': web_button_enabled,
        'web_pressed': web_button_pressed,
        'timestamp': time.time()
    }), 200

@app.route('/button/reset', methods=['POST'])
def reset_button():
    """Endpoint para resetar o estado do botão"""
    global web_button_pressed
    web_button_pressed = False
    return jsonify({
        'status': 'success',
        'message': 'Estado do botão resetado'
    }), 200

def start_web_server(host='0.0.0.0', port=5000):
    """Inicia o servidor web Flask em uma thread separada"""
    app.run(host=host, port=port, debug=False, use_reloader=False)

def check_web_button():
    """Verifica se o botão foi pressionado via web"""
    global web_button_pressed
    if web_button_pressed:
        web_button_pressed = False
        return True
    return False

def parallelIK(ikSolver, s0, ik, time_stamp):
    ikSolver.track(s0)
    ik.put([time.time()-time_stamp])
    time.sleep(0.005)

def readIMU(q, b, fake_online_data, init_time, signals_per_sensor, save_dir_init, home_dir, calibration_q=None, recalibration=None):
    """
    Read IMU sensor data from multiple TCA9548A multiplexed I2C channels and process quaternion estimates.
    This function initializes IMU sensors, handles sensor calibration, reads acceleration and gyroscope data,
    computes quaternion orientations using Mahony filter, and manages web-based control for recording sessions.
    Parameters
    ----------
    q : queue.Queue
        Queue for sending timestamp, quaternion data, and head error to main process
    b : queue.Queue
        Queue for receiving control signals and sending initialization/control information
    fake_online_data : str
        Base path for loading fake/offline IMU data files
    init_time : float
        Initialization time in seconds for sensor calibration data collection
    signals_per_sensor : int
        Number of signals per sensor (typically 6: 3 accel + 3 gyro)
    save_dir_init : str
        Root directory path for saving recorded IMU data
    home_dir : str
        Home directory path for storing calibration data
    calibration_q : queue.Queue, optional
        Queue for sending calibration completion signals (default: None)
    recalibration : queue.Queue, optional
        Queue for receiving recalibration trigger signals (default: None)
    Returns
    -------
    None
        Function runs continuously in a separate process, communicating via queues
    Notes
    -----
    - Reads sensor configuration from 'settings.txt' file (body parts, TCA indices, sampling rate, etc.)
    - Supports ISM330DHCX, LSM6DS33, and LSM6DS032 IMU sensors
    - Implements gyroscope bias calibration and stores offsets in calibration directory
    - Uses web server interface (default port 5000) for remote recording control
    - Supports both real-time and offline (fake data) data collection modes
    - Applies sensor-specific rotation transformations before quaternion computation
    - Saves raw IMU data as numpy arrays to disk during recording sessions
    - Handles graceful sensor I/O errors with continue logic in main loop
    """
    global web_button_enabled
    
    # Load the initialization information about the sensors
    tca_inds = []
    num_parts = 0
    calibrate_sensors = False
    parallelize = False
    old_lines = []
    save_folder = 'test_dir'
    sim_len = 600
    # Defining the external signal trigger
    imu_only = False
    enable_web_control = True  # Habilitar controle web por padrão
    web_port = 5000  # Porta do servidor web
    
    # Iniciar servidor web em thread separada
    if enable_web_control:
        web_button_enabled = True
        web_thread = Thread(target=start_web_server, kwargs={'host': '0.0.0.0', 'port': web_port}, daemon=True)
        web_thread.start()
        print(f"🌐 Servidor web iniciado em http://0.0.0.0:{web_port}")
        print(f"   - Pressionar botão: http://localhost:{web_port}/button/press")
        print(f"   - Verificar status: http://localhost:{web_port}/button/status")
    
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(diretorio_atual, 'settings.txt'), 'r') as f:
        for cnt, line in enumerate(f):
            old_lines.append(line)
            if cnt == 0:
                body_parts = line.split(',')
                num_parts = len(body_parts)
            elif cnt == 1:
                tca_inds = line.split(',')
                if num_parts != len(tca_inds):
                    print("Wrong number of tca_indeces given, doesn't match number of body parts.")
                alt_address_list = []
                tca_inds = tca_inds[:-1]
                for i in range(len(tca_inds)):
                    if len(tca_inds[i]) == 1: # alternate
                        tca_inds[i] = int(tca_inds[i])
                        alt_address_list.append(False)
                    elif len(tca_inds[i]) > 1:
                        tca_inds[i] = int(tca_inds[i][0])
                        alt_address_list.append(True)
            elif cnt == 2:
                rate = float(line)
                print("Rate:",rate)
            elif cnt == 7:
                cal_word = line.strip()
                if cal_word == 'calibrate': # calibrate IMUs at start
                    calibrate_sensors = True
            elif cnt == 6: 
                sensor_name = line.strip()                    
            elif cnt == 3:
                cal_word = line.strip()
                if cal_word == 'parallel': # run with extra thread multiprocessing
                    parallelize = True
                    fake_real_time = False
                elif cal_word == 'online': # run offline with given file path in recordings folder
                    fake_real_time = False
                elif cal_word == 'offline':
                    fake_real_time = False
                    imu_only = True
                else:
                    fake_path = cal_word
                    fake_real_time = True
            elif cnt == 4:
                cal_word = line.strip()
                save_folder = cal_word
            elif cnt == 5:
                sim_len = float(line)
                print("Sim length:",sim_len)
    f.close()
    if calibrate_sensors:
        with open(os.path.join(diretorio_atual, 'settings.txt'), 'w') as f:
            f.writelines(old_lines[:-1])
        f.close()

    if not fake_real_time:
        from adafruit_lsm6ds import Rate, AccelRange, GyroRange
        if sensor_name == 'ISM330DHCX':
            from adafruit_lsm6ds.ism330dhcx import ISM330DHCX as Sensor
        elif sensor_name == 'LSM6DS33':
            from adafruit_lsm6ds.lsm6ds33 import LSM6DS33 as Sensor
        elif sensor_name == 'LSM6DS032':
            from adafruit_lsm6ds import LSM6DSOX as Sensor
        else:
            print("An unknown IMU has been specified, please add the text to specify the ISM330DHCX, LSM6DS33, or LSM6DS032 to the second to last line of the settings file (the line before calibrate).")
        
        import adafruit_tca9548a
        import board
        import busio
        import digitalio
        from micropython import const
        from adafruit_bus_device.i2c_device import I2CDevice
        from digitalio import DigitalInOut
        #start_vicon = digitalio.DigitalInOut(board.D5)
        #stop_vicon = digitalio.DigitalInOut(board.D6)
        #start_vicon.direction = digitalio.Direction.INPUT
        #start_vicon.pull = None  # floating (no pull-up or pull-down)
        #stop_vicon.direction = digitalio.Direction.INPUT
        #stop_vicon.pull = None  # floating (no pull-up or pull-down)

        #trigger = digitalio.DigitalInOut(board.D16) # external signal should be applied to the BCM 16 pin
        #trigger.direction = digitalio.Direction.INPUT # this signal will be checked, if 3.3V is applied, recording will be started
        #trigger.pull = digitalio.Pull.DOWN # pull this input low at all times
        #trigger_status = False # set to true if the trigger is used to start a recording
        # Initializing the different methods
        # desabilitando o trigger externo
        # button_address = const(0x6F) # I2c address for LED button
        i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
        tca = adafruit_tca9548a.TCA9548A(i2c)
        #show channels
        print("Fazendo verredura nos canais do TCA9548A ...")
        for channel in range(8):
            if tca[channel].try_lock():
                try:
                    devices = tca[channel].scan()
                    if devices:
                        print(f"Dispositivos no canal {channel}: ",
                              ", ".join(f"0x{addr:02X}" for addr in devices))
                    else:
                        print(f"Nenhum dispositivo encontrado no canal {channel}")
                finally:
                    tca[channel].unlock()

        #button = I2CDevice(tca[tca_inds[0]], button_address)
        #last_pressed = time.time() - 1.0
        pressed = False
        #button_mode(button, 0) # turn button off
        #clear_button(button)
    # define sensors
    sensor_inds = tca_inds[1:]
    #print("Sensor indices:", sensor_inds)
    alt_address_list = alt_address_list[1:]
    sensor_list = []
    sensor_ind_list = []
    sensor_number = []
    sensor_cnt = 0
    sensor_rot = []
    sensor_rot_type = [0,0,1,1,3,2,2,3,1,1,1,2,2,2] # define rotation types
    sensor_labels_full = ['pelvis_imu','torso_imu','femur_l_imu','tibia_l_imu','calcn_l_imu','femur_r_imu','tibia_r_imu','calcn_r_imu','humerus_l_imu','ulna_l_imu','hand_l_imu','humerus_r_imu','ulna_r_imu','hand_r_imu']
    sensor_label_list = []
    for i, s_ind in enumerate(sensor_inds):
        #print("Indices dos sensores que serao lidos:", sensor_inds)
        #print("nome dos sensores",sensor_labels_full)
        #quit()
        #exit()
        #print("Sensor index:", s_ind, "Alternate address:", alt_address_list[i], "Label:", sensor_labels_full[i])
        #print("numero de sensores:", len(sensor_inds))
        if s_ind != 9:
            if not fake_real_time:
                #print("--->>>alt_address_list do indice",s_ind, alt_address_list[i])
                #print("\n")
                if alt_address_list[i]: # if true use alternate address
                    try:
                        s = Sensor(tca[s_ind], address=const(0x6B))
                        print(f"Sensor inicializado no canal TCA9548A {s_ind} no endereço 0x6B")
                        sensores_status[sensor_labels_full[i]] = "OK"                        
                        time.sleep(0.1)  
                    except OSError as e:
                        print(f"[Error] Falha ao inicializar o sensor no canal TCA9548A {s_ind} no endereço 0x6B: {e}")
                        continue
                else:
                    #print("vai ajustar o I2C para 0x6A para o canal",s_ind)
                    #print("\n")
                    try:
                        s = Sensor(tca[s_ind], address=const(0x6A))
                        print(f"Sensor inicializado no canal TCA9548A {s_ind} no endereço 0x6A")  
                        sensores_status[sensor_labels_full[i]] = "OK"  
                        time.sleep(0.1)
                    except OSError as e:
                        #print("deu erro aqui",s_ind)
                        print(f"[Error] Falha ao inicializar o sensor no canal TCA9548A {s_ind} no endereço 0x6A: {e}")
                        continue

                sensor_list.append(s)
            sensor_ind_list.append(s_ind)
            len_sensor_list = len(sensor_ind_list)
            sensor_number.append(sensor_cnt)
            sensor_cnt += 1
            sensor_rot.append(sensor_rot_type[i]) # say for this number sensor how to rotate it
            sensor_label_list.append(sensor_labels_full[i])

     
    #print("Sensores lidos FULL ---->: ", sensor_labels_full)
    #print("Sensores label list",sensor_label_list)
    #print("lista de sensores", sensor_list)
    #print("Número de sensores lidos:", len(sensor_list)) 
    #print("SENSORES STATUS:", sensores_status)


    #quit()
    #exit()
    #return()

    
    # Making the text header for which body segments have IMU data
    header_text = 'time\t'
    for label in sensor_label_list:
        header_text = header_text + '\t' + label
    header_text = header_text + '\n'
    num_sensors = len(sensor_number)
    if not fake_real_time:
        for s in sensor_list: # setting all sensors to same default values
            try:
                s.accelerometer_range = AccelRange.RANGE_8G
                s.gyro_range = GyroRange.RANGE_2000_DPS
            except OSError as e:
                print(f"[Erro---] Falha ao configurar o sensor:{s} -  {e}")
                pass
            # To change the imu data sampling frequency, use the lines below. 104 Hz is default.
            #s.accelerometer_data_rate = Rate.RATE_416_HZ # Other options: 52_HZ, 26_HZ, 104_HZ, 416_HZ
            #s.gyroscope_data_rate = Rate.RATE_416_HZ

    # load fake data and figure out number of sensors
    quat_cal_offset = int(init_time*rate) # array for data for calibrating sensors
    #cwd = os.getcwd() #
    sensor_vec = np.zeros(num_sensors*signals_per_sensor)
    scaling = np.ones(num_sensors*signals_per_sensor)
    offsets = np.zeros(num_sensors*signals_per_sensor)
    imu_data = np.zeros((quat_cal_offset, num_sensors*signals_per_sensor))
    fake_data_len = 0
    if fake_real_time:
        cal_data = imu_data
        imu_data = np.load(fake_online_data + fake_path) # load fake dataset
        cal_data = imu_data[:quat_cal_offset,:]
        fake_data_len = imu_data.shape[0]
        print("Starting offline analysis for file with",fake_data_len,"samples")
    # calibrating or loading calibration data
    if not fake_real_time:
        cal_dir = home_dir+'calibration'
        gyro_file = '/gyro_offsets.npy'
        if calibrate_sensors or not os.path.exists(cal_dir): # also check if calibration folder exists
            print("Calibrating sensors!")
            try: # create calibration dir
                os.makedirs(cal_dir)
            except:
                pass
            calibrating_sensors(cal_dir, gyro_file, rate, rate, sensor_list)
            #button_mode(button, 0) # turn button off
        offsets = np.load(cal_dir+gyro_file)# loading calibration vec
    else:
        offsets = 0.0
    save_dir = save_dir_init+save_folder+'/' # append the folder name here
    file_cnt = 0
    try: # create save dir or count number of files so I don't save over some
        os.makedirs(save_dir)
    except:
        f = os.listdir(save_dir)
        for s in f:
            if nome_paciente in s:
                file_cnt += 1

    b.put([sensor_number, rate, header_text, parallelize, save_folder, file_cnt, sim_len, fake_real_time,fake_data_len,]) # ready to start running
    if fake_real_time and False: # if using fake data, calibrate with the fake data
        time.sleep(2.)
        for i in range(quat_cal_offset):# pull in real data and compute quats for init_time
            cal_data[i,:] = imu_data[0,:]
        Qi, head_err, rot_mats = h.compute_quat(cal_data, len_sensor_list, quat_cal_offset, sensor_rot, num_sensors)

        q.put([time.time(), Qi, head_err]) # sending initialized info
        time_start = time.time()
        dt = 1/rate
        madgwick = ahrs.filters.Mahony(frequency=rate)
        t = 0
        sensor_vec = np.zeros(num_sensors*signals_per_sensor)
        start = q.get() # waiting for confirmation of sim Starting
        time.sleep(0.3)
        while(t < fake_data_len): # Pull data at the desired rate
            try:
                sensor_vec = imu_data[t,:]
                for i in range(len_sensor_list):
                    s_off = i*signals_per_sensor
                    accel = np.matmul(sensor_vec[s_off:s_off+3],rot_mats[i,:,:])
                    gyro = np.matmul(sensor_vec[s_off+3:s_off+6],rot_mats[i,:,:])
                    Qi[i,:] = madgwick.updateIMU(Qi[i,:], gyro, accel)
                while(not q.empty()):
                    time.sleep(0.003)
                q.put([time.time(), Qi])
            except IndexError as e:
                print(f"Erro de índice no frame {t}: {e}")
                break
            except Exception as e:
                print(f"Erro inesperado no frame {t}: {e}")
                break
            t += 1
        b.put([True]) # end the script
    else:
        while(True): # outer loop for resetting the simulation
            #button_mode(button, 1) # make button blink
            #clear_button(button)
            pressed = False
            calibracao_iniciada = False
            while(not pressed): # wait for button press
                #pressed, last_pressed = check_button(button, last_pressed)
                # Verificar também o botão web
                if not pressed and enable_web_control:
                    pressed = check_web_button()
                    if pressed:
                        print("🌐 Gravação iniciada via controle web!")
                    if not pressed and check_web_calibrate():
                        print("\n🌐 Iniciando calibração via controle web! Por favor, aguarde...")
                        cal_dir = home_dir + 'calibration'
                        gyro_file = '/gyro_offsets.npy'
                        
                        # Chama a função de calibração (passando None para o botão físico que removemos)
                        calibrating_sensors(cal_dir, gyro_file, cal_dir, rate, sensor_list)
                        calibracao_iniciada = True
                        
                        # Atualiza os offsets locais com o novo arquivo gerado
                        offsets = np.load(cal_dir + gyro_file)
                        if calibration_q is not None:
                        #------------construcao do modelo --------------
                            if(  True):
                                for i in range(quat_cal_offset):# pull in real data and compute quats for init_time
                                    for j, s in enumerate(sensor_list):
                                        s_off = j*signals_per_sensor
                                        imu_data[i, s_off:s_off+3] = s.acceleration
                                        imu_data[i, s_off+3:s_off+6] = s.gyro + offsets[s_off+3:s_off+6] 
                                        
                                #imu_data[i,:] = imu_data[i,:] + offsets # correcting gyro bias
                                #A linha acimda deve comentada para evitar um calculo duplo do offsts, já que estou corrigindo os dados de calibração com o offset na hora de ler os sensores 
                                # e não estou salvando os dados de calibração corrigidos, então não preciso corrigir os dados de calibração novamente aqui
                                Qi, head_err, rot_mats = h.compute_quat(imu_data, len_sensor_list, quat_cal_offset, sensor_rot, num_sensors)


                                #imprime no terminal os valores do quaternion e do head_err para verificar se estão razoáveis
                            # print("Quaternions de calibração:")
                                #for i in range(len_sensor_list):
                                #   print(f"Sensor {i} ({sensor_label_list[i]}): {Qi[i,:]}")
                                #print(f"Erro da cabeça: {head_err}")

                                #exit() # para evitar que o código continue rodando depois da calibração, já que o objetivo aqui é apenas verificar se a calibração está funcionando e os valores estão razoáveis. Remova essa linha depois de verificar a calibração.

                                #---------------CALIBRACAO DO MODELO ----------------
                                if(calibracao_iniciada):
                                    calibracao_iniciada=False # resetando a variável para evitar múltiplas calibrações seguidas sem necessidade
                                    print("Calibração iniciada, enviando sinal para o modelo calibrar...")

                                    calibration_q.put([time.time(), Qi, head_err, "calibrated"])  # Envia uma mensagem para o processo principal indicando que a calibração foi concluída

                                    #
                                    # q.put([time.time(), Qi, head_err,"recalibra"]) # sending initialized info with calibrate signal
                                    # Espera um pouco para garantir que o modelo tenha tempo de processar a calibração antes de enviar os dados normais
                                    time.sleep(1.0)
                                    print("Sinal de calibração enviado, continuando com a execução normal...")


                                #---------------------------------------------------


                            #----------------------------------------------
      
            for i in range(quat_cal_offset):# pull in real data and compute quats for init_time
                for j, s in enumerate(sensor_list):
                    s_off = j*signals_per_sensor
                    imu_data[i, s_off:s_off+3] = s.acceleration
                    imu_data[i, s_off+3:s_off+6] = s.gyro + offsets[s_off+3:s_off+6] 
                    
           # imu_data[i,:] = imu_data[i,:] + offsets # correcting gyro bias
            #A linha acimda deve comentada para evitar um calculo duplo do offsts, já que estou corrigindo os dados de calibração com o offset na hora de ler os sensores 
            # e não estou salvando os dados de calibração corrigidos, então não preciso corrigir os dados de calibração novamente aqui
            Qi, head_err, rot_mats = h.compute_quat(imu_data, len_sensor_list, quat_cal_offset, sensor_rot, num_sensors)
 
            
            q.put([time.time(), Qi, head_err]) # sending initialized info
            time_start = time.time()
            dt = 1/rate
            madgwick = ahrs.filters.Mahony(frequency=rate)
            t = 0
            sensor_vec = np.zeros(num_sensors*signals_per_sensor)
            sensor_mat = np.zeros((int(sim_len*rate),num_sensors*signals_per_sensor))
            start = q.get() # waiting for confirmation of sim Starting
            time.sleep(0.3)
           
            while(True): # Pull data at the desired rate
                cur_time = time.time()
                if cur_time >= time_start + dt: # time for next reading
                    try:
                        #pressed, last_pressed = check_button(button, last_pressed)
                        # Verificar também o botão web para parar
                        pressed = False
                        if not pressed and enable_web_control:
                            pressed = check_web_button()
                            if pressed:
                                print("🌐 Gravação finalizada via controle web!")
                    except Exception as e:
                        print(f"Erro ao verificar botão: {e}")
                        pressed = False
               
                    if pressed or (not b.empty()): # send message to exit the recording
                        b.put([pressed])
                        q.put([cur_time, Qi])
                        #button_mode(button, 0) # turn button off
                        np.save(save_dir+nome_paciente+'_raw_imu_'+str(file_cnt)+'.npy', sensor_mat[:t,:]) # saving kinematics
                        file_cnt += 1
                        pressed = False
                        #stop_vicon.direction = digitalio.Direction.OUTPUT
                        #stop_vicon.value = False
                        #send_command_to_nexus(stop_xml)
                        time.sleep(1.0)
                        break
                    time_start = cur_time
                    try:
                        if recalibration is not None and not recalibration.empty():
                            recalib_signal = recalibration.get()
                            if recalib_signal == "recalibrate":
                                print("Sinal de recalibração recebido, iniciando processo de recalibração...")
                                cal_dir = home_dir + 'calibration'
                                gyro_file = '/gyro_offsets.npy'
                                
                                # Executar calibração dos sensores
                                calibrating_sensors(cal_dir, gyro_file, cal_dir, rate, sensor_list)
                                
                                # Carregar os novos offsets calibrados
                                offsets = np.load(cal_dir + gyro_file)
                                
                                # Enviar sinal de recalibração concluída para o modelo
                                if calibration_q is not None:
                                    calibration_q.put([time.time(), Qi, head_err, "recalibrated"])
                                
                                print("Recalibração concluída e sinal enviado para o modelo.")
                        for j, s in enumerate(sensor_list):
                          #  print(f"Reading sensor {j} de nome {sensor_label_list[j]} at time {cur_time:.2f}s")
                           # if(sensor_label_list[j]=='calcn_l_imu'  ):
                            #    print(f"Sensor {j} ({sensor_label_list[j]}) - Accel: {s.acceleration} - Gyro: {s.gyro}")
                            s_off = j*signals_per_sensor
                            sensor_vec[s_off:s_off+3] = s.acceleration
                            sensor_vec[s_off+3:s_off+6] = s.gyro
                        sensor_vec = sensor_vec + offsets # preping
                        sensor_mat[t,:] = sensor_vec
                        for i in range(len(sensor_list)):
                            s_off = i*signals_per_sensor
                            accel = np.matmul(sensor_vec[s_off:s_off+3],rot_mats[i,:,:])
                            gyro = np.matmul(sensor_vec[s_off+3:s_off+6],rot_mats[i,:,:])
                            Qi[i,:] = madgwick.updateIMU(Qi[i,:], gyro, accel)
                        if not imu_only:
                            q.put([cur_time, Qi])
                        t += 1
                    except OSError as e:
                        #exibe qual sensor deu erro
                        sensor_error_index = j
                        print(f"Erro de I/O ao ler sensor no frame {t}, sensor {sensor_error_index}: {e}")
                       # print(f"Erro de I/O ao ler sensor no frame {t}: {e}")
                        continue
                    except IndexError as e:
                        print(f"Erro de índice no frame {t}: {e}")
                        continue
                    except Exception as e:
                        print(f"Erro inesperado no frame {t}: {e}")
                        continue

  

def calibrating_sensors(cal_dir, gyro_file, botaoFake, rate, sensor_list, calibration_time=10.0, signals_per_sensor=6, b_brightness=0x19):
    dt = 1/rate
    calibration_time=2.0
    num_samples = int(calibration_time//dt)
    num_sensors = len(sensor_list)
    cal_data = np.zeros((num_samples, 6*num_sensors))
    time_start = time.time()
    led_range = 255
    sample_cnt = 0
    #print("Numero de samples=",num_samples)
    #print(cal_data)
    while sample_cnt < num_samples:
        cur_time = time.time()
        if cur_time >= time_start + dt: # time for next reading
            time_start = cur_time
            for j, s in enumerate(sensor_list):
                s_off = j*signals_per_sensor
                #cal_data[sample_cnt, s_off+0:s_off+3] = 1
                cal_data[sample_cnt, s_off+3:s_off+6] = s.gyro
             
            sample_cnt += 1
    gyro_offset = -1.0*np.mean(cal_data,axis=0)
    #print("Dados de calibração= ")
    #print(gyro_offset)
    #cal_data = np.zeros((num_samples, 6*num_sensors))
    #gyro_offset = -1.0*np.mean(cal_data,axis=0)
  
    np.save(cal_dir+gyro_file, gyro_offset)
