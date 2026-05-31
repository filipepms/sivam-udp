#!/usr/bin/python3
# Estimates kinematics from IMU data processed into quaternions using a musculoskeletal model
from flask import jsonify
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
import workers  # define the worker functions in this .py file
import inspect
from opensim import ArrayDouble
import psutil
import queue
from opensim import Quaternion, TimeSeriesTableQuaternion
import signal
import socket
import json

host_windows = '10.4.1.94'  # IP address of the computer running the python script.
host_ik = ''

osim.Logger.setLevelString("error")


class UDPSender:
    host_windows2 = workers.ip_computador_conectado  # get the IP address of the connected computer from workers.py

    def __init__(self, host=host_windows, port=5005):
        diretorio = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(diretorio, 'endereco_ip.txt'), 'r') as f:
            host_windows = f.read().strip()
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
                labels = [
                    "pelvis_imu", "femur_l_imu", "tibia_l_imu", "calcn_l_imu",
                    "femur_r_imu", "tibia_r_imu", "calcn_r_imu"
                ]

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
real_time = True  # set to True for using the kinematics in the python script for real-time applications

# Parameters for IK solver
fake_real_time = False  # True to run offline, False to record data and run online
log_temp = False  # True to log CPU temperature data
log_data = True  # if true save all IK outputs, else only use those in reporter_list for easier custom coding
home_dir = '/home/pebimu3/sivam/'
uncal_model = 'Rajagopal_2015.osim'
uncal_model_filename = home_dir + uncal_model
model_filename = home_dir + 'calibrated_' + uncal_model
fake_online_data = home_dir + 'recordings/'
sto_filename = home_dir + 'tiny_file.sto'
error_log_file = home_dir + 'error_log.txt'
visualize = False
rate = 20.0  # samples hz of IMUs
accuracy = 0.001
constraint_var = 10.0
init_time = 4.0

# Initialize the quaternions
signals_per_sensor = 6
file_cnt = 0
save_dir_init = home_dir + 'recordings/'
save_file = '/recording_'
ts_file = '/timestamp_'
script_live = True

q = Queue()  # queue for IMU messages
b = Queue()  # queue for button messages
calibration_q = Queue()  # queue for calibration messages

primeira_vez = True


def handle_sigint(sig, frame):
    print("\n🛑 Encerrando com segurança...")
    if imuProc.is_alive():
        print("Finalizando processo IMU...")
        imuProc.terminate()
        imuProc.join()
    sys.exit(0)


signal.signal(signal.SIGINT, handle_sigint)

imuProc = Process(target=workers.readIMU, args=(q, b, fake_online_data, init_time, signals_per_sensor, save_dir_init, home_dir, calibration_q))
imuProc.start()

sensor_ind_list, rate, header_text, save_folder, save_folder, file_cnt, sim_len, fake_real_time, fake_data_len = b.get()
save_dir = save_dir_init + save_folder + '/'
kin_store_size = sim_len + 10.0
sim_steps = int(sim_len * rate)
dt = 1 / rate

last_time_ms = 0

print("start IMU")
if log_temp and not fake_real_time:
    from gpiozero import CPUTemperature
    cpu = CPUTemperature()

import threading

while(script_live):
    while(not q.empty()):
        q.get()
    while(not b.empty()):
        b.get()
    while(not calibration_q.empty()):
        calibration_q.get()

    print("Pronto para iniciar, aguardando comando...")

    if(primeira_vez):
        primeira_vez = False
        print("Aguardando mensagem para iniciar calibração...")
        mensagem_teste = calibration_q.get()

        init_time, Qi, head_err = mensagem_teste[0], mensagem_teste[1], mensagem_teste[2]

        diretorio = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(diretorio, 'nomes.txt'), 'r') as f:
            nome_paciente = f.read()
            print("Nome do paciente lido:", nome_paciente)

        nome_arquivo_calibrado = 'modelo_calibrado_mesmo' + nome_paciente + '.osim'
        sto_filename = home_dir + nome_paciente + 'tiny_file.sto'

        quat2sto_single(Qi, header_text, sto_filename, 0., rate, sensor_ind_list)

        visualize_init = False
        sensor_to_opensim_rotations = Vec3(-np.pi/2, head_err, 0)
        imuPlacer = osim.IMUPlacer()
        imuPlacer.set_model_file(uncal_model_filename)
        imuPlacer.set_orientation_file_for_calibration(sto_filename)
        imuPlacer.set_sensor_to_opensim_rotations(sensor_to_opensim_rotations)
        imuPlacer.run(visualize_init)

        model = imuPlacer.getCalibratedModel()
        model.printToXML(nome_arquivo_calibrado)
        print("Modelo calibrado salvo como:", nome_arquivo_calibrado)

        def enviar_arquivo_calibrado_para_IP():
            with open(sto_filename, 'r') as f:
                model_data = f.read()
                diretorio = os.path.dirname(os.path.abspath(__file__))
                with open(os.path.join(diretorio, 'endereco_ip.txt'), 'r') as f:
                    host_conectado = f.read().strip()

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host_conectado, 5006))
                sock.sendall(model_data.encode('utf-8'))
                sock.close()
                print(f"Arquivo {nome_arquivo_calibrado} enviado para {host_conectado}")
            except Exception as e:
                print(f"Erro ao enviar arquivo: {e}")

        print("Modelo calibrado enviado para o IP conectado. Iniciando a simulação...")
        print("Iniciando a simulação...")

    if(not primeira_vez):
        init_time, Qi, head_err = q.get()

        diretorio = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(diretorio, 'nomes.txt'), 'r') as f:
            nome_paciente = f.read()
            print("Nome do paciente lido:", nome_paciente)

        nome_arquivo_calibrado = 'modelo_calibrado' + nome_paciente + '.osim'
        sto_filename = home_dir + nome_paciente + 'tiny_file.sto'

        quat2sto_single(Qi, header_text, sto_filename, 0., rate, sensor_ind_list)

        visualize_init = False
        sensor_to_opensim_rotations = Vec3(-np.pi/2, head_err, 0)
        imuPlacer = osim.IMUPlacer()
        imuPlacer.set_model_file(uncal_model_filename)
        imuPlacer.set_orientation_file_for_calibration(sto_filename)
        imuPlacer.set_sensor_to_opensim_rotations(sensor_to_opensim_rotations)
        imuPlacer.run(visualize_init)

        model = imuPlacer.getCalibratedModel()
        model.printToXML(nome_arquivo_calibrado)
        print("Modelo calibrado salvo como:", nome_arquivo_calibrado)
        print("Iniciando a simulação...")

    rt_samples = int(kin_store_size * rate)
    time_vec = np.zeros((rt_samples, 2))
    coordinates = model.getCoordinateSet()
    ikReporter = osim.TableReporter()
    ikReporter.setName('ik_reporter')
    for coord in coordinates:
        if log_data:
            ikReporter.addToReport(coord.getOutput('value'), coord.getName())
    model.addComponent(ikReporter)
    model.finalizeConnections()  # FIX

    labels = ["pelvis_imu", "femur_l_imu", "tibia_l_imu", "calcn_l_imu", "femur_r_imu", "tibia_r_imu", "calcn_r_imu"]
    row_vector = osim.RowVectorQuaternion()
    quatRecord = osim.TimeSeriesTableQuaternion()
    set_column_labels(quatRecord, labels)

    quatTable = osim.TimeSeriesTableQuaternion(sto_filename)
    orientationsData = osim.OpenSenseUtilities.convertQuaternionsToRotations(quatTable)
    oRefs = osim.OrientationsReference(orientationsData)

    init_state = model.initSystem()
    mRefs = osim.MarkersReference()
    coordinateReferences = osim.SimTKArrayCoordinateReference()
    if visualize:
        model.setUseVisualizer(True)

    s0 = init_state
    ikSolver = osim.InverseKinematicsSolver(model, mRefs, oRefs, coordinateReferences, constraint_var)
    print("IK solver initialized.")
    print("Assembling IK solver...")
    ikSolver.setAccuracy(accuracy)  # FIX
    s0.setTime(0.)
    ikSolver.assemble(s0)

    if visualize:
        model.getVisualizer().show(s0)
        model.getVisualizer().getSimbodyVisualizer().setShowSimTime(True)

    udp_sender = UDPSender(host_windows, 5005)

    t = 0
    st = 0.
    temp_data = []
    add_time = 0.
    running = True
    start_sim_time = time.time()
    q.put(['received'])
    print("Iniciando a gravação dos dados...")

    while(running):
        if (not b.empty()) or (t == sim_steps):
            print("Starting while...")
            if t == sim_steps:
                b.put(["done"])

            if log_data:
                diretorio = os.path.dirname(os.path.abspath(__file__))

                with open(os.path.join(diretorio, 'nomes.txt'), 'r') as f:
                    nome_paciente = f.read()
                    print("Nome do paciente lido:", nome_paciente)

                with open(os.path.join(diretorio, 'arquivo.txt'), 'w') as f:
                    f.write('')

                print("Starting log_data...")
                ik_results = ikReporter.getTable()
                osim.STOFileAdapter.write(ik_results, save_dir + save_file + str(file_cnt) + '.mot')
                osim.STOFileAdapterQuaternion.write(quatRecord, save_dir + nome_paciente + 'imu_quat_' + str(file_cnt) + '.sto')
                np.save(save_dir + ts_file + str(file_cnt) + '.npy', time_vec[:t, :])

                if log_temp and not fake_real_time:
                    np.save(save_dir + '/tempdata_' + str(file_cnt) + '.npy', temp_data)

                file_cnt += 1

            print("Time used in IK:", st, "Total time:", time.time() - start_sim_time)
            time.sleep(0.5)
            if fake_real_time:
                print("Saved the offline files...")
                exit()
            else:
                break

        time_stamp, Qi = q.get()
        add_time = time.time()
        time_s = t * dt

        quat2sto_single(Qi, header_text, sto_filename, time_s, rate, sensor_ind_list)
        append_quat_row(quatRecord, time_s, Qi)

        current_time_ms = time.perf_counter_ns() // 1000000
        if(current_time_ms - last_time_ms > 200.):
            udp_sender.send(time_stamp, Qi)
            last_time_ms = current_time_ms

        # IK
        quatTable = osim.TimeSeriesTableQuaternion(sto_filename)
        orientationsData = osim.OpenSenseUtilities.convertQuaternionsToRotations(quatTable)

        oRefs = osim.OrientationsReference(orientationsData)
        ikSolver = osim.InverseKinematicsSolver(model, mRefs, oRefs, coordinateReferences, constraint_var)
        ikSolver.setAccuracy(accuracy)

        s0.setTime(time_s)
        ikSolver.assemble(s0)
        ikSolver.track(s0)

        if visualize:
            model.getVisualizer().show(s0)
        model.realizeReport(s0)

        if real_time:
            rowind = ikReporter.getTable().getRowIndexBeforeTime((t + 1) * dt)
            kin_step = ikReporter.getTable().getRowAtIndex(rowind).to_numpy()
            # ADD CUSTOM CODE HERE FOR REAL-TIME APPLICATIONS

        st += time.time() - add_time
        time_vec[t, 0] = time_stamp
        time_vec[t, 1] = time.time() - time_stamp

        if (t % int(rate) == 0):
            if fake_real_time:
                print(np.round(t * 100.0 / fake_data_len, 1), '%')
            elif log_temp:
                temp_data.append(cpu.temperature)

        t += 1
        print(".", end='', flush=True)

    print("\n fim da gravacao.")