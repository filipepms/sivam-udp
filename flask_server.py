#!/usr/bin/env python3
"""
Servidor Flask para controle do sistema RealTimeKin via web
Transforma o Raspberry Pi em ponto de acesso com interface web completa
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
import subprocess
import os
import sys
import json
import threading
import time
from datetime import datetime
import psutil
import glob

app = Flask(__name__)

# Configurações globais
home_dir = '/home/pebimu3/opensim-workspace/RealTimeKin/'
recordings_dir = os.path.join(home_dir, 'recordings')

# Estado global do sistema
system_state = {
    'recording': False,
    'button_mode': 'off',
    'last_press': None,
    'web_trigger': False,
    'system_info': {},
    'ap_status': 'unknown'
}

def get_system_info():
    """Coleta informações do sistema"""
    try:
        cpu_temp = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                cpu_temp = float(f.read()) / 1000.0
        except:
            pass
        
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        info = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'cpu_temp': cpu_temp,
            'memory_percent': memory.percent,
            'memory_used': f"{memory.used / (1024**3):.1f}",
            'memory_total': f"{memory.total / (1024**3):.1f}",
            'disk_percent': disk.percent,
            'disk_used': f"{disk.used / (1024**3):.1f}",
            'disk_total': f"{disk.total / (1024**3):.1f}",
            'uptime': time.time() - psutil.boot_time()
        }
        return info
    except Exception as e:
        print(f"Erro ao coletar info do sistema: {e}")
        return {}

def get_ap_status():
    """Verifica status do Access Point"""
    try:
        result = subprocess.run(['systemctl', 'is-active', 'hostapd'], 
                              capture_output=True, text=True, timeout=5)
        return result.stdout.strip() == 'active'
    except:
        return False

def get_connected_clients():
    """Lista clientes conectados ao AP"""
    try:
        result = subprocess.run(['iw', 'dev', 'wlan0', 'station', 'dump'],
                              capture_output=True, text=True, timeout=5)
        clients = []
        for line in result.stdout.split('\n'):
            if 'Station' in line:
                mac = line.split()[1]
                clients.append(mac)
        return clients
    except:
        return []

def get_recordings():
    """Lista gravações disponíveis"""
    try:
        recordings = []
        for folder in os.listdir(recordings_dir):
            folder_path = os.path.join(recordings_dir, folder)
            if os.path.isdir(folder_path):
                files = glob.glob(os.path.join(folder_path, '*.mot'))
                files.extend(glob.glob(os.path.join(folder_path, '*.npy')))
                if files:
                    recordings.append({
                        'name': folder,
                        'files': len(files),
                        'size': sum(os.path.getsize(f) for f in files) / (1024**2),  # MB
                        'date': datetime.fromtimestamp(os.path.getmtime(folder_path)).strftime('%Y-%m-%d %H:%M')
                    })
        return sorted(recordings, key=lambda x: x['date'], reverse=True)
    except Exception as e:
        print(f"Erro ao listar gravações: {e}")
        return []

# Rotas da API

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Retorna status completo do sistema"""
    system_state['system_info'] = get_system_info()
    system_state['ap_status'] = 'active' if get_ap_status() else 'inactive'
    system_state['connected_clients'] = len(get_connected_clients())
    return jsonify(system_state)

@app.route('/api/button/press', methods=['POST'])
def api_button_press():
    """Simula pressionamento do botão"""
    system_state['web_trigger'] = True
    system_state['last_press'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({
        'status': 'success',
        'message': 'Botão pressionado',
        'time': system_state['last_press']
    })

@app.route('/api/button/mode/<mode>', methods=['POST'])
def api_button_mode(mode):
    """Altera modo do botão LED"""
    valid_modes = ['off', 'blink', 'solid']
    if mode not in valid_modes:
        return jsonify({'status': 'error', 'message': 'Modo inválido'}), 400
    
    system_state['button_mode'] = mode
    return jsonify({
        'status': 'success',
        'mode': mode
    })

@app.route('/api/recordings')
def api_recordings():
    """Lista gravações disponíveis"""
    recordings = get_recordings()
    return jsonify({
        'recordings': recordings,
        'total': len(recordings)
    })

@app.route('/api/system/info')
def api_system_info():
    """Informações detalhadas do sistema"""
    info = get_system_info()
    info['hostname'] = subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()
    info['ip_address'] = subprocess.run(['hostname', '-I'], capture_output=True, text=True).stdout.strip()
    return jsonify(info)

@app.route('/api/ap/status')
def api_ap_status():
    """Status do Access Point"""
    try:
        hostapd_active = get_ap_status()
        dnsmasq_result = subprocess.run(['systemctl', 'is-active', 'dnsmasq'],
                                       capture_output=True, text=True, timeout=5)
        dnsmasq_active = dnsmasq_result.stdout.strip() == 'active'
        
        clients = get_connected_clients()
        
        # Tentar obter SSID
        ssid = "Unknown"
        try:
            with open('/etc/hostapd/hostapd.conf', 'r') as f:
                for line in f:
                    if line.startswith('ssid='):
                        ssid = line.split('=')[1].strip()
                        break
        except:
            pass
        
        return jsonify({
            'hostapd': 'active' if hostapd_active else 'inactive',
            'dnsmasq': 'active' if dnsmasq_active else 'inactive',
            'clients': clients,
            'client_count': len(clients),
            'ssid': ssid
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ap/setup', methods=['POST'])
def api_ap_setup():
    """Configura Access Point"""
    data = request.get_json()
    ssid = data.get('ssid', 'RealTimeKin_AP')
    password = data.get('password', 'opensim2025')
    
    if len(password) < 8:
        return jsonify({'status': 'error', 'message': 'Senha deve ter mínimo 8 caracteres'}), 400
    
    try:
        cmd = [
            'sudo', 'python3',
            os.path.join(home_dir, 'setup_access_point.py'),
            '--setup',
            '--ssid', ssid,
            '--password', password
        ]
        
        # Executar em background
        subprocess.Popen(cmd)
        
        return jsonify({
            'status': 'success',
            'message': 'Configuração iniciada. Reinicie o sistema após conclusão.',
            'ssid': ssid
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/ap/disable', methods=['POST'])
def api_ap_disable():
    """Desabilita Access Point"""
    try:
        cmd = [
            'sudo', 'python3',
            os.path.join(home_dir, 'setup_access_point.py'),
            '--disable'
        ]
        subprocess.Popen(cmd)
        
        return jsonify({
            'status': 'success',
            'message': 'Access Point desabilitado. Reinicie o sistema.'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/system/reboot', methods=['POST'])
def api_system_reboot():
    """Reinicia o sistema"""
    try:
        subprocess.Popen(['sudo', 'reboot'])
        return jsonify({
            'status': 'success',
            'message': 'Sistema reiniciando...'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/system/shutdown', methods=['POST'])
def api_system_shutdown():
    """Desliga o sistema"""
    try:
        subprocess.Popen(['sudo', 'shutdown', '-h', 'now'])
        return jsonify({
            'status': 'success',
            'message': 'Sistema desligando...'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Função para integração com workers.py
def check_web_trigger():
    """Verifica se o botão foi acionado via web"""
    global system_state
    if system_state['web_trigger']:
        system_state['web_trigger'] = False
        return True
    return False

def get_button_mode():
    """Retorna modo atual do botão"""
    mode_map = {'off': 0, 'blink': 1, 'solid': 2}
    return mode_map.get(system_state['button_mode'], 0)

def update_recording_status(recording):
    """Atualiza status de gravação"""
    system_state['recording'] = recording

def run_flask_server(host='0.0.0.0', port=5000, debug=False):
    """Inicia servidor Flask"""
    print(f"🌐 Servidor Flask iniciando em http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)

if __name__ == '__main__':
    # Criar diretório de templates se não existir
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    # Iniciar servidor
    run_flask_server(host='0.0.0.0', port=5000, debug=True)
