import os

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'

@app.route('/api/hello/<name>')
def hello_name(name):
    return f'Hello, {name}!'

@app.route('/calibrar', methods=['POST'])
def iniciar_calibracao():
    if request.method == 'POST':
        # Lógica para iniciar a calibração
        print(request.json)  # Exemplo de como acessar os dados enviados no corpo da requisição
        pass
    return 'Calibração iniciada!'
@app.route('/listararquivos')
def listar_arquivos():
    # Lógica para listar arquivos
    arquivos=[f for f in os.listdir('.') if os.path.isfile(f)]

    return jsonify({"arquivos": arquivos})
    print("arquivos listado")

@app.route('/sto_calibracao', methods=['GET'])
def sto_calibracao():
    return send_file('teste1.sto', 
                     mimetype='application/octet-stream', 
                     as_attachment=True, 
                     download_name='sto_calibracao.sto')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)