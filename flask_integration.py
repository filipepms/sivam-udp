#!/usr/bin/env python3
"""
Integração do servidor Flask com o sistema workers.py
Permite controle web do RealTimeKin via Flask
"""

import sys
import os
from threading import Thread
import time

# Adicionar diretório ao path
sys.path.insert(0, '/home/pebimu3/opensim-workspace/RealTimeKin')

# Importar servidor Flask
from flask_server import app, system_state, run_flask_server

# Funções de integração com workers.py

def check_web_button_trigger():
    """
    Verifica se o botão foi acionado via web
    Use esta função no workers.py no lugar de check_web_button()
    """
    global system_state
    if system_state.get('web_trigger', False):
        system_state['web_trigger'] = False
        return True
    return False

def get_web_button_mode():
    """
    Retorna modo do botão configurado via web
    Retorna: 0 (off), 1 (blink), 2 (solid) ou None
    """
    mode_map = {'off': 0, 'blink': 1, 'solid': 2}
    mode = system_state.get('button_mode', 'off')
    return mode_map.get(mode, None)

def update_recording_state(recording=True):
    """
    Atualiza estado de gravação no sistema
    Call esta função do workers.py quando iniciar/parar gravação
    """
    system_state['recording'] = recording

def start_flask_background(host='0.0.0.0', port=5000):
    """
    Inicia servidor Flask em thread separada
    Use esta função ao invés de start_web_server() no workers.py
    """
    flask_thread = Thread(target=run_flask_server, args=(host, port, False), daemon=True)
    flask_thread.start()
    print(f"🌐 Servidor Flask iniciado em http://{host}:{port}")
    return flask_thread

# Exemplo de uso no workers.py:
"""
# No início do arquivo workers.py, adicione:
from flask_integration import start_flask_background, check_web_button_trigger, update_recording_state

# Na função readIMU, após inicializar variáveis:
if not fake_real_time:
    start_flask_background(host='0.0.0.0', port=5000)

# Nos loops onde verifica botão:
if check_web_button_trigger():
    pressed = True

# Quando iniciar gravação:
update_recording_state(True)

# Quando parar gravação:
update_recording_state(False)
"""

if __name__ == "__main__":
    print("Iniciando servidor Flask integrado...")
    start_flask_background()
    
    # Manter o programa rodando
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
