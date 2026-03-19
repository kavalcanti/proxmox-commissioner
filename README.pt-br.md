# Provisionador do Lab

[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/kavalcanti/lab-provisioning/blob/main/README.md)

## O que é esse repo?

Eu faço homelab há alguns anos e uso proxmox para subir VMs para os meus
projetos e stacks em casa. Tou cansado de fazer click-ops para subir VMs, então
fiz esse repo para automatizar esse processso.

### O que ele faz?

Provisiona máquinas virtuais em um cluster Proxmox e aplica configurações de
segurança e serviços com Ansible. Cada **serviço** (ex: media stack, banco de
dados, aplicação web) tem seu próprio estado Terraform, diretório de
configuração e ciclo de vida -- permitindo criar, proteger e configurar VMs de
forma independente por serviço.

### Estrutura do projeto

```
config/
  defaults/
    terraform/
      infrastructure.env          # Defaults compartilhados Terraform + Proxmox (gitignored)
      infrastructure.env.example # Exemplo para infrastructure.env
    local.env.example            # Template para o local.env
    local.env                    # Config Ansible/vault (gitignored)
    ansible/
      base.yml                 # Vars Ansible não sensíveis
      vault.yml.example        # Exemplo de arquivo vault (cripte isso)
      vault.yml                # Vault com segredos criptografados (usado pelos playbooks)
    services/
      service-template/
        service-template.infrastructure.env.example  # Template para overrides por serviço
  services/
    <serviço>/
      <serviço>.infrastructure.env  # Specs da VM e overrides por serviço
      terraform/                   # Root Terraform do serviço (state + outputs)
      filesystem/                  # Payload de arquivos do serviço
      ansible/
        <serviço>.inventory.yml  # Inventário auto-gerado para essa VM

terraform/
  modules/
    proxmox-vm/                 # Módulo compartilhado de VM (resources, variables, outputs)
    proxmox-lxc/

ansible/
  playbooks/                  # Segurança, Docker, Nginx, etc.
  roles/                      # Roles Ansible reutilizáveis

scripts/
  service-commission.sh  # Terraform apply + info da VM (e optional qm migrate)
  service-decommission.sh    # Terraform destroy
  inventories-regenerate-all.sh  # Gera inventário para todos os serviços
  inventory-generate.sh      # Gera inventário para um serviço
  secure-vm.sh               # Roda playbooks de segurança em uma VM de serviço
  install-docker.sh          # Instala Docker em uma VM de serviço
  install-nginx.sh           # Instala Nginx em uma VM de serviço
  mount-nfs.sh              # Configura mounts NFS em uma VM
  service-push.sh           # Push de arquivos + (opcional) docker compose
  lib/common.sh             # Helpers compartilhados
```

### Como ele faz?

Os scripts de conveniência estão na pasta `scripts/` e devem ser o caminho
principal para fazer tudo funcionar. Todos os scripts recebem o **nome do
serviço** como primeiro argumento.

1. Criar uma VM Debian para um serviço.
`scripts/service-commission.sh <serviço>`

2. Gerar / atualizar o inventário Ansible a partir dos outputs do Terraform.
`scripts/inventory-generate.sh <serviço>`
Para todos os serviços, use `scripts/inventories-regenerate-all.sh`.

3. Rodar configurações básicas de segurança. Só é possível executar uma vez por VM.
`scripts/secure-vm.sh <serviço>`

4. Instalar Docker.
`scripts/install-docker.sh <serviço>`

Isso configura regras de segurança Docker/UFW, mas não abre automaticamente as portas
do host publicadas pelo seu `docker-compose.yml`. Adicione regras explícitas com
`ufw allow` para as portas que você quer manter acessíveis.

5. Instalar Nginx e configurar UFW para tráfego web.
`scripts/install-nginx.sh <serviço>`

6. (Opcional) Montar compartilhamentos NFS.
`scripts/mount-nfs.sh <serviço>`

7. Fazer deploy dos arquivos do serviço e (opcional) subir docker compose.
`scripts/service-push.sh <serviço> [docker-deploy=true]`

## Antes de começar

### Criar um template com cloud-init

Estou usando uma imagem cloud-init que precisa ser criada previamente no
Proxmox. Esta imagem será clonada pelo Terraform quando uma nova VM for
provisionada. Aqui estão as instruções para criar este template a partir de uma
imagem Debian 12. Os playbooks Ansible foram feitos pensando em Debian, então
devem funcionar em qualquer distro baseada em Debian.

Deve rodar no servidor Proxmox.

``` bash
# Baixa a imagem cloud do Debian 12
cd /tmp
wget https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2

# Importa o qcow2 como uma VM template com id 9000
qm create 9000 --name debian-12-cloud --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0
qm importdisk 9000 debian-12-generic-amd64.qcow2 local-lvm
qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0
qm set 9000 --ide2 local-lvm:cloudinit
qm set 9000 --boot c --bootdisk scsi0
qm set 9000 --agent enabled=1
qm set 9000 --serial0 socket
qm set 9000 --vga qxl 
# Converte para template
qm template 9000

# Limpa o download
rm debian-12-generic-amd64.qcow2
```

### Credenciais do Proxmox

Será necessário criar uma chave de API para o host do Proxmox. Recomendo criar
um novo usuário para esta automação em vez de utilizar o usuário root. Para
habilitar agentes QEMU é necessário acesso via SSH ao host proxmox. Para um
homelab é possível (e mais simples) utilizar o usuário root.

### Problemas conhecidos

Pode ser preciso configurar os storages do Proxmox (local-lvm e local) para
aceitarem snippets.

Verifique se há um storage para snippets no host Proxmox

```bash
pvesm status --content snippets 
```

Caso não esteja configurado, adicione snippets ao storage local

```bash
pvesm set local --content vztmpl,iso,backup,snippets
```

## Configuração

Todas as configurações são gerenciadas por variáveis de ambiente em `config/`:

- **`config/defaults/terraform/infrastructure.env`** - Defaults compartilhados Terraform + Proxmox (gitignored; criar a partir de `config/defaults/terraform/infrastructure.env.example`)
- **`config/defaults/local.env`** - Configuração Ansible (gitignored; criar a partir de `config/defaults/local.env.example`)
- **`config/services/<serviço>/<serviço>.infrastructure.env`** - Specs da VM e overrides por serviço (gitignored; criado a partir de `config/defaults/services/service-template/`)

A configuração é em camadas: a config Ansible (`local.env`) é carregada primeiro,
depois os defaults Terraform/Proxmox (`terraform/infrastructure.env`), e por último
os overrides por serviço. Arquivos mais novos sobrescrevem os anteriores.

## Setup inicial

### Configuração do Terraform

```bash
# 1. Copie o template da config Ansible (local.env)
cp config/defaults/local.env.example config/defaults/local.env

# 2. Copie os defaults compartilhados Terraform/Proxmox
cp config/defaults/terraform/infrastructure.env.example config/defaults/terraform/infrastructure.env

# 3. Edite os defaults Terraform/Proxmox (tokens, senhas, clone/storage/network etc.)
nano config/defaults/terraform/infrastructure.env
```

### Configuração do Ansible e vault

#### Estrutura das variáveis
- `config/defaults/ansible/base.yml`: Configurações comuns não sensíveis
- `config/defaults/ansible/vault.yml`: Variáveis sensíveis criptografadas (usadas via Ansible vault)
- `config/services/<serviço>/ansible/<serviço>.inventory.yml`: Inventário por serviço auto-gerado a partir dos outputs do Terraform

Configure o Ansible vault

```bash
# 1. (Se necessário) crie vault.yml a partir do exemplo e criptografe
cp config/defaults/ansible/vault.yml.example config/defaults/ansible/vault.yml
ansible-vault encrypt config/defaults/ansible/vault.yml

# 2. Edite o vault (funciona para arquivos já criptografados também)
ansible-vault edit config/defaults/ansible/vault.yml
```

### Adicionando um novo serviço

```bash
# 1. Criar a pasta do serviço (a partir do template)
./scripts/new-service-from-template.sh meuservico

# 2. Editar o env de infra do serviço (VM specs + overrides)
nano config/services/meuservico/meuservico.infrastructure.env

# 3. Provisionar a VM
./scripts/service-commission.sh meuservico

# 4. Gerar/atualizar o inventário Ansible
./scripts/inventory-generate.sh meuservico

# 5. Proteger a VM
./scripts/secure-vm.sh meuservico
```

### Cluster: direcionando para diferentes nós Proxmox

A VM é clonada no nó de origem do Proxmox (`TF_VAR_proxmox_node` /
`TF_VAR_proxmox_node_ip` de `config/defaults/terraform/infrastructure.env`).

Para mover a VM para outro nó após o provisionamento, defina
`TF_VAR_proxmox_destination_node` e `TF_VAR_proxmox_destination_node_ip`
no `*.infrastructure.env` do serviço.

## Provisionando VM

```bash
# Rode o script de provisionamento para um serviço
./scripts/service-commission.sh arr

# Depois de criar a VM, gere o inventário Ansible desse serviço
./scripts/inventory-generate.sh arr

# Proteja a VM
./scripts/secure-vm.sh arr

# Instale Docker
./scripts/install-docker.sh arr

# (Opcional) Instale Nginx
./scripts/install-nginx.sh arr

# (Opcional) Envie arquivos do serviço + deploy do docker compose
./scripts/service-push.sh arr true
```

Esse processo irá:
1. Carregar config Ansible (`config/defaults/local.env`), defaults Terraform/Proxmox
   (`config/defaults/terraform/infrastructure.env`) e overrides do serviço
   (`config/services/<serviço>/<serviço>.infrastructure.env`)
2. Rodar Terraform em `config/services/<serviço>/terraform/` para criar a VM
3. Exibir o IP da VM
4. Gerar/atualizar o inventário Ansible do serviço a partir dos outputs do Terraform
