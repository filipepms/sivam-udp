#!/usr/bin/python3
# Estimates kinematics from IMU data processed into quaternions using a musculoskeletal model
from flask import   jsonify

from flask import app

import opensim as osim
from opensim import Vec3
import numpy as np
from helper import quat2sto_single, sto2quat
import helper as h
import time
import os
import sys
from multiprocessing import Process, Queue
import workers # define the worker functions in this .py file
import inspect
from opensim import ArrayDouble
import psutil
import queue
from opensim import Quaternion, TimeSeriesTableQuaternion
import signal
import socket
import json


host_windows='10.4.1.94'#IP address of the computer running the python script, which should be the same as the one in workers.py. This is where the UDP packets will be sent to.

host_ik=''

class UDPSender:
    host_windows2 = workers.ip_computador_conectado # get the IP address of the connected computer from the workers module


        
    def __init__(self, host=host_windows, port=5005):
        
        diretorio=os.path.dirname(os.path.abspath(__file__)) 
            #ler o IP do arquivo de texto e usar esse IP para enviar os dados via UDP
        with open(os.path.join(diretorio,'endereco_ip.txt'), 'r') as f:
            host_windows = f.read().strip()  # read the IP address from the file and remove any whitespace
        global host_ik
        self.host = host_windows if host_windows else host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print('-- UDP Sender initialized --')
        print("UDP sender initialized with host:", self.host, "and port:", self.port)
        print("Old ip from workers:", workers.ip_computador_conectado)
        print("NOVO IP:", host_windows)

    def send(self, timestamp, quats_array, labels=None):
        try:
            if labels is None:
                labels = ["pelvis_imu", "femur_l_imu", "tibia_l_imu", "calcn_l_imu", 
                          "femur_r_imu", "tibia_r_imu", "calcn_r_imu"]
            
            quats_dict = {}
            for i, label in enumerate(labels):
                w, x, y, z = quats_array[i]
                quats_dict[label] = [float(w), float(x), float(y), float(z)]
            
            packet = {
                "time": float(timestamp),
                "quats": quats_dict
            }
            
            msg = json.dumps(packet, separators=(',', ':')).encode("utf-8")
           
            self.socket.sendto(msg, (self.host, self.port))
            
        except Exception as e:
            print("UDP send error:", e)

    def close(self):
        self.socket.close()


def clear(q):
    try:
        while True:
            q.get_nowait()
    except:
        pass

def append_quat_row(table, timestamp, quat_data):
    num_sensors = len(quat_data)
    row = osim.RowVectorQuaternion(num_sensors)
    for i in range(num_sensors):
        w, x, y, z = quat_data[i]
        quat = osim.Quaternion(w, x, y, z)
        vec4 = row.updElt(0, i)
        vec4.set(0, w)  # w
        vec4.set(1, x)  # x
        vec4.set(2, y)  # y
        vec4.set(3, z)  # z
    table.appendRow(timestamp, row)

def set_column_labels(table, labels):
    labels_vec = osim.StdVectorString()
    for label in labels:
        labels_vec.push_back(label)
    table.setColumnLabels(labels_vec)

# Customize real-time kinematics for use by setting flag and looking at corresponding code below.
real_time = True # set to True for using the kinematics in the python script for real-time applications

# Parameters for IK solver
fake_real_time = False # True to run offline, False to record data and run online
log_temp = False # True to log CPU temperature data
log_data = True # if true save all IK outputs, else only use those in reporter_list for easier custom coding
home_dir = '/home/pebimu3/sivam/' # ARQUIVO LOCAL PARA TESTES, MUDAR PARA O DIRETÓRIO DESEJADO PARA SALVAR OS ARQUIVOS DE CALIBRAÇÃO E GRAVAÇÃO DOS DADOS
uncal_model = 'Rajagopal_2015.osim'
uncal_model_filename = home_dir + uncal_model
model_filename = home_dir+'calibrated_' + uncal_model
fake_online_data = home_dir+'recordings/'#test_data.npy'#'test_IMU_data.npy'#'MT_012005D6_009-001_orientations.sto'
sto_filename = home_dir+'tiny_file.sto'
error_log_file = home_dir+'error_log.txt'
visualize = False
rate = 20.0 # samples hz of IMUs
accuracy = 0.001 # value tuned for accurate and fast IK solver
constraint_var = 10.0 # value tuned for accurate and fast IK solver
init_time = 4.0 # seconds of data to initialize from

# Initialize the quaternions
signals_per_sensor = 6
file_cnt = 0
save_dir_init = home_dir+ 'recordings/' # appending folder name here
save_file = '/recording_'
ts_file = '/timestamp_'
script_live = True

q = Queue() # queue for IMU messages
b = Queue() # queue for button messages
calibration_q = Queue() # queue for calibration messages

primeira_vez = True
#
def handle_sigint(sig, frame):
    print("\n🛑 Encerrando com segurança...")
    if imuProc.is_alive():
        print("Finalizando processo IMU...")
        imuProc.terminate()
        imuProc.join()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)
#
imuProc = Process(target=workers.readIMU, args=(q, b, fake_online_data, init_time, signals_per_sensor, save_dir_init, home_dir, calibration_q))
imuProc.start() # spawning IMU process
sensor_ind_list, rate, header_text, save_folder, save_folder, file_cnt, sim_len, fake_real_time, fake_data_len = b.get()
save_dir = save_dir_init+save_folder+'/' # append the folder name here
kin_store_size = sim_len + 10.0
sim_steps = int(sim_len*rate)
dt = 1/rate

last_time_ms=0

print("start IMU")
if log_temp and not fake_real_time:
    from gpiozero import CPUTemperature
    
    cpu = CPUTemperature()
import socket
import threading

while(script_live):
    while(not q.empty()): # clearing the queues that may have old messages
        q.get()         
    while(not b.empty()):
        b.get()
    while(not calibration_q.empty()):
        calibration_q.get()
        
    print("Pronto para iniciar, aguardando comando...")
    
    


    #mensagem_2=q.get() # wait for message from IMU process with the initial quaternions and head error for calibration
    if( primeira_vez   ):

        primeira_vez=False # resetando a variável para evitar múltiplas calibrações seguidas sem necessidade
        print("Aguardando mensagem para iniciar calibração...")
        mensagem_teste=calibration_q.get() # wait for message from button process to start calibration
       

       # print("Mensagem recebida do processo IMU para iniciar calibração:", mensagem_teste[0], mensagem_teste[1], mensagem_teste[2], mensagem_teste[3])
            
         
        #exit() # apenas para teste, depois removo essa linha para rodar o código completo
        #init_time, Qi, head_err = q.get()

        init_time, Qi, head_err = mensagem_teste[0], mensagem_teste[1], mensagem_teste[2]
        #print("mensagem recebida pelo q.get() para iniciar calibração. Tempo de inicialização:", init_time, "Erro de cabeça:", head_err)

        #ler o nome do paciente do arquivo de texto e usar esse nome para salvar o arquivo de calibração com o nome do paciente, por exemplo, "calibracao_nome_paciente.osim"
        
        diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta

        with open(os.path.join(diretorio, 'nomes.txt'), 'r') as f:
            nome_paciente = f.read()  # lê tudo de uma vez 
            print("Nome do paciente lido:", nome_paciente)
        nome_arquivo_calibrado = 'modelo_calibrado_mesmo' + nome_paciente + '.osim'
        sto_filename=''
        sto_filename=home_dir+nome_paciente+'tiny_file.sto'
        
        # calibrate model and save
        quat2sto_single(Qi, header_text, sto_filename, 0., rate, sensor_ind_list)
    
        visualize_init = False
        sensor_to_opensim_rotations = Vec3(-np.pi/2,head_err,0)
        imuPlacer = osim.IMUPlacer();
        imuPlacer.set_model_file(uncal_model_filename);
        imuPlacer.set_orientation_file_for_calibration(sto_filename);
        imuPlacer.set_sensor_to_opensim_rotations(sensor_to_opensim_rotations);
        imuPlacer.run(visualize_init);
    

        model = imuPlacer.getCalibratedModel();
        model.printToXML(nome_arquivo_calibrado)
        print("Modelo calibrado salvo como:", nome_arquivo_calibrado)

        def enviar_arquivo_calibrado_para_IP():
            with open(sto_filename, 'r') as f:
                model_data = f.read()
                diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta
                with open(os.path.join(diretorio,'endereco_ip.txt'), 'r') as f:
                    host_conectado = f.read().strip()  # read the IP address from the file and remove any whitespace

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host_conectado, 5006))  # porta diferente do UDP
                sock.sendall(model_data.encode('utf-8'))
                sock.close()
                print(f"Arquivo {nome_arquivo_calibrado} enviado para {host_conectado}")
            except Exception as e:
                print(f"Erro ao enviar arquivo: {e}")    
        #enviar_arquivo_calibrado_para_IP()
        #ARQUIVO NAO ESTA SENDO ENVIADO VIA UDP - estou fazendo uma solicitacao via POST/GET

        print("Modelo calibrado enviado para o IP conectado. Iniciando a simulação...")
        print("Iniciando a simulação...")
    
    if(not primeira_vez) :

         
        init_time, Qi, head_err = q.get()

       #init_time, Qi, head_err = mensagem_teste[0], mensagem_teste[1], mensagem_teste[2]
        #print("mensagem recebida pelo q.get() para iniciar calibração. Tempo de inicialização:", init_time, "Erro de cabeça:", head_err)

        #ler o nome do paciente do arquivo de texto e usar esse nome para salvar o arquivo de calibração com o nome do paciente, por exemplo, "calibracao_nome_paciente.osim"
        diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta

        with open(os.path.join(diretorio, 'nomes.txt'), 'r') as f:
            nome_paciente = f.read()  # lê tudo de uma vez 
            print("Nome do paciente lido:", nome_paciente)
        nome_arquivo_calibrado = 'modelo_calibrado' + nome_paciente + '.osim'
        sto_filename=''
        sto_filename=home_dir+nome_paciente+'tiny_file.sto'
        
        # calibrate model and save
        quat2sto_single(Qi, header_text, sto_filename, 0., rate, sensor_ind_list)
    
        visualize_init = False
        sensor_to_opensim_rotations = Vec3(-np.pi/2,head_err,0)
        imuPlacer = osim.IMUPlacer();
        imuPlacer.set_model_file(uncal_model_filename);
        imuPlacer.set_orientation_file_for_calibration(sto_filename);
        imuPlacer.set_sensor_to_opensim_rotations(sensor_to_opensim_rotations);
        imuPlacer.run(visualize_init);
    

        model = imuPlacer.getCalibratedModel();
        model.printToXML(nome_arquivo_calibrado)
        print("Modelo calibrado salvo como:", nome_arquivo_calibrado)

 
        print("Iniciando a simulação...")
        
    
    #init_time, Qi, head_err = q.get()

    # Initialize model
    rt_samples = int(kin_store_size*rate)
    #kin_mat = np.zeros((rt_samples, 39)) # 39 is the number of joints stored in the .sto files accessible at each time step
    time_vec = np.zeros((rt_samples,2))
    coordinates = model.getCoordinateSet()
    ikReporter = osim.TableReporter()
    ikReporter.setName('ik_reporter')
    for coord in coordinates:
        if log_data:
            ikReporter.addToReport(coord.getOutput('value'),coord.getName())
    model.addComponent(ikReporter)
    model.finalizeConnections

    # Initialize simulation
    labels = ["pelvis_imu", "femur_l_imu", "tibia_l_imu", "calcn_l_imu", "femur_r_imu", "tibia_r_imu", "calcn_r_imu"]
    row_vector = osim.RowVectorQuaternion()
    quatRecord = osim.TimeSeriesTableQuaternion()
    set_column_labels(quatRecord, labels)
    #
    quatTable = osim.TimeSeriesTableQuaternion(sto_filename)
    orientationsData = osim.OpenSenseUtilities.convertQuaternionsToRotations(quatTable)
    oRefs = osim.OrientationsReference(orientationsData)
    init_state = model.initSystem()
    mRefs = osim.MarkersReference()
    coordinateReferences = osim.SimTKArrayCoordinateReference()
    if visualize:
        model.setUseVisualizer(True)
    model.initSystem()
    s0 = init_state
    ikSolver = osim.InverseKinematicsSolver(model, mRefs, oRefs, coordinateReferences, constraint_var)
    print("IK solver initialized.")
    print("Assembling IK solver...")
    ikSolver.setAccuracy = accuracy
    s0.setTime(0.)
    ikSolver.assemble(s0)
    if visualize: # initialize visualization
        model.getVisualizer().show(s0)
        model.getVisualizer().getSimbodyVisualizer().setShowSimTime(True)
   
    #initialize UDP
    udp_sender = UDPSender(host_windows, 5005)
    # IK solver loop
    t = 0 # number of steps
    st = 0. # timing simulation
    temp_data = []
    add_time = 0.
    running = True
    start_sim_time = time.time()
    q.put(['received']) # tell IMUs to start passing real-time data
    print("Iniciando a gravação dos dados...")
    #o bloco abaixo faz a gravação dos dados
    
    while(running):
        if (not b.empty()) or (t == sim_steps): # new button press so we should save the data and restart the sim
            print("Starting while...")
            if t == sim_steps: # tell IMUs to reset too
                b.put(["done"])
            if log_data:
                diretorio=os.path.dirname(os.path.abspath(__file__)) #pega o diretório atual do arquivo workers.py para acessar o arquivo de calibração que está na mesma pasta
  
                with open(os.path.join(diretorio,'nomes.txt'), 'r') as f:
                    nome_paciente = f.read()  # lê tudo de uma vez 
                    print("Nome do paciente lido:", nome_paciente) 
                with open(os.path.join(diretorio,'arquivo.txt'), 'w') as f:
                    f.write('')              
                print("Starting log_data...")
                ik_results = ikReporter.getTable()
                osim.STOFileAdapter.write(ik_results, save_dir+save_file+str(file_cnt)+'.mot')
                osim.STOFileAdapterQuaternion.write(quatRecord,  save_dir+nome_paciente+'imu_quat_'+str(file_cnt)+'.sto')
                np.save(save_dir+ts_file+str(file_cnt)+'.npy', time_vec[:t,:])
                if log_temp and not fake_real_time:
                    np.save(save_dir+'/tempdata_'+str(file_cnt)+'.npy', temp_data)
                file_cnt += 1
            print("Time used in IK:",st,"Total time:",time.time()-start_sim_time)
            time.sleep(0.5)
            if fake_real_time:
                print("Saved the offline files...")
                exit()
            else:
                break # exit loop and wait until button pressed for reset
        time_stamp, Qi = q.get()
        #print(f"Time {time_stamp:.4f} | {Qi}") 
        add_time = time.time()
        time_s = t*dt
        quat2sto_single(Qi, header_text, sto_filename, time_s, rate, sensor_ind_list) # store next line of fake online data to one-line STO
        append_quat_row(quatRecord, time_s, Qi) #save quaternions
        
        # send quaternion via UDP

        
        current_time_ms=time.perf_counter_ns()//1000000
        if(current_time_ms-last_time_ms>200.):
            udp_sender.send(time_stamp, Qi)
            last_time_ms=current_time_ms
            print(current_time_ms)
        
        # IK
        quatTable = osim.TimeSeriesTableQuaternion(sto_filename)
        orientationsData = osim.OpenSenseUtilities.convertQuaternionsToRotations(quatTable)
        rowVecView = orientationsData.getNearestRow(time_s)
        rowVec = osim.RowVectorRotation(rowVecView)
        #ikSolver.addOrientationValuesToTrack(time_s+dt, rowVec)
        s0.setTime(time_s+dt)
        #ikSolver.track(s0)
        if visualize:
            model.getVisualizer().show(s0)
        model.realizeReport(s0)
        if real_time: # The previous kinematics are pulled here and can be used to implement any custom real-time applications
            rowind = ikReporter.getTable().getRowIndexBeforeTime((t+1)*dt) # most recent index in kinematics table
            kin_step = ikReporter.getTable().getRowAtIndex(rowind).to_numpy() # joint angles for current time step as numpy array
            # see the header of the saved .sto files for the names of the corresponding joints.
            ### ADD CUSTOM CODE HERE FOR REAL-TIME APPLICATIONS ###

        st += time.time() - add_time
        time_vec[t,0] = time_stamp
        time_vec[t,1] = time.time()-time_stamp # delay
        if (t%int(rate)==0):
            if fake_real_time: # log temp data
                print(np.round(t*100.0/fake_data_len,1),'%')
            elif log_temp:
                temp_data.append(cpu.temperature)
                #temp_data.append(psutil.sensors_temperatures()['cpu_thermal'][0].current)
            #print("Delay (ms):", 1000.*np.mean(time_vec[t-int(rate):t,1],axis=0))
        t += 1
        #print("tempo", t)
        print(".", end='', flush=True)     # indicate running status
    print("\n fim da gravacao.")
