import pandas as pd
import os

import matplotlib.pyplot as plt


def substituir_virgula_por_tab(caminho_arquivo):
    """
    Lê um arquivo, substitui vírgulas por tabulação e salva com sufixo _tab
    """
    # Ler o conteúdo do arquivo
    with open(caminho_arquivo, 'r') as f:
        conteudo = f.read()
    
    # Substituir vírgulas por tabulação
    conteudo_modificado = conteudo.replace(',', '\t')
    
    # Criar o novo nome do arquivo
    diretorio = os.path.dirname(caminho_arquivo)
    nome_arquivo = os.path.basename(caminho_arquivo)
    nome_sem_extensao, extensao = os.path.splitext(nome_arquivo)
    novo_nome = f"{nome_sem_extensao}_tab{extensao}"
    novo_caminho = os.path.join(diretorio, novo_nome)
    
    # Salvar o novo arquivo
    with open(novo_caminho, 'w') as f:
        f.write(conteudo_modificado)
    
    return novo_caminho

# Ler o arquivo (ajuste o caminho e separador conforme necessário)
#linha para importar o arquivo de dados do diretorio de gravação
arquivo = os.path.join(os.getcwd(), 'recordings', 'debug', 'imu_quat_17.sto')
 
arquivo_tab = substituir_virgula_por_tab(arquivo)
df = pd.read_csv(arquivo_tab, sep='\s+', header=None, skiprows=5)  # sep='\s+' para espaços/tabs



# Renomear as três primeiras colunas
df.columns = ['tempo', 'col1', 'col2', 'col3','col4'] + [f'col{i}' for i in range(5, len(df.columns))]

# Criar o gráfico
plt.figure(figsize=(10, 6))
plt.plot(df['tempo'], df['col1'], label='col1', marker='o')
plt.plot(df['tempo'], df['col2'], label='col2', marker='s')
plt.plot(df['tempo'], df['col3'], label='col3', marker='^')
plt.plot(df['tempo'], df['col4'], label='col4', marker='d')

plt.xlabel('Tempo')
plt.ylabel('Valores')
plt.title('Gráfico de col1 e col2 vs Tempo')
plt.legend()
plt.grid(True)
plt.show()