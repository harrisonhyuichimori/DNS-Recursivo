# Em desenvolvimento por Harrison Mori, programa para automação de bloqueio de DNS via DNS Recursivo Unbound

import sqlite3
from netmiko import ConnectHandler
from netmiko import file_transfer

# Função para criar ou recriar o banco de dados e a tabela


def criar_banco():
    conn = sqlite3.connect("clientes.db")
    cursor = conn.cursor()

    # Verifica se a tabela 'clientes' já existe
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='clientes'")
    tabela_existe = cursor.fetchone()

    if not tabela_existe:  # Se a tabela não existir, cria diretamente
        cursor.execute("""
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL,
            host TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            port INTEGER NOT NULL,
            senha_root TEXT NOT NULL
        )
        """)
        print("Tabela 'clientes' criada com sucesso!")
    else:
        # Verifica se a tabela precisa ser atualizada para incluir o campo 'senha_root'
        cursor.execute("PRAGMA table_info(clientes)")
        colunas = cursor.fetchall()
        if len(colunas) < 7:  # Se o campo 'senha_root' não existir, recria a tabela
            cursor.execute("ALTER TABLE clientes RENAME TO clientes_backup")

            # Cria a nova tabela com o campo 'senha_root'
            cursor.execute("""
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                host TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                port INTEGER NOT NULL,
                senha_root TEXT NOT NULL
            )
            """)

            # Copia os dados da tabela antiga para a nova (adicionando senha_root padrão)
            cursor.execute("""
            INSERT INTO clientes (id, cliente, host, username, password, port, senha_root)
            SELECT id, cliente, host, username, password, port, '' AS senha_root FROM clientes_backup
            """)

            # Remove a tabela antiga
            cursor.execute("DROP TABLE clientes_backup")
            print("Tabela 'clientes' atualizada com sucesso!")

    conn.commit()
    conn.close()

# Função para consultar os dados do banco de dados


def consultar_dados():
    conn = sqlite3.connect("clientes.db")
    cursor = conn.cursor()

    # Consulta todos os registros da tabela 'clientes'
    cursor.execute("SELECT * FROM clientes")
    resultados = cursor.fetchall()

    conn.close()

    # Exibe os resultados
    if resultados:
        print("ID | Cliente            | Host           | Username | Password   | Porta | Senha Root")
        print("-" * 90)
        for row in resultados:
            print(
                f"{row[0]:<3} | {row[1]:<13} | {row[2]:<15} | {row[3]:<8} | {row[4]:<10} | {row[5]:<5} | {row[6]}")
    else:
        print("Nenhum dado encontrado no banco de dados.")

# Função para inserir um novo cliente no banco de dados


def inserir_dados_cliente():
    conn = sqlite3.connect("clientes.db")
    cursor = conn.cursor()

    # Solicita os dados do cliente
    cliente = input("Digite o nome do cliente: ").strip()
    host = input("Digite o endereço IP do cliente: ").strip()
    username = input("Digite o nome de usuário do cliente: ").strip()
    password = input("Digite a senha do cliente: ").strip()
    port = int(input("Digite a porta SSH do cliente (ex: 22): ").strip())
    senha_root = input("Digite a senha do root: ").strip()

    # Insere os dados no banco de dados
    cursor.execute("""
    INSERT INTO clientes (cliente, host, username, password, port, senha_root)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (cliente, host, username, password, port, senha_root))

    conn.commit()
    conn.close()
    print("Dados do cliente inseridos com sucesso!")

# Função para apagar um cliente do banco de dados


def apagar_cliente():
    conn = sqlite3.connect("clientes.db")
    cursor = conn.cursor()

    # Solicita o ID do cliente a ser apagado
    client_id = int(
        input("Digite o ID do cliente que deseja apagar: ").strip())

    # Apaga o cliente pelo ID
    cursor.execute("DELETE FROM clientes WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()

    print(f"Cliente com ID {client_id} apagado com sucesso!")

# Função para buscar os dados do cliente no banco de dados


def get_client_data(client_id):
    conn = sqlite3.connect("clientes.db")
    cursor = conn.cursor()

    # Busca os dados do cliente pelo ID
    cursor.execute(
        "SELECT host, username, password, port, senha_root FROM clientes WHERE id = ?", (client_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            "device_type": "linux",
            "host": result[0],
            "username": result[1],
            "password": result[2],
            "port": result[3],
            "senha_root": result[4],
            "global_delay_factor": 3
        }
    else:
        raise ValueError("Cliente não encontrado no banco de dados.")


def adicionar_sites_bloqueados(local_file):
    import os

    # Caminhos dos arquivos
    lista_txt = "lista.txt"
    sitesblock_conf = local_file

    # Verifica se o arquivo sitesblock.conf existe, se não, cria
    os.makedirs(os.path.dirname(sitesblock_conf), exist_ok=True)
    if not os.path.exists(sitesblock_conf):
        with open(sitesblock_conf, "w") as f:
            pass

    print("\n=== Adicionar Sites aos arquivos de bloqueio do Cliente ===")
    print("1. Digitar sites manualmente")
    print("2. Escolher sites do arquivo lista.txt")
    opcao = input("Escolha uma opção: ").strip()

    # Carrega os sites existentes no arquivo para evitar duplicatas
    if os.path.exists(sitesblock_conf):
        with open(sitesblock_conf, "r") as f:
            sites_existentes = set(f.readlines())
    else:
        sites_existentes = set()

    novos_sites = []

    if opcao == "1":
        # Adicionar sites manualmente
        while True:
            site = input(
                "Digite o site para bloquear (ou 'sair' para finalizar): ").strip()
            if site.lower() == "sair":
                break
            if site:
                # Adiciona o site no formato correto
                novos_sites.append(f'local-zone: "{site}" static\n')
                novos_sites.append(f'local-data: "{site} A 127.0.0.1"\n')

    elif opcao == "2":
        # Verifica se o arquivo lista.txt existe
        if not os.path.exists(lista_txt):
            print(f"Arquivo {lista_txt} não encontrado.")
            return

        # Lê os sites do arquivo lista.txt
        with open(lista_txt, "r") as f:
            sites = f.readlines()

        # Remove espaços em branco e linhas vazias e adiciona no formato correto
        for site in sites:
            site = site.strip()
            if site:
                novos_sites.append(f'local-zone: "{site}" static\n')
                novos_sites.append(f'local-data: "{site} A 127.0.0.1"\n')

    else:
        print("Opção inválida. Tente novamente.")
        return

    # Remove duplicatas mantendo a ordem
    sites_unicos = [
        site for site in novos_sites if site not in sites_existentes]
    if sites_unicos:
        with open(sitesblock_conf, "a") as f:
            f.writelines(sites_unicos)
        print("Sites adicionados ao arquivo sitesblock.conf com sucesso!")
        return "Sites adicionados ao arquivo sitesblock.conf com sucesso!"
    else:
        print("Nenhum site novo para adicionar.")
        return "Nenhum site foi adicionado."


# Função principal
if __name__ == "__main__":
    criar_banco()  # Garante que o banco de dados e a tabela existam

    while True:
        print("\n=== Menu ===")
        print("1. Consultar clientes")
        print("2. Adicionar novo cliente")
        print("3. Apagar cliente")
        print("4. Conectar a um cliente")
        print("5. Sair")
        opcao = input("Escolha uma opção: ").strip()

        if opcao == "1":
            consultar_dados()
        elif opcao == "2":
            inserir_dados_cliente()
        elif opcao == "3":
            apagar_cliente()
        elif opcao == "4":
            try:
                client_id = int(
                    input("Digite o ID do cliente para conectar: "))
                device = get_client_data(client_id)

                # Conexão SSH
                connection = ConnectHandler(
                    device_type=device["device_type"],
                    host=device["host"],
                    username=device["username"],
                    password=device["password"],
                    port=device["port"],
                    global_delay_factor=device["global_delay_factor"]
                )

                # Obter acesso root
                root = connection.send_command_timing("su")
                if "Password" in root:
                    root = connection.send_command_timing(device["senha_root"])
                else:
                    root = connection.send_command_timing(device["senha_root"])
                # Envio do arquivo sitesblock.conf
                connection.send_command("export LANG=C")

                # Esse trecho do código vai definir o arquivo local e destino baseado no cliente
                if client_id == 2:
                    local_file = "sites_bloqueados\stylos\sitesblock.conf"
                    remote_file = "/tmp/sitesblock.conf"
                    resultado = adicionar_sites_bloqueados(local_file)
                    if resultado == "Sites adicionados ao arquivo sitesblock.conf com sucesso!":
                        connection.send_command("export LANG=C")
                        transfer_result = file_transfer(
                            connection,
                            source_file=local_file,
                            dest_file=remote_file,
                            file_system="/",
                            direction="put",
                            disable_md5=False,  # Mantenha a verificação de MD5 para garantir integridade
                            overwrite_file=True,  # Permitir sobrescrever o arquivo remoto
                        )
                        print("Criando backup [...]")
                        connection.send_command_timing(
                            "cp /etc/unbound/unbound.conf/sitesblock.conf /etc/unbound/unbound.conf.d/sitesblock.conf.old")
                        print("Movendo arquivo recebido[...]")
                        connection.send_command_timing(
                            "cp /tmp/sitesblock.conf /etc/unbound/unbound.conf.d/")
                        print("Reiniciando o serviço Unbound [...]")
                        connection.send_command_timing(
                            "systemctl restart unbound")
                    else:
                        print("Nenhuma ação feita.")

                elif client_id == 3:
                    local_file = "sites_bloqueados\speednetwork\sitesblock.conf"
                    remote_file = "/tmp/sitesblock.conf"
                    adicionar_sites_bloqueados(local_file)
                    if adicionar_sites_bloqueados(local_file) == "Sites adicionados ao arquivo sitesblock.conf com sucesso!":
                        connection.send_command("export LANG=C")
                        transfer_result = file_transfer(
                            connection,
                            source_file=local_file,
                            dest_file=remote_file,
                            file_system="/",
                            direction="put",
                            disable_md5=False,  # Mantenha a verificação de MD5 para garantir integridade
                            overwrite_file=True,  # Permitir sobrescrever o arquivo remoto
                        )
                        print("Criando backup [...]")
                        connection.send_command_timing(
                            "cp /etc/unbound/unbound.conf/sitesblock.conf /etc/unbound/unbound.conf.d/sitesblock.conf.old")
                        print("Movendo arquivo recebido[...]")
                        connection.send_command_timing(
                            "cp /tmp/sitesblock.conf /etc/unbound/unbound.conf.d/")
                        print("Reiniciando o serviço Unbound [...]")
                        connection.send_command_timing(
                            "systemctl restart unbound")

                elif client_id == 1:
                    local_file = "sites_bloqueados\Ambiente_de_teste\sitesblock.conf"
                    remote_file = "/tmp/sitesblock.conf"
                    # adicionar_sites_bloqueados(local_file)
                    if adicionar_sites_bloqueados(local_file) == "Sites adicionados ao arquivo sitesblock.conf com sucesso!":
                        connection.send_command("export LANG=C")
                        transfer_result = file_transfer(
                            connection,
                            source_file=local_file,
                            dest_file=remote_file,
                            file_system="/",
                            direction="put",
                            disable_md5=False,  # Mantenha a verificação de MD5 para garantir integridade
                            overwrite_file=True,  # Permitir sobrescrever o arquivo remoto
                        )
                        print("Criando backup [...]")
                        connection.send_command_timing(
                            "cp /etc/unbound/unbound.conf/sitesblock.conf /etc/unbound/unbound.conf.d/sitesblock.conf.old")
                        print("Movendo arquivo recebido[...]")
                        connection.send_command_timing(
                            "cp /tmp/sitesblock.conf /etc/unbound/unbound.conf.d/")
                        print("Reiniciando o serviço Unbound [...]")
                        connection.send_command_timing(
                            "systemctl restart unbound")

                    else:
                        print("Nenhuma ação feita.")

                else:
                    local_file = "lista_bloqueada.txt"
                    remote_file = "/tmp/lista_bloqueada.txt"

                # Executar comandos

            except ValueError as e:
                print(e)
            except Exception as e:
                print(f"Erro ao conectar ou executar o comando: {e}")
        elif opcao == "5":
            print("Saindo...")
            break
        else:
            print("Opção inválida. Tente novamente.")
