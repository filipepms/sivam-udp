#arquivo que vai iniciar quando o RPI for ligado, para ler o nome do paciente e criar o arquivo de log
#deve criar um servidor e ficar esperando os comandos para executar as funções de gravação e leitura do nome do paciente
from flask import Flask, request, jsonify
import os
import subprocess

#iniciar servidor Flask na porta 6000
# O Flask é um micro framework para criar aplicações web em Python. Ele é leve e fácil de usar, ideal para criar APIs simples ou servidores web.
# 
#  
app = Flask(__name__)

@app.route('/iniciar_captura', methods=['POST'])
def iniciar():
    try:
        # 1. Coloque o nome do seu ambiente Conda aqui
        nome_do_env = 'opensim-env311' 
        
        # 2. O caminho absoluto do seu script
        script_grande = '/home/pi/seu_projeto/script_grande.py'
        
        # 3. O comando final fica: conda run -n nome_do_env python script.py
        subprocess.Popen(['conda', 'run', '-n', nome_do_env, 'python', script_grande])
        
        return jsonify({"status": "sucesso", "mensagem": "Iniciado via Conda Run!"}), 200
        
    except Exception as erro:
        return jsonify({"status": "erro", "mensagem": str(erro)}), 500